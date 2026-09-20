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

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "request_id": self.request_id,
            "satellite_id": self.satellite_id,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "valid": self.valid,
            "invalid_reason": self.invalid_reason,
        }

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
        )
