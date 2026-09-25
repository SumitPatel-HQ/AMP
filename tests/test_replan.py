"""Replanning: freeze what started, rebuild the rest, version the result.

Drives MissionSession rather than HTTP, per ADR-0001.
"""

from dataclasses import replace
from datetime import timedelta

import pytest

from amis.constraints import validate_plan
from amis.demo import (
    CanonicalWindowProvider,
    REPLAN_START,
    build_canonical_replan_scenario,
)
from amis.domain import (
    ActionStatus,
    MissionState,
    PlanChangeType,
    ReasonCode,
    RequestStatus,
)
from amis.errors import PlanVersionConflictError, SimulationStateError
from amis.ids import ACTION_ID_PREFIX, PLAN_ID_PREFIX, next_id, next_number
from amis.planning import GreedyPlanner
from amis.session import MissionSession


def _blocked_session() -> MissionSession:
    """Plan v1, run five minutes, then cloud block the 10:20 window."""

    session = MissionSession(window_provider=CanonicalWindowProvider())
    session.load_scenario(build_canonical_replan_scenario())
    session.generate_windows()
    session.plan()
    session.step(300)
    session.inject_cloud_block("OBS-B", "WIN-OBS-B-1")
    return session


def _start_by_request(plan) -> dict:
    return {action.request_id: action.start for action in plan.actions}


def test_replanning_moves_the_blocked_request_and_leaves_everything_else_alone():
    session = _blocked_session()
    version_one = session.get_plan()

    version_two = session.replan()

    assert _start_by_request(version_one)["OBS-B"] == REPLAN_START + timedelta(minutes=20)
    assert _start_by_request(version_two)["OBS-B"] == REPLAN_START + timedelta(minutes=75)
    moved = next(
        action for action in version_two.actions if action.request_id == "OBS-B"
    )
    assert moved.window_id == "WIN-OBS-B-2"

    for request_id in ("OBS-A", "OBS-C", "OBS-D", "OBS-E"):
        assert (
            _start_by_request(version_two)[request_id]
            == _start_by_request(version_one)[request_id]
        )


def test_a_new_version_names_its_parent_and_leaves_the_previous_version_untouched():
    session = _blocked_session()
    version_one = session.get_plan()
    version_one_before = version_one.to_dict()

    version_two = session.replan()

    assert version_two.version == 2
    assert version_two.parent_plan_id == version_one.id
    assert version_two.id == "PLAN-002"
    assert version_one.to_dict() == version_one_before
    assert session.get_plan_by_version(1) is version_one


def test_every_started_action_is_frozen_and_identical_in_the_new_version():
    session = _blocked_session()
    version_one = session.get_plan()
    frozen_before = tuple(
        action
        for action in version_one.actions
        if action.start <= session.get_state().simulated_time
    )
    assert frozen_before  # the demo freezes OBS-A before the block lands

    version_two = session.replan()

    frozen_ids = {action.id for action in frozen_before}
    frozen_after = tuple(
        action for action in version_two.actions if action.id in frozen_ids
    )
    assert frozen_after == frozen_before
    assert all(action.status is ActionStatus.STARTED for action in frozen_after)


def test_replanning_reconsiders_a_request_the_previous_version_dropped():
    session = MissionSession(window_provider=CanonicalWindowProvider())
    scenario = build_canonical_replan_scenario()
    tight = replace(
        scenario,
        satellite=replace(scenario.satellite, battery_charge_wh=120.0),
    )
    session.load_scenario(tight)
    session.generate_windows()
    version_one = session.plan()
    assert {entry.request_id for entry in version_one.unscheduled} == {"OBS-D", "OBS-E"}

    version_two = session.replan()

    assert {entry.request_id for entry in version_two.unscheduled} == {"OBS-D", "OBS-E"}
    assert {action.request_id for action in version_two.actions} == {
        "OBS-A",
        "OBS-B",
        "OBS-C",
    }
    dropped_requests = [
        request
        for request in session.get_request_pool()
        if request.id in {"OBS-D", "OBS-E"}
    ]
    assert all(request.status is RequestStatus.DROPPED for request in dropped_requests)


def test_a_requests_previous_window_is_tried_first_while_it_stays_valid():
    """The stability rule beats earliest start, or churn would measure the planner."""

    scenario = build_canonical_replan_scenario()
    windows = CanonicalWindowProvider().generate(scenario, scenario.requests)
    mission_state = MissionState.initial(scenario)
    planner = GreedyPlanner()
    parked_late = planner.plan(
        scenario,
        mission_state,
        scenario.requests,
        [window for window in windows if window.id != "WIN-OBS-B-1"],
    )
    assert _start_by_request(parked_late)["OBS-B"] == REPLAN_START + timedelta(minutes=75)

    rebuilt = planner.plan(
        scenario,
        mission_state,
        scenario.requests,
        windows,
        previous_plan=parked_late,
    )

    assert _start_by_request(rebuilt)["OBS-B"] == REPLAN_START + timedelta(minutes=75)


class _SingleWindowProvider(CanonicalWindowProvider):
    """The canonical windows with the 11:15 alternative for OBS-B removed."""

    def generate(self, scenario, requests):
        return [
            window
            for window in super().generate(scenario, requests)
            if window.id != "WIN-OBS-B-2"
        ]


def test_a_blocked_request_with_no_later_window_is_dropped_with_no_alternative_window():
    session = MissionSession(window_provider=_SingleWindowProvider())
    session.load_scenario(build_canonical_replan_scenario())
    session.generate_windows()
    session.plan()
    session.step(300)
    session.inject_cloud_block("OBS-B", "WIN-OBS-B-1")

    version_two = session.replan()

    assert "OBS-B" not in {action.request_id for action in version_two.actions}
    unscheduled = {entry.request_id: entry.reason_code for entry in version_two.unscheduled}
    assert unscheduled["OBS-B"] is ReasonCode.NO_ALTERNATIVE_WINDOW


def test_replanning_with_no_event_reproduces_its_parent_as_a_new_version():
    session = MissionSession(window_provider=CanonicalWindowProvider())
    session.load_scenario(build_canonical_replan_scenario())
    session.generate_windows()
    version_one = session.plan()

    version_two = session.replan()

    assert version_two.version == 2
    assert version_two.parent_plan_id == version_one.id
    assert _start_by_request(version_two) == _start_by_request(version_one)
    assert [action.window_id for action in version_two.actions] == [
        action.window_id for action in version_one.actions
    ]
    assert version_two.unscheduled == version_one.unscheduled
    assert version_two.mission_utility == version_one.mission_utility


def test_validating_the_new_version_covers_the_unfrozen_actions_only():
    session = _blocked_session()
    version_two = session.replan()

    violations = validate_plan(
        session.get_scenario(),
        session.get_state(),
        session.get_request_pool(),
        session.get_windows(),
        version_two,
    )

    assert violations == []
    assert any(action.status is ActionStatus.STARTED for action in version_two.actions)


def test_replanning_against_a_stale_parent_is_rejected():
    session = _blocked_session()
    current = session.get_plan()

    with pytest.raises(PlanVersionConflictError) as raised:
        session.replan(expected_parent_plan_id="PLAN-999")

    assert raised.value.code == "PLAN_VERSION_CONFLICT"
    assert session.get_plan() is current

    assert session.replan(expected_parent_plan_id=current.id).version == 2


def test_replanning_requires_a_plan():
    session = MissionSession(window_provider=CanonicalWindowProvider())
    session.load_scenario(build_canonical_replan_scenario())
    session.generate_windows()

    with pytest.raises(SimulationStateError, match="plan"):
        session.replan()


def test_generated_ids_are_sequential_per_scenario_and_never_reused():
    session = _blocked_session()
    version_one = session.get_plan()
    version_two = session.replan()
    version_three = session.replan()

    assert [plan.id for plan in (version_one, version_two, version_three)] == [
        "PLAN-001",
        "PLAN-002",
        "PLAN-003",
    ]
    request_by_action_id: dict[str, str] = {}
    for plan in (version_one, version_two, version_three):
        for action in plan.actions:
            assert (
                request_by_action_id.setdefault(action.id, action.request_id)
                == action.request_id
            )


def test_a_trace_attributes_to_the_event_that_actually_caused_the_change_not_the_latest_one():
    # Regression for GAP-08: two events land before one replan. Every
    # trace used to be attributed to the *latest* event (here, the
    # battery drop) regardless of which event actually caused the
    # change. OBS-B's window was invalidated by the cloud block; the
    # battery drop's own impact re-evaluation still finds OBS-B's action
    # invalid (the window is still blocked), so a naive "use the latest
    # impact's event" reattributes it to the battery drop instead.
    session = _blocked_session()
    cloud_block_event_id = session.get_events()[-1].id

    battery_event = session.inject_battery_drop("SAT-001", 400.0)
    assert battery_event.id != cloud_block_event_id

    version_two = session.replan()
    traces = session.get_traces(version_two.id)
    obs_b_trace = next(trace for trace in traces if trace.request_id == "OBS-B")

    assert obs_b_trace.event_id == cloud_block_event_id


def test_reset_clears_every_plan_version_and_trace():
    session = _blocked_session()
    session.replan()

    session.reset()

    with pytest.raises(SimulationStateError, match="plan"):
        session.get_plan()
    assert session.get_traces() == ()
    assert session.get_events() == ()


def test_a_comparison_spans_two_non_adjacent_versions():
    session = _blocked_session()
    session.replan()
    session.replan()

    comparison = session.compare_versions(1, 3)

    assert comparison.from_plan_id == "PLAN-001"
    assert comparison.to_plan_id == "PLAN-003"
    moved = comparison.entry_for("OBS-B")
    assert moved.change_type is PlanChangeType.MOVED
    assert moved.old_start == REPLAN_START + timedelta(minutes=20)
    assert moved.new_start == REPLAN_START + timedelta(minutes=75)


def test_an_id_counter_is_recovered_from_the_records_rather_than_a_running_count():
    assert next_number(PLAN_ID_PREFIX, []) == 1
    assert next_number(PLAN_ID_PREFIX, ["PLAN-003", "PLAN-001"]) == 4
    assert next_number(ACTION_ID_PREFIX, ["PLAN-009", "ACT-002"]) == 3
    assert next_id(ACTION_ID_PREFIX, ["ACT-011"]) == "ACT-012"
