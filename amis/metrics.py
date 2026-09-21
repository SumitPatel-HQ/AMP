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

from amis.diff import CHANGED_CHANGE_TYPES, rebuilt_actions
from amis.domain import (
    DecisionTrace,
    MetricsResult,
    MissionPlan,
    MissionState,
    ObservationRequest,
    PlanDiff,
    RequestStatus,
    Scenario,
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

    utility_request_ids = {action.request_id for action in plan.actions} | set(
        mission_state.completed_request_ids
    )
    mission_utility = sum(priority_by_id[request_id] for request_id in utility_request_ids)

    pool_size = len(pool)
    completed_count = sum(1 for request in pool if request.status is RequestStatus.COMPLETED)
    completion_rate = completed_count / pool_size if pool_size else 0.0

    battery_capacity = scenario.satellite.battery_capacity_wh
    battery_utilisation = (
        (battery_capacity - mission_state.battery_wh) / battery_capacity if battery_capacity else 0.0
    )
    storage_capacity = scenario.satellite.storage_capacity_mb
    storage_utilisation = mission_state.storage_usage_mb / storage_capacity if storage_capacity else 0.0

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
        plan_churn=compute_plan_churn(previous_plan, plan, diff),
        explanation_coverage=compute_explanation_coverage(diff, traces),
    )


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
