"""MetricsResult: a plan's quality expressed as plain, serialisable data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass(frozen=True)
class SatelliteMetrics:
    """Wave 7 (ADR-0014): the per-satellite view alongside mission totals."""

    satellite_id: str
    battery_utilisation: float
    storage_utilisation: float
    downlink_action_count: int = 0
    downlink_volume_mb: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "satellite_id": self.satellite_id,
            "battery_utilisation": self.battery_utilisation,
            "storage_utilisation": self.storage_utilisation,
            "downlink_action_count": self.downlink_action_count,
            "downlink_volume_mb": self.downlink_volume_mb,
        }


@dataclass(frozen=True)
class EmergencyResponse:
    """How one emergency arrival is answered: planned and achieved imaging.

    Arrival is the accepted ``EMERGENCY_TASK`` event's simulated time.
    Planned fields read the measured plan's imaging action for the request;
    achieved fields read the session's executed history and are set only
    once imaging has actually started. Acquisition means imaging began, not
    that it finished or was downlinked. A null start is no service, never
    zero latency.
    """

    request_id: str
    event_id: str
    arrival_time: datetime
    request_status: str
    planned_start_time: Optional[datetime] = None
    planned_latency_s: Optional[float] = None
    planned_satellite_id: Optional[str] = None
    achieved_start_time: Optional[datetime] = None
    achieved_latency_s: Optional[float] = None
    achieved_satellite_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "event_id": self.event_id,
            "arrival_time": self.arrival_time.isoformat(),
            "request_status": self.request_status,
            "planned_start_time": _isoformat(self.planned_start_time),
            "planned_latency_s": self.planned_latency_s,
            "planned_satellite_id": self.planned_satellite_id,
            "achieved_start_time": _isoformat(self.achieved_start_time),
            "achieved_latency_s": self.achieved_latency_s,
            "achieved_satellite_id": self.achieved_satellite_id,
        }


def _isoformat(value: Optional[datetime]) -> Optional[str]:
    return None if value is None else value.isoformat()


@dataclass(frozen=True)
class MetricsResult:
    plan_id: str
    mission_utility: float
    completion_rate: float
    violation_count: int
    planning_time_ms: float
    battery_utilisation: float
    storage_utilisation: float
    request_pool_size: int
    request_pool_ids: frozenset[str]
    # The simulated instant of the mission state the metrics read. Completion
    # and utilisation follow that state, not the plan, so the same plan scores
    # differently as the clock runs.
    measured_at: datetime
    plan_churn: Optional[float] = None
    explanation_coverage: Optional[float] = None
    # Wave 4 (ADR-0011): downlink actions in the plan and their total
    # capacity (rate x duration). Every kept downlink frees storage.
    downlink_action_count: int = 0
    downlink_volume_mb: float = 0.0
    # Wave 7 (ADR-0014): mission totals above stay request-keyed and
    # single-number; this adds the per-satellite breakdown they average.
    per_satellite: tuple[SatelliteMetrics, ...] = ()
    # Emergency response (ADR-0015): one row per eligible emergency arrival.
    # Planned and achieved means never mix, and each carries its own
    # denominator; an empty denominator gives a null mean, never zero.
    emergency_response: tuple[EmergencyResponse, ...] = ()
    # Wire names follow the spec. "Time to first acquisition" is the mean
    # latency over the requests with a planned (or achieved) imaging start,
    # not the earliest acquisition across requests.
    time_to_first_acquisition_s: Optional[float] = None
    achieved_time_to_first_acquisition_s: Optional[float] = None
    emergency_request_count: int = 0
    planned_emergency_request_count: int = 0
    achieved_emergency_request_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "mission_utility": self.mission_utility,
            "completion_rate": self.completion_rate,
            "violation_count": self.violation_count,
            "planning_time_ms": self.planning_time_ms,
            "battery_utilisation": self.battery_utilisation,
            "storage_utilisation": self.storage_utilisation,
            "request_pool_size": self.request_pool_size,
            "request_pool_ids": sorted(self.request_pool_ids),
            "measured_at": self.measured_at.isoformat(),
            "plan_churn": self.plan_churn,
            "explanation_coverage": self.explanation_coverage,
            "downlink_action_count": self.downlink_action_count,
            "downlink_volume_mb": self.downlink_volume_mb,
            "per_satellite": [item.to_dict() for item in self.per_satellite],
            "emergency_response": [item.to_dict() for item in self.emergency_response],
            "time_to_first_acquisition_s": self.time_to_first_acquisition_s,
            "achieved_time_to_first_acquisition_s": self.achieved_time_to_first_acquisition_s,
            "emergency_request_count": self.emergency_request_count,
            "planned_emergency_request_count": self.planned_emergency_request_count,
            "achieved_emergency_request_count": self.achieved_emergency_request_count,
        }
