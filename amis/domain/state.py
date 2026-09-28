"""MissionState: a value snapshot of the mission at one simulated instant.

Wave 7 (ADR-0014): resources, availability, and completed requests are
tracked per satellite. There is no mission-wide battery or storage
number -- each satellite has its own -- so every reader names the
satellite it means. ``completed_request_ids`` stays a mission-total
convenience (the union across satellites) because a request completes
on exactly one satellite and nothing needs to know which one to count
it.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any

from amis.domain.scenario import Scenario


@dataclass(frozen=True)
class SatelliteState:
    satellite_id: str
    battery_wh: float
    storage_usage_mb: float
    available: bool
    completed_request_ids: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "satellite_id": self.satellite_id,
            "battery_wh": self.battery_wh,
            "storage_usage_mb": self.storage_usage_mb,
            "available": self.available,
            "completed_request_ids": list(self.completed_request_ids),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "SatelliteState":
        return SatelliteState(
            satellite_id=data["satellite_id"],
            battery_wh=data["battery_wh"],
            storage_usage_mb=data["storage_usage_mb"],
            available=data["available"],
            completed_request_ids=tuple(data.get("completed_request_ids", ())),
        )


@dataclass(frozen=True, init=False)
class MissionState:
    scenario_id: str
    simulated_time: datetime
    satellites: tuple[SatelliteState, ...]
    active_event_ids: tuple[str, ...] = field(default_factory=tuple)
    mission_complete: bool = False

    def __init__(
        self,
        scenario_id: str,
        simulated_time: datetime,
        satellites: tuple[SatelliteState, ...] | None = None,
        active_event_ids: tuple[str, ...] = (),
        mission_complete: bool = False,
        # Pre-Wave-7 single-satellite shape (legacy tests and callers).
        satellite_id: str | None = None,
        battery_wh: float | None = None,
        storage_usage_mb: float | None = None,
        available: bool | None = None,
        completed_request_ids: tuple[str, ...] | None = None,
    ) -> None:
        if satellites is not None and satellite_id is not None:
            raise ValueError("pass either satellites or satellite_id, not both")
        if satellites is None:
            if satellite_id is None or battery_wh is None or storage_usage_mb is None or available is None:
                raise ValueError("a mission state requires satellites or legacy single-satellite fields")
            satellites = (
                SatelliteState(
                    satellite_id=satellite_id,
                    battery_wh=battery_wh,
                    storage_usage_mb=storage_usage_mb,
                    available=available,
                    completed_request_ids=tuple(completed_request_ids or ()),
                ),
            )
        object.__setattr__(self, "scenario_id", scenario_id)
        object.__setattr__(self, "simulated_time", simulated_time)
        object.__setattr__(self, "satellites", tuple(satellites))
        object.__setattr__(self, "active_event_ids", tuple(active_event_ids))
        object.__setattr__(self, "mission_complete", mission_complete)

    @staticmethod
    def initial(scenario: Scenario) -> "MissionState":
        return MissionState(
            scenario_id=scenario.id,
            simulated_time=scenario.start_time,
            satellites=tuple(
                SatelliteState(
                    satellite_id=satellite.id,
                    battery_wh=satellite.battery_charge_wh,
                    storage_usage_mb=satellite.storage_usage_mb,
                    available=satellite.available,
                )
                for satellite in scenario.satellites
            ),
        )

    def for_satellite(self, satellite_id: str) -> SatelliteState:
        state = next(
            (item for item in self.satellites if item.satellite_id == satellite_id),
            None,
        )
        if state is None:
            raise ValueError(f"mission state has no satellite with id {satellite_id!r}")
        return state

    def with_satellite(self, satellite_id: str, **changes: Any) -> "MissionState":
        """A copy with one satellite's state replaced by ``changes``."""
        updated = tuple(
            replace(item, **changes) if item.satellite_id == satellite_id else item
            for item in self.satellites
        )
        return replace(self, satellites=updated)

    @property
    def satellite_id(self) -> str:
        """Single-satellite convenience: the first satellite's id."""
        return self.satellites[0].satellite_id

    @property
    def battery_wh(self) -> float:
        """Single-satellite convenience: the first satellite's battery."""
        return self.satellites[0].battery_wh

    @property
    def storage_usage_mb(self) -> float:
        """Single-satellite convenience: the first satellite's storage."""
        return self.satellites[0].storage_usage_mb

    @property
    def available(self) -> bool:
        """Single-satellite convenience: the first satellite's availability."""
        return self.satellites[0].available

    @property
    def completed_request_ids(self) -> tuple[str, ...]:
        """Mission total: every request completed, on any satellite."""
        seen: list[str] = []
        for satellite in self.satellites:
            for request_id in satellite.completed_request_ids:
                if request_id not in seen:
                    seen.append(request_id)
        return tuple(seen)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "scenario_id": self.scenario_id,
            "simulated_time": self.simulated_time.isoformat(),
            "satellites": [satellite.to_dict() for satellite in self.satellites],
            "active_event_ids": list(self.active_event_ids),
            "mission_complete": self.mission_complete,
        }
        # Single-satellite convenience for pre-Wave-7 readers (REST tests,
        # old clients): the first satellite's fields at the top level plus
        # the mission-total completed set. Multi-satellite missions omit
        # them because no single number is correct.
        if len(self.satellites) == 1:
            only = self.satellites[0]
            result["satellite_id"] = only.satellite_id
            result["battery_wh"] = only.battery_wh
            result["storage_usage_mb"] = only.storage_usage_mb
            result["available"] = only.available
            result["completed_request_ids"] = list(self.completed_request_ids)
        return result

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "MissionState":
        satellites_raw = data.get("satellites")
        if satellites_raw is not None:
            satellites = tuple(SatelliteState.from_dict(item) for item in satellites_raw)
        else:
            # Pre-Wave-7 stored shape: one satellite's fields at the top level.
            satellites = (
                SatelliteState(
                    satellite_id=data["satellite_id"],
                    battery_wh=data["battery_wh"],
                    storage_usage_mb=data["storage_usage_mb"],
                    available=data["available"],
                    completed_request_ids=tuple(data.get("completed_request_ids", ())),
                ),
            )
        return MissionState(
            scenario_id=data["scenario_id"],
            simulated_time=datetime.fromisoformat(data["simulated_time"]),
            satellites=satellites,
            active_event_ids=tuple(data.get("active_event_ids", ())),
            mission_complete=data.get("mission_complete", False),
        )
