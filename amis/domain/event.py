"""Mission event records and their typed payloads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Union

from amis.domain.enums import EventType
from amis.domain.scenario import ObservationRequest
from amis.domain.window import ObservationWindow


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


@dataclass(frozen=True)
class EmergencyRequestPayload:
    """The request and windows recorded by the ``EMERGENCY_TASK`` wire event."""

    request: ObservationRequest
    windows: tuple[ObservationWindow, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.request.to_dict(),
            "windows": [window.to_dict() for window in self.windows],
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "EmergencyRequestPayload":
        return EmergencyRequestPayload(
            request=ObservationRequest.from_dict(data["request"]),
            windows=tuple(
                ObservationWindow.from_dict(window) for window in data["windows"]
            ),
        )


@dataclass(frozen=True)
class SatelliteOutagePayload:
    """Payload outage over an interval: the instrument cannot observe inside it."""

    satellite_id: str
    outage_start: datetime
    outage_end: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "satellite_id": self.satellite_id,
            "outage_start": self.outage_start.isoformat(),
            "outage_end": self.outage_end.isoformat(),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "SatelliteOutagePayload":
        return SatelliteOutagePayload(
            satellite_id=data["satellite_id"],
            outage_start=datetime.fromisoformat(data["outage_start"]),
            outage_end=datetime.fromisoformat(data["outage_end"]),
        )


@dataclass(frozen=True)
class CommunicationOutagePayload:
    """Station outage over an interval: contacts overlapping it are lost (ADR-0011)."""

    station_id: str
    outage_start: datetime
    outage_end: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "station_id": self.station_id,
            "outage_start": self.outage_start.isoformat(),
            "outage_end": self.outage_end.isoformat(),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "CommunicationOutagePayload":
        return CommunicationOutagePayload(
            station_id=data["station_id"],
            outage_start=datetime.fromisoformat(data["outage_start"]),
            outage_end=datetime.fromisoformat(data["outage_end"]),
        )


EventPayload = Union[
    CloudBlockPayload,
    BatteryDropPayload,
    EmergencyRequestPayload,
    SatelliteOutagePayload,
    CommunicationOutagePayload,
]


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

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "MissionEvent":
        event_type = EventType(data["event_type"])
        if event_type is EventType.CLOUD_BLOCK:
            payload: EventPayload = CloudBlockPayload.from_dict(data["payload"])
        elif event_type is EventType.BATTERY_DROP:
            payload = BatteryDropPayload.from_dict(data["payload"])
        elif event_type is EventType.EMERGENCY_TASK:
            payload = EmergencyRequestPayload.from_dict(data["payload"])
        elif event_type is EventType.SATELLITE_UNAVAILABLE:
            payload = SatelliteOutagePayload.from_dict(data["payload"])
        elif event_type is EventType.COMMUNICATION_OUTAGE:
            payload = CommunicationOutagePayload.from_dict(data["payload"])
        else:
            raise ValueError(f"unsupported mission event type: {event_type.value}")
        return MissionEvent(
            id=data["id"],
            scenario_id=data["scenario_id"],
            event_type=event_type,
            event_time=datetime.fromisoformat(data["event_time"]),
            payload=payload,
        )
