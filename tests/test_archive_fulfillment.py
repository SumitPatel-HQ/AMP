"""Archive fulfillment through the confirmed MissionSession lifecycle seam."""

from datetime import timedelta

import pytest

from amis.demo import CanonicalWindowProvider, build_canonical_replan_scenario
from amis.session import MissionSession
from amis.errors import InvalidEventError, SimulationStateError


def planned_session():
    session = MissionSession(window_provider=CanonicalWindowProvider())
    session.load_scenario(build_canonical_replan_scenario())
    session.generate_windows()
    session.plan()
    session.step(300)
    return session


def evidence(session, request_id="OBS-B"):
    request = next(r for r in session.get_request_pool() if r.id == request_id)
    now = session.get_state().simulated_time
    return {
        "request_id": request_id,
        "catalogue_source": "synthetic-catalogue",
        "collection_id": "synthetic-optical",
        "item_id": "synthetic-scene-001",
        "source_url": "https://example.org/synthetic-scene-001",
        "source_response_sha256": "a" * 64,
        "source_credit": "Synthetic fixture; no real catalogue or image product",
        "acquisition_start": (now - timedelta(days=1)).isoformat(),
        "acquisition_end": (now - timedelta(days=1)).isoformat(),
        "retrieved_at": (now - timedelta(minutes=1)).isoformat(),
        "target_lat": request.target_lat,
        "target_lon": request.target_lon,
        "footprint": {"type": "Polygon", "coordinates": [[
            [request.target_lon - 1, request.target_lat - 1],
            [request.target_lon + 1, request.target_lat - 1],
            [request.target_lon + 1, request.target_lat + 1],
            [request.target_lon - 1, request.target_lat + 1],
            [request.target_lon - 1, request.target_lat - 1],
        ]]},
        "cloud_cover_pct": 12,
        "gsd_m": 10,
        "policy_version": "archive-point-v1",
        "profile": {
            "version": "synthetic-profile-v1",
            "allowed_collections": ["synthetic-optical"],
            "acquisition_start": (now - timedelta(days=2)).isoformat(),
            "acquisition_end": now.isoformat(),
            "max_cloud_cover_pct": 20,
            "max_gsd_m": 10,
            "sensor_product_assertion": "Author accepts synthetic optical product for this demonstration",
        },
    }


def test_archive_satisfaction_records_evidence_without_replanning_or_consumption():
    session = planned_session()
    old_plan, old_state = session.get_plan(), session.get_state()
    pristine = session.get_scenario().to_dict()
    payload = evidence(session)

    event = session.inject_event("REQUEST_SATISFIED_BY_ARCHIVE", payload)

    assert event.to_dict()["payload"] == payload
    assert session.get_plan() == old_plan
    assert session.get_state().satellites == old_state.satellites
    assert session.get_scenario().to_dict() == pristine
    assert next(r for r in session.get_request_pool() if r.id == "OBS-B").status.value == "satisfied_by_archive"
    action = next(a for a in old_plan.actions if a.request_id == "OBS-B")
    assert action.id in session.get_last_impact().invalid_unfrozen_action_ids
    assert [r.value for r in session.get_last_impact().reason_codes[action.id]] == ["SATISFIED_BY_ARCHIVE"]


def snapshot(session):
    return (session.get_state(), session.get_plans(), session.get_request_pool(),
            session.get_windows(), session.get_events(), session.get_impacts(), session.get_traces())


def test_affected_clock_requires_explicit_replan_and_preserves_frozen_execution():
    session = planned_session()
    old = session.get_plan()
    frozen = next(a for a in old.actions if a.request_id == "OBS-A")
    before_metrics = session.get_metrics()
    session.inject_event("REQUEST_SATISFIED_BY_ARCHIVE", evidence(session))
    before = snapshot(session)
    with pytest.raises(SimulationStateError, match="replan"):
        session.step(3600)
    assert snapshot(session) == before
    # Advancing before the obsolete action is still permitted.
    session.step(60)
    revised = session.replan()
    assert session.get_state().satellites == before[0].satellites
    assert next(a for a in revised.actions if a.request_id == "OBS-A") == frozen
    assert not any(a.request_id == "OBS-B" for a in revised.actions)
    diff = session.compare_versions(1, 2)
    entry = next(e for e in diff.entries if e.request_id == "OBS-B")
    assert entry.change_type.value == entry.reason_code.value == "SATISFIED_BY_ARCHIVE"
    trace = next(t for t in session.get_traces(revised.id) if t.request_id == "OBS-B")
    assert "archive" in trace.message and trace.new_action is None
    metrics = session.get_metrics()
    assert metrics.archive_satisfied_count == 1
    assert metrics.archive_satisfied_utility == 4
    assert metrics.total_fulfilled_count == 5
    assert metrics.total_fulfilled_utility == before_metrics.mission_utility
    assert metrics.mission_utility == before_metrics.mission_utility - 4
    assert metrics.completion_rate == 0
    assert session.get_metrics(old.id).archive_satisfied_count == 0
    session.step(3 * 3600)
    assert "OBS-B" not in session.get_state().completed_request_ids
    assert next(r for r in session.get_request_pool() if r.id == "OBS-B").status.value == "satisfied_by_archive"


@pytest.mark.parametrize("field,value", [
    ("cloud_cover_pct", 21), ("cloud_cover_pct", float("nan")), ("gsd_m", 0),
    ("gsd_m", True), ("target_lat", 0), ("source_response_sha256", "bad"),
    ("retrieved_at", "2099-01-01T00:00:00+00:00"), ("acquisition_end", "2099-01-01T00:00:00+00:00"),
    ("profile", {}), ("footprint", {"type": "Point", "coordinates": [77, 28]}),
    ("request_id", "unknown"), ("item_id", ""),
])
def test_invalid_archive_evidence_is_atomic_and_does_not_consume_ids(field, value):
    session = planned_session()
    payload = evidence(session)
    payload[field] = value
    before = snapshot(session)
    with pytest.raises(InvalidEventError):
        session.inject_event("REQUEST_SATISFIED_BY_ARCHIVE", payload)
    assert snapshot(session) == before
    event = session.inject_event("REQUEST_SATISFIED_BY_ARCHIVE", evidence(session))
    assert event.id == "EVT-001"


@pytest.mark.parametrize("advance,request_id", [(0, "OBS-A"), (10 * 60, "OBS-A"), (21 * 60, "OBS-B")])
def test_archive_rejects_authoritative_frozen_started_and_completed_imaging(advance, request_id):
    session = planned_session()
    if advance:
        session.step(advance)
    before = snapshot(session)
    with pytest.raises(InvalidEventError):
        session.inject_event("REQUEST_SATISFIED_BY_ARCHIVE", evidence(session, request_id))
    assert snapshot(session) == before


def test_duplicate_rejection_and_caller_evidence_cannot_rewrite_accepted_event():
    session = planned_session()
    payload = evidence(session)
    event = session.inject_event("REQUEST_SATISFIED_BY_ARCHIVE", payload)
    payload["profile"]["max_cloud_cover_pct"] = 99
    assert event.to_dict()["payload"]["profile"]["max_cloud_cover_pct"] == 20
    before = snapshot(session)
    with pytest.raises(InvalidEventError):
        session.inject_event("REQUEST_SATISFIED_BY_ARCHIVE", evidence(session))
    assert snapshot(session) == before


def test_pending_emergency_fulfillment_has_explanation_and_no_invented_acquisition():
    from amis.demo import build_emergency_replan_fixture

    session = planned_session()
    _, arrival = build_emergency_replan_fixture()
    session.inject_event("EMERGENCY_TASK", arrival.to_dict())
    archive = session.inject_event("REQUEST_SATISFIED_BY_ARCHIVE", evidence(session, arrival.request.id))
    immediate = session.get_metrics()
    assert immediate.archive_satisfied_count == 1
    assert immediate.archive_satisfied_utility == arrival.request.priority
    assert arrival.request.id not in immediate.request_pool_ids
    assert immediate.emergency_response[0].request_status == "satisfied_by_archive"
    assert immediate.emergency_response[0].achieved_latency_s is None
    revised = session.replan()
    trace = next(t for t in session.get_traces(revised.id) if t.request_id == arrival.request.id)
    assert trace.event_id == archive.id
    assert trace.previous_action is trace.new_action is None
    metrics = session.get_metrics()
    row, = metrics.emergency_response
    assert row.request_status == "satisfied_by_archive"
    assert row.planned_start_time is row.planned_latency_s is row.planned_satellite_id is None
    assert row.achieved_start_time is row.achieved_latency_s is row.achieved_satellite_id is None
    assert metrics.emergency_request_count == 1
    assert metrics.achieved_time_to_first_acquisition_s is None
    session.replan()
    assert session.get_metrics(revised.id).archive_satisfied_count == 1
    assert session.get_metrics(session.get_plans()[0].id).archive_satisfied_count == 0
    assert session.get_metrics(session.get_plans()[0].id).emergency_response == ()


@pytest.mark.parametrize("planner", ["greedy", "cp_sat"])
def test_archive_terminal_eligibility_for_each_planner(planner):
    session = planned_session()
    session.inject_event("REQUEST_SATISFIED_BY_ARCHIVE", evidence(session))
    session.select_planner(planner)
    session.replan()
    assert not any(a.request_id == "OBS-B" for a in session.get_plan().actions)
    assert not any(u.request_id == "OBS-B" for u in session.get_plan().unscheduled)


def test_persisted_offline_reconstruction_reset_and_event_replay(tmp_path):
    from sqlalchemy import create_engine
    from amis.db.repositories import build_repositories
    from amis.db.schema import metadata
    from amis.domain import MissionEvent
    from amis.repositories import MissionSessionStore

    database = f"sqlite:///{tmp_path / 'archive.db'}"
    engine = create_engine(database)
    metadata.create_all(engine)
    store = MissionSessionStore(build_repositories(engine), window_provider=CanonicalWindowProvider())
    session = store.create(build_canonical_replan_scenario())
    session.generate_windows()
    old = session.plan()
    session.step(300)
    event = session.inject_event("REQUEST_SATISFIED_BY_ARCHIVE", evidence(session))
    store.save(session)
    session = store.load(session.get_scenario().id)
    assert session.get_events() == (event,)
    with pytest.raises(SimulationStateError, match="replan"):
        session.step(3600)
    session.replan()
    store.save(session)
    engine.dispose()
    restarted_engine = create_engine(database)
    restored = MissionSessionStore(build_repositories(restarted_engine), window_provider=CanonicalWindowProvider()).load(session.get_scenario().id)
    assert restored.get_request_pool() == session.get_request_pool()
    assert restored.get_traces() == session.get_traces()
    assert restored.get_metrics().to_dict() == session.get_metrics().to_dict()
    assert restored.get_metrics(old.id).archive_satisfied_count == 0
    recorded = MissionEvent.from_dict(event.to_dict())
    restored.reset()
    assert restored.get_events() == ()
    assert all(r.status.value == "pending" for r in restored.get_request_pool())
    restored.generate_windows()
    restored.plan()
    restored.step(300)
    assert restored.inject_event(recorded.event_type, recorded.payload).payload == event.payload
    restored.replan()
    assert [(e.request_id, e.change_type) for e in restored.compare_versions(1, 2).entries] == [
        (e.request_id, e.change_type) for e in session.compare_versions(1, 2).entries
    ]
    restarted_engine.dispose()


def test_event_api_preserves_evidence_and_status_filter_contract():
    from fastapi.testclient import TestClient
    from amis.api import create_app
    from amis.repositories import MissionSessionStore, Repositories

    store = MissionSessionStore(Repositories.in_memory(), window_provider=CanonicalWindowProvider())
    session = store.create(build_canonical_replan_scenario())
    session.generate_windows()
    session.plan()
    session.step(300)
    store.save(session)
    client = TestClient(create_app(repositories=store.repositories, window_provider=CanonicalWindowProvider()))
    path = f"/scenarios/{session.get_scenario().id}"
    payload = evidence(session)
    response = client.post(path + "/events", json={"event_type": "REQUEST_SATISFIED_BY_ARCHIVE", "payload": payload})
    assert response.status_code == 201, response.text
    assert response.json()["payload"] == payload
    assert client.get(path + "/events").json()[0]["payload"] == payload
    assert store.load(session.get_scenario().id).get_request_pool()[1].status.value == "satisfied_by_archive"
    pool = client.get(path + "/requests").json()
    assert next(r for r in pool if r["id"] == "OBS-B")["status"] == "satisfied_by_archive"
    duplicate = client.post(path + "/events", json={"event_type": "REQUEST_SATISFIED_BY_ARCHIVE", "payload": payload})
    assert duplicate.status_code == 400


@pytest.mark.parametrize("status", ["expired", "completed", "dropped", "satisfied_by_archive"])
def test_terminal_or_dropped_requests_are_rejected_before_any_mutation(status):
    from dataclasses import replace
    from amis.domain import RequestStatus

    scenario = build_canonical_replan_scenario()
    # Preserve supplied statuses, without needing a fabricated completed action.
    scenario = replace(scenario, requests=tuple(replace(r, status=RequestStatus(status)) if r.id == "OBS-B" else r for r in scenario.requests))
    session = MissionSession(window_provider=CanonicalWindowProvider())
    session.load_scenario(scenario)
    session.generate_windows()
    session.plan()
    # Dropped is eligible to schedule again; force that request to remain dropped.
    if status == "dropped":
        session = MissionSession(window_provider=CanonicalWindowProvider())
        scenario = replace(scenario, requests=tuple(replace(r, deadline=scenario.start_time) if r.id == "OBS-B" else r for r in scenario.requests))
        session.load_scenario(scenario)
        session.generate_windows()
        session.plan()
    session.step(300)
    before = snapshot(session)
    with pytest.raises(InvalidEventError):
        session.inject_event("REQUEST_SATISFIED_BY_ARCHIVE", evidence(session))
    assert snapshot(session) == before


def test_later_archive_event_does_not_rewrite_existing_plan_comparisons():
    session = planned_session()
    session.replan()
    before = session.compare_versions(1, 2)
    session.inject_event("REQUEST_SATISFIED_BY_ARCHIVE", evidence(session))
    assert session.compare_versions(1, 2).entries == before.entries
    assert session.get_metrics().archive_satisfied_count == 1
    session.replan()
    assert next(e for e in session.compare_versions(2, 3).entries if e.request_id == "OBS-B").change_type.value == "SATISFIED_BY_ARCHIVE"
    assert session.get_metrics(session.get_plans()[1].id).archive_satisfied_count == 0


def test_point_coverage_includes_boundary_but_does_not_infer_coverage_from_bbox():
    session = planned_session()
    payload = evidence(session)
    x, y = payload["target_lon"], payload["target_lat"]
    # Target is in the triangle's bounding box, outside the actual footprint.
    payload["footprint"]["coordinates"] = [[[x - 1, y - 1], [x + 1, y - 1], [x - 1, y + 0.5], [x - 1, y - 1]]]
    before = snapshot(session)
    with pytest.raises(InvalidEventError, match="cover"):
        session.inject_event("REQUEST_SATISFIED_BY_ARCHIVE", payload)
    assert snapshot(session) == before
    payload["footprint"]["coordinates"] = [[[x, y - 1], [x + 1, y - 1], [x + 1, y + 1], [x, y + 1], [x, y - 1]]]
    assert session.inject_event("REQUEST_SATISFIED_BY_ARCHIVE", payload)


@pytest.mark.parametrize("change", [
    {"max_cloud_cover_pct": float("inf")}, {"max_gsd_m": -1},
    {"allowed_collections": ["other"]}, {"sensor_product_assertion": ""},
    {"acquisition_start": "2099-01-01T00:00:00Z"}, {"max_view_angle_deg": 30},
    {"unsupported_required_quality": 1},
])
def test_profile_requirements_fail_closed(change):
    session = planned_session()
    payload = evidence(session)
    payload["profile"].update(change)
    before = snapshot(session)
    with pytest.raises(InvalidEventError):
        session.inject_event("REQUEST_SATISFIED_BY_ARCHIVE", payload)
    assert snapshot(session) == before


def test_optional_required_viewing_limit_accepts_measured_boundary():
    session = planned_session()
    payload = evidence(session)
    payload["profile"]["max_view_angle_deg"] = 30
    payload["view_angle_deg"] = 30
    assert session.inject_event("REQUEST_SATISFIED_BY_ARCHIVE", payload)


def test_public_event_evidence_cannot_be_mutated_after_validation():
    session = planned_session()
    accepted = session.inject_event("REQUEST_SATISFIED_BY_ARCHIVE", evidence(session))
    original = accepted.to_dict()
    for event in (accepted, session.get_events()[0]):
        with pytest.raises(TypeError):
            event.payload.profile["max_cloud_cover_pct"] = 0
        with pytest.raises(TypeError):
            event.payload.footprint["coordinates"][0][0][0] = 0
    serialized = accepted.to_dict()
    serialized["payload"]["profile"]["allowed_collections"].clear()
    assert session.get_events()[0].to_dict() == original
