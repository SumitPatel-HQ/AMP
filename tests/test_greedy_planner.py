from datetime import datetime, timezone

from amis.domain import MissionState, ObservationRequest, Satellite, Scenario
from amis.planning import GreedyPlanner
from amis.windows import SyntheticWindowProvider


def _scenario() -> Scenario:
    satellite = Satellite(
        id="SAT-001",
        battery_capacity_wh=1000.0,
        battery_charge_wh=1000.0,
        storage_capacity_mb=2000.0,
        storage_usage_mb=0.0,
        available=True,
    )
    request = ObservationRequest(
        id="OBS-A",
        target_lat=12.97,
        target_lon=77.59,
        priority=5,
        duration_s=300.0,
        deadline=datetime(2026, 1, 2, tzinfo=timezone.utc),
        energy_cost_wh=50.0,
        storage_cost_mb=100.0,
    )
    return Scenario(
        id="SCN-001",
        name="Greedy planner test",
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
        satellite=satellite,
        requests=(request,),
    )


def test_greedy_planner_schedules_the_one_request_into_the_one_window():
    scenario = _scenario()
    windows = SyntheticWindowProvider().generate(scenario, scenario.requests)
    mission_state = MissionState.initial(scenario)

    plan = GreedyPlanner().plan(scenario, mission_state, scenario.requests, windows)

    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.request_id == "OBS-A"
    assert action.window_id == windows[0].id
    assert plan.unscheduled == ()
    assert plan.mission_utility == 5


def test_greedy_planner_reports_unscheduled_reason_when_no_window_exists():
    scenario = _scenario()
    mission_state = MissionState.initial(scenario)

    plan = GreedyPlanner().plan(scenario, mission_state, scenario.requests, windows=[])

    assert plan.actions == ()
    assert len(plan.unscheduled) == 1
    assert plan.unscheduled[0].request_id == "OBS-A"
    assert plan.mission_utility == 0
