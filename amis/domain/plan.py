"""ScheduledAction and MissionPlan domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from amis.domain.enums import ActionKind, ActionStatus, ReasonCode


@dataclass(frozen=True)
class ScheduledAction:
    """An imaging action (keyed by request) or a downlink action (keyed by station).

    Downlink actions carry ``request_id=None``, ``window_id=<contact id>``, and a
    negative ``storage_cost_mb``. See ADR-0011.
    """

    id: str
    request_id: Optional[str]
    satellite_id: str
    window_id: str
    start: datetime
    end: datetime
    energy_cost_wh: float
    storage_cost_mb: float
    status: ActionStatus = ActionStatus.PLANNED
    kind: ActionKind = ActionKind.IMAGING
    station_id: Optional[str] = None

    @property
    def is_downlink(self) -> bool:
        return self.kind is ActionKind.DOWNLINK

    @property
    def subject_key(self) -> str:
        """Request id for imaging, action id for downlink (ADR-0011)."""
        return self.request_id if self.request_id is not None else self.id

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
            "kind": self.kind.value,
            "station_id": self.station_id,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "ScheduledAction":
        return ScheduledAction(
            id=data["id"],
            request_id=data.get("request_id"),
            satellite_id=data["satellite_id"],
            window_id=data["window_id"],
            start=datetime.fromisoformat(data["start"]),
            end=datetime.fromisoformat(data["end"]),
            energy_cost_wh=data["energy_cost_wh"],
            storage_cost_mb=data["storage_cost_mb"],
            status=ActionStatus(data["status"]),
            kind=ActionKind(data.get("kind") or ActionKind.IMAGING.value),
            station_id=data.get("station_id"),
        )


@dataclass(frozen=True)
class UnscheduledEntry:
    request_id: str
    reason_code: ReasonCode

    def to_dict(self) -> dict[str, Any]:
        return {"request_id": self.request_id, "reason_code": self.reason_code.value}

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "UnscheduledEntry":
        return UnscheduledEntry(
            request_id=data["request_id"],
            reason_code=ReasonCode(data["reason_code"]),
        )


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
    planner_name: str = "greedy"
    solver_details: dict[str, Any] | None = None

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
            "planner_name": self.planner_name,
            "solver_details": self.solver_details,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "MissionPlan":
        return MissionPlan(
            id=data["id"],
            scenario_id=data["scenario_id"],
            version=data["version"],
            parent_plan_id=data.get("parent_plan_id"),
            created_at=datetime.fromisoformat(data["created_at"]),
            actions=tuple(ScheduledAction.from_dict(a) for a in data["actions"]),
            unscheduled=tuple(
                UnscheduledEntry.from_dict(u) for u in data["unscheduled"]
            ),
            mission_utility=data["mission_utility"],
            violation_count=data["violation_count"],
            planning_time_ms=data["planning_time_ms"],
            planner_name=data.get("planner_name") or "greedy",
            solver_details=data.get("solver_details"),
        )
