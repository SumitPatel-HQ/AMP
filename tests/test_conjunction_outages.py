"""Conjunction evidence at the agreed MissionSession lifecycle seam."""
from dataclasses import replace
from datetime import timedelta

from amis.demo import CanonicalWindowProvider, build_canonical_replan_scenario
from amis.orbital.elements import catalogue
from amis.session import MissionSession


def scenario():
    base = build_canonical_replan_scenario()
    return replace(base, satellites=(replace(base.satellite, orbit=catalogue()[0]),))


def session_for(sc=None):
    sc = sc or scenario()
    session = MissionSession(window_provider=CanonicalWindowProvider(), plan_id_prefix=f"{sc.id}:PLAN")
    session.load_scenario(sc)
    session.generate_windows()
    session.plan()
    return session


def payload(session, encounter="synthetic-1"):
    action = next(a for a in session.get_plan().actions if a.request_id == "OBS-B")
    return {
        "satellite_id": "SAT-001", "outage_start": action.start.isoformat(),
        "outage_end": action.end.isoformat(),
        "conjunction": {
            "source": "synthetic training fixture", "encounter_id": encounter,
            "matched_norad_id": session.get_scenario().satellite.orbit.norad_id,
            "counterpart_norad_id": 99999,
            "tca": (action.start + timedelta(minutes=5)).isoformat(),
            "miss_distance_km": 0.25, "maximum_probability": 0.0002,
            "threshold": 0.0001, "policy_version": "socrates-outage-v1",
            "pre_padding_s": 300, "post_padding_s": 300,
        },
    }


def test_evidence_is_recorded_and_only_explicit_replan_moves_imaging():
    session = session_for()
    before = session.get_plan()
    data = payload(session)
    event = session.inject_event("SATELLITE_UNAVAILABLE", data)
    assert event.payload.to_dict() == data
    assert session.get_plan() == before
    impact = session.get_last_impact()
    action = next(a for a in before.actions if a.request_id == "OBS-B")
    assert impact.invalid_unfrozen_action_ids == (action.id,)
    assert [r.value for r in impact.reason_codes[action.id]] == ["COLLISION_AVOIDANCE_OUTAGE"]
    session.replan()
    trace = next(t for t in session.get_traces() if t.request_id == "OBS-B")
    assert trace.reason_code.value == "COLLISION_AVOIDANCE_OUTAGE"
    assert trace.event_id == event.id
    assert "99999" in trace.message
    assert trace.metadata["conjunction_events"][0]["event_id"] == event.id


import copy
import pytest
from amis.errors import InvalidEventError


@pytest.mark.parametrize("change", [
    {"threshold": 0.1}, {"maximum_probability": float("nan")},
    {"pre_padding_s": 0}, {"counterpart_norad_id": True},
    {"matched_norad_id": 123}, {"tca": "2026-09-21T10:35:00"},
    {"post_padding_s": 301}, {"policy_version": "unrecognized"},
])
def test_bad_evidence_is_atomic(change):
    session = session_for()
    before = (session.get_state(), session.get_plan(), session.get_events(), session.get_impacts())
    data = payload(session)
    data["conjunction"].update(change)
    with pytest.raises(InvalidEventError):
        session.inject_event("SATELLITE_UNAVAILABLE", data)
    assert (session.get_state(), session.get_plan(), session.get_events(), session.get_impacts()) == before
    assert session.inject_event("SATELLITE_UNAVAILABLE", payload(session)).id == "EVT-001"


def test_api_evidence_group_is_complete_and_round_trips():
    from fastapi.testclient import TestClient
    from amis.api import create_app
    session = session_for()
    data = payload(session)
    with TestClient(create_app(window_provider=CanonicalWindowProvider())) as client:
        sc = session.get_scenario()
        assert client.post("/scenarios", json=sc.to_dict()).status_code == 201
        client.post(f"/scenarios/{sc.id}/windows/generate")
        client.post(f"/scenarios/{sc.id}/plan")
        partial = copy.deepcopy(data)
        del partial["conjunction"]["threshold"]
        route = f"/scenarios/{sc.id}/events"
        assert client.post(route, json={"event_type": "SATELLITE_UNAVAILABLE", "payload": partial}).status_code == 422
        assert client.get(route).json() == []
        accepted = client.post(route, json={"event_type": "SATELLITE_UNAVAILABLE", "payload": data})
        assert accepted.status_code == 201, accepted.text
        from amis.domain import SatelliteOutagePayload
        assert SatelliteOutagePayload.from_dict(accepted.json()["payload"]).to_dict() == data
        assert SatelliteOutagePayload.from_dict(client.get(route).json()[0]["payload"]).to_dict() == data
        assert client.post(route, json={"event_type": "SATELLITE_UNAVAILABLE", "payload": data}).status_code == 400

        oversized = copy.deepcopy(data)
        oversized["conjunction"]["pre_padding_s"] = 1e300
        assert client.post(route, json={"event_type": "SATELLITE_UNAVAILABLE", "payload": oversized}).status_code == 422


def test_overlaps_remain_distinct_and_duplicate_is_atomic():
    session = session_for()
    first = payload(session)
    session.inject_event("SATELLITE_UNAVAILABLE", first)
    second = payload(session, "synthetic-2")
    second.update(outage_start="2026-09-21T10:15:00+00:00", outage_end="2026-09-21T10:35:00+00:00")
    second["conjunction"].update(pre_padding_s=600, post_padding_s=600)
    session.inject_event("SATELLITE_UNAVAILABLE", second)
    assert len(session.get_events()) == 2
    assert len(session.get_last_impact().invalid_unfrozen_action_ids) == 1
    before = (session.get_state(), session.get_events(), session.get_impacts())
    with pytest.raises(InvalidEventError, match="duplicate"):
        session.inject_event("SATELLITE_UNAVAILABLE", first)
    assert (session.get_state(), session.get_events(), session.get_impacts()) == before
    session.replan()
    trace = next(t for t in session.get_traces() if t.request_id == "OBS-B")
    assert len(trace.metadata["conjunction_events"]) == 2


def test_unrelated_resource_failures_retain_constraint_reasons():
    session = session_for()
    session.inject_event("SATELLITE_UNAVAILABLE", payload(session))
    session.inject_battery_drop("SAT-001", 0)
    session.replan()
    traces = {t.request_id: t for t in session.get_traces()}
    assert traces["OBS-B"].reason_code.value == "INSUFFICIENT_BATTERY"
    assert traces["OBS-C"].reason_code.value == "INSUFFICIENT_BATTERY"
    assert "conjunction_events" not in traces["OBS-C"].metadata


def test_frozen_conflict_is_visible_but_execution_history_is_preserved():
    session = session_for()
    session.step(60)
    frozen = next(a for a in session.get_plan().actions if a.request_id == "OBS-A")
    data = payload(session)
    data.update(outage_start=(frozen.end - timedelta(minutes=2)).isoformat(),
                outage_end=(frozen.end + timedelta(minutes=2)).isoformat())
    data["conjunction"].update(tca=frozen.end.isoformat(), pre_padding_s=120, post_padding_s=120)
    state = session.get_state()
    session.inject_event("SATELLITE_UNAVAILABLE", data)
    impact = session.get_last_impact()
    assert frozen.id in impact.frozen_action_ids
    assert frozen.id not in impact.invalid_unfrozen_action_ids
    assert impact.reason_codes[frozen.id][0].value == "COLLISION_AVOIDANCE_OUTAGE"
    after = session.replan()
    assert next(a for a in after.actions if a.id == frozen.id) == frozen
    assert session.get_state().satellites == state.satellites


@pytest.mark.parametrize("mutation", ["late", "outside", "partial", "missing-orbit"])
def test_evidence_timing_horizon_and_completeness(mutation):
    session = session_for()
    data = payload(session)
    if mutation == "late":
        session.step(1260)
    elif mutation == "outside":
        data["conjunction"]["pre_padding_s"] = 1800
        data["outage_start"] = "2026-09-21T09:55:00+00:00"
    elif mutation == "partial":
        del data["conjunction"]["source"]
    else:
        session = session_for(build_canonical_replan_scenario())
    before = (session.get_state(), session.get_events(), session.get_impacts())
    with pytest.raises(InvalidEventError):
        session.inject_event("SATELLITE_UNAVAILABLE", data)
    assert (session.get_state(), session.get_events(), session.get_impacts()) == before


def test_persistence_and_replay_need_only_pristine_scenario_and_recorded_events(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from amis.db.schema import metadata
    from amis.db.repositories import build_repositories
    from amis.repositories import MissionSessionStore
    from amis.domain import MissionEvent
    import socket

    def forbidden(*args, **kwargs):
        raise AssertionError("network forbidden during replay")

    sc = scenario()
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    db = f"sqlite:///{tmp_path / 'conjunction.db'}"
    engine = create_engine(db)
    metadata.create_all(engine)
    store = MissionSessionStore(build_repositories(engine), window_provider=CanonicalWindowProvider())
    session = store.create(sc)
    session.generate_windows()
    session.plan()
    session.step(60)
    session.inject_event("SATELLITE_UNAVAILABLE", payload(session))
    impact = session.get_last_impact()
    session.replan()
    store.save(session)
    recorded = [e.to_dict() for e in session.get_events()]
    engine.dispose()
    engine = create_engine(db)
    restored = MissionSessionStore(build_repositories(engine), window_provider=CanonicalWindowProvider()).load(sc.id)
    assert restored.get_events() == session.get_events()
    assert restored.get_traces() == session.get_traces()
    assert restored.get_last_impact() == impact
    replay = session_for(sc)
    for wire in recorded:
        event = MissionEvent.from_dict(wire)
        replay.step((event.event_time - replay.get_state().simulated_time).total_seconds())
        replay.inject_event(event.event_type, event.payload)
    replay.replan()
    assert replay.get_last_impact().to_dict() == impact.to_dict()
    assert [t.to_dict() for t in replay.get_traces()] == [t.to_dict() for t in session.get_traces()]
    assert replay.get_plan().actions == session.get_plan().actions
    engine.dispose()


def test_manual_outage_retains_wire_shape_and_reason_even_with_later_conjunction():
    session = session_for()
    data = payload(session)
    manual = {k: v for k, v in data.items() if k != "conjunction"}
    event = session.inject_event("SATELLITE_UNAVAILABLE", manual)
    assert event.payload.to_dict() == manual
    session.inject_event("SATELLITE_UNAVAILABLE", data)
    session.replan()
    trace = next(t for t in session.get_traces() if t.request_id == "OBS-B")
    assert trace.reason_code.value == "SATELLITE_UNAVAILABLE"
    assert trace.event_id == event.id


@pytest.mark.parametrize("planner", ["greedy", "cp_sat"])
def test_dropped_imaging_reports_conjunction_cause(planner):
    sc = scenario()
    sc = replace(sc, requests=tuple(replace(r, deadline=sc.start_time + timedelta(minutes=60))
                                  if r.id == "OBS-B" else r for r in sc.requests))
    session = session_for(sc)
    session.select_planner(planner)
    session.inject_event("SATELLITE_UNAVAILABLE", payload(session))
    session.replan()
    trace = next(t for t in session.get_traces() if t.request_id == "OBS-B")
    assert trace.metadata["change_type"] == "DROPPED"
    assert trace.reason_code.value == "COLLISION_AVOIDANCE_OUTAGE"


def test_selected_satellite_only_is_affected():
    sc = scenario()
    sc = replace(sc, satellites=(sc.satellite, replace(sc.satellite, id="SAT-002")),
                 requests=tuple(replace(r, satellite_id="SAT-002" if r.id == "OBS-C" else "SAT-001") for r in sc.requests))
    session = session_for(sc)
    before = next(a for a in session.get_plan().actions if a.request_id == "OBS-C")
    data = payload(session)
    data.update(outage_end="2026-09-21T10:55:00+00:00")
    data["conjunction"]["post_padding_s"] = 1800
    session.inject_event("SATELLITE_UNAVAILABLE", data)
    assert before.id in session.get_last_impact().valid_unfrozen_action_ids
    session.replan()
    after = next(a for a in session.get_plan().actions if a.request_id == "OBS-C")
    assert (after.satellite_id, after.start, after.end) == (before.satellite_id, before.start, before.end)
