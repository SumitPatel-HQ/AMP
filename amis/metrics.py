"""compute_metrics: quantify a plan's quality as plain data.

Metrics are computed over the request pool rather than the scenario, so
an expired request stays counted against completion.

Churn and coverage need a comparison to compute over, so they stay null
until a plan has a parent version. Both also return null when their own
denominator is zero rather than a score, because 1.0 is the exact number
the demonstration quotes as evidence of explainability and a vacuous 1.0
would be defensible arithmetic and a misleading headline.
"""

from __future__ import annotations

from typing import Iterable, Optional

from amis.constraints.resources import ResourceProjection
from amis.diff import CHANGED_CHANGE_TYPES, rebuilt_actions
from amis.domain import (
    DecisionTrace,
    MetricsResult,
    MissionPlan,
    MissionState,
    ObservationRequest,
    PlanDiff,
    RequestStatus,
    Satellite,
    SatelliteMetrics,
    Scenario,
    imaging_actions,
)


def compute_metrics(
    scenario: Scenario,
    mission_state: MissionState,
    request_pool: Iterable[ObservationRequest],
    plan: MissionPlan,
    previous_plan: Optional[MissionPlan] = None,
    diff: Optional[PlanDiff] = None,
    traces: Iterable[DecisionTrace] = (),
) -> MetricsResult:
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
    )


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
