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

from amis.diff import compare_plans
from amis.domain import (
    ActionStatus,
    BatteryDropPayload,
    CloudBlockPayload,
    DecisionTrace,
    EmergencyRequestPayload,
    EventPayload,
    EventType,
    Impact,
    MetricsResult,
    MissionEvent,
    MissionPlan,
    MissionState,
    ObservationRequest,
    ObservationWindow,
    PlanDiff,
    ReasonCode,
    RequestStatus,
    Scenario,
)
from amis.errors import (
    InvalidEventError,
    PlanVersionConflictError,
    SimulationStateError,
)
from amis.ids import (
    ACTION_ID_PREFIX,
    EVENT_ID_PREFIX,
    IMPACT_ID_PREFIX,
    PLAN_ID_PREFIX,
    TRACE_ID_PREFIX,
    next_id,
    next_number,
)
from amis.impact import analyze_impact
from amis.metrics import compute_metrics
from amis.planning import GreedyPlanner, Planner
from amis.trace import build_traces
from amis.windows import SyntheticWindowProvider, WindowProvider


class MissionSession:
    def __init__(
        self,
        window_provider: WindowProvider | None = None,
        planner: Planner | None = None,
        plan_id_prefix: str = PLAN_ID_PREFIX,
    ) -> None:
        self._scenario: Scenario | None = None
        self._windows: list[ObservationWindow] = []
        self._plans: list[MissionPlan] = []
        self._state: MissionState | None = None
        self._request_pool: tuple[ObservationRequest, ...] = ()
        self._request_pool_ids_by_plan_id: dict[str, frozenset[str]] = {}
        self._events: list[MissionEvent] = []
        self._traces: list[DecisionTrace] = []
        self._impacts: list[Impact] = []
        self._window_provider = window_provider or SyntheticWindowProvider()
        self._planner = planner or GreedyPlanner()
        self._plan_id_prefix = plan_id_prefix

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

    def get_windows(self) -> tuple[ObservationWindow, ...]:
        self._require_scenario()
        return tuple(self._windows)

    def plan(self) -> MissionPlan:
        scenario = self._require_scenario()
        if not self._windows:
            raise SimulationStateError(
                "observation windows must be generated before planning"
            )
        mission_state = self.get_state()
        plan = self._planner.plan(
            scenario,
            mission_state,
            self._request_pool,
            self._windows,
            plan_id=self._next_plan_id(),
            first_action_number=self._next_action_number(),
        )
        self._plans.append(plan)
        self._update_request_statuses_from_plan()
        self._record_request_pool_for(plan)
        return plan

    def replan(self, expected_parent_plan_id: str | None = None) -> MissionPlan:
        """Freeze what started, rebuild the rest, write the next version.

        The caller names the plan version it believes is current. A
        mismatch is rejected rather than written, because a session is
        rebuilt per request and two concurrent replans would otherwise
        both read the same parent and both write the next version.
        """

        scenario = self._require_scenario()
        previous_plan = self.get_plan()
        mission_state = self.get_state()

        if (
            expected_parent_plan_id is not None
            and expected_parent_plan_id != previous_plan.id
        ):
            raise PlanVersionConflictError(
                "replan named a plan version that is no longer current",
                details={
                    "expected_parent_plan_id": expected_parent_plan_id,
                    "current_plan_id": previous_plan.id,
                },
            )

        plan = self._planner.plan(
            scenario,
            mission_state,
            self._request_pool,
            self._windows,
            previous_plan=previous_plan,
            plan_id=self._next_plan_id(),
            first_action_number=self._next_action_number(),
        )

        diff = self._compare(previous_plan, plan)
        traces = build_traces(
            previous_plan,
            plan,
            diff,
            event_id=self._triggering_event_id(previous_plan),
            first_trace_number=next_number(
                TRACE_ID_PREFIX, [trace.id for trace in self._traces]
            ),
        )

        self._plans.append(plan)
        self._traces.extend(traces)
        self._update_request_statuses_from_plan()
        self._record_request_pool_for(plan)
        return plan

    def compare_versions(self, from_version: int, to_version: int) -> PlanDiff:
        """Compare any two stored versions, adjacent or not.

        The comparison is recomputed from the stored plans rather than
        cached, so that running the clock forward cannot leave it
        disagreeing with the versions it names.
        """

        previous_plan = self.get_plan_by_version(from_version)
        plan = self.get_plan_by_version(to_version)
        comparison = self._compare(previous_plan, plan)
        metrics_before = self.get_metrics(previous_plan.id)
        metrics_after = self.get_metrics(plan.id)
        return replace(
            comparison,
            metrics_before=metrics_before,
            metrics_after=metrics_after,
            request_pool_mismatch=(
                metrics_before.request_pool_ids != metrics_after.request_pool_ids
            ),
        )

    def get_state(self) -> MissionState:
        self._require_scenario()
        if self._state is None:
            raise SimulationStateError("simulation state is not initialized")
        return self._state

    def get_scenario(self) -> Scenario:
        return self._require_scenario()

    def get_plan(self) -> MissionPlan:
        if not self._plans:
            raise SimulationStateError("no mission plan exists")
        return self._plans[-1]

    def get_plans(self) -> tuple[MissionPlan, ...]:
        self._require_scenario()
        return tuple(self._plans)

    def get_plan_by_version(self, version: int) -> MissionPlan:
        plan = next((plan for plan in self._plans if plan.version == version), None)
        if plan is None:
            raise SimulationStateError(
                "no mission plan exists for that version",
                details={"version": version},
            )
        return plan

    def get_plan_by_id(self, plan_id: str) -> MissionPlan:
        return self._plan_by_id(plan_id)

    def get_traces(self, plan_id: str | None = None) -> tuple[DecisionTrace, ...]:
        self._require_scenario()
        if plan_id is None:
            return tuple(self._traces)
        return tuple(trace for trace in self._traces if trace.plan_id == plan_id)

    def get_request_pool(self) -> tuple[ObservationRequest, ...]:
        self._require_scenario()
        return self._request_pool

    def get_metrics(self, plan_id: str | None = None) -> MetricsResult:
        scenario = self._require_scenario()
        plan = self.get_plan() if plan_id is None else self._plan_by_id(plan_id)
        state = self.get_state()
        parent_plan = (
            self._plan_by_id(plan.parent_plan_id) if plan.parent_plan_id else None
        )
        return compute_metrics(
            scenario,
            state,
            self._request_pool_for_plan(plan),
            plan,
            previous_plan=parent_plan,
            diff=self._compare(parent_plan, plan) if parent_plan else None,
            traces=self.get_traces(plan.id),
        )

    def inject_event(
        self,
        event_type: EventType | str,
        payload: EventPayload | dict[str, Any],
    ) -> MissionEvent:
        scenario = self._require_scenario()
        plan = self.get_plan()
        state = self.get_state()

        try:
            parsed_event_type = EventType(event_type)
        except ValueError as error:
            raise InvalidEventError(
                "unknown mission event type",
                details={"event_type": str(event_type)},
            ) from error

        if parsed_event_type is EventType.CLOUD_BLOCK:
            cloud_payload = self._parse_cloud_block_payload(payload)
            self._validate_cloud_block(cloud_payload)
            event_payload: EventPayload = cloud_payload
        elif parsed_event_type is EventType.BATTERY_DROP:
            event_payload = self._parse_battery_drop_payload(payload)
            self._validate_battery_drop(event_payload)
        elif parsed_event_type is EventType.EMERGENCY_TASK:
            event_payload = self._parse_emergency_request_payload(payload)
            self._validate_emergency_request(event_payload)
        else:
            raise InvalidEventError(
                "mission event type is not implemented",
                details={"event_type": parsed_event_type.value},
            )

        event = MissionEvent(
            id=next_id(EVENT_ID_PREFIX, [record.id for record in self._events]),
            scenario_id=scenario.id,
            event_type=parsed_event_type,
            event_time=state.simulated_time,
            payload=event_payload,
        )

        if parsed_event_type is EventType.CLOUD_BLOCK:
            assert isinstance(event_payload, CloudBlockPayload)
            self._windows = [
                replace(
                    window,
                    valid=False,
                    invalid_reason=ReasonCode.WINDOW_INVALIDATED.value,
                )
                if window.id == event_payload.window_id
                else window
                for window in self._windows
            ]
            self._state = replace(
                state,
                active_event_ids=state.active_event_ids + (event.id,),
            )
        elif parsed_event_type is EventType.BATTERY_DROP:
            assert isinstance(event_payload, BatteryDropPayload)
            # No clamping: the state takes the injected value exactly, even
            # if a frozen in flight action can no longer afford itself.
            # See ADR-0003.
            self._state = replace(
                state,
                battery_wh=event_payload.new_battery_wh,
                active_event_ids=state.active_event_ids + (event.id,),
            )
        else:
            assert isinstance(event_payload, EmergencyRequestPayload)
            self._request_pool = self._request_pool + (event_payload.request,)
            self._windows.extend(event_payload.windows)
            self._state = replace(
                state,
                active_event_ids=state.active_event_ids + (event.id,),
            )

        impact = analyze_impact(
            impact_id=next_id(IMPACT_ID_PREFIX, [record.id for record in self._impacts]),
            event_id=event.id,
            scenario=scenario,
            mission_state=self._state,
            requests=self._request_pool,
            windows=self._windows,
            plan=plan,
        )
        self._events.append(event)
        self._impacts.append(impact)
        return event

    def inject_cloud_block(self, request_id: str, window_id: str) -> MissionEvent:
        return self.inject_event(
            EventType.CLOUD_BLOCK,
            CloudBlockPayload(request_id=request_id, window_id=window_id),
        )

    def inject_battery_drop(self, satellite_id: str, new_battery_wh: float) -> MissionEvent:
        return self.inject_event(
            EventType.BATTERY_DROP,
            BatteryDropPayload(satellite_id=satellite_id, new_battery_wh=new_battery_wh),
        )

    def inject_emergency_request(
        self,
        request: ObservationRequest,
        windows: tuple[ObservationWindow, ...],
    ) -> MissionEvent:
        """Inject the request carried by the ``EMERGENCY_TASK`` wire event."""

        return self.inject_event(
            EventType.EMERGENCY_TASK,
            EmergencyRequestPayload(request=request, windows=windows),
        )

    def get_events(self) -> tuple[MissionEvent, ...]:
        self._require_scenario()
        return tuple(self._events)

    def get_last_impact(self) -> Impact:
        if not self._impacts:
            raise SimulationStateError("no impact exists")
        return self._impacts[-1]

    def get_impacts(self) -> tuple[Impact, ...]:
        self._require_scenario()
        return tuple(self._impacts)

    def restore(
        self,
        scenario: Scenario,
        *,
        windows: tuple[ObservationWindow, ...] = (),
        plans: tuple[MissionPlan, ...] = (),
        state: MissionState | None = None,
        events: tuple[MissionEvent, ...] = (),
        impacts: tuple[Impact, ...] = (),
        traces: tuple[DecisionTrace, ...] = (),
    ) -> None:
        """Rebuild a request-scoped session from repository records."""

        self._scenario = scenario
        self._windows = list(windows)
        self._plans = list(plans)
        self._state = state or MissionState.initial(scenario)
        self._events = list(events)
        self._impacts = list(impacts)
        self._traces = list(traces)

        introduced_by_event_id = {
            event.id: request
            for event in events
            if (
                request := getattr(event.payload, "request", None)
            ) is not None
            and isinstance(request, ObservationRequest)
        }
        introduced_requests = tuple(introduced_by_event_id.values())
        self._request_pool = scenario.requests + introduced_requests

        base_request_ids = {request.id for request in scenario.requests}
        plan_by_id = {plan.id: plan for plan in plans}
        introduced_at_version = [
            (evaluated_plan.version, introduced_request.id)
            for impact in impacts
            if (evaluated_plan := plan_by_id.get(impact.evaluated_plan_id))
            is not None
            and (
                introduced_request := introduced_by_event_id.get(impact.event_id)
            )
            is not None
        ]
        self._request_pool_ids_by_plan_id = {
            plan.id: frozenset(
                base_request_ids
                | {
                    request_id
                    for version, request_id in introduced_at_version
                    if version < plan.version
                }
            )
            for plan in plans
        }

        if self._plans:
            self._update_request_statuses_from_plan()
            self._update_request_statuses_after_step()

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

        self._plans[-1] = replace(
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
        self._plans = []
        self._state = MissionState.initial(scenario)
        self._request_pool = scenario.requests
        self._request_pool_ids_by_plan_id = {}
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

    def _compare(self, previous_plan: MissionPlan, plan: MissionPlan) -> PlanDiff:
        return compare_plans(
            previous_plan,
            plan,
            reasons_by_request=self._impact_reasons_by_request(previous_plan),
        )

    def _record_request_pool_for(self, plan: MissionPlan) -> None:
        self._request_pool_ids_by_plan_id[plan.id] = frozenset(
            request.id for request in self._request_pool
        )

    def _request_pool_for_plan(
        self, plan: MissionPlan
    ) -> tuple[ObservationRequest, ...]:
        request_ids = self._request_pool_ids_by_plan_id.get(plan.id)
        if request_ids is None:
            return self._request_pool
        return tuple(
            request for request in self._request_pool if request.id in request_ids
        )

    def _next_plan_id(self) -> str:
        return next_id(self._plan_id_prefix, [plan.id for plan in self._plans])

    def _next_action_number(self) -> int:
        return next_number(
            ACTION_ID_PREFIX,
            [action.id for plan in self._plans for action in plan.actions],
        )

    def _plan_by_id(self, plan_id: str) -> MissionPlan:
        plan = next((plan for plan in self._plans if plan.id == plan_id), None)
        if plan is None:
            raise SimulationStateError(
                "no mission plan exists with that id", details={"plan_id": plan_id}
            )
        return plan

    def _latest_impact_for(self, plan: MissionPlan) -> Impact | None:
        """The stored impact explains only the plan it was evaluated against."""

        return next(
            (
                impact
                for impact in reversed(self._impacts)
                if impact.evaluated_plan_id == plan.id
            ),
            None,
        )

    def _triggering_event_id(self, plan: MissionPlan) -> str | None:
        impact = self._latest_impact_for(plan)
        return impact.event_id if impact else None

    def _impact_reasons_by_request(self, plan: MissionPlan) -> dict[str, ReasonCode]:
        impact = self._latest_impact_for(plan)
        if impact is None:
            return {}
        request_by_action_id = {action.id: action.request_id for action in plan.actions}
        return {
            request_by_action_id[action_id]: reasons[0]
            for action_id, reasons in impact.reason_codes.items()
            if action_id in request_by_action_id and reasons
        }

    def _require_scenario(self) -> Scenario:
        if self._scenario is None:
            raise ValueError("no scenario loaded")
        return self._scenario

    @staticmethod
    def _parse_cloud_block_payload(
        payload: EventPayload | dict[str, Any],
    ) -> CloudBlockPayload:
        if isinstance(payload, CloudBlockPayload):
            return payload
        if not isinstance(payload, dict):
            raise InvalidEventError("cloud block payload has the wrong shape")
        try:
            return CloudBlockPayload.from_dict(payload)
        except (KeyError, TypeError) as error:
            raise InvalidEventError(
                "cloud block payload requires request_id and window_id"
            ) from error

    def _validate_cloud_block(self, payload: CloudBlockPayload) -> None:
        request_ids = {request.id for request in self._request_pool}
        if payload.request_id not in request_ids:
            raise InvalidEventError(
                "cloud block request does not exist",
                details={"request_id": payload.request_id},
            )

        window = next(
            (window for window in self._windows if window.id == payload.window_id),
            None,
        )
        if window is None:
            raise InvalidEventError(
                "cloud block window does not exist",
                details={"window_id": payload.window_id},
            )
        if window.request_id != payload.request_id:
            raise InvalidEventError(
                "cloud block window does not belong to the request",
                details={
                    "request_id": payload.request_id,
                    "window_id": payload.window_id,
                },
            )

    @staticmethod
    def _parse_battery_drop_payload(
        payload: EventPayload | dict[str, Any],
    ) -> BatteryDropPayload:
        if isinstance(payload, BatteryDropPayload):
            return payload
        if not isinstance(payload, dict):
            raise InvalidEventError("battery drop payload has the wrong shape")
        try:
            return BatteryDropPayload.from_dict(payload)
        except (KeyError, TypeError) as error:
            raise InvalidEventError(
                "battery drop payload requires satellite_id and new_battery_wh"
            ) from error

    def _validate_battery_drop(self, payload: BatteryDropPayload) -> None:
        scenario = self._require_scenario()
        state = self.get_state()
        if payload.satellite_id != state.satellite_id:
            raise InvalidEventError(
                "battery drop satellite does not match the mission satellite",
                details={"satellite_id": payload.satellite_id},
            )
        capacity_wh = scenario.satellite.battery_capacity_wh
        if (
            not math.isfinite(payload.new_battery_wh)
            or payload.new_battery_wh < 0
            or payload.new_battery_wh > capacity_wh
        ):
            raise InvalidEventError(
                "battery drop value must be between zero and battery capacity",
                details={
                    "new_battery_wh": payload.new_battery_wh,
                    "battery_capacity_wh": capacity_wh,
                },
            )

    @staticmethod
    def _parse_emergency_request_payload(
        payload: EventPayload | dict[str, Any],
    ) -> EmergencyRequestPayload:
        if isinstance(payload, EmergencyRequestPayload):
            return payload
        if not isinstance(payload, dict):
            raise InvalidEventError("emergency request payload has the wrong shape")
        try:
            return EmergencyRequestPayload.from_dict(payload)
        except (KeyError, TypeError, ValueError) as error:
            raise InvalidEventError(
                "emergency request payload requires a request and explicit windows"
            ) from error

    def _validate_emergency_request(self, payload: EmergencyRequestPayload) -> None:
        scenario = self._require_scenario()
        request = payload.request
        windows = payload.windows

        if request.id in {item.id for item in self._request_pool}:
            raise InvalidEventError(
                "emergency request id already exists",
                details={"request_id": request.id},
            )
        if not windows:
            raise InvalidEventError(
                "emergency request requires at least one explicit observation window",
                details={"request_id": request.id},
            )

        existing_window_ids = {window.id for window in self._windows}
        payload_window_ids: set[str] = set()
        for window in windows:
            if window.id in existing_window_ids or window.id in payload_window_ids:
                raise InvalidEventError(
                    "emergency request window id already exists",
                    details={"window_id": window.id},
                )
            if window.request_id != request.id:
                raise InvalidEventError(
                    "emergency request window does not belong to the request",
                    details={
                        "request_id": request.id,
                        "window_id": window.id,
                    },
                )
            if window.satellite_id != scenario.satellite.id:
                raise InvalidEventError(
                    "emergency request window satellite does not match the mission satellite",
                    details={
                        "satellite_id": window.satellite_id,
                        "window_id": window.id,
                    },
                )
            payload_window_ids.add(window.id)
