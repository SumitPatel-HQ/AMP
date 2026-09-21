"""Planner protocol.

A planner never reads UI state, performs HTTP requests, queries live
services, writes React facing structures, or mutates a previous plan.

The scenario, the mission state, the requests, and the windows describe
the planning problem. The remaining arguments describe which plan record
is being written: the previous version to rebuild from, and the ids the
repository recovered for the new plan and its actions. A planner that
receives no previous plan produces version 1.
"""

from __future__ import annotations

from typing import Iterable, Optional, Protocol

from amis.domain import MissionPlan, MissionState, ObservationRequest, ObservationWindow, Scenario
from amis.ids import FIRST_PLAN_ID


class Planner(Protocol):
    def plan(
        self,
        scenario: Scenario,
        mission_state: MissionState,
        requests: Iterable[ObservationRequest],
        windows: Iterable[ObservationWindow],
        previous_plan: Optional[MissionPlan] = None,
        plan_id: str = FIRST_PLAN_ID,
        first_action_number: int = 1,
    ) -> MissionPlan: ...
