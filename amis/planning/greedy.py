"""GreedyPlanner: the MVP's only planner.

Walking-skeleton scope: place each request into the earliest window
that passes window containment. Priority ordering, the stability
rule, and the remaining five constraint checks widen this later
without changing the Planner protocol.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from amis.constraints import check_window_containment
from amis.domain import (
    MissionPlan,
    MissionState,
    ObservationRequest,
    ObservationWindow,
    ReasonCode,
    Scenario,
    ScheduledAction,
    UnscheduledEntry,
    Violation,
)


class GreedyPlanner:
    def plan(
        self,
        scenario: Scenario,
        mission_state: MissionState,
        requests: Iterable[ObservationRequest],
        windows: Iterable[ObservationWindow],
    ) -> MissionPlan:
        start_perf = time.perf_counter()
        request_list = list(requests)

        windows_by_request: dict[str, list[ObservationWindow]] = {}
        for window in windows:
            windows_by_request.setdefault(window.request_id, []).append(window)

        actions: list[ScheduledAction] = []
        unscheduled: list[UnscheduledEntry] = []
        action_seq = 1

        for request in request_list:
            candidates = sorted(
                windows_by_request.get(request.id, []), key=lambda w: w.start
            )
            last_violation: Optional[Violation] = None
            placed_action: Optional[ScheduledAction] = None

            for window in candidates:
                candidate_start = window.start
                candidate_end = candidate_start + timedelta(seconds=request.duration_s)
                violation = check_window_containment(
                    request.id, window, candidate_start, candidate_end
                )
                if violation is None:
                    placed_action = ScheduledAction(
                        id=f"ACT-{action_seq:03d}",
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
                action_seq += 1
            else:
                reason_code = (
                    last_violation.reason_code
                    if last_violation is not None
                    else ReasonCode.WINDOW_INVALIDATED
                )
                unscheduled.append(
                    UnscheduledEntry(request_id=request.id, reason_code=reason_code)
                )

        scheduled_request_ids = {action.request_id for action in actions}
        mission_utility = sum(
            request.priority
            for request in request_list
            if request.id in scheduled_request_ids
        )
        planning_time_ms = (time.perf_counter() - start_perf) * 1000

        return MissionPlan(
            id="PLAN-001",
            scenario_id=scenario.id,
            version=1,
            parent_plan_id=None,
            created_at=datetime.now(timezone.utc),
            actions=tuple(actions),
            unscheduled=tuple(unscheduled),
            mission_utility=mission_utility,
            violation_count=len(unscheduled),
            planning_time_ms=planning_time_ms,
        )
