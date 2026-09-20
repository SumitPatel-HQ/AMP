"""Integration test: the whole walking-skeleton path through MissionSession.

Drives load -> generate windows -> plan with no HTTP involved, per
ADR-0001.
"""

from amis.demo import build_demo_scenario
from amis.domain import MissionPlan
from amis.session import MissionSession


def test_one_request_reaches_a_printed_plan_through_the_facade():
    session = MissionSession()

    scenario = session.load_scenario(build_demo_scenario())
    windows = session.generate_windows()
    plan = session.plan()

    assert scenario.requests[0].id == "OBS-A"
    assert len(windows) == 1
    assert isinstance(plan, MissionPlan)
    assert len(plan.actions) == 1
    assert plan.actions[0].request_id == "OBS-A"
    assert plan.unscheduled == ()
