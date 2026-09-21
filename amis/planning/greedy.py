"""GreedyPlanner: the MVP's only planner.

Sorts requests priority descending, then deadline ascending, then
duration ascending, then request id ascending, so ties never resolve
arbitrarily. For each request it takes the first candidate window that
passes every check, and otherwise records the request as unscheduled
with the reason code the checks produced.

Checks run window containment, deadline, satellite availability,
projected battery, projected storage, then overlap, in that order, so
a request's own limits are reported ahead of contention with another
request when both apply.

Passing a previous plan turns the same call into a replan. Every action
whose start time has passed is frozen: it is carried into the new
version unchanged and it still occupies time against the rebuilt
actions. Candidate windows then follow the stability rule, so a request
keeps its previous placement whenever that placement is still feasible
and plan churn measures the disruption rather than the planner's own
variability.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from amis.constraints import (
    ResourceProjection,
    check_deadline,
    check_overlap,
    check_projected_battery,
    check_projected_storage,
    check_satellite_availability,
    check_window_containment,
)
from amis.domain import (
    ActionStatus,
    MissionPlan,
    MissionState,
    ObservationRequest,
    ObservationWindow,
    ReasonCode,
    RequestStatus,
    Scenario,
    ScheduledAction,
    UnscheduledEntry,
    Violation,
)
from amis.ids import ACTION_ID_PREFIX, FIRST_PLAN_ID, format_id


class GreedyPlanner:
    def plan(
        self,
        scenario: Scenario,
        mission_state: MissionState,
        requests: Iterable[ObservationRequest],
        windows: Iterable[ObservationWindow],
        previous_plan: Optional[MissionPlan] = None,
        plan_id: str = FIRST_PLAN_ID,
        first_action_number: int = 1,
    ) -> MissionPlan:
        start_perf = time.perf_counter()
        all_requests = tuple(requests)

        windows_by_request: dict[str, list[ObservationWindow]] = {}
        for window in windows:
            windows_by_request.setdefault(window.request_id, []).append(window)

        frozen_actions = _frozen_actions(previous_plan, mission_state)
        frozen_request_ids = {action.request_id for action in frozen_actions}
        previous_window_by_request = {
            action.request_id: action.window_id
            for action in (previous_plan.actions if previous_plan else ())
        }

        eligible_requests = (
            request
            for request in all_requests
            if request.status not in (RequestStatus.COMPLETED, RequestStatus.EXPIRED)
            and request.id not in frozen_request_ids
        )
        ordered_requests = sorted(
            eligible_requests,
            key=lambda request: (
                -request.priority,
                request.deadline,
                request.duration_s,
                request.id,
            ),
        )

        projection = ResourceProjection(mission_state.battery_wh, mission_state.storage_usage_mb)
        for action in frozen_actions:
            # A frozen action that has started is already charged to mission
            # state. One frozen only because the clock reached its start time
            # is not, so the projection still has to carry its cost.
            if action.status is ActionStatus.PLANNED:
                projection.commit(action)

        placed_actions: list[ScheduledAction] = list(frozen_actions)
        actions: list[ScheduledAction] = list(frozen_actions)
        unscheduled: list[UnscheduledEntry] = []
        action_number = first_action_number

        for request in ordered_requests:
            previous_window_id = previous_window_by_request.get(request.id)
            candidates = _ordered_candidates(
                windows_by_request.get(request.id, []), previous_window_id
            )
            last_violation: Optional[Violation] = None
            placed_action: Optional[ScheduledAction] = None

            for window in candidates:
                candidate_start = max(window.start, mission_state.simulated_time)
                candidate_end = candidate_start + timedelta(seconds=request.duration_s)
                battery_wh, storage_used_mb = projection.available_at(candidate_start)

                violation = (
                    check_window_containment(request.id, window, candidate_start, candidate_end)
                    or check_deadline(request.id, request.deadline, candidate_end)
                    or check_satellite_availability(request.id, mission_state.available)
                    or check_projected_battery(request.id, request.energy_cost_wh, battery_wh)
                    or check_projected_storage(
                        request.id,
                        request.storage_cost_mb,
                        storage_used_mb,
                        scenario.satellite.storage_capacity_mb,
                    )
                    or check_overlap(request.id, candidate_start, candidate_end, placed_actions)
                )

                if violation is None:
                    placed_action = ScheduledAction(
                        id=format_id(ACTION_ID_PREFIX, action_number),
                        request_id=request.id,
                        satellite_id=scenario.satellite.id,
                        window_id=window.id,
                        start=candidate_start,
                        end=candidate_end,
                        energy_cost_wh=request.energy_cost_wh,
                        storage_cost_mb=request.storage_cost_mb,
                    )
                    break
                last_violation = violation

            if placed_action is not None:
                actions.append(placed_action)
                placed_actions.append(placed_action)
                projection.commit(placed_action)
                action_number += 1
            else:
                unscheduled.append(
                    UnscheduledEntry(
                        request_id=request.id,
                        reason_code=_unscheduled_reason(last_violation, previous_window_id),
                    )
                )

        priority_by_request = {request.id: request.priority for request in all_requests}
        scheduled_request_ids = {action.request_id for action in actions}
        mission_utility = sum(
            priority_by_request[request_id]
            for request_id in scheduled_request_ids
            if request_id in priority_by_request
        )
        planning_time_ms = (time.perf_counter() - start_perf) * 1000

        return MissionPlan(
            id=plan_id,
            scenario_id=scenario.id,
            version=previous_plan.version + 1 if previous_plan else 1,
            parent_plan_id=previous_plan.id if previous_plan else None,
            created_at=datetime.now(timezone.utc),
            actions=tuple(actions),
            unscheduled=tuple(unscheduled),
            mission_utility=mission_utility,
            violation_count=len(unscheduled),
            planning_time_ms=planning_time_ms,
        )


def _frozen_actions(
    previous_plan: Optional[MissionPlan], mission_state: MissionState
) -> tuple[ScheduledAction, ...]:
    if previous_plan is None:
        return ()
    return tuple(
        action
        for action in previous_plan.actions
        if action.start <= mission_state.simulated_time
    )


def _ordered_candidates(
    candidates: Iterable[ObservationWindow], previous_window_id: Optional[str]
) -> list[ObservationWindow]:
    """The stability rule: the previous window first while it is still valid."""

    return sorted(
        candidates,
        key=lambda window: (
            0 if window.id == previous_window_id and window.valid else 1,
            window.start,
            window.id,
        ),
    )


def _unscheduled_reason(
    last_violation: Optional[Violation], previous_window_id: Optional[str]
) -> ReasonCode:
    reason_code = (
        last_violation.reason_code
        if last_violation is not None
        else ReasonCode.WINDOW_INVALIDATED
    )
    if previous_window_id is not None and reason_code is ReasonCode.WINDOW_INVALIDATED:
        # The request held a placement and every window it could move to
        # failed on the window itself, which is the no alternative case.
        return ReasonCode.NO_ALTERNATIVE_WINDOW
    return reason_code
