import json
from datetime import datetime, timezone

from amis.domain import (
    CloudBlockPayload,
    DecisionTrace,
    EventType,
    Impact,
    MissionEvent,
    MissionPlan,
    MissionState,
    ObservationRequest,
    ReasonCode,
    ScheduledAction,
    Satellite,
    Scenario,
    UnscheduledEntry,
)


def _build_scenario() -> Scenario:
    satellite = Satellite(
        id="SAT-001",
        battery_capacity_wh=1000.0,
        battery_charge_wh=875.5,
        storage_capacity_mb=2000.0,
        storage_usage_mb=120.0,
        available=True,
    )
    request = ObservationRequest(
        id="OBS-A",
        target_lat=12.97,
        target_lon=77.59,
        priority=5,
        duration_s=300.0,
        deadline=datetime(2026, 1, 2, 0, 0, tzinfo=timezone.utc),
        energy_cost_wh=50.0,
        storage_cost_mb=100.0,
    )
    return Scenario(
        id="SCN-001",
        name="Round trip scenario",
        start_time=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 2, 0, 0, tzinfo=timezone.utc),
        satellite=satellite,
        requests=(request,),
    )


def test_scenario_survives_json_round_trip():
    scenario = _build_scenario()

    serialised = json.dumps(scenario.to_dict())
    restored = Scenario.from_dict(json.loads(serialised))

    assert restored == scenario


def _round_trip(entity):
    return type(entity).from_dict(json.loads(json.dumps(entity.to_dict())))


def test_mission_plan_survives_json_round_trip():
    action = ScheduledAction(
        id="ACT-001",
        request_id="OBS-A",
        satellite_id="SAT-001",
        window_id="WIN-OBS-A-1",
        start=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
        end=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc),
        energy_cost_wh=10.0,
        storage_cost_mb=5.0,
    )
    plan = MissionPlan(
        id="SCN-001:PLAN-001",
        scenario_id="SCN-001",
        version=1,
        created_at=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
        actions=(action,),
        unscheduled=(UnscheduledEntry("OBS-B", ReasonCode.TIME_OVERLAP),),
        mission_utility=5.0,
        violation_count=0,
        planning_time_ms=1.2,
        parent_plan_id=None,
    )

    assert _round_trip(plan) == plan


def test_mission_state_survives_json_round_trip():
    state = MissionState(
        scenario_id="SCN-001",
        simulated_time=datetime(2026, 1, 1, 0, 10, tzinfo=timezone.utc),
        satellite_id="SAT-001",
        battery_wh=100.0,
        storage_usage_mb=20.0,
        available=True,
        active_event_ids=("EVT-001",),
        completed_request_ids=("OBS-A",),
        mission_complete=False,
    )

    assert _round_trip(state) == state


def test_impact_survives_json_round_trip():
    impact = Impact(
        id="IMP-001",
        event_id="EVT-001",
        evaluated_plan_id="SCN-001:PLAN-001",
        frozen_action_ids=("ACT-001",),
        valid_unfrozen_action_ids=("ACT-002",),
        invalid_unfrozen_action_ids=("ACT-003",),
        reason_codes={"ACT-003": (ReasonCode.WINDOW_INVALIDATED,)},
    )

    assert _round_trip(impact) == impact


def test_decision_trace_survives_json_round_trip():
    previous_action = ScheduledAction(
        id="ACT-001",
        request_id="OBS-A",
        satellite_id="SAT-001",
        window_id="WIN-OBS-A-1",
        start=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
        end=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc),
        energy_cost_wh=10.0,
        storage_cost_mb=5.0,
    )
    trace = DecisionTrace(
        id="TRACE-001",
        plan_id="SCN-001:PLAN-002",
        reason_code=ReasonCode.WINDOW_INVALIDATED,
        message="OBS-A moved because its observation window was invalidated.",
        event_id="EVT-001",
        request_id="OBS-A",
        previous_action=previous_action,
        new_action=None,
        constraint_name="window_containment",
        metadata={"change_type": "DROPPED"},
    )

    assert _round_trip(trace) == trace


def test_mission_event_survives_json_round_trip():
    event = MissionEvent(
        id="EVT-001",
        scenario_id="SCN-001",
        event_type=EventType.CLOUD_BLOCK,
        event_time=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
        payload=CloudBlockPayload(request_id="OBS-A", window_id="WIN-OBS-A-1"),
    )

    assert _round_trip(event) == event
