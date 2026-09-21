"""compute_metrics: quantify a plan's quality as plain data.

Metrics are computed over the request pool rather than the scenario, so
an expired request stays counted against completion. Churn and coverage
need a second plan version to compare against, so they return null
until replanning exists.
"""

from __future__ import annotations

from typing import Iterable

from amis.domain import MetricsResult, MissionPlan, MissionState, ObservationRequest, RequestStatus, Scenario


def compute_metrics(
    scenario: Scenario,
    mission_state: MissionState,
    request_pool: Iterable[ObservationRequest],
    plan: MissionPlan,
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
    )
