"""Validated HTTP schemas for the AMIS REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, Self, Union

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator

from amis.domain import (
    ActionKind,
    ActionStatus,
    AlertLevel,
    EventType,
    PlanChangeType,
    ReasonCode,
    RequestStatus,
    emergency_evidence_error,
)
from amis.errors import ErrorCode


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OrbitalElementsSchema(ApiModel):
    norad_id: int = Field(gt=0)
    name: str = Field(min_length=1)
    international_designator: str = Field(min_length=1)
    epoch: datetime
    omm: dict[str, Any]
    source: str = Field(min_length=1)
    retrieved_at: datetime
    sha256: str = Field(min_length=64, max_length=64)
    tle_line1: str | None = None
    tle_line2: str | None = None

    @model_validator(mode="after")
    def validate_elements(self) -> Self:
        from amis.orbital.elements import from_omm, from_tle, omm_hash

        if self.epoch.tzinfo is None or self.retrieved_at.tzinfo is None:
            raise ValueError("element epoch and retrieval time require a timezone")
        if self.sha256 != omm_hash(self.omm):
            raise ValueError("element checksum does not match OMM")
        try:
            parsed = from_omm(self.omm, source=self.source, retrieved_at=self.retrieved_at)
        except (ValueError, KeyError, TypeError) as error:
            raise ValueError(f"OMM cannot be parsed: {error}") from error
        if parsed.norad_id != self.norad_id or parsed.name != self.name or parsed.international_designator != self.international_designator or abs((parsed.epoch - self.epoch).total_seconds()) > 0.001:
            raise ValueError("element identity or epoch does not match OMM")
        if (self.tle_line1 is None) != (self.tle_line2 is None):
            raise ValueError("both TLE lines are required together")
        if self.tle_line1 is not None and self.tle_line2 is not None:
            try:
                tle = from_tle(self.tle_line1, self.tle_line2, name=self.name, retrieved_at=self.retrieved_at)
            except (ValueError, KeyError, TypeError) as error:
                raise ValueError(f"TLE cannot be parsed: {error}") from error
            if tle.norad_id != self.norad_id or abs((tle.epoch - self.epoch).total_seconds()) > 0.001 or tle.sha256 != self.sha256:
                raise ValueError("TLE does not match stored OMM")
        return self


class WindowPolicySchema(ApiModel):
    provider: Literal["synthetic", "canonical_demo", "orbital"]
    max_off_nadir_deg: float = Field(default=30, ge=0, le=60, allow_inf_nan=False)
    min_sun_elevation_deg: float | None = Field(default=10, ge=-10, le=60, allow_inf_nan=False)
    settling_time_s: float = Field(default=0, ge=0, allow_inf_nan=False)
    culmination_placement: bool = False
    ground_station_ids: list[str] = Field(default_factory=list)
    downlink_rate_mb_s: float = Field(default=0, ge=0, allow_inf_nan=False)
    slew_rate_deg_s: float = Field(default=0, ge=0, allow_inf_nan=False)
    recharge_rate_w: float = Field(default=0, ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_orbital_dynamics(self) -> Self:
        if (self.slew_rate_deg_s or self.recharge_rate_w) and self.provider != "orbital":
            raise ValueError("slew and recharge require the orbital window provider")
        return self

    @model_validator(mode="after")
    def validate_ground_stations(self) -> Self:
        if self.ground_station_ids:
            from amis.orbital.stations import stations_by_ids

            if self.provider != "orbital":
                raise ValueError("ground stations require the orbital window provider")
            if len(set(self.ground_station_ids)) != len(self.ground_station_ids):
                raise ValueError("ground station ids must be unique")
            stations_by_ids(self.ground_station_ids)
        return self


class GroundStationSchema(ApiModel):
    id: str
    name: str
    lat: float
    lon: float
    altitude_m: float
    min_elevation_deg: float


class ContactWindowSchema(ApiModel):
    id: str
    station_id: str
    satellite_id: str
    start: datetime
    end: datetime
    peak_elevation_deg: float
    peak_time: datetime
    valid: bool
    invalid_reason: str | None = None
    source: str | None = None


class SatelliteSchema(ApiModel):
    id: str = Field(min_length=1)
    battery_capacity_wh: float = Field(gt=0, allow_inf_nan=False)
    battery_charge_wh: float = Field(ge=0, allow_inf_nan=False)
    storage_capacity_mb: float = Field(gt=0, allow_inf_nan=False)
    storage_usage_mb: float = Field(ge=0, allow_inf_nan=False)
    available: bool = True
    orbit: OrbitalElementsSchema | None = None

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
    target_name: str | None = None
    # Wave 7 (ADR-0014): naming a satellite pins the request to it; absent
    # means the planner assigns whichever satellite can serve it.
    satellite_id: str | None = None

    @model_validator(mode="after")
    def validate_deadline_timezone(self) -> Self:
        # Checked here, not only when a request is embedded in
        # ScenarioSchema, so the emergency-event payload (which reuses
        # this schema directly, never nested in a scenario) cannot bypass
        # it: a naive deadline previously reached MissionState
        # unvalidated and made every later step()/replan() comparison
        # raise a 500 (GAP-07).
        if self.deadline.tzinfo is None:
            raise ValueError("observation request deadline must include a timezone")
        return self


class ScenarioSchema(ApiModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    start_time: datetime
    end_time: datetime
    # Wave 7 (ADR-0014): ``satellites`` is canonical; ``satellite`` stays as
    # legacy single-satellite input so old clients keep working.
    satellite: SatelliteSchema | None = None
    satellites: list[SatelliteSchema] | None = None
    requests: list[ObservationRequestSchema]
    window_policy: WindowPolicySchema | None = None

    @model_validator(mode="after")
    def validate_scenario(self) -> Self:
        if self.start_time.tzinfo is None or self.end_time.tzinfo is None:
            raise ValueError("scenario times must include a timezone")
        if self.end_time <= self.start_time:
            raise ValueError("scenario end_time must be after start_time")
        if self.satellite is not None and self.satellites is not None:
            # Single-satellite output carries both keys for backward
            # compat; accept when the singular matches the list's only entry.
            if len(self.satellites) != 1 or self.satellites[0] != self.satellite:
                raise ValueError("pass either satellite or satellites, not both")
            resolved = self.satellites
        elif self.satellites is not None:
            resolved = self.satellites
        elif self.satellite is not None:
            resolved = [self.satellite]
        else:
            raise ValueError("a scenario requires at least one satellite")
        satellite_ids = [satellite.id for satellite in resolved]
        if len(satellite_ids) != len(set(satellite_ids)):
            raise ValueError("satellite ids must be unique")
        request_ids = [request.id for request in self.requests]
        if len(request_ids) != len(set(request_ids)):
            raise ValueError("observation request ids must be unique")
        for request in self.requests:
            if request.satellite_id is not None and request.satellite_id not in satellite_ids:
                raise ValueError(f"request {request.id} names an unknown satellite")
        if self.window_policy is not None and self.window_policy.provider == "orbital":
            for satellite in resolved:
                if satellite.orbit is None:
                    raise ValueError("orbital missions require satellite.orbit")
        # Each request already validates its own deadline's timezone
        # (ObservationRequestSchema.validate_deadline_timezone).
        return self


class ObservationWindowSchema(ApiModel):
    id: str
    request_id: str
    satellite_id: str
    start: datetime
    end: datetime
    valid: bool
    invalid_reason: str | None
    peak_elevation_deg: float | None = None
    peak_time: datetime | None = None
    min_off_nadir_deg: float | None = None
    sun_elevation_deg: float | None = None
    source: str | None = None

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        # Checked here so both the scenario-create path and the
        # emergency-event path (whose explicit windows reuse this same
        # schema) reject a naive-timestamp or inverted window before it
        # ever reaches MissionState (GAP-07).
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("observation window start/end must include a timezone")
        if self.end <= self.start:
            raise ValueError("observation window end must be after start")
        return self


class ScheduledActionSchema(ApiModel):
    id: str
    request_id: str | None
    satellite_id: str
    window_id: str
    start: datetime
    end: datetime
    energy_cost_wh: float
    storage_cost_mb: float
    status: ActionStatus
    kind: ActionKind = ActionKind.IMAGING
    station_id: str | None = None


class UnscheduledEntrySchema(ApiModel):
    request_id: str
    reason_code: ReasonCode


class MissionPlanSchema(ApiModel):
    planner_name: str = "greedy"
    solver_details: dict[str, Any] | None = None
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


class SatelliteStateSchema(ApiModel):
    satellite_id: str
    battery_wh: float
    storage_usage_mb: float
    available: bool
    completed_request_ids: list[str] = Field(default_factory=list)


class MissionStateSchema(ApiModel):
    scenario_id: str
    simulated_time: datetime
    # Wave 7 (ADR-0014): ``satellites`` is canonical; the singular fields
    # stay as legacy single-satellite output so old readers keep working.
    satellites: list[SatelliteStateSchema] | None = None
    satellite_id: str | None = None
    battery_wh: float | None = None
    storage_usage_mb: float | None = None
    available: bool | None = None
    active_event_ids: list[str]
    completed_request_ids: list[str] | None = None
    mission_complete: bool

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        if self.satellites is None and self.satellite_id is None:
            raise ValueError("mission state requires satellites or legacy satellite fields")
        return self


class CloudBlockPayloadSchema(ApiModel):
    request_id: str = Field(min_length=1)
    window_id: str = Field(min_length=1)
    # Wave 5 (ADR-0012): archived-weather evidence. A weather-derived
    # block carries all three; a hand-injected block carries none.
    source: str | None = Field(default=None, min_length=1)
    cloud_cover_pct: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    threshold_pct: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_weather_evidence(self) -> Self:
        evidence = (self.source, self.cloud_cover_pct, self.threshold_pct)
        if any(item is None for item in evidence) and any(item is not None for item in evidence):
            raise ValueError(
                "weather cloud blocks carry source, cloud_cover_pct, and threshold_pct together"
            )
        return self


class BatteryDropPayloadSchema(ApiModel):
    satellite_id: str = Field(min_length=1)
    new_battery_wh: float = Field(ge=0, allow_inf_nan=False)


class SatelliteOutagePayloadSchema(ApiModel):
    satellite_id: str = Field(min_length=1)
    outage_start: datetime
    outage_end: datetime

    @model_validator(mode="after")
    def validate_outage_interval(self) -> Self:
        if self.outage_start.tzinfo is None or self.outage_end.tzinfo is None:
            raise ValueError("payload outage interval must include a timezone")
        if self.outage_end <= self.outage_start:
            raise ValueError("payload outage end must be after outage start")
        return self


class CommunicationOutagePayloadSchema(ApiModel):
    station_id: str = Field(min_length=1)
    outage_start: datetime
    outage_end: datetime

    @model_validator(mode="after")
    def validate_outage_interval(self) -> Self:
        if self.outage_start.tzinfo is None or self.outage_end.tzinfo is None:
            raise ValueError("communication outage interval must include a timezone")
        if self.outage_end <= self.outage_start:
            raise ValueError("communication outage end must be after outage start")
        return self


class EmergencyTaskPayloadSchema(ApiModel):
    """The emergency request and the explicit windows it arrives with.

    A cue arrival (ADR-0015) also carries ``source``, ``source_event_id``
    and ``alert_level`` together, with optional ``mag`` and ``sig``.
    """

    request: ObservationRequestSchema
    windows: list[ObservationWindowSchema] | None = None
    source: str | None = Field(default=None, min_length=1)
    source_event_id: str | None = Field(default=None, min_length=1)
    alert_level: AlertLevel | None = None
    # Source-reported USGS magnitude and significance score, both unitless.
    mag: float | None = Field(default=None, allow_inf_nan=False, strict=True)
    sig: float | None = Field(default=None, allow_inf_nan=False, strict=True)

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        # The domain owns the all-or-nothing rule; the schema only delegates.
        error = emergency_evidence_error(
            self.source, self.source_event_id, self.alert_level, self.mag, self.sig
        )
        if error is not None:
            raise ValueError(error)
        return self


class CloudBlockEventRequest(ApiModel):
    event_type: Literal[EventType.CLOUD_BLOCK]
    payload: CloudBlockPayloadSchema


class BatteryDropEventRequest(ApiModel):
    event_type: Literal[EventType.BATTERY_DROP]
    payload: BatteryDropPayloadSchema


class SatelliteOutageEventRequest(ApiModel):
    event_type: Literal[EventType.SATELLITE_UNAVAILABLE]
    payload: SatelliteOutagePayloadSchema


class CommunicationOutageEventRequest(ApiModel):
    event_type: Literal[EventType.COMMUNICATION_OUTAGE]
    payload: CommunicationOutagePayloadSchema


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
                SatelliteOutageEventRequest,
                CommunicationOutageEventRequest,
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


class SatelliteOutageMissionEventSchema(MissionEventFields):
    event_type: Literal[EventType.SATELLITE_UNAVAILABLE]
    payload: SatelliteOutagePayloadSchema


class CommunicationOutageMissionEventSchema(MissionEventFields):
    event_type: Literal[EventType.COMMUNICATION_OUTAGE]
    payload: CommunicationOutagePayloadSchema


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
                SatelliteOutageMissionEventSchema,
                CommunicationOutageMissionEventSchema,
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


class SatelliteMetricsSchema(ApiModel):
    satellite_id: str
    battery_utilisation: float
    storage_utilisation: float
    downlink_action_count: int = 0
    downlink_volume_mb: float = 0.0


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
    downlink_action_count: int = 0
    downlink_volume_mb: float = 0
    # Wave 7 (ADR-0014): per-satellite breakdown alongside mission totals.
    per_satellite: list[SatelliteMetricsSchema] = Field(default_factory=list)


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
    planner: Literal["greedy", "cp_sat"] | None = None
    expected_parent_plan_id: str = Field(min_length=1)


class ErrorBody(ApiModel):
    code: ErrorCode
    message: str
    details: dict[str, Any]


class ErrorEnvelope(ApiModel):
    error: ErrorBody


class ScenarioSummarySchema(ApiModel):
    id: str
    name: str
    start_time: datetime
    end_time: datetime
    provider: str


class ScenarioPreviewSchema(ApiModel):
    errors: list[str]
    warnings: list[str]
    windows: list[ObservationWindowSchema]
    window_counts: dict[str, int]
    ground_track: list[GroundTrackPointSchema] = []


class TleParseRequest(ApiModel):
    name: str = Field(min_length=1)
    line1: str
    line2: str


class GroundTrackPointSchema(ApiModel):
    time: datetime
    lat: float
    lon: float
    altitude_km: float
