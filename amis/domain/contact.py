"""Ground stations and the contact windows computed at them (ADR-0011)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass(frozen=True)
class GroundStation:
    id: str
    name: str
    lat: float
    lon: float
    altitude_m: float
    min_elevation_deg: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "lat": self.lat,
            "lon": self.lon,
            "altitude_m": self.altitude_m,
            "min_elevation_deg": self.min_elevation_deg,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "GroundStation":
        return GroundStation(
            id=data["id"],
            name=data["name"],
            lat=data["lat"],
            lon=data["lon"],
            altitude_m=data.get("altitude_m", 0.0),
            min_elevation_deg=data["min_elevation_deg"],
        )


@dataclass(frozen=True)
class ContactWindow:
    id: str
    station_id: str
    satellite_id: str
    start: datetime
    end: datetime
    peak_elevation_deg: float
    peak_time: datetime
    valid: bool = True
    invalid_reason: Optional[str] = None
    source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "station_id": self.station_id,
            "satellite_id": self.satellite_id,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "peak_elevation_deg": self.peak_elevation_deg,
            "peak_time": self.peak_time.isoformat(),
            "valid": self.valid,
            "invalid_reason": self.invalid_reason,
            "source": self.source,
        }
