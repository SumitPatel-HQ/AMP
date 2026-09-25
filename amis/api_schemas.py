"""Validated HTTP schemas for the AMIS REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, Self, Union

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator

from amis.domain import ActionStatus, EventType, PlanChangeType, ReasonCode, RequestStatus
from amis.errors import ErrorCode


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SatelliteSchema(ApiModel):
    id: str = Field(min_length=1)
    battery_capacity_wh: float = Field(gt=0, allow_inf_nan=False)
    battery_charge_wh: float = Field(ge=0, allow_inf_nan=False)
    storage_capacity_mb: float = Field(gt=0, allow_inf_nan=False)
    storage_usage_mb: float = Field(ge=0, allow_inf_nan=False)
    available: bool = True

    @model_validator(mode="after")
    def validate_capacities(self) -> Self:
        if self.battery_charge_wh > self.battery_capacity_wh:
            raise ValueError("battery charge cannot exceed battery capacity")
        if self.storage_usage_mb > self.storage_capacity_mb:
            raise ValueError("storage usage cannot exceed storage capacity")
        return self


class ObservationRequestSchema(ApiModel):
    id: str = Field(min_length=1)
    target_lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    target_lon: float = Field(ge=-180, le=180, allow_inf_nan=False)
    priority: int = Field(ge=1, le=5)
    duration_s: float = Field(gt=0, allow_inf_nan=False)
    deadline: datetime
    energy_cost_wh: float = Field(ge=0, allow_inf_nan=False)
    storage_cost_mb: float = Field(ge=0, allow_inf_nan=False)
    status: RequestStatus = RequestStatus.PENDING


class ScenarioSchema(ApiModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    start_time: datetime
    end_time: datetime
    satellite: SatelliteSchema
    requests: list[ObservationRequestSchema]

    @model_validator(mode="after")
    def validate_scenario(self) -> Self:
        if self.start_time.tzinfo is None or self.end_time.tzinfo is None:
            raise ValueError("scenario times must include a timezone")
        if self.end_time <= self.start_time:
            raise ValueError("scenario end_time must be after start_time")
        request_ids = [request.id for request in self.requests]
        if len(request_ids) != len(set(request_ids)):
            raise ValueError("observation request ids must be unique")
        if any(request.deadline.tzinfo is None for request in self.requests):
            raise ValueError("observation request deadlines must include a timezone")
        return self


class ObservationWindowSchema(ApiModel):
    id: str
    request_id: str
    satellite_id: str
    start: datetime
    end: datetime
    valid: bool
    invalid_reason: str | None


class ScheduledActionSchema(ApiModel):
    id: str
    request_id: str
    satellite_id: str
    window_id: str
    start: datetime
    end: datetime
    energy_cost_wh: float
    storage_cost_mb: float
    status: ActionStatus


class UnscheduledEntrySchema(ApiModel):
    request_id: str
    reason_code: ReasonCode


class MissionPlanSchema(ApiModel):
    id: str
    scenario_id: str
    version: int
    parent_plan_id: str | None
    created_at: datetime
    actions: list[ScheduledActionSchema]
    unscheduled: list[UnscheduledEntrySchema]
    mission_utility: float
    violation_count: int
    planning_time_ms: float


class MissionStateSchema(ApiModel):
    scenario_id: str
    simulated_time: datetime
    satellite_id: str
    battery_wh: float
    storage_usage_mb: float
    available: bool
    active_event_ids: list[str]
    completed_request_ids: list[str]
    mission_complete: bool


class CloudBlockPayloadSchema(ApiModel):
    request_id: str = Field(min_length=1)
    window_id: str = Field(min_length=1)


class BatteryDropPayloadSchema(ApiModel):
    satellite_id: str = Field(min_length=1)
    new_battery_wh: float = Field(ge=0, allow_inf_nan=False)


class EmergencyTaskPayloadSchema(ApiModel):
    """The emergency request and the explicit windows it arrives with."""

    request: ObservationRequestSchema
    windows: list[ObservationWindowSchema] = Field(min_length=1)


class CloudBlockEventRequest(ApiModel):
    event_type: Literal[EventType.CLOUD_BLOCK]
    payload: CloudBlockPayloadSchema


class BatteryDropEventRequest(ApiModel):
    event_type: Literal[EventType.BATTERY_DROP]
    payload: BatteryDropPayloadSchema


class EmergencyTaskEventRequest(ApiModel):
    event_type: Literal[EventType.EMERGENCY_TASK]
    payload: EmergencyTaskPayloadSchema


class MissionEventRequest(
    RootModel[
        Annotated[
            Union[
                CloudBlockEventRequest,
                BatteryDropEventRequest,
                EmergencyTaskEventRequest,
            ],
            Field(discriminator="event_type"),
        ]
    ]
):
    """Every event the route accepts, chosen by ``event_type``."""


class MissionEventFields(ApiModel):
    id: str
    scenario_id: str
    event_time: datetime


class CloudBlockMissionEventSchema(MissionEventFields):
    event_type: Literal[EventType.CLOUD_BLOCK]
    payload: CloudBlockPayloadSchema


class BatteryDropMissionEventSchema(MissionEventFields):
    event_type: Literal[EventType.BATTERY_DROP]
    payload: BatteryDropPayloadSchema


class EmergencyTaskMissionEventSchema(MissionEventFields):
    event_type: Literal[EventType.EMERGENCY_TASK]
    payload: EmergencyTaskPayloadSchema


class MissionEventSchema(
    RootModel[
        Annotated[
            Union[
                CloudBlockMissionEventSchema,
                BatteryDropMissionEventSchema,
                EmergencyTaskMissionEventSchema,
            ],
            Field(discriminator="event_type"),
        ]
    ]
):
    """Every event the log can hold, chosen by ``event_type``."""


class ImpactSchema(ApiModel):
    id: str
    event_id: str
    evaluated_plan_id: str
    frozen_action_ids: list[str]
    valid_unfrozen_action_ids: list[str]
    invalid_unfrozen_action_ids: list[str]
    reason_codes: dict[str, list[ReasonCode]]


class MetricsSchema(ApiModel):
    plan_id: str
    mission_utility: float
    completion_rate: float
    violation_count: int
    planning_time_ms: float
    battery_utilisation: float
    storage_utilisation: float
    request_pool_size: int
    request_pool_ids: list[str]
    measured_at: datetime
    plan_churn: float | None
    explanation_coverage: float | None


class PlanDiffEntrySchema(ApiModel):
    request_id: str
    change_type: PlanChangeType
    reason_code: ReasonCode
    old_start: datetime | None
    new_start: datetime | None


class PlanDiffSchema(ApiModel):
    from_plan_id: str
    to_plan_id: str
    entries: list[PlanDiffEntrySchema]
    metrics_before: MetricsSchema | None = None
    metrics_after: MetricsSchema | None = None
    request_pool_mismatch: bool = False


class DecisionTraceSchema(ApiModel):
    id: str
    plan_id: str
    event_id: str | None
    request_id: str | None
    reason_code: ReasonCode
    previous_action: ScheduledActionSchema | None
    new_action: ScheduledActionSchema | None
    constraint_name: str | None
    message: str
    metadata: dict[str, Any]


class StepRequest(ApiModel):
    seconds: float = Field(gt=0, allow_inf_nan=False)


class ReplanRequest(ApiModel):
    expected_parent_plan_id: str = Field(min_length=1)


class ErrorBody(ApiModel):
    code: ErrorCode
    message: str
    details: dict[str, Any]


class ErrorEnvelope(ApiModel):
    error: ErrorBody
