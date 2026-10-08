"""Evidence-bearing emergency arrivals (A1+B ticket 02, ADR-0015).

A cue enters only as an ordinary ``EMERGENCY_TASK`` carrying evidence.
These checks cover the all-or-nothing evidence group, the unchanged
evidence-free shape, recorded orbital windows, persistence, reset, and
replay from the pristine Scenario plus the accepted event log.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine

from amis.api import create_app
from amis.db.repositories import build_repositories
from amis.db.schema import metadata
from amis.demo import CanonicalWindowProvider, build_emergency_replan_fixture
from amis.domain import (
    EmergencyRequestPayload,
    EventType,
    MissionEvent,
    ObservationWindow,
    WindowPolicy,
)
from amis.errors import InvalidEventError
from amis.repositories import MissionSessionStore
from amis.session import MissionSession

EVIDENCE = {
    "source": "usgs",
    "source_event_id": "us7000test",
    "alert_level": "orange",
    "mag": 6.4,
    "sig": 650,
}


class _OrbitalStubProvider(CanonicalWindowProvider):
    """Canonical windows for the Scenario; a fixed answer for arrivals."""

    def __init__(self, arrival_windows: tuple[ObservationWindow, ...] = ()) -> None:
        self.arrival_windows = arrival_windows
        self.arrival_calls = 0

    def generate(self, scenario, requests):
        requests = tuple(requests)
        if requests == scenario.requests:
            return super().generate(scenario, requests)
        self.arrival_calls += 1
        return list(self.arrival_windows)


def _orbital_scenario():
    scenario, payload = build_emergency_replan_fixture()
    return replace(scenario, window_policy=WindowPolicy("orbital")), payload


def _planned(scenario, provider):
    session = MissionSession(window_provider=provider)
    session.load_scenario(scenario)
    session.generate_windows()
    session.plan()
    session.step(300)
    return session


def _snapshot(session: MissionSession):
    return (
        session.get_events(),
        session.get_impacts(),
        session.get_windows(),
        session.get_request_pool(),
        session.get_state(),
        session.get_plan(),
    )


def _cue_payload(payload: EmergencyRequestPayload, **evidence) -> dict:
    return {**payload.to_dict(), **(evidence or EVIDENCE)}


def test_evidence_free_payload_keeps_its_previous_serialized_shape():
    _, payload = build_emergency_replan_fixture()

    assert set(payload.to_dict()) == {"request", "windows"}
    assert not payload.has_evidence
    assert payload.evidence_error() is None
    legacy = {"request": payload.request.to_dict(), "windows": [w.to_dict() for w in payload.windows]}
    assert EmergencyRequestPayload.from_dict(legacy) == payload


def test_cue_evidence_survives_injection_and_round_trip_on_the_simulated_clock():
    scenario, payload = build_emergency_replan_fixture()
    session = _planned(scenario, CanonicalWindowProvider())
    scenario_before = scenario.to_dict()
    clock = session.get_state().simulated_time

    event = session.inject_event(EventType.EMERGENCY_TASK, _cue_payload(payload))

    assert event.event_time == clock
    assert event.id == "EVT-001"
    assert event.payload.has_evidence
    assert (event.payload.source, event.payload.source_event_id, event.payload.alert_level) == (
        "usgs", "us7000test", "orange",
    )
    assert (event.payload.mag, event.payload.sig) == (6.4, 650)
    assert MissionEvent.from_dict(event.to_dict()) == event
    assert session.get_events() == (event,)
    assert session.get_scenario().to_dict() == scenario_before
    # Injection stores an ordinary impact and leaves replan explicit.
    assert session.get_last_impact().event_id == event.id
    assert session.get_plan().version == 1


def test_optional_magnitude_and_significance_are_omitted_when_absent():
    scenario, payload = build_emergency_replan_fixture()
    session = _planned(scenario, CanonicalWindowProvider())

    event = session.inject_event(
        EventType.EMERGENCY_TASK,
        _cue_payload(payload, source="usgs", source_event_id="us1", alert_level="unknown"),
    )

    serialized = event.to_dict()["payload"]
    assert serialized["alert_level"] == "unknown"
    assert "mag" not in serialized and "sig" not in serialized


@pytest.mark.parametrize(
    ("evidence", "message"),
    [
        ({"source": "usgs"}, "missing source_event_id, alert_level"),
        ({"source_event_id": "us1", "alert_level": "red"}, "missing source"),
        ({"mag": 6.1}, "requires source"),
        ({**EVIDENCE, "alert_level": "RED"}, "alert_level must be one of"),
        ({**EVIDENCE, "alert_level": "purple"}, "alert_level must be one of"),
        ({**EVIDENCE, "source": " "}, "source must be a nonempty string"),
        ({**EVIDENCE, "source_event_id": ""}, "source_event_id must be a nonempty string"),
        ({**EVIDENCE, "mag": float("nan")}, "mag must be a finite number"),
        ({**EVIDENCE, "sig": True}, "sig must be a finite number"),
        ({**EVIDENCE, "sig": "650"}, "sig must be a finite number"),
    ],
)
def test_invalid_evidence_fails_before_any_state_change(evidence, message):
    scenario, payload = build_emergency_replan_fixture()
    session = _planned(scenario, CanonicalWindowProvider())
    before = _snapshot(session)

    with pytest.raises(InvalidEventError, match=message):
        session.inject_event(EventType.EMERGENCY_TASK, {**payload.to_dict(), **evidence})

    assert _snapshot(session) == before


def test_a_generated_input_cannot_rewrite_the_recorded_time():
    scenario, payload = build_emergency_replan_fixture()
    session = _planned(scenario, CanonicalWindowProvider())
    before = _snapshot(session)

    with pytest.raises(InvalidEventError, match="simulated clock") as raised:
        session.inject_event(
            EventType.EMERGENCY_TASK,
            {**_cue_payload(payload), "injection_time": scenario.start_time.isoformat()},
        )

    assert raised.value.details == {"fields": ["injection_time"]}
    assert _snapshot(session) == before


def test_duplicate_cue_injection_fails_without_changing_the_mission():
    scenario, payload = build_emergency_replan_fixture()
    session = _planned(scenario, CanonicalWindowProvider())
    session.inject_event(EventType.EMERGENCY_TASK, _cue_payload(payload))
    before = _snapshot(session)

    with pytest.raises(InvalidEventError, match="already exists"):
        session.inject_event(EventType.EMERGENCY_TASK, _cue_payload(payload))

    assert _snapshot(session) == before


def test_orbital_cue_with_no_window_records_the_empty_set_and_replay_reuses_it():
    scenario, payload = _orbital_scenario()
    provider = _OrbitalStubProvider()
    session = _planned(scenario, provider)
    cue = {key: value for key, value in _cue_payload(payload).items() if key != "windows"}

    event = session.inject_event(EventType.EMERGENCY_TASK, cue)

    assert provider.arrival_calls == 1
    assert event.payload.windows == ()
    assert event.to_dict()["payload"]["windows"] == []
    # A cue with no feasible action is still a legitimate arrival.
    assert session.get_request_pool()[-1] == payload.request
    revised = session.replan()
    assert payload.request.id in {entry.request_id for entry in revised.unscheduled}

    replay_provider = _OrbitalStubProvider(arrival_windows=payload.windows)
    replay = _planned(scenario, replay_provider)
    for recorded in session.get_events():
        restored = MissionEvent.from_dict(recorded.to_dict())
        replay.inject_event(restored.event_type, restored.to_dict()["payload"])
    replay_plan = replay.replan()

    assert replay_provider.arrival_calls == 0
    assert replay.get_events() == session.get_events()
    assert replay.get_windows() == session.get_windows()
    assert replay.get_request_pool() == session.get_request_pool()
    assert [(e.request_id, e.reason_code) for e in replay_plan.unscheduled] == [
        (e.request_id, e.reason_code) for e in revised.unscheduled
    ]


def test_orbital_cue_records_the_provider_windows_it_received():
    scenario, payload = _orbital_scenario()
    provider = _OrbitalStubProvider(arrival_windows=payload.windows)
    session = _planned(scenario, provider)
    cue = {key: value for key, value in _cue_payload(payload).items() if key != "windows"}

    event = session.inject_event(EventType.EMERGENCY_TASK, cue)

    assert event.payload.windows == payload.windows
    assert session.get_windows()[-1:] == payload.windows


def test_evidence_survives_restart_and_reset_removes_it(tmp_path):
    db_path = tmp_path / "amis.db"
    engine = create_engine(f"sqlite:///{db_path}")
    metadata.create_all(engine)
    store = MissionSessionStore(build_repositories(engine), window_provider=CanonicalWindowProvider())
    scenario, payload = build_emergency_replan_fixture()
    session = store.create(scenario)
    session.generate_windows()
    session.plan()
    session.step(300)
    event = session.inject_event(EventType.EMERGENCY_TASK, _cue_payload(payload))
    store.save(session)
    engine.dispose()

    restarted = create_engine(f"sqlite:///{db_path}")
    restarted_store = MissionSessionStore(
        build_repositories(restarted), window_provider=CanonicalWindowProvider()
    )
    restored = restarted_store.load(scenario.id)
    assert restored.get_events() == (event,)
    assert restored.get_events()[0].payload.source_event_id == "us7000test"
    assert payload.request.id in {request.id for request in restored.get_request_pool()}

    restored.reset()
    restarted_store.save(restored)
    assert restarted_store.load(scenario.id).get_events() == ()
    restarted.dispose()


def _http(provider=None):
    app = create_app(window_provider=provider or CanonicalWindowProvider())
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _planned_over_http(client, scenario):
    await client.post("/scenarios", json=scenario.to_dict())
    await client.post(f"/scenarios/{scenario.id}/windows/generate")
    await client.post(f"/scenarios/{scenario.id}/plan")
    await client.post(f"/scenarios/{scenario.id}/simulation/step", json={"seconds": 300})


def test_http_accepts_and_lists_cue_evidence_and_keeps_manual_shape():
    async def run() -> None:
        scenario, payload = build_emergency_replan_fixture()
        async with _http() as client:
            await _planned_over_http(client, scenario)
            body = {"event_type": "EMERGENCY_TASK", "payload": _cue_payload(payload)}

            injected = await client.post(f"/scenarios/{scenario.id}/events", json=body)

            assert injected.status_code == 201, injected.text
            recorded = injected.json()["payload"]
            assert {key: recorded[key] for key in EVIDENCE} == EVIDENCE
            listed = (await client.get(f"/scenarios/{scenario.id}/events")).json()
            assert listed == [injected.json()]

            manual = replace(payload.request, id="OBS-MANUAL")
            manual_window = replace(payload.windows[0], id="WIN-OBS-MANUAL-1", request_id="OBS-MANUAL")
            manual_body = {
                "event_type": "EMERGENCY_TASK",
                "payload": EmergencyRequestPayload(manual, (manual_window,)).to_dict(),
            }
            accepted = await client.post(f"/scenarios/{scenario.id}/events", json=manual_body)
            assert accepted.status_code == 201, accepted.text
            assert set(accepted.json()["payload"]) == {"request", "windows"}

    asyncio.run(run())


def test_http_rejects_partial_evidence_and_generated_input_envelopes():
    async def run() -> None:
        scenario, payload = build_emergency_replan_fixture()
        async with _http() as client:
            await _planned_over_http(client, scenario)
            partial = {
                "event_type": "EMERGENCY_TASK",
                "payload": {**payload.to_dict(), "source": "usgs"},
            }
            generated = {
                "injection_time": scenario.start_time.isoformat(),
                "event_type": "EMERGENCY_TASK",
                "payload": _cue_payload(payload),
            }
            bad_alert = {
                "event_type": "EMERGENCY_TASK",
                "payload": _cue_payload(payload, **{**EVIDENCE, "alert_level": "severe"}),
            }

            for body in (partial, generated, bad_alert):
                response = await client.post(f"/scenarios/{scenario.id}/events", json=body)
                assert response.status_code == 422, response.text
                assert response.json()["error"]["code"] == "INVALID_EVENT"

            assert (await client.get(f"/scenarios/{scenario.id}/events")).json() == []

    asyncio.run(run())


@pytest.mark.parametrize(
    "evidence",
    [
        {"alert_level": "red"},
        {**EVIDENCE, "alert_level": "severe"},
        {**EVIDENCE, "mag": float("inf")},
        {"sig": 10},
    ],
)
def test_invalid_orbital_evidence_is_rejected_before_the_provider_runs(evidence):
    scenario, payload = _orbital_scenario()
    provider = _OrbitalStubProvider(arrival_windows=payload.windows)
    session = _planned(scenario, provider)
    before = _snapshot(session)

    with pytest.raises(InvalidEventError, match="emergency evidence"):
        session.inject_event(
            EventType.EMERGENCY_TASK,
            {"request": payload.request.to_dict(), "windows": None, **evidence},
        )

    assert provider.arrival_calls == 0
    assert _snapshot(session) == before


def test_unknown_orbital_fields_are_rejected_before_the_provider_runs():
    scenario, payload = _orbital_scenario()
    provider = _OrbitalStubProvider()
    session = _planned(scenario, provider)

    with pytest.raises(InvalidEventError, match="simulated clock"):
        session.inject_event(
            EventType.EMERGENCY_TASK,
            {"request": payload.request.to_dict(), "event_time": "2026-01-01T00:00:00+00:00"},
        )

    assert provider.arrival_calls == 0


@pytest.mark.parametrize(
    "evidence",
    [
        {"source": "usgs"},
        {"alert_level": "red"},
        {"source": "usgs", "source_event_id": "us1"},
        {"source": "usgs", "source_event_id": " ", "alert_level": "red"},
        {**EVIDENCE, "alert_level": "purple"},
        {"mag": 6.0},
    ],
)
def test_has_evidence_agrees_with_the_validator_for_partial_or_invalid_groups(evidence):
    _, payload = build_emergency_replan_fixture()
    partial = replace(payload, **evidence)

    assert partial.evidence_error() is not None
    assert not partial.has_evidence


def test_has_evidence_is_true_for_a_complete_valid_group():
    _, payload = build_emergency_replan_fixture()
    complete = replace(payload, **EVIDENCE)

    assert complete.evidence_error() is None
    assert complete.has_evidence


def test_api_schema_and_domain_report_the_same_evidence_message():
    from pydantic import ValidationError

    from amis.api_schemas import EmergencyTaskPayloadSchema

    _, payload = build_emergency_replan_fixture()
    partial = {**payload.to_dict(), "source": "usgs"}
    domain_message = EmergencyRequestPayload.from_dict(partial).evidence_error()

    with pytest.raises(ValidationError) as raised:
        EmergencyTaskPayloadSchema.model_validate(partial)

    assert domain_message is not None
    assert domain_message in str(raised.value)
