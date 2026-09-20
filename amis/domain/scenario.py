"""Scenario, Satellite, and ObservationRequest domain types.

See CONTEXT.md for the vocabulary these types follow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from amis.domain.enums import RequestStatus


@dataclass(frozen=True)
class Satellite:
    id: str
    battery_capacity_wh: float
    battery_charge_wh: float
    storage_capacity_mb: float
    storage_usage_mb: float
    available: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "battery_capacity_wh": self.battery_capacity_wh,
            "battery_charge_wh": self.battery_charge_wh,
            "storage_capacity_mb": self.storage_capacity_mb,
            "storage_usage_mb": self.storage_usage_mb,
            "available": self.available,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Satellite":
        return Satellite(
            id=data["id"],
            battery_capacity_wh=data["battery_capacity_wh"],
            battery_charge_wh=data["battery_charge_wh"],
            storage_capacity_mb=data["storage_capacity_mb"],
            storage_usage_mb=data["storage_usage_mb"],
            available=data["available"],
        )


@dataclass(frozen=True)
class ObservationRequest:
    id: str
    target_lat: float
    target_lon: float
    priority: int
    duration_s: float
    deadline: datetime
    energy_cost_wh: float
    storage_cost_mb: float
    status: RequestStatus = RequestStatus.PENDING

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "target_lat": self.target_lat,
            "target_lon": self.target_lon,
            "priority": self.priority,
            "duration_s": self.duration_s,
            "deadline": self.deadline.isoformat(),
            "energy_cost_wh": self.energy_cost_wh,
            "storage_cost_mb": self.storage_cost_mb,
            "status": self.status.value,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "ObservationRequest":
        return ObservationRequest(
            id=data["id"],
            target_lat=data["target_lat"],
            target_lon=data["target_lon"],
            priority=data["priority"],
            duration_s=data["duration_s"],
            deadline=datetime.fromisoformat(data["deadline"]),
            energy_cost_wh=data["energy_cost_wh"],
            storage_cost_mb=data["storage_cost_mb"],
            status=RequestStatus(data["status"]),
        )


@dataclass(frozen=True)
class Scenario:
    id: str
    name: str
    start_time: datetime
    end_time: datetime
    satellite: Satellite
    requests: tuple[ObservationRequest, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "satellite": self.satellite.to_dict(),
            "requests": [r.to_dict() for r in self.requests],
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Scenario":
        return Scenario(
            id=data["id"],
            name=data["name"],
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]),
            satellite=Satellite.from_dict(data["satellite"]),
            requests=tuple(
                ObservationRequest.from_dict(r) for r in data["requests"]
            ),
        )
