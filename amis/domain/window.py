"""ObservationWindow domain type."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass(frozen=True)
class ObservationWindow:
    id: str
    request_id: str
    satellite_id: str
    start: datetime
    end: datetime
    valid: bool = True
    invalid_reason: Optional[str] = None
    peak_elevation_deg: float | None = None
    peak_time: datetime | None = None
    min_off_nadir_deg: float | None = None
    sun_elevation_deg: float | None = None
    source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "id": self.id,
            "request_id": self.request_id,
            "satellite_id": self.satellite_id,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "valid": self.valid,
            "invalid_reason": self.invalid_reason,
        }
        for key in ("peak_elevation_deg", "min_off_nadir_deg", "sun_elevation_deg", "source"):
            value = getattr(self, key)
            if value is not None:
                result[key] = value
        if self.peak_time is not None:
            result["peak_time"] = self.peak_time.isoformat()
        return result

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "ObservationWindow":
        return ObservationWindow(
            id=data["id"],
            request_id=data["request_id"],
            satellite_id=data["satellite_id"],
            start=datetime.fromisoformat(data["start"]),
            end=datetime.fromisoformat(data["end"]),
            valid=data["valid"],
            invalid_reason=data["invalid_reason"],
            peak_elevation_deg=data.get("peak_elevation_deg"),
            peak_time=datetime.fromisoformat(data["peak_time"]) if data.get("peak_time") else None,
            min_off_nadir_deg=data.get("min_off_nadir_deg"),
            sun_elevation_deg=data.get("sun_elevation_deg"),
            source=data.get("source"),
        )
