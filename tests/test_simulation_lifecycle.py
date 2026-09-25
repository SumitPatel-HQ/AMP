from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from amis.domain import ActionStatus, ObservationRequest, RequestStatus, Satellite, Scenario
from amis.errors import SimulationStateError
from amis.session import MissionSession


START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = START + timedelta(seconds=20)


def _scenario() -> Scenario:
    satellite = Satellite(
        id="SAT-001",
        battery_capacity_wh=100.0,
        battery_charge_wh=75.0,
        storage_capacity_mb=100.0,
        storage_usage_mb=10.0,
    )
    requests = (
        ObservationRequest(
            id="OBS-A",
            target_lat=12.97,
            target_lon=77.59,
            priority=5,
            duration_s=10.0,
            deadline=END,
            energy_cost_wh=25.0,
            storage_cost_mb=15.0,
        ),
        ObservationRequest(
            id="OBS-B",
            target_lat=28.61,
            target_lon=77.21,
            priority=1,
            duration_s=10.0,
            deadline=START + timedelta(seconds=5),
            energy_cost_wh=5.0,
            storage_cost_mb=5.0,
        ),
    )
    return Scenario(
        id="SCN-001",
        name="Simulation lifecycle test",
        start_time=START,
        end_time=END,
        satellite=satellite,
        requests=requests,
    )


def _planned_session() -> MissionSession:
    session = MissionSession()
    session.load_scenario(_scenario())
    session.generate_windows()
    session.plan()
    return session


def _request_statuses(session: MissionSession) -> dict[str, RequestStatus]:
    return {request.id: request.status for request in session.get_request_pool()}


def test_step_starts_and_completes_an_action_and_charges_resources_once():
    session = _planned_session()

    started = session.step(1)

    assert started.simulated_time == START + timedelta(seconds=1)
    assert started.battery_wh == 50.0
    assert started.storage_usage_mb == 25.0
    assert session.get_plan().actions[0].status is ActionStatus.STARTED

    still_started = session.step(4)

    assert still_started.battery_wh == 50.0
    assert still_started.storage_usage_mb == 25.0
    assert session.get_plan().actions[0].status is ActionStatus.STARTED

    completed = session.step(5)

    assert completed.completed_request_ids == ("OBS-A",)
    assert completed.battery_wh == 50.0
    assert completed.storage_usage_mb == 25.0
    assert session.get_plan().actions[0].status is ActionStatus.COMPLETED
    assert _request_statuses(session)["OBS-A"] is RequestStatus.COMPLETED


def test_mission_state_is_an_immutable_value_snapshot():
    session = _planned_session()
    before = session.get_state()
    after = session.step(1)

    assert before.simulated_time == START
    assert after is not before
    with pytest.raises(FrozenInstanceError):
        after.battery_wh = 0.0  # type: ignore[misc]


def test_deadline_passage_expires_an_incomplete_request_permanently():
    session = _planned_session()

    session.step(5)

    assert _request_statuses(session)["OBS-B"] is RequestStatus.DROPPED

    session.step(1)

    assert _request_statuses(session)["OBS-B"] is RequestStatus.EXPIRED

    session.step(1)

    assert _request_statuses(session)["OBS-B"] is RequestStatus.EXPIRED


def test_expired_and_completed_requests_are_excluded_from_a_later_plan():
    # A later planning pass, now that plan() rejects a second call
    # (GAP-05), goes through replan(): completed OBS-A is carried
    # forward frozen (its cost is not lost), and expired OBS-B is
    # invisible to planning entirely, not reported as unscheduled.
    session = _planned_session()
    session.step(10)

    later_plan = session.replan()

    assert {action.request_id for action in later_plan.actions} == {"OBS-A"}
    assert later_plan.actions[0].status is ActionStatus.COMPLETED
    assert later_plan.unscheduled == ()
    assert _request_statuses(session) == {
        "OBS-A": RequestStatus.COMPLETED,
        "OBS-B": RequestStatus.EXPIRED,
    }


def test_step_clamps_at_scenario_end_and_rejects_a_further_step():
    session = _planned_session()

    final_state = session.step(100)

    assert final_state.simulated_time == END
    assert final_state.mission_complete is True

    with pytest.raises(SimulationStateError, match="mission is complete") as raised:
        session.step(1)

    assert raised.value.code == "SIMULATION_STATE_ERROR"


def test_mission_complete_rejects_further_events_and_replans():
    # Regression for GAP-05: POST /events and POST /replan used to be
    # accepted after mission_complete, silently rewriting a "finished"
    # mission's history.
    session = _planned_session()
    session.step(100)
    assert session.get_state().mission_complete is True

    with pytest.raises(SimulationStateError, match="mission is complete"):
        session.inject_battery_drop("SAT-001", 10.0)

    with pytest.raises(SimulationStateError, match="mission is complete"):
        session.replan()


def test_plan_rejects_a_second_call_once_a_plan_exists():
    # Regression for GAP-05: a second plan() call used to append another
    # version=1, parent=None plan, corrupting the version lineage
    # replan() and compare_versions() depend on.
    session = _planned_session()

    with pytest.raises(SimulationStateError, match="already exists"):
        session.plan()

    assert len(session.get_plans()) == 1


def test_generate_windows_rejects_regeneration_once_a_plan_exists():
    # Regression for GAP-05: regenerating windows after a plan exists
    # used to silently discard any invalidation an event already made
    # (e.g. a CLOUD_BLOCK's window.valid=False), leaving the event log
    # unable to explain the persisted window state.
    session = _planned_session()

    with pytest.raises(SimulationStateError, match="cannot be regenerated"):
        session.generate_windows()


def test_step_requires_a_plan_and_a_positive_number_of_seconds():
    session = MissionSession()
    session.load_scenario(_scenario())

    with pytest.raises(SimulationStateError, match="plan"):
        session.step(1)

    session.generate_windows()
    session.plan()

    with pytest.raises(SimulationStateError, match="positive"):
        session.step(0)
    with pytest.raises(SimulationStateError, match="positive"):
        session.step(-1)


def test_reset_returns_to_load_time_and_clears_derived_session_data():
    session = _planned_session()
    session.step(10)

    reset_state = session.reset()

    assert reset_state == session.get_state()
    assert reset_state.simulated_time == START
    assert reset_state.battery_wh == 75.0
    assert reset_state.storage_usage_mb == 10.0
    assert reset_state.completed_request_ids == ()
    assert reset_state.active_event_ids == ()
    assert reset_state.mission_complete is False
    assert session.get_request_pool() == _scenario().requests

    with pytest.raises(SimulationStateError, match="plan"):
        session.get_plan()
    with pytest.raises(SimulationStateError, match="plan"):
        session.step(1)


def test_same_scenario_and_step_sequence_produce_the_same_final_state():
    def run() -> tuple:
        session = _planned_session()
        for seconds in (1, 4, 5, 100):
            session.step(seconds)
        return (
            session.get_state(),
            session.get_request_pool(),
            session.get_plan().actions,
        )

    assert run() == run()
