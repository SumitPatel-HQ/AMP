"""compute_metrics: quantify a plan's quality as plain data.

Metrics are computed over the request pool rather than the scenario, so
an expired request stays counted against completion.

Churn and coverage need a comparison to compute over, so they stay null
until a plan has a parent version. Both also return null when their own
denominator is zero rather than a score, because 1.0 is the exact number
the demonstration quotes as evidence of explainability and a vacuous 1.0
would be defensible arithmetic and a misleading headline.

Emergency response follows the same rule: a mean over no served request
is null, and an unserved request is never counted as zero latency.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from amis.constraints.resources import ResourceProjection
from amis.diff import CHANGED_CHANGE_TYPES, rebuilt_actions
from amis.domain import (
    DecisionTrace,
    EmergencyRequestPayload,
    EmergencyResponse,
    EventType,
    MetricsResult,
    MissionEvent,
    MissionPlan,
    MissionState,
    ObservationRequest,
    PlanDiff,
    RequestStatus,
    Satellite,
    SatelliteMetrics,
    Scenario,
    ScheduledAction,
    imaging_actions,
)
from amis.errors import SimulationStateError


def compute_metrics(
    scenario: Scenario,
    mission_state: MissionState,
    request_pool: Iterable[ObservationRequest],
    plan: MissionPlan,
    previous_plan: Optional[MissionPlan] = None,
    diff: Optional[PlanDiff] = None,
    traces: Iterable[DecisionTrace] = (),
    events: Iterable[MissionEvent] = (),
    executed_actions: Iterable[ScheduledAction] = (),
) -> MetricsResult:
    """``executed_actions`` is the session's authoritative history of
    actions that have actually started. Without it nothing is achieved:
    a plan's proposed starts are never read as execution, whatever the
    clock says.
    """
    pool = tuple(request_pool)
    priority_by_id = {request.id: request.priority for request in pool}

    utility_request_ids = {action.request_id for action in imaging_actions(plan.actions)} | set(
        mission_state.completed_request_ids
    )
    mission_utility = sum(priority_by_id[request_id] for request_id in utility_request_ids)

    pool_size = len(pool)
    completed_count = sum(1 for request in pool if request.status is RequestStatus.COMPLETED)
    completion_rate = completed_count / pool_size if pool_size else 0.0

    # Wave 7 (ADR-0014): the mission-wide number is the mean across
    # satellites, which is exactly the one satellite's own number when
    # there is only one (single-satellite parity).
    single = len(scenario.satellites) == 1
    per_satellite = tuple(
        _satellite_metrics(satellite, mission_state, plan, single)
        for satellite in scenario.satellites
    )
    battery_utilisation = (
        sum(item.battery_utilisation for item in per_satellite) / len(per_satellite)
        if per_satellite else 0.0
    )
    storage_utilisation = (
        sum(item.storage_utilisation for item in per_satellite) / len(per_satellite)
        if per_satellite else 0.0
    )

    responses = compute_emergency_response(
        events, pool, plan, executed_actions, mission_state.simulated_time
    )
    planned_mean, planned_count = _mean_of_known(
        item.planned_latency_s for item in responses
    )
    achieved_mean, achieved_count = _mean_of_known(
        item.achieved_latency_s for item in responses
    )

    return MetricsResult(
        plan_id=plan.id,
        mission_utility=mission_utility,
        completion_rate=completion_rate,
        violation_count=plan.violation_count,
        planning_time_ms=plan.planning_time_ms,
        battery_utilisation=battery_utilisation,
        storage_utilisation=storage_utilisation,
        request_pool_size=pool_size,
        request_pool_ids=frozenset(request.id for request in pool),
        measured_at=mission_state.simulated_time,
        plan_churn=compute_plan_churn(previous_plan, plan, diff),
        explanation_coverage=compute_explanation_coverage(diff, traces),
        downlink_action_count=sum(1 for action in plan.actions if action.is_downlink),
        downlink_volume_mb=sum(item.downlink_volume_mb for item in per_satellite),
        per_satellite=per_satellite,
        emergency_response=responses,
        time_to_first_acquisition_s=planned_mean,
        achieved_time_to_first_acquisition_s=achieved_mean,
        emergency_request_count=len(responses),
        planned_emergency_request_count=planned_count,
        achieved_emergency_request_count=achieved_count,
    )


def compute_emergency_response(
    events: Iterable[MissionEvent],
    request_pool: Iterable[ObservationRequest],
    plan: MissionPlan,
    executed_actions: Iterable[ScheduledAction],
    measured_at: datetime,
) -> tuple[EmergencyResponse, ...]:
    """One row per accepted emergency arrival in the measured plan's pool.

    Planned values come from ``plan``, so a historical plan keeps its own
    attribution. Achieved values come only from ``executed_actions`` that
    started at or before ``measured_at``; a proposed start is never proof
    of execution. Downlinks never count as acquisition.
    """

    pool_by_id = {request.id: request for request in request_pool}
    arrivals: dict[str, MissionEvent] = {}
    for event in events:
        if event.event_type is not EventType.EMERGENCY_TASK or not isinstance(
            event.payload, EmergencyRequestPayload
        ):
            continue
        request_id = event.payload.request.id
        if request_id in pool_by_id and request_id not in arrivals:
            arrivals[request_id] = event

    planned_by_request = _first_imaging_by_request(plan.actions)
    achieved_by_request = _first_imaging_by_request(
        action for action in executed_actions if action.start <= measured_at
    )

    rows = []
    for request_id, event in arrivals.items():
        planned = planned_by_request.get(request_id)
        achieved = achieved_by_request.get(request_id)
        rows.append(
            EmergencyResponse(
                request_id=request_id,
                event_id=event.id,
                arrival_time=event.event_time,
                request_status=pool_by_id[request_id].status.value,
                planned_start_time=planned.start if planned else None,
                planned_latency_s=_latency(event, planned),
                planned_satellite_id=planned.satellite_id if planned else None,
                achieved_start_time=achieved.start if achieved else None,
                achieved_latency_s=_latency(event, achieved),
                achieved_satellite_id=achieved.satellite_id if achieved else None,
            )
        )
    return tuple(sorted(rows, key=lambda row: (row.arrival_time, row.request_id)))


def _first_imaging_by_request(
    actions: Iterable[ScheduledAction],
) -> dict[str, ScheduledAction]:
    first: dict[str, ScheduledAction] = {}
    for action in sorted(imaging_actions(actions), key=lambda item: (item.start, item.id)):
        if action.request_id is not None:
            first.setdefault(action.request_id, action)
    return first


def _latency(event: MissionEvent, action: Optional[ScheduledAction]) -> Optional[float]:
    if action is None:
        return None
    latency = (action.start - event.event_time).total_seconds()
    if latency < 0:
        # An action starting before its request arrived is an inconsistent
        # association; clamping it to zero would read as instant service.
        raise SimulationStateError(
            "emergency imaging action starts before its request arrived",
            details={
                "request_id": action.request_id,
                "event_id": event.id,
                "action_id": action.id,
                "arrival_time": event.event_time.isoformat(),
                "action_start": action.start.isoformat(),
            },
        )
    return latency


def _mean_of_known(values: Iterable[Optional[float]]) -> tuple[Optional[float], int]:
    """Mean over the non-null values and its denominator; null when empty."""
    known = [value for value in values if value is not None]
    return (sum(known) / len(known) if known else None), len(known)


def _satellite_metrics(
    satellite: Satellite, mission_state: MissionState, plan: MissionPlan, single: bool = False
) -> SatelliteMetrics:
    satellite_state = mission_state.for_satellite(satellite.id)
    battery_capacity = satellite.battery_capacity_wh
    battery_utilisation = (
        (battery_capacity - satellite_state.battery_wh) / battery_capacity if battery_capacity else 0.0
    )
    storage_capacity = satellite.storage_capacity_mb
    storage_utilisation = (
        satellite_state.storage_usage_mb / storage_capacity if storage_capacity else 0.0
    )
    satellite_actions = tuple(action for action in plan.actions if action.satellite_id == satellite.id)
    if single and not satellite_actions:
        # Pre-Wave-7 hand-crafted plans use dummy satellite ids; a single
        # satellite owns the whole plan, so count everything there.
        satellite_actions = tuple(plan.actions)
    return SatelliteMetrics(
        satellite_id=satellite.id,
        battery_utilisation=battery_utilisation,
        storage_utilisation=storage_utilisation,
        downlink_action_count=sum(1 for action in satellite_actions if action.is_downlink),
        downlink_volume_mb=_downlink_volume_for(satellite.storage_usage_mb, satellite_actions),
    )


def compute_downlink_volume(scenario: Scenario, plan: MissionPlan) -> float:
    """Storage the plan's downlinks actually free, floored at zero (ADR-0011).

    The mission total across every satellite (Wave 7, ADR-0014). The plan
    carries every executed action forward, so walking each satellite's own
    actions from its own initial storage replays its full storage story.
    Nominal rate x duration overstates a downlink that ends with less stored.
    """
    if len(scenario.satellites) == 1:
        # Pre-Wave-7 hand-crafted plans use dummy satellite ids; walk the
        # whole plan from the single satellite's initial storage.
        only = scenario.satellites[0]
        matched = tuple(action for action in plan.actions if action.satellite_id == only.id)
        actions = matched if matched else tuple(plan.actions)
        return _downlink_volume_for(only.storage_usage_mb, actions)
    return sum(
        _downlink_volume_for(
            satellite.storage_usage_mb,
            tuple(action for action in plan.actions if action.satellite_id == satellite.id),
        )
        for satellite in scenario.satellites
    )


def _downlink_volume_for(initial_storage_usage_mb: float, actions: Iterable) -> float:
    projection = ResourceProjection(0.0, initial_storage_usage_mb)
    for action in actions:
        projection.commit(action)
    return sum(projection.freed_by_downlinks().values())


def compute_plan_churn(
    previous_plan: Optional[MissionPlan],
    plan: MissionPlan,
    diff: Optional[PlanDiff],
) -> Optional[float]:
    """Changed unfrozen actions over the unfrozen actions of the earlier version.

    An inserted request holds no action in the earlier version, so it
    cannot reach the numerator and needs no special case here.
    """

    if previous_plan is None or diff is None:
        return None

    unfrozen_before = rebuilt_actions(previous_plan, plan)
    if not unfrozen_before:
        return None

    changed_request_ids = {
        entry.request_id
        for entry in diff.entries
        if entry.change_type in CHANGED_CHANGE_TYPES
    }
    changed_count = sum(
        1 for action in unfrozen_before if action.request_id in changed_request_ids
    )
    return changed_count / len(unfrozen_before)


def compute_explanation_coverage(
    diff: Optional[PlanDiff], traces: Iterable[DecisionTrace] = ()
) -> Optional[float]:
    """Changed actions carrying a decision trace over changed actions."""

    if diff is None:
        return None

    changed_request_ids = [
        entry.request_id
        for entry in diff.entries
        if entry.change_type in CHANGED_CHANGE_TYPES
    ]
    if not changed_request_ids:
        return None

    traced_request_ids = {trace.request_id for trace in traces}
    covered = sum(
        1 for request_id in changed_request_ids if request_id in traced_request_ids
    )
    return covered / len(changed_request_ids)
