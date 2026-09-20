"""Planner protocol.

A planner never reads UI state, performs HTTP requests, queries live
services, writes React facing structures, or mutates a previous plan.
"""

from __future__ import annotations

from typing import Iterable, Protocol

from amis.domain import MissionPlan, MissionState, ObservationRequest, ObservationWindow, Scenario


class Planner(Protocol):
    def plan(
        self,
        scenario: Scenario,
        mission_state: MissionState,
        requests: Iterable[ObservationRequest],
        windows: Iterable[ObservationWindow],
    ) -> MissionPlan: ...
