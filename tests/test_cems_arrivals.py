"""Synthetic CEMS arrivals through the confirmed lifecycle and HTTP seams."""
import asyncio
from dataclasses import replace
from datetime import timedelta

import pytest

from amis.domain import EventType, MissionEvent
from amis.demo import build_emergency_replan_fixture
from amis.errors import InvalidEventError
from test_emergency_evidence import (
    _OrbitalStubProvider, _orbital_scenario, _planned, _snapshot,
    _http, _planned_over_http,
)


def cems_payload(payload, clock):
    return {
        **payload.to_dict(),
        "request": replace(payload.request, priority=5, deadline=clock + timedelta(hours=24)).to_dict(),
        "source": "cems", "source_event_id": "SYNTHETIC-CEMS-001",
        "alert_level": "unknown", "category": "Synthetic flood",
        "activation_time": clock.isoformat(),
        "source_event_time": (clock - timedelta(hours=1)).isoformat(),
        "source_url": "https://mapping.emergency.copernicus.eu/",
        "centroid_policy_version": "cems-centroid-v1",
    }


def test_cems_exact_arrival_records_windows_impact_and_explicit_replan():
    scenario, payload = _orbital_scenario()
    scenario = replace(scenario, requests=tuple(replace(r, priority=4) if r.id == "OBS-C" else r for r in scenario.requests))
    provider = _OrbitalStubProvider(payload.windows)
    session = _planned(scenario, provider)
    pristine = scenario.to_dict()
    clock = session.get_state().simulated_time
    body = cems_payload(payload, clock)
    body.pop("windows")
    event = session.inject_event(EventType.EMERGENCY_TASK, body)
    assert event.event_time == clock
    assert event.payload.windows == payload.windows
    assert MissionEvent.from_dict(event.to_dict()) == event
    assert event.payload.to_dict()["category"] == "Synthetic flood"
    assert session.get_plan().version == 1
    assert session.get_last_impact().event_id == event.id
    assert session.get_scenario().to_dict() == pristine
    frozen = set(session.get_last_impact().frozen_action_ids)
    baseline = session.get_plan()
    plan = session.replan()
    assert plan.version == 2
    assert [a for a in plan.actions if a.id in frozen] == [a for a in baseline.actions if a.id in frozen]
    assert session.get_traces(plan.id)
    assert session.get_metrics().emergency_response[0].arrival_time == clock


@pytest.mark.parametrize("change", [
    {"source_url": "https://127.1/"}, {"source_url": "https://0x7f.0x1/"},
    {"source_url": "https://0177.0.0.1/"}, {"source_url": "https://copernicus.eu:bad/"},
    {"source_url": "https://localhost/"}, {"source_url": "https://127.0.0.1/"},
    {"source_url": "https://192.168.1.1/"}, {"source_url": "https://[::1]/"},
    {"category": None}, {"activation_time": None}, {"source_url": "javascript:alert(1)"},
    {"centroid_policy_version": "other"}, {"alert_level": "red"}, {"mag": 6},
    {"activation_time": "2026-01-01T00:00:00"},
    {"activation_time": "2026-01-01T01:00:00+01:00"},
    {"source_event_time": "2099-01-01T00:00:00Z"},
])
def test_invalid_cems_is_rejected_before_windows_or_mutation(change):
    scenario, payload = _orbital_scenario()
    provider = _OrbitalStubProvider()
    session = _planned(scenario, provider)
    body = cems_payload(payload, session.get_state().simulated_time)
    body.pop("windows")
    body.update(change)
    before = _snapshot(session)
    with pytest.raises(InvalidEventError):
        session.inject_event(EventType.EMERGENCY_TASK, body)
    assert _snapshot(session) == before
    assert provider.arrival_calls == 0


@pytest.mark.parametrize("field,value", [("target_lat", 91), ("target_lon", float("nan")), ("duration_s", 0), ("energy_cost_wh", -1)])
def test_bad_cems_profile_is_rejected_before_generation(field, value):
    scenario, payload = _orbital_scenario()
    provider = _OrbitalStubProvider()
    session = _planned(scenario, provider)
    body = cems_payload(payload, session.get_state().simulated_time)
    body.pop("windows")
    body["request"][field] = value
    with pytest.raises(InvalidEventError):
        session.inject_event(EventType.EMERGENCY_TASK, body)
    assert provider.arrival_calls == 0


def test_cems_http_accepts_complete_evidence_and_rejects_partial():
    async def run():
        scenario, payload = build_emergency_replan_fixture()
        async with _http(_OrbitalStubProvider()) as client:
            await _planned_over_http(client, scenario)
            clock = scenario.start_time + timedelta(seconds=300)
            body = cems_payload(payload, clock)
            path = f"/scenarios/{scenario.id}/events"
            bad = await client.post(path, json={"event_type": "EMERGENCY_TASK", "payload": {**body, "category": None}})
            assert bad.status_code == 422
            accepted = await client.post(path, json={"event_type": "EMERGENCY_TASK", "payload": body})
            assert accepted.status_code == 201, accepted.text
            from amis.domain import EmergencyRequestPayload
            assert EmergencyRequestPayload.from_dict(accepted.json()["payload"]) == EmergencyRequestPayload.from_dict(body)
            assert (await client.get(path)).json() == [accepted.json()]
    asyncio.run(run())

@pytest.mark.parametrize("empty", [False, True])
def test_cems_persistence_and_offline_replay_preserve_evidence_windows_and_response(tmp_path, monkeypatch, empty):
    import socket
    from sqlalchemy import create_engine
    from amis.db.repositories import build_repositories
    from amis.db.schema import metadata
    from amis.repositories import MissionSessionStore

    def no_network(*args, **kwargs):
        raise AssertionError("network forbidden during CEMS lifecycle/replay")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.chdir(tmp_path)  # No source archive exists here.
    scenario, payload = _orbital_scenario()
    scenario = replace(scenario, end_time=scenario.start_time + timedelta(days=2),
        requests=tuple(replace(r, priority=4) if r.id == "OBS-C" else r for r in scenario.requests))
    provider = _OrbitalStubProvider(() if empty else payload.windows)
    engine = create_engine(f"sqlite:///{tmp_path / 'cems.db'}")
    metadata.create_all(engine)
    store = MissionSessionStore(build_repositories(engine), window_provider=provider)
    session = store.create(scenario)
    session.generate_windows()
    session.plan()
    session.step(300)
    body = cems_payload(payload, session.get_state().simulated_time)
    body.pop("windows")
    event = session.inject_event(EventType.EMERGENCY_TASK, body)
    plan = session.replan()
    row = session.get_metrics().emergency_response[0]
    if empty:
        assert row.planned_start_time is None
        session.step(24 * 60 * 60 + 1)
        assert session.get_metrics().emergency_response[0].request_status == "expired"
    else:
        assert row.planned_start_time is not None
        session.step((row.planned_start_time - session.get_state().simulated_time).total_seconds())
        assert session.get_metrics().emergency_response[0].achieved_start_time == row.planned_start_time
    expected = session.get_metrics().emergency_response
    store.save(session)
    engine.dispose()

    restarted = create_engine(f"sqlite:///{tmp_path / 'cems.db'}")
    restored = MissionSessionStore(build_repositories(restarted), window_provider=provider).load(scenario.id)
    assert restored.get_events() == (event,)
    assert restored.get_windows() == session.get_windows()
    assert restored.get_metrics().emergency_response == expected
    assert restored.get_scenario().to_dict() == scenario.to_dict()

    replay_provider = _OrbitalStubProvider()
    replay = _planned(scenario, replay_provider)
    replay.inject_event(event.event_type, event.to_dict()["payload"])
    replay_plan = replay.replan()
    assert replay_provider.arrival_calls == 0
    assert replay.get_events() == (event,)
    assert replay.get_windows() == session.get_windows()
    assert [(a.request_id, a.start, a.end) for a in replay_plan.actions] == [(a.request_id, a.start, a.end) for a in plan.actions]
    restored.reset()
    assert restored.get_events() == ()
    assert restored.get_request_pool() == scenario.requests
    restarted.dispose()


def test_duplicate_cems_identity_and_wrong_injection_time_fail_before_generation():
    scenario, payload = _orbital_scenario()
    provider = _OrbitalStubProvider()
    session = _planned(scenario, provider)
    clock = session.get_state().simulated_time
    body = cems_payload(payload, clock)
    body.pop("windows")
    late = {**body, "activation_time": (clock - timedelta(seconds=1)).isoformat()}
    with pytest.raises(InvalidEventError, match="injection time"):
        session.inject_event(EventType.EMERGENCY_TASK, late)
    assert provider.arrival_calls == 0
    session.inject_event(EventType.EMERGENCY_TASK, body)
    duplicate = {**body, "request": {**body["request"], "id": "OTHER-REQUEST"}}
    before = _snapshot(session)
    with pytest.raises(InvalidEventError, match="already exists"):
        session.inject_event(EventType.EMERGENCY_TASK, duplicate)
    assert provider.arrival_calls == 1
    assert _snapshot(session) == before


@pytest.mark.parametrize("source", [None, "usgs", "cems"])
def test_orbital_provider_failure_keeps_the_structured_emergency_error(source):
    class FailingProvider(_OrbitalStubProvider):
        def generate(self, scenario, requests):
            if tuple(requests) != scenario.requests:
                raise ValueError("synthetic provider failure")
            return super().generate(scenario, requests)

    scenario, payload = _orbital_scenario()
    session = _planned(scenario, FailingProvider())
    if source == "cems":
        body = cems_payload(payload, session.get_state().simulated_time)
    else:
        body = payload.to_dict()
        if source:
            body.update(source=source, source_event_id="synthetic-usgs", alert_level="unknown")
    body.pop("windows")
    before = _snapshot(session)
    with pytest.raises(InvalidEventError, match="could not generate"):
        session.inject_event(EventType.EMERGENCY_TASK, body)
    assert _snapshot(session) == before
