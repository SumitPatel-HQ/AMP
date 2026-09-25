from datetime import datetime, timedelta, timezone

from amis.domain import (
    ActionStatus,
    MissionPlan,
    MissionState,
    ObservationRequest,
    RequestStatus,
    Satellite,
    Scenario,
    ScheduledAction,
)
from amis.metrics import compute_metrics

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 1, 2, tzinfo=timezone.utc)


def _scenario(requests: tuple[ObservationRequest, ...]) -> Scenario:
    satellite = Satellite(
        id="SAT-001",
        battery_capacity_wh=100.0,
        battery_charge_wh=60.0,
        storage_capacity_mb=200.0,
        storage_usage_mb=50.0,
        available=True,
    )
    return Scenario(
        id="SCN-001",
        name="Metrics test",
        start_time=START,
        end_time=END,
        satellite=satellite,
        requests=requests,
    )


def _plan(actions: tuple[ScheduledAction, ...]) -> MissionPlan:
    return MissionPlan(
        id="PLAN-001",
        scenario_id="SCN-001",
        version=1,
        created_at=START,
        actions=actions,
        unscheduled=(),
        mission_utility=0,
        violation_count=2,
        planning_time_ms=12.5,
    )


def _action(request_id: str) -> ScheduledAction:
    return ScheduledAction(
        id=f"ACT-{request_id}",
        request_id=request_id,
        satellite_id="SAT-001",
        window_id=f"WIN-{request_id}",
        start=START,
        end=START + timedelta(minutes=5),
        energy_cost_wh=10.0,
        storage_cost_mb=5.0,
        status=ActionStatus.PLANNED,
    )


def test_mission_utility_counts_scheduled_and_completed_requests_once_each():
    requests = (
        ObservationRequest(
            id="OBS-A",
            target_lat=0.0,
            target_lon=0.0,
            priority=5,
            duration_s=300.0,
            deadline=END,
            energy_cost_wh=10.0,
            storage_cost_mb=5.0,
            status=RequestStatus.SCHEDULED,
        ),
        ObservationRequest(
            id="OBS-B",
            target_lat=0.0,
            target_lon=0.0,
            priority=3,
            duration_s=300.0,
            deadline=END,
            energy_cost_wh=10.0,
            storage_cost_mb=5.0,
            status=RequestStatus.COMPLETED,
        ),
        ObservationRequest(
            id="OBS-C",
            target_lat=0.0,
            target_lon=0.0,
            priority=1,
            duration_s=300.0,
            deadline=END,
            energy_cost_wh=10.0,
            storage_cost_mb=5.0,
            status=RequestStatus.DROPPED,
        ),
    )
    scenario = _scenario(requests)
    mission_state = MissionState(
        scenario_id=scenario.id,
        simulated_time=START,
        satellite_id="SAT-001",
        battery_wh=60.0,
        storage_usage_mb=50.0,
        available=True,
        completed_request_ids=("OBS-B",),
    )
    plan = _plan((_action("OBS-A"),))

    metrics = compute_metrics(scenario, mission_state, requests, plan)

    assert metrics.mission_utility == 8


def test_mission_utility_counts_a_request_that_is_both_scheduled_and_completed_once():
    requests = (
        ObservationRequest(
            id="OBS-A",
            target_lat=0.0,
            target_lon=0.0,
            priority=5,
            duration_s=300.0,
            deadline=END,
            energy_cost_wh=10.0,
            storage_cost_mb=5.0,
            status=RequestStatus.COMPLETED,
        ),
    )
    scenario = _scenario(requests)
    mission_state = MissionState(
        scenario_id=scenario.id,
        simulated_time=START,
        satellite_id="SAT-001",
        battery_wh=60.0,
        storage_usage_mb=50.0,
        available=True,
        completed_request_ids=("OBS-A",),
    )
    plan = _plan((_action("OBS-A"),))

    metrics = compute_metrics(scenario, mission_state, requests, plan)

    assert metrics.mission_utility == 5


def test_expired_requests_count_against_completion_rate():
    requests = (
        ObservationRequest(
            id="OBS-A",
            target_lat=0.0,
            target_lon=0.0,
            priority=5,
            duration_s=300.0,
            deadline=END,
            energy_cost_wh=10.0,
            storage_cost_mb=5.0,
            status=RequestStatus.COMPLETED,
        ),
        ObservationRequest(
            id="OBS-B",
            target_lat=0.0,
            target_lon=0.0,
            priority=3,
            duration_s=300.0,
            deadline=START,
            energy_cost_wh=10.0,
            storage_cost_mb=5.0,
            status=RequestStatus.EXPIRED,
        ),
    )
    scenario = _scenario(requests)
    mission_state = MissionState(
        scenario_id=scenario.id,
        simulated_time=START,
        satellite_id="SAT-001",
        battery_wh=60.0,
        storage_usage_mb=50.0,
        available=True,
        completed_request_ids=("OBS-A",),
    )
    plan = _plan(())

    metrics = compute_metrics(scenario, mission_state, requests, plan)

    assert metrics.completion_rate == 0.5


def test_completion_rate_is_zero_for_an_empty_request_pool():
    scenario = _scenario(())
    mission_state = MissionState.initial(scenario)
    plan = _plan(())

    metrics = compute_metrics(scenario, mission_state, (), plan)

    assert metrics.completion_rate == 0.0


def test_battery_and_storage_utilisation_are_relative_to_capacity():
    scenario = _scenario(())
    mission_state = MissionState(
        scenario_id=scenario.id,
        simulated_time=START,
        satellite_id="SAT-001",
        battery_wh=60.0,
        storage_usage_mb=50.0,
        available=True,
    )
    plan = _plan(())

    metrics = compute_metrics(scenario, mission_state, (), plan)

    assert metrics.battery_utilisation == 0.4
    assert metrics.storage_utilisation == 0.25


def test_violation_count_and_planning_time_pass_through_from_the_plan():
    scenario = _scenario(())
    mission_state = MissionState.initial(scenario)
    plan = _plan(())

    metrics = compute_metrics(scenario, mission_state, (), plan)

    assert metrics.violation_count == 2
    assert metrics.planning_time_ms == 12.5


def test_metrics_carry_the_request_pool_as_a_size_and_an_id_set():
    requests = (
        ObservationRequest(
            id="OBS-A",
            target_lat=0.0,
            target_lon=0.0,
            priority=5,
            duration_s=300.0,
            deadline=END,
            energy_cost_wh=10.0,
            storage_cost_mb=5.0,
        ),
        ObservationRequest(
            id="OBS-B",
            target_lat=0.0,
            target_lon=0.0,
            priority=3,
            duration_s=300.0,
            deadline=END,
            energy_cost_wh=10.0,
            storage_cost_mb=5.0,
        ),
    )
    scenario = _scenario(requests)
    mission_state = MissionState.initial(scenario)
    plan = _plan(())

    metrics = compute_metrics(scenario, mission_state, requests, plan)

    assert metrics.request_pool_size == 2
    assert metrics.request_pool_ids == frozenset({"OBS-A", "OBS-B"})


def test_churn_and_coverage_are_null_with_no_second_plan_version():
    scenario = _scenario(())
    mission_state = MissionState.initial(scenario)
    plan = _plan(())

    metrics = compute_metrics(scenario, mission_state, (), plan)

    assert metrics.plan_churn is None
    assert metrics.explanation_coverage is None


def test_metrics_result_serialises_to_a_plain_dict_with_no_ui_dependency():
    scenario = _scenario(())
    mission_state = MissionState.initial(scenario)
    plan = _plan(())

    metrics = compute_metrics(scenario, mission_state, (), plan)
    data = metrics.to_dict()

    assert data["plan_id"] == "PLAN-001"
    assert data["request_pool_ids"] == []
    assert data["plan_churn"] is None
    assert data["explanation_coverage"] is None
    assert isinstance(data, dict)


def test_metrics_name_the_simulated_instant_they_were_measured_at():
    # Utilisation and completion read the live mission state rather than the
    # plan, so the same plan scores differently as the clock runs. The instant
    # travels with the metrics so a reader can tell which reading it holds.
    scenario = _scenario(())
    later = START + timedelta(hours=3)
    mission_state = MissionState(
        scenario_id=scenario.id,
        simulated_time=later,
        satellite_id="SAT-001",
        battery_wh=60.0,
        storage_usage_mb=50.0,
        available=True,
    )

    metrics = compute_metrics(scenario, mission_state, (), _plan(()))

    assert metrics.measured_at == later
    assert metrics.to_dict()["measured_at"] == later.isoformat()
