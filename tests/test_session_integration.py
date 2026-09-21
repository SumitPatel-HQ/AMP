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

    assert len(plan.actions) == 1
    assert plan.actions[0].request_id == "OBS-A"

    unscheduled_by_id = {entry.request_id: entry.reason_code for entry in plan.unscheduled}
    assert unscheduled_by_id["OBS-B"] is ReasonCode.INSUFFICIENT_BATTERY
    assert unscheduled_by_id["OBS-C"] is ReasonCode.DEADLINE_VIOLATION
    assert unscheduled_by_id["OBS-D"] is ReasonCode.INSUFFICIENT_STORAGE
    assert unscheduled_by_id["OBS-E"] is ReasonCode.TIME_OVERLAP
    assert unscheduled_by_id["OBS-F"] is ReasonCode.TIME_OVERLAP

    metrics = session.get_metrics()

    assert metrics.plan_id == plan.id
    assert metrics.mission_utility == 5
    assert metrics.violation_count == plan.violation_count
    assert metrics.planning_time_ms == plan.planning_time_ms
    assert metrics.request_pool_size == 6
    assert metrics.request_pool_ids == {request.id for request in scenario.requests}
    assert metrics.plan_churn is None
    assert metrics.explanation_coverage is None
