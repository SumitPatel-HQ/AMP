"""MissionSession: the single in-process test seam.

Integration tests drive this facade rather than HTTP. See
docs/adr/0001-mission-session-as-the-single-test-seam.md. Every
method returns domain objects, never a framework-specific type.
"""

from __future__ import annotations

import json
import math
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any, Union

from amis.domain import (
    ActionStatus,
    MetricsResult,
    MissionPlan,
    MissionState,
    ObservationRequest,
    ObservationWindow,
    RequestStatus,
    Scenario,
)
from amis.errors import SimulationStateError
from amis.metrics import compute_metrics
from amis.planning import GreedyPlanner
from amis.windows import SyntheticWindowProvider


class MissionSession:
    def __init__(self) -> None:
        self._scenario: Scenario | None = None
        self._windows: list[ObservationWindow] = []
        self._plan: MissionPlan | None = None
        self._state: MissionState | None = None
        self._request_pool: tuple[ObservationRequest, ...] = ()
        self._events: list[Any] = []
        self._traces: list[Any] = []
        self._impacts: list[Any] = []
        self._window_provider = SyntheticWindowProvider()
        self._planner = GreedyPlanner()

    def load_scenario(self, source: Union[Scenario, dict[str, Any], str, Path]) -> Scenario:
        if isinstance(source, Scenario):
            scenario = source
        elif isinstance(source, (str, Path)):
            scenario = Scenario.from_dict(json.loads(Path(source).read_text()))
        else:
            scenario = Scenario.from_dict(source)

        self._scenario = scenario
        self._reset_derived_state()
        return scenario

    def generate_windows(self) -> list[ObservationWindow]:
        scenario = self._require_scenario()
        self._windows = self._window_provider.generate(scenario, scenario.requests)
        return list(self._windows)

    def plan(self) -> MissionPlan:
        scenario = self._require_scenario()
        mission_state = self.get_state()
        self._plan = self._planner.plan(
            scenario, mission_state, self._request_pool, self._windows
        )
        self._update_request_statuses_from_plan()
        return self._plan

    def get_state(self) -> MissionState:
        self._require_scenario()
        if self._state is None:
            raise SimulationStateError("simulation state is not initialized")
        return self._state

    def get_plan(self) -> MissionPlan:
        if self._plan is None:
            raise SimulationStateError("no mission plan exists")
        return self._plan

    def get_request_pool(self) -> tuple[ObservationRequest, ...]:
        self._require_scenario()
        return self._request_pool

    def get_metrics(self) -> MetricsResult:
        scenario = self._require_scenario()
        plan = self.get_plan()
        state = self.get_state()
        return compute_metrics(scenario, state, self._request_pool, plan)

    def step(self, seconds: float) -> MissionState:
        scenario = self._require_scenario()
        plan = self.get_plan()
        state = self.get_state()

        if state.mission_complete:
            raise SimulationStateError(
                "mission is complete; reset the simulation before stepping again"
            )
        if not math.isfinite(seconds) or seconds <= 0:
            raise SimulationStateError(
                "step seconds must be a positive finite number",
                details={"seconds": seconds},
            )

        remaining_seconds = (scenario.end_time - state.simulated_time).total_seconds()
        elapsed_seconds = min(seconds, remaining_seconds)
        target_time = state.simulated_time + timedelta(seconds=elapsed_seconds)
        action_statuses: dict[str, ActionStatus] = {}
        completed_request_ids = list(state.completed_request_ids)
        completed_request_id_set = set(completed_request_ids)
        battery_wh = state.battery_wh
        storage_usage_mb = state.storage_usage_mb

        for action in sorted(plan.actions, key=lambda item: (item.start, item.id)):
            status = action.status
            if status is ActionStatus.PLANNED and action.start <= target_time:
                status = ActionStatus.STARTED
                battery_wh = max(0.0, battery_wh - action.energy_cost_wh)
                storage_usage_mb = max(0.0, storage_usage_mb + action.storage_cost_mb)

            if status is ActionStatus.STARTED and action.end <= target_time:
                status = ActionStatus.COMPLETED
                if action.request_id not in completed_request_id_set:
                    completed_request_ids.append(action.request_id)
                    completed_request_id_set.add(action.request_id)

            action_statuses[action.id] = status

        self._plan = replace(
            plan,
            actions=tuple(
                replace(action, status=action_statuses[action.id])
                for action in plan.actions
            ),
        )
        self._state = MissionState(
            scenario_id=state.scenario_id,
            simulated_time=target_time,
            satellite_id=state.satellite_id,
            battery_wh=battery_wh,
            storage_usage_mb=storage_usage_mb,
            available=state.available,
            active_event_ids=state.active_event_ids,
            completed_request_ids=tuple(completed_request_ids),
            mission_complete=target_time == scenario.end_time,
        )
        self._update_request_statuses_after_step()
        return self._state

    def reset(self) -> MissionState:
        self._require_scenario()
        self._reset_derived_state()
        return self.get_state()

    def _reset_derived_state(self) -> None:
        scenario = self._require_scenario()
        self._windows = []
        self._plan = None
        self._state = MissionState.initial(scenario)
        self._request_pool = scenario.requests
        self._events = []
        self._traces = []
        self._impacts = []

    def _update_request_statuses_from_plan(self) -> None:
        plan = self.get_plan()
        scheduled_request_ids = {action.request_id for action in plan.actions}
        unscheduled_request_ids = {entry.request_id for entry in plan.unscheduled}

        updated_requests = []
        for request in self._request_pool:
            if request.status in (RequestStatus.COMPLETED, RequestStatus.EXPIRED):
                updated_requests.append(request)
            elif request.id in scheduled_request_ids:
                updated_requests.append(replace(request, status=RequestStatus.SCHEDULED))
            elif request.id in unscheduled_request_ids:
                updated_requests.append(replace(request, status=RequestStatus.DROPPED))
            else:
                updated_requests.append(request)
        self._request_pool = tuple(updated_requests)

    def _update_request_statuses_after_step(self) -> None:
        state = self.get_state()
        completed_request_ids = set(state.completed_request_ids)

        updated_requests = []
        for request in self._request_pool:
            if request.id in completed_request_ids:
                status = RequestStatus.COMPLETED
            elif request.status is RequestStatus.EXPIRED:
                status = RequestStatus.EXPIRED
            elif state.simulated_time > request.deadline:
                status = RequestStatus.EXPIRED
            else:
                status = request.status
            updated_requests.append(replace(request, status=status))
        self._request_pool = tuple(updated_requests)

    def _require_scenario(self) -> Scenario:
        if self._scenario is None:
            raise ValueError("no scenario loaded")
        return self._scenario
