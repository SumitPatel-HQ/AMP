"""Scenario, Satellite, and ObservationRequest domain types.

See CONTEXT.md for the vocabulary these types follow.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from amis.domain.enums import RequestStatus
from amis.domain.orbit import OrbitalElements, WindowPolicy


@dataclass(frozen=True)
class Satellite:
    id: str
    battery_capacity_wh: float
    battery_charge_wh: float
    storage_capacity_mb: float
    storage_usage_mb: float
    available: bool = True
    orbit: OrbitalElements | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "id": self.id,
            "battery_capacity_wh": self.battery_capacity_wh,
            "battery_charge_wh": self.battery_charge_wh,
            "storage_capacity_mb": self.storage_capacity_mb,
            "storage_usage_mb": self.storage_usage_mb,
            "available": self.available,
        }
        if self.orbit is not None:
            result["orbit"] = self.orbit.to_dict()
        return result

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Satellite":
        return Satellite(
            id=data["id"],
            battery_capacity_wh=data["battery_capacity_wh"],
            battery_charge_wh=data["battery_charge_wh"],
            storage_capacity_mb=data["storage_capacity_mb"],
            storage_usage_mb=data["storage_usage_mb"],
            available=data["available"],
            orbit=OrbitalElements.from_dict(data["orbit"]) if data.get("orbit") else None,
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
    target_name: str | None = None
    # Wave 7 (ADR-0014): naming a satellite pins the request to it; absent
    # means the planner assigns whichever satellite can serve it.
    satellite_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
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
        if self.target_name is not None:
            result["target_name"] = self.target_name
        if self.satellite_id is not None:
            result["satellite_id"] = self.satellite_id
        return result

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
            target_name=data.get("target_name"),
            satellite_id=data.get("satellite_id"),
        )


@dataclass(frozen=True, init=False)
class Scenario:
    """Wave 7 (ADR-0014): a mission holds one or more satellites.

    ``satellites`` is the canonical field. The constructor also accepts a
    single ``satellite=`` keyword as a convenience that wraps it in a
    one-tuple, so every mission built before this wave keeps working
    unchanged. Reading ``scenario.satellite`` returns ``satellites[0]``
    for single-satellite code that has not been updated to iterate yet.
    """

    id: str
    name: str
    start_time: datetime
    end_time: datetime
    requests: tuple[ObservationRequest, ...]
    window_policy: WindowPolicy | None
    satellites: tuple[Satellite, ...]

    def __init__(
        self,
        id: str,
        name: str,
        start_time: datetime,
        end_time: datetime,
        satellite: Satellite | None = None,
        requests: tuple[ObservationRequest, ...] = (),
        window_policy: WindowPolicy | None = None,
        satellites: tuple[Satellite, ...] | None = None,
    ) -> None:
        # ``satellite`` wins when both are given. ``dataclasses.replace``
        # on a Scenario built before this wave passes the old
        # ``satellites`` tuple along implicitly while the caller overrides
        # ``satellite=``, so rejecting both would break every
        # ``replace(scenario, satellite=...)`` call in tests and examples.
        if satellite is not None:
            resolved = (satellite,)
        elif satellites is not None:
            resolved = satellites
        else:
            resolved = ()
        if not resolved:
            raise ValueError("a scenario requires at least one satellite")
        ids = [item.id for item in resolved]
        if len(ids) != len(set(ids)):
            raise ValueError("satellite ids must be unique")
        object.__setattr__(self, "id", id)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "start_time", start_time)
        object.__setattr__(self, "end_time", end_time)
        object.__setattr__(self, "requests", tuple(requests))
        object.__setattr__(self, "window_policy", window_policy)
        object.__setattr__(self, "satellites", tuple(resolved))

    @property
    def satellite(self) -> Satellite:
        """The single-satellite convenience accessor: the first satellite."""
        return self.satellites[0]

    def satellite_by_id(self, satellite_id: str) -> Satellite:
        satellite = next((item for item in self.satellites if item.id == satellite_id), None)
        if satellite is None:
            raise ValueError(f"scenario has no satellite with id {satellite_id!r}")
        return satellite

    def to_dict(self) -> dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "satellites": [s.to_dict() for s in self.satellites],
            "requests": [r.to_dict() for r in self.requests],
        }
        # Single-satellite convenience for pre-Wave-7 readers: the only
        # satellite under the legacy singular key as well. Multi-satellite
        # missions omit it because no single satellite is correct.
        if len(self.satellites) == 1:
            result["satellite"] = self.satellites[0].to_dict()
        if self.window_policy is not None:
            result["window_policy"] = self.window_policy.to_dict()
        return result

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Scenario":
        satellites_raw = data.get("satellites")
        satellite_raw = data.get("satellite")
        if satellites_raw is not None:
            satellites = tuple(Satellite.from_dict(s) for s in satellites_raw)
        elif satellite_raw is not None:
            # Pre-Wave-7 stored shape: one satellite under a singular key.
            satellites = (Satellite.from_dict(satellite_raw),)
        else:
            raise KeyError("scenario requires 'satellites' or legacy 'satellite'")
        return Scenario(
            id=data["id"],
            name=data["name"],
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]),
            satellites=satellites,
            requests=tuple(
                ObservationRequest.from_dict(r) for r in data["requests"]
            ),
            window_policy=WindowPolicy.from_dict(data["window_policy"]) if data.get("window_policy") else None,
        )
