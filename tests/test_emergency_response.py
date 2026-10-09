"""Planned and achieved emergency response (ticket 04, ADR-0015).

Every eligible emergency arrival stays visible, planned and achieved
means never mix, missing service is never zero latency, and an
acquisition that began survives replans and reconstruction.
"""

import asyncio
from dataclasses import replace
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine

from amis.api import create_app
from amis.db.repositories import build_repositories
from amis.db.schema import metadata
from amis.demo import (
    REPLAN_START,
    CanonicalWindowProvider,
    build_emergency_replan_fixture,
)
from amis.domain import (
    ActionKind,
    ActionStatus,
    EmergencyRequestPayload,
    EventType,
    MetricsResult,
    MissionEvent,
    ScheduledAction,
)
from amis.errors import SimulationStateError
from amis.metrics import compute_emergency_response
from amis.repositories import MissionSessionStore, Repositories
from amis.session import MissionSession


ARRIVAL = REPLAN_START + timedelta(minutes=5)


def _planned_session():
    scenario, payload = build_emergency_replan_fixture()
    session = MissionSession(window_provider=CanonicalWindowProvider())
    session.load_scenario(scenario)
    session.generate_windows()
    version_one = session.plan()
    session.step(300)
    return session, payload, version_one


def _unservable(payload: EmergencyRequestPayload) -> EmergencyRequestPayload:
    """A second arrival whose only window opens after its deadline."""
    request = replace(
        payload.request,
        id="OBS-EMERGENCY-LATE",
        deadline=REPLAN_START + timedelta(minutes=30),
    )
    window = replace(payload.windows[0], id="WIN-OBS-EMERGENCY-LATE-1", request_id=request.id)
    return EmergencyRequestPayload(request=request, windows=(window,))


def test_no_emergency_arrival_gives_an_empty_collection_zero_counts_and_null_means():
    session, _, version_one = _planned_session()

    metrics = session.get_metrics(version_one.id)

    assert metrics.emergency_response == ()
    assert metrics.emergency_request_count == 0
    assert metrics.planned_emergency_request_count == 0
    assert metrics.achieved_emergency_request_count == 0
    assert metrics.time_to_first_acquisition_s is None
    assert metrics.achieved_time_to_first_acquisition_s is None


def test_planned_response_follows_the_selected_plan_and_excludes_later_arrivals():
    session, payload, version_one = _planned_session()
    event = session.inject_event(EventType.EMERGENCY_TASK, payload.to_dict())

    unplanned = session.get_metrics(version_one.id)
    version_two = session.replan()
    planned = session.get_metrics(version_two.id)

    # The earlier plan's RequestPool never held the arrival.
    assert unplanned.emergency_response == ()
    assert unplanned.emergency_request_count == 0

    (row,) = planned.emergency_response
    assert row.request_id == payload.request.id
    assert row.event_id == event.id
    assert row.arrival_time == event.event_time == ARRIVAL
    assert row.request_status == "scheduled"
    assert row.planned_start_time == REPLAN_START + timedelta(minutes=40)
    assert row.planned_latency_s == 35 * 60
    assert row.planned_satellite_id == "SAT-001"
    # Imaging is still in the future: nothing is achieved yet.
    assert row.achieved_start_time is None
    assert row.achieved_latency_s is None
    assert row.achieved_satellite_id is None
    assert planned.time_to_first_acquisition_s == 35 * 60
    assert planned.achieved_time_to_first_acquisition_s is None
    assert (
        planned.emergency_request_count,
        planned.planned_emergency_request_count,
        planned.achieved_emergency_request_count,
    ) == (1, 1, 0)
    assert planned.measured_at == session.get_state().simulated_time


def test_unserved_and_expired_arrivals_stay_visible_without_zero_latency():
    session, payload, _ = _planned_session()
    session.inject_event(EventType.EMERGENCY_TASK, payload.to_dict())
    late = _unservable(payload)
    session.inject_event(EventType.EMERGENCY_TASK, late.to_dict())
    version_two = session.replan()

    session.step(30 * 60)
    metrics = session.get_metrics(version_two.id)

    rows = {row.request_id: row for row in metrics.emergency_response}
    assert [row.request_id for row in metrics.emergency_response] == [
        payload.request.id,
        late.request.id,
    ]
    unserved = rows[late.request.id]
    assert unserved.request_status == "expired"
    assert unserved.planned_start_time is None
    assert unserved.planned_latency_s is None
    assert unserved.planned_satellite_id is None
    assert unserved.achieved_latency_s is None
    assert metrics.emergency_request_count == 2
    assert metrics.planned_emergency_request_count == 1
    # The mean covers only the served request; it is not diluted by zero.
    assert metrics.time_to_first_acquisition_s == 35 * 60


def test_achieved_response_appears_at_imaging_start_and_survives_completion_and_replans():
    session, payload, _ = _planned_session()
    session.inject_event(EventType.EMERGENCY_TASK, payload.to_dict())
    version_two = session.replan()

    session.step(34 * 60)  # one minute before imaging starts
    assert session.get_metrics().emergency_response[0].achieved_start_time is None

    session.step(60)  # exactly at imaging start
    started = session.get_metrics().emergency_response[0]
    assert started.achieved_start_time == REPLAN_START + timedelta(minutes=40)
    assert started.achieved_latency_s == 35 * 60
    assert started.achieved_satellite_id == "SAT-001"

    session.step(15 * 60)  # imaging completed
    session.inject_battery_drop("SAT-001", 200.0)
    version_three = session.replan()
    for plan in (version_two, version_three):
        metrics = session.get_metrics(plan.id)
        (row,) = metrics.emergency_response
        assert row.request_status == "completed"
        assert (row.achieved_start_time, row.achieved_latency_s, row.achieved_satellite_id) == (
            started.achieved_start_time,
            started.achieved_latency_s,
            started.achieved_satellite_id,
        )
        assert metrics.achieved_time_to_first_acquisition_s == 35 * 60
        assert metrics.achieved_emergency_request_count == 1


def test_reset_clears_achieved_response_with_the_mission_history():
    session, payload, _ = _planned_session()
    session.inject_event(EventType.EMERGENCY_TASK, payload.to_dict())
    session.replan()
    session.step(60 * 60)

    session.reset()
    session.generate_windows()
    session.plan()

    assert session.get_metrics().emergency_response == ()


def test_reconstructed_session_keeps_planned_and_achieved_response(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'amis.db'}")
    metadata.create_all(engine)
    store = MissionSessionStore(
        build_repositories(engine), window_provider=CanonicalWindowProvider()
    )
    scenario, payload = build_emergency_replan_fixture()

    session = store.create(scenario)
    session.generate_windows()
    session.plan()
    session.step(300)
    session.inject_event(EventType.EMERGENCY_TASK, payload.to_dict())
    session.replan()
    session.step(45 * 60)
    expected = session.get_metrics()
    store.save(session)

    restored = store.load(scenario.id)
    assert restored.get_metrics().emergency_response == expected.emergency_response

    restored.inject_battery_drop("SAT-001", 200.0)
    restored.replan()
    store.save(restored)
    after_replan = store.load(scenario.id).get_metrics()
    assert [
        (row.achieved_start_time, row.achieved_satellite_id)
        for row in after_replan.emergency_response
    ] == [(row.achieved_start_time, row.achieved_satellite_id) for row in expected.emergency_response]


def _arrival(request_id="OBS-EMERGENCY", at=ARRIVAL):
    _, payload = build_emergency_replan_fixture()
    request = replace(payload.request, id=request_id)
    return MissionEvent(
        id="EVT-001",
        scenario_id="SCN-002",
        event_type=EventType.EMERGENCY_TASK,
        event_time=at,
        payload=EmergencyRequestPayload(request=request, windows=()),
    ), request


def _action(action_id, start_minutes, *, request_id="OBS-EMERGENCY", satellite_id="SAT-001", kind=ActionKind.IMAGING):
    start = REPLAN_START + timedelta(minutes=start_minutes)
    return ScheduledAction(
        id=action_id,
        request_id=request_id if kind is ActionKind.IMAGING else None,
        window_id="WIN-1",
        start=start,
        end=start + timedelta(minutes=10),
        energy_cost_wh=40.0,
        storage_cost_mb=100.0,
        satellite_id=satellite_id,
        kind=kind,
    )


def _plan(*actions):
    session, _, version_one = _planned_session()
    return replace(version_one, actions=actions)


def test_moved_or_dropped_unfrozen_action_changes_planned_values():
    event, request = _arrival()
    measured_at = REPLAN_START + timedelta(minutes=10)

    moved = compute_emergency_response(
        (event,), (request,), _plan(_action("ACT-1", 60, satellite_id="SAT-002")), (), measured_at
    )
    dropped = compute_emergency_response((event,), (request,), _plan(), (), measured_at)

    assert moved[0].planned_start_time == REPLAN_START + timedelta(minutes=60)
    assert moved[0].planned_latency_s == 55 * 60
    assert moved[0].planned_satellite_id == "SAT-002"
    assert dropped[0].planned_start_time is None
    assert dropped[0].planned_latency_s is None
    assert dropped[0].planned_satellite_id is None


def test_downlinks_never_count_as_acquisition():
    event, request = _arrival()
    downlink = _action("ACT-DL", 20, kind=ActionKind.DOWNLINK)

    (row,) = compute_emergency_response(
        (event,), (request,), _plan(downlink), (downlink,), REPLAN_START + timedelta(hours=1)
    )

    assert row.planned_start_time is None
    assert row.achieved_start_time is None


def test_a_proposed_start_alone_is_not_an_acquisition():
    event, request = _arrival()
    proposed = _action("ACT-1", 20)

    # The clock is past the proposed start, but no executed history names it.
    (row,) = compute_emergency_response(
        (event,), (request,), _plan(proposed), (), REPLAN_START + timedelta(hours=1)
    )

    assert row.planned_start_time == proposed.start
    assert row.achieved_start_time is None


def test_negative_latency_is_rejected_rather_than_clamped():
    event, request = _arrival()
    early = _action("ACT-1", 0)

    with pytest.raises(SimulationStateError, match="before its request arrived") as raised:
        compute_emergency_response((event,), (request,), _plan(early), (), ARRIVAL)
    assert raised.value.details["action_id"] == "ACT-1"

    with pytest.raises(SimulationStateError):
        compute_emergency_response(
            (event,), (request,), _plan(), (replace(early, status=ActionStatus.STARTED),), ARRIVAL
        )


def test_metrics_result_serializes_every_emergency_response_field():
    session, payload, _ = _planned_session()
    session.inject_event(EventType.EMERGENCY_TASK, payload.to_dict())
    session.replan()
    session.step(40 * 60)

    data = session.get_metrics().to_dict()

    assert isinstance(session.get_metrics(), MetricsResult)
    assert data["emergency_response"] == [
        {
            "request_id": payload.request.id,
            "event_id": "EVT-001",
            "arrival_time": ARRIVAL.isoformat(),
            "request_status": "scheduled",
            "planned_start_time": (REPLAN_START + timedelta(minutes=40)).isoformat(),
            "planned_latency_s": 2100.0,
            "planned_satellite_id": "SAT-001",
            "achieved_start_time": (REPLAN_START + timedelta(minutes=40)).isoformat(),
            "achieved_latency_s": 2100.0,
            "achieved_satellite_id": "SAT-001",
        }
    ]
    assert data["time_to_first_acquisition_s"] == 2100.0
    assert data["achieved_time_to_first_acquisition_s"] == 2100.0
    assert (
        data["emergency_request_count"],
        data["planned_emergency_request_count"],
        data["achieved_emergency_request_count"],
    ) == (1, 1, 1)


def test_metrics_route_exposes_planned_and_achieved_response():
    scenario, payload = build_emergency_replan_fixture()
    app = create_app(Repositories.in_memory(), window_provider=CanonicalWindowProvider())

    async def run():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/scenarios", json=scenario.to_dict())
            await client.post(f"/scenarios/{scenario.id}/windows/generate")
            version_one = (await client.post(f"/scenarios/{scenario.id}/plan")).json()
            await client.post(f"/scenarios/{scenario.id}/simulation/step", json={"seconds": 300})
            await client.post(
                f"/scenarios/{scenario.id}/events",
                json={"event_type": "EMERGENCY_TASK", "payload": payload.to_dict()},
            )
            version_two = (
                await client.post(
                    f"/scenarios/{scenario.id}/replan",
                    json={"expected_parent_plan_id": version_one["id"]},
                )
            ).json()
            await client.post(f"/scenarios/{scenario.id}/simulation/step", json={"seconds": 2400})
            before = (await client.get(f"/plans/{version_one['id']}/metrics")).json()
            after = (await client.get(f"/plans/{version_two['id']}/metrics")).json()
            return before, after

    before, after = asyncio.run(run())

    assert before["emergency_response"] == []
    assert before["emergency_request_count"] == 0
    (row,) = after["emergency_response"]
    assert row["request_id"] == payload.request.id
    assert row["planned_latency_s"] == 2100.0
    assert row["achieved_latency_s"] == 2100.0
    assert row["achieved_satellite_id"] == "SAT-001"
    assert after["achieved_emergency_request_count"] == 1


def test_without_executed_history_a_past_proposed_start_is_never_achieved():
    from amis.metrics import compute_metrics

    session, payload, _ = _planned_session()
    session.inject_event(EventType.EMERGENCY_TASK, payload.to_dict())
    version_two = session.replan()
    session.step(60 * 60)  # clock well past the proposed imaging start

    metrics = compute_metrics(
        session.get_scenario(),
        session.get_state(),
        session.get_request_pool(),
        version_two,
        events=session.get_events(),
    )

    (row,) = metrics.emergency_response
    assert row.planned_start_time == REPLAN_START + timedelta(minutes=40)
    assert row.achieved_start_time is None
    assert row.achieved_latency_s is None
    assert row.achieved_satellite_id is None
    assert metrics.achieved_emergency_request_count == 0
    assert metrics.achieved_time_to_first_acquisition_s is None


def test_missing_pool_snapshot_still_excludes_later_arrivals():
    session, payload, version_one = _planned_session()
    session.inject_event(EventType.EMERGENCY_TASK, payload.to_dict())
    version_two = session.replan()
    # Simulate a plan recorded before RequestPool snapshots existed.
    session._request_pool_ids_by_plan_id.clear()

    earlier = session.get_metrics(version_one.id)
    later = session.get_metrics(version_two.id)

    assert payload.request.id not in earlier.request_pool_ids
    assert earlier.emergency_response == ()
    assert [row.request_id for row in later.emergency_response] == [payload.request.id]


def test_metrics_schema_accepts_payloads_recorded_before_emergency_response():
    from amis.api_schemas import MetricsSchema

    old = {
        "plan_id": "SCN:PLAN-001",
        "mission_utility": 15,
        "completion_rate": 0.4,
        "violation_count": 0,
        "planning_time_ms": 0.2,
        "battery_utilisation": 0.1,
        "storage_utilisation": 0.1,
        "request_pool_size": 5,
        "request_pool_ids": ["OBS-A"],
        "measured_at": REPLAN_START.isoformat(),
        "plan_churn": None,
        "explanation_coverage": None,
    }

    metrics = MetricsSchema.model_validate(old)

    assert metrics.emergency_response == []
    assert metrics.time_to_first_acquisition_s is None
    assert metrics.achieved_time_to_first_acquisition_s is None
    assert (
        metrics.emergency_request_count,
        metrics.planned_emergency_request_count,
        metrics.achieved_emergency_request_count,
    ) == (0, 0, 0)
