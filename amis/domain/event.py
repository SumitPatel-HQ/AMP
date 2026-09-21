"""Mission event records and their typed payloads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Union

from amis.domain.enums import EventType


@dataclass(frozen=True)
class CloudBlockPayload:
    request_id: str
    window_id: str

    def to_dict(self) -> dict[str, str]:
        return {"request_id": self.request_id, "window_id": self.window_id}

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "CloudBlockPayload":
        return CloudBlockPayload(
            request_id=data["request_id"],
            window_id=data["window_id"],
        )


@dataclass(frozen=True)
class BatteryDropPayload:
    satellite_id: str
    new_battery_wh: float

    def to_dict(self) -> dict[str, Any]:
        return {"satellite_id": self.satellite_id, "new_battery_wh": self.new_battery_wh}

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "BatteryDropPayload":
        return BatteryDropPayload(
            satellite_id=data["satellite_id"],
            new_battery_wh=data["new_battery_wh"],
        )


EventPayload = Union[CloudBlockPayload, BatteryDropPayload]


@dataclass(frozen=True)
class MissionEvent:
    id: str
    scenario_id: str
    event_type: EventType
    event_time: datetime
    payload: EventPayload

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "scenario_id": self.scenario_id,
            "event_type": self.event_type.value,
            "event_time": self.event_time.isoformat(),
            "payload": self.payload.to_dict(),
        }
