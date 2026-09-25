"""Integration test: the multi request planning path through MissionSession.

Drives load -> generate windows -> plan with no HTTP involved, per
ADR-0001.
"""

from amis.demo import build_demo_scenario
from amis.domain import MissionPlan, ReasonCode
from amis.session import MissionSession


def test_multi_request_scenario_reaches_a_plan_with_an_unscheduled_list_through_the_facade():
    session = MissionSession()

    scenario = session.load_scenario(build_demo_scenario())
    windows = session.generate_windows()
    plan = session.plan()

    assert len(scenario.requests) == 6
    assert len(windows) == 6
    assert isinstance(plan, MissionPlan)

    # OBS-A schedules first (highest priority). OBS-E and OBS-F fit into
    # the rest of the same (whole-scenario-wide) window after OBS-A, now
    # that the planner searches for more than one start instant per
    # window (GAP-04) -- they are no longer wrongly dropped as
    # TIME_OVERLAP just because the window's first instant was taken.
    assert {action.request_id for action in plan.actions} == {"OBS-A", "OBS-E", "OBS-F"}
    assert plan.actions[0].request_id == "OBS-A"

    unscheduled_by_id = {entry.request_id: entry.reason_code for entry in plan.unscheduled}
    assert unscheduled_by_id["OBS-B"] is ReasonCode.INSUFFICIENT_BATTERY
    assert unscheduled_by_id["OBS-C"] is ReasonCode.DEADLINE_VIOLATION
    assert unscheduled_by_id["OBS-D"] is ReasonCode.INSUFFICIENT_STORAGE

    metrics = session.get_metrics()

    assert metrics.plan_id == plan.id
    assert metrics.mission_utility == 7
    # The plan itself is fully valid (three dropped requests, zero
    # validate_plan violations) -- GAP-09.
    assert plan.violation_count == 0
    assert metrics.violation_count == plan.violation_count
    assert metrics.planning_time_ms == plan.planning_time_ms
    assert metrics.request_pool_size == 6
    assert metrics.request_pool_ids == {request.id for request in scenario.requests}
    assert metrics.plan_churn is None
    assert metrics.explanation_coverage is None
