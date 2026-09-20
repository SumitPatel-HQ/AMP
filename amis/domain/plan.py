"""ScheduledAction and MissionPlan domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from amis.domain.enums import ActionStatus, ReasonCode


@dataclass(frozen=True)
class ScheduledAction:
    id: str
    request_id: str
    satellite_id: str
    window_id: str
    start: datetime
    end: datetime
    energy_cost_wh: float
    storage_cost_mb: float
    status: ActionStatus = ActionStatus.PLANNED

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "request_id": self.request_id,
            "satellite_id": self.satellite_id,
            "window_id": self.window_id,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "energy_cost_wh": self.energy_cost_wh,
            "storage_cost_mb": self.storage_cost_mb,
            "status": self.status.value,
        }


@dataclass(frozen=True)
class UnscheduledEntry:
    request_id: str
    reason_code: ReasonCode

    def to_dict(self) -> dict[str, Any]:
        return {"request_id": self.request_id, "reason_code": self.reason_code.value}


@dataclass(frozen=True)
class MissionPlan:
    id: str
    scenario_id: str
    version: int
    created_at: datetime
    actions: tuple[ScheduledAction, ...]
    unscheduled: tuple[UnscheduledEntry, ...]
    mission_utility: float
    violation_count: int
    planning_time_ms: float
    parent_plan_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "scenario_id": self.scenario_id,
            "version": self.version,
            "parent_plan_id": self.parent_plan_id,
            "created_at": self.created_at.isoformat(),
            "actions": [a.to_dict() for a in self.actions],
            "unscheduled": [u.to_dict() for u in self.unscheduled],
            "mission_utility": self.mission_utility,
            "violation_count": self.violation_count,
            "planning_time_ms": self.planning_time_ms,
        }
