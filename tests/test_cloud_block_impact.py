from datetime import datetime, timedelta, timezone

import pytest

from amis.domain import (
    CloudBlockPayload,
    EventType,
    ObservationRequest,
    ObservationWindow,
    ReasonCode,
    Satellite,
    Scenario,
)
from amis.errors import InvalidEventError, SimulationStateError
from amis.session import MissionSession


START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = START + timedelta(minutes=2)


def _scenario() -> Scenario:
    requests = tuple(
        ObservationRequest(
            id=request_id,
            target_lat=0.0,
            target_lon=0.0,
            priority=priority,
            duration_s=10.0,
            deadline=END,
            energy_cost_wh=10.0,
            storage_cost_mb=10.0,
        )
        for request_id, priority in (("OBS-A", 5), ("OBS-B", 4), ("OBS-C", 3))
    )
    return Scenario(
        id="SCN-001",
        name="Cloud block impact test",
        start_time=START,
        end_time=END,
        satellite=Satellite(
            id="SAT-001",
            battery_capacity_wh=100.0,
            battery_charge_wh=100.0,
            storage_capacity_mb=100.0,
            storage_usage_mb=0.0,
        ),
        requests=requests,
    )


class _ThreeWindowProvider:
    def generate(self, scenario, requests):
        starts = {
            "OBS-A": START,
            "OBS-B": START + timedelta(seconds=20),
            "OBS-C": START + timedelta(seconds=40),
        }
        return [
            ObservationWindow(
                id=f"WIN-{request.id}-1",
                request_id=request.id,
                satellite_id=scenario.satellite.id,
                start=starts[request.id],
                end=starts[request.id] + timedelta(seconds=10),
            )
            for request in requests
        ]


def _planned_session() -> tuple[MissionSession, Scenario]:
    session = MissionSession(window_provider=_ThreeWindowProvider())
    scenario = session.load_scenario(_scenario())
    session.generate_windows()
    session.plan()
    return session, scenario


def test_cloud_block_records_event_and_stored_two_way_impact_without_replanning():
    session, scenario = _planned_session()
    scenario_before = scenario.to_dict()
    session.step(5)
    plan_before = session.get_plan()

    event = session.inject_event(
        EventType.CLOUD_BLOCK,
        CloudBlockPayload(request_id="OBS-B", window_id="WIN-OBS-B-1"),
    )

    assert event.id == "EVT-001"
    assert event.scenario_id == scenario.id
    assert event.event_type is EventType.CLOUD_BLOCK
    assert event.event_time == START + timedelta(seconds=5)
    assert event.payload == CloudBlockPayload("OBS-B", "WIN-OBS-B-1")
    assert session.get_events() == (event,)
    assert session.get_state().active_event_ids == (event.id,)

    blocked_window = next(
        window for window in session.get_windows() if window.id == "WIN-OBS-B-1"
    )
    assert blocked_window.valid is False
    assert blocked_window.invalid_reason == ReasonCode.WINDOW_INVALIDATED.value

    impact = session.get_last_impact()
    actions_by_request = {
        action.request_id: action.id for action in plan_before.actions
    }
    assert impact.event_id == event.id
    assert impact.evaluated_plan_id == plan_before.id
    assert impact.frozen_action_ids == (actions_by_request["OBS-A"],)
    assert impact.valid_unfrozen_action_ids == (actions_by_request["OBS-C"],)
    assert impact.invalid_unfrozen_action_ids == (actions_by_request["OBS-B"],)
    assert impact.reason_codes == {
        actions_by_request["OBS-B"]: (ReasonCode.WINDOW_INVALIDATED,)
    }

    unfrozen_ids = {
        action.id for action in plan_before.actions if action.start > event.event_time
    }
    classified_unfrozen_ids = set(impact.valid_unfrozen_action_ids) | set(
        impact.invalid_unfrozen_action_ids
    )
    assert classified_unfrozen_ids == unfrozen_ids
    assert not (
        set(impact.valid_unfrozen_action_ids)
        & set(impact.invalid_unfrozen_action_ids)
    )

    assert session.get_plan() is plan_before
    assert scenario.to_dict() == scenario_before

    stored_impact = session.get_last_impact()
    session.step(5)
    assert session.get_last_impact() is stored_impact
    assert session.get_last_impact() == impact


def test_action_starting_at_event_time_is_frozen_even_when_its_window_is_blocked():
    session, _ = _planned_session()
    action = session.get_plan().actions[0]
    assert action.start == session.get_state().simulated_time

    session.inject_cloud_block(action.request_id, action.window_id)

    impact = session.get_last_impact()
    assert impact.frozen_action_ids == (action.id,)
    assert action.id not in impact.valid_unfrozen_action_ids
    assert action.id not in impact.invalid_unfrozen_action_ids
    assert action.id not in impact.reason_codes


def test_cloud_block_requires_a_plan_and_matching_request_and_window():
    session = MissionSession(window_provider=_ThreeWindowProvider())
    session.load_scenario(_scenario())
    session.generate_windows()

    with pytest.raises(SimulationStateError, match="plan"):
        session.inject_cloud_block("OBS-B", "WIN-OBS-B-1")

    session.plan()

    with pytest.raises(InvalidEventError, match="does not belong") as raised:
        session.inject_cloud_block("OBS-A", "WIN-OBS-B-1")

    assert raised.value.code == "INVALID_EVENT"
    assert session.get_events() == ()
    with pytest.raises(SimulationStateError, match="impact"):
        session.get_last_impact()


def test_event_and_impact_records_are_serialisable():
    session, _ = _planned_session()
    session.step(5)
    event = session.inject_event(
        "CLOUD_BLOCK",
        {"request_id": "OBS-B", "window_id": "WIN-OBS-B-1"},
    )

    assert event.to_dict()["payload"] == {
        "request_id": "OBS-B",
        "window_id": "WIN-OBS-B-1",
    }
    assert session.get_last_impact().to_dict()["reason_codes"] == {
        "ACT-002": ["WINDOW_INVALIDATED"]
    }
