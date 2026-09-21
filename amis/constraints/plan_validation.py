"""validate_plan: the constraint engine's aggregate check.

Runs every check against every action in one call and returns every
violation found, rather than stopping at the first. See ADR-0003 for
the frozen-action exemption. A started or completed action is frozen:
its resource cost is already reflected in mission_state, so it is
skipped for checks and for resource projection, but it still occupies
time for the overlap check against unfrozen actions.
"""

from __future__ import annotations

from typing import Iterable

from amis.constraints.availability import check_satellite_availability
from amis.constraints.containment import check_window_containment
from amis.constraints.deadline import check_deadline
from amis.constraints.overlap import check_overlap
from amis.constraints.resources import (
    ResourceProjection,
    check_projected_battery,
    check_projected_storage,
)
from amis.domain import (
    ActionStatus,
    MissionPlan,
    MissionState,
    ObservationRequest,
    ObservationWindow,
    Scenario,
    Violation,
)


def validate_plan(
    scenario: Scenario,
    mission_state: MissionState,
    requests: Iterable[ObservationRequest],
    windows: Iterable[ObservationWindow],
    plan: MissionPlan,
) -> list[Violation]:
    requests_by_id = {request.id: request for request in requests}
    windows_by_id = {window.id: window for window in windows}
    ordered_actions = sorted(plan.actions, key=lambda action: (action.start, action.id))

    projection = ResourceProjection(mission_state.battery_wh, mission_state.storage_usage_mb)
    violations: list[Violation] = []

    for index, action in enumerate(ordered_actions):
        if action.status is not ActionStatus.PLANNED:
            continue

        request = requests_by_id[action.request_id]
        window = windows_by_id[action.window_id]
        other_actions = ordered_actions[:index] + ordered_actions[index + 1 :]
        battery_wh, storage_used_mb = projection.available_at(action.start)

        checks = (
            check_window_containment(action.request_id, window, action.start, action.end),
            check_deadline(action.request_id, request.deadline, action.end),
            check_satellite_availability(action.request_id, mission_state.available),
            check_projected_battery(action.request_id, action.energy_cost_wh, battery_wh),
            check_projected_storage(
                action.request_id,
                action.storage_cost_mb,
                storage_used_mb,
                scenario.satellite.storage_capacity_mb,
            ),
            check_overlap(action.request_id, action.start, action.end, other_actions),
        )
        violations.extend(violation for violation in checks if violation is not None)
        projection.commit(action)

    return violations
