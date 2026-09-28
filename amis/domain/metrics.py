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
        }
