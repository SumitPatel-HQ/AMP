"""SQLAlchemy repositories: same protocols, disk instead of memory.

Drives the canonical replan demo through ``MissionSessionStore`` backed
by a file-based SQLite database (SQLite so this needs no server and no
API key, matching ticket 10's offline requirement; the repositories
themselves are dialect-agnostic SQLAlchemy Core and are the same code
path Docker Compose points at PostgreSQL), then drops the engine and
opens a fresh one against the same file to simulate a process restart.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from amis.db.repositories import build_repositories
from amis.db.schema import metadata
from amis.demo import (
    CanonicalWindowProvider,
    build_canonical_replan_scenario,
    build_emergency_replan_fixture,
)
from amis.errors import PlanVersionConflictError, ResourceNotFoundError
from amis.repositories import MissionSessionStore

import pytest


def _engine(db_path) -> Engine:
    return create_engine(f"sqlite:///{db_path}")


def _store(engine: Engine) -> MissionSessionStore:
    return MissionSessionStore(
        build_repositories(engine), window_provider=CanonicalWindowProvider()
    )


def test_plan_event_impact_and_traces_survive_a_restart(tmp_path):
    db_path = tmp_path / "amis.db"
    engine = _engine(db_path)
    metadata.create_all(engine)
    store = _store(engine)
    scenario = build_canonical_replan_scenario()

    session = store.create(scenario)
    session.generate_windows()
    version_one = session.plan()
    store.save(session)

    session = store.load(scenario.id)
    session.step(300)
    event = session.inject_cloud_block("OBS-B", "WIN-OBS-B-1")
    impact = session.get_last_impact()
    store.save(session)

    session = store.load(scenario.id)
    version_two = session.replan(expected_parent_plan_id=version_one.id)
    store.save(session, expected_current_plan_id=version_one.id)
    traces = session.get_traces(version_two.id)

    engine.dispose()

    restarted_engine = _engine(db_path)
    restarted_store = _store(restarted_engine)
    restored = restarted_store.load(scenario.id)

    assert restored.get_scenario() == scenario
    assert restored.get_windows() == session.get_windows()

    restored_plans = restored.get_plans()
    assert [plan.version for plan in restored_plans] == [1, 2]
    assert restored_plans[0].id == version_one.id
    assert restored_plans[1].id == version_two.id
    assert restored_plans[1].parent_plan_id == version_one.id
    assert restored_plans[1].actions == version_two.actions

    restored_events = restored.get_events()
    assert [item.id for item in restored_events] == [event.id]
    assert restored_events[0].payload == event.payload
    assert restored_events[0].event_time == event.event_time

    restored_impact = restored.get_last_impact()
    assert restored_impact.id == impact.id
    assert restored_impact.evaluated_plan_id == version_one.id

    restored_traces = restored.get_traces(version_two.id)
    assert [t.id for t in restored_traces] == [t.id for t in traces]
    assert len(restored_traces) == 1
    assert restored_traces[0].previous_action == traces[0].previous_action
    assert restored_traces[0].new_action == traces[0].new_action


def test_id_counters_recover_from_persisted_records_after_a_restart(tmp_path):
    db_path = tmp_path / "amis.db"
    engine = _engine(db_path)
    metadata.create_all(engine)
    store = _store(engine)
    scenario = build_canonical_replan_scenario()

    session = store.create(scenario)
    session.generate_windows()
    version_one = session.plan()
    store.save(session)

    session = store.load(scenario.id)
    session.step(300)
    session.inject_cloud_block("OBS-B", "WIN-OBS-B-1")
    session.replan(expected_parent_plan_id=version_one.id)
    store.save(session, expected_current_plan_id=version_one.id)
    engine.dispose()

    restarted_engine = _engine(db_path)
    restarted_store = _store(restarted_engine)
    session = restarted_store.load(scenario.id)

    current_plan = session.get_plan()
    version_three = session.replan(expected_parent_plan_id=current_plan.id)

    assert version_three.version == 3
    assert version_three.id == f"{scenario.id}:PLAN-003"

    third_event = session.inject_cloud_block("OBS-D", "WIN-OBS-D-1")
    assert third_event.id == "EVT-002"


def test_a_concurrent_replan_conflicts_at_the_repository_boundary(tmp_path):
    """Two requests both load while version one is current; a double click.

    Each session is independently rebuilt from the repositories, per
    ADR-0001, and each replans successfully in isolation because each
    still believes version one is current. Only the first save may
    write version two; the second must be rejected by the repository
    the same way the in-memory implementation rejects it.
    """

    db_path = tmp_path / "amis.db"
    engine = _engine(db_path)
    metadata.create_all(engine)
    store = _store(engine)
    scenario = build_canonical_replan_scenario()

    session = store.create(scenario)
    session.generate_windows()
    version_one = session.plan()
    store.save(session)

    first = store.load(scenario.id)
    first.step(300)
    first.inject_cloud_block("OBS-B", "WIN-OBS-B-1")
    first.replan(expected_parent_plan_id=version_one.id)

    second = store.load(scenario.id)
    second.step(300)
    second.inject_cloud_block("OBS-B", "WIN-OBS-B-1")
    second.replan(expected_parent_plan_id=version_one.id)

    store.save(first, expected_current_plan_id=version_one.id)

    with pytest.raises(PlanVersionConflictError):
        store.save(second, expected_current_plan_id=version_one.id)


def test_a_second_scenario_with_the_same_id_is_rejected(tmp_path):
    db_path = tmp_path / "amis.db"
    engine = _engine(db_path)
    metadata.create_all(engine)
    store = _store(engine)
    scenario = build_canonical_replan_scenario()

    store.create(scenario)

    from amis.errors import InvalidScenarioError

    with pytest.raises(InvalidScenarioError):
        store.repositories.scenarios.add(scenario)


def test_loading_an_unknown_scenario_raises_resource_not_found(tmp_path):
    db_path = tmp_path / "amis.db"
    engine = _engine(db_path)
    metadata.create_all(engine)
    store = _store(engine)

    with pytest.raises(ResourceNotFoundError):
        store.load("SCN-DOES-NOT-EXIST")


def test_battery_drop_and_emergency_task_payloads_survive_a_restart(tmp_path):
    """CLOUD_BLOCK is covered above; the other two event payload shapes
    (a flat float, and a nested request plus windows) round-trip through
    the same JSON payload column, so both are exercised here too."""

    db_path = tmp_path / "amis.db"
    engine = _engine(db_path)
    metadata.create_all(engine)
    store = _store(engine)
    scenario, emergency_payload = build_emergency_replan_fixture()

    session = store.create(scenario)
    session.generate_windows()
    session.plan()
    store.save(session)

    session = store.load(scenario.id)
    session.step(60)
    battery_event = session.inject_battery_drop(scenario.satellite.id, 50.0)
    store.save(session)

    session = store.load(scenario.id)
    emergency_event = session.inject_emergency_request(
        emergency_payload.request, emergency_payload.windows
    )
    store.save(session)
    engine.dispose()

    restarted_engine = _engine(db_path)
    restarted_store = _store(restarted_engine)
    restored = restarted_store.load(scenario.id)

    restored_events = {event.id: event for event in restored.get_events()}
    assert restored_events[battery_event.id].payload == battery_event.payload
    assert restored_events[emergency_event.id].payload == emergency_event.payload
    assert emergency_payload.request.id in {
        request.id for request in restored.get_request_pool()
    }
