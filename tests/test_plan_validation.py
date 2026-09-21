from datetime import datetime, timedelta, timezone

from amis.constraints import validate_plan
from amis.domain import (
    ActionStatus,
    MissionPlan,
    MissionState,
    ObservationRequest,
    ObservationWindow,
    ReasonCode,
    Satellite,
    Scenario,
    ScheduledAction,
)

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 1, 2, tzinfo=timezone.utc)


def _scenario() -> Scenario:
    satellite = Satellite(
        id="SAT-001",
        battery_capacity_wh=100.0,
        battery_charge_wh=30.0,
        storage_capacity_mb=1000.0,
        storage_usage_mb=0.0,
        available=True,
    )
    requests = (
        ObservationRequest(
            id="OBS-A",
            target_lat=0.0,
            target_lon=0.0,
            priority=5,
            duration_s=300.0,
            deadline=END,
            energy_cost_wh=20.0,
            storage_cost_mb=10.0,
        ),
        ObservationRequest(
            id="OBS-B",
            target_lat=0.0,
            target_lon=0.0,
            priority=4,
            duration_s=300.0,
            deadline=END,
            energy_cost_wh=20.0,
            storage_cost_mb=10.0,
        ),
    )
    return Scenario(
        id="SCN-001",
        name="Plan validation test",
        start_time=START,
        end_time=END,
        satellite=satellite,
        requests=requests,
    )


def _windows() -> list[ObservationWindow]:
    return [
        ObservationWindow(
            id="WIN-OBS-A-1",
            request_id="OBS-A",
            satellite_id="SAT-001",
            start=START,
            end=END,
        ),
        ObservationWindow(
            id="WIN-OBS-B-1",
            request_id="OBS-B",
            satellite_id="SAT-001",
            start=START + timedelta(minutes=30),
            end=END,
        ),
    ]


def test_validate_plan_returns_every_violation_in_one_call():
    scenario = _scenario()
    mission_state = MissionState.initial(scenario)
    windows = _windows()

    plan = MissionPlan(
        id="PLAN-001",
        scenario_id=scenario.id,
        version=1,
        created_at=START,
        actions=(
            ScheduledAction(
                id="ACT-001",
                request_id="OBS-A",
                satellite_id="SAT-001",
                window_id="WIN-OBS-A-1",
                start=START,
                end=START + timedelta(minutes=5),
                energy_cost_wh=20.0,
                storage_cost_mb=10.0,
                status=ActionStatus.PLANNED,
            ),
            ScheduledAction(
                id="ACT-002",
                request_id="OBS-B",
                satellite_id="SAT-001",
                window_id="WIN-OBS-B-1",
                start=START + timedelta(minutes=30),
                end=START + timedelta(minutes=35),
                energy_cost_wh=20.0,
                storage_cost_mb=10.0,
                status=ActionStatus.PLANNED,
            ),
        ),
        unscheduled=(),
        mission_utility=9,
        violation_count=0,
        planning_time_ms=0.0,
    )

    violations = validate_plan(scenario, mission_state, scenario.requests, windows, plan)

    assert len(violations) == 1
    assert violations[0].reason_code is ReasonCode.INSUFFICIENT_BATTERY
    assert violations[0].request_id == "OBS-B"


def test_validate_plan_skips_a_started_action_whose_cost_is_already_in_mission_state():
    scenario = _scenario()
    windows = _windows()
    initial_state = MissionState.initial(scenario)
    started_state = MissionState(
        scenario_id=initial_state.scenario_id,
        simulated_time=START,
        satellite_id=initial_state.satellite_id,
        battery_wh=initial_state.battery_wh - 20.0,
        storage_usage_mb=initial_state.storage_usage_mb + 10.0,
        available=initial_state.available,
    )

    plan = MissionPlan(
        id="PLAN-001",
        scenario_id=scenario.id,
        version=1,
        created_at=START,
        actions=(
            ScheduledAction(
                id="ACT-001",
                request_id="OBS-A",
                satellite_id="SAT-001",
                window_id="WIN-OBS-A-1",
                start=START,
                end=START + timedelta(minutes=5),
                energy_cost_wh=20.0,
                storage_cost_mb=10.0,
                status=ActionStatus.STARTED,
            ),
        ),
        unscheduled=(),
        mission_utility=5,
        violation_count=0,
        planning_time_ms=0.0,
    )

    violations = validate_plan(scenario, started_state, scenario.requests, windows, plan)

    assert violations == []


def test_validate_plan_returns_no_violations_for_a_feasible_plan():
    scenario = _scenario()
    mission_state = MissionState.initial(scenario)
    windows = _windows()

    plan = MissionPlan(
        id="PLAN-001",
        scenario_id=scenario.id,
        version=1,
        created_at=START,
        actions=(
            ScheduledAction(
                id="ACT-001",
                request_id="OBS-A",
                satellite_id="SAT-001",
                window_id="WIN-OBS-A-1",
                start=START,
                end=START + timedelta(minutes=5),
                energy_cost_wh=20.0,
                storage_cost_mb=10.0,
                status=ActionStatus.PLANNED,
            ),
        ),
        unscheduled=(),
        mission_utility=5,
        violation_count=0,
        planning_time_ms=0.0,
    )

    violations = validate_plan(scenario, mission_state, scenario.requests, windows, plan)

    assert violations == []
