"""Mission event records and their typed payloads."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal, Union, get_args
from urllib.parse import urlsplit

from amis.domain.enums import EventType
from amis.domain.scenario import ObservationRequest
from amis.domain.window import ObservationWindow


@dataclass(frozen=True)
class CloudBlockPayload:
    """A blocked observation window.

    Hand-injected blocks carry only the request and window. Blocks
    derived offline from archived weather (Wave 5, ADR-0012) carry the
    full evidence triple -- source, coverage, and threshold -- so a
    replay reads recorded values and the planner never sees weather.
    """

    request_id: str
    window_id: str
    source: str | None = None
    cloud_cover_pct: float | None = None
    threshold_pct: float | None = None

    def to_dict(self) -> dict[str, Any]:
        # Optional evidence keys are omitted when absent, so payloads
        # recorded before Wave 5 keep their exact serialized shape.
        result: dict[str, Any] = {
            "request_id": self.request_id,
            "window_id": self.window_id,
        }
        if self.source is not None:
            result["source"] = self.source
        if self.cloud_cover_pct is not None:
            result["cloud_cover_pct"] = self.cloud_cover_pct
        if self.threshold_pct is not None:
            result["threshold_pct"] = self.threshold_pct
        return result

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "CloudBlockPayload":
        return CloudBlockPayload(
            request_id=data["request_id"],
            window_id=data["window_id"],
            source=data.get("source"),
            cloud_cover_pct=data.get("cloud_cover_pct"),
            threshold_pct=data.get("threshold_pct"),
        )

    @property
    def is_weather_derived(self) -> bool:
        """True when the block carries archived-weather evidence."""
        return (
            self.source is not None
            and self.cloud_cover_pct is not None
            and self.threshold_pct is not None
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


# Normalized cue alert levels (ADR-0015). ``unknown`` is the explicit value
# for an absent source alert. The API schema and the frontend read this set.
AlertLevel = Literal["red", "orange", "yellow", "green", "unknown"]
CUE_ALERT_LEVELS: tuple[str, ...] = get_args(AlertLevel)
CEMS_EVIDENCE_FIELDS = ("category", "activation_time", "source_event_time", "source_url", "centroid_policy_version")

EMERGENCY_EVIDENCE_FIELDS = ("source", "source_event_id", "alert_level")


def emergency_evidence_error(
    source: Any,
    source_event_id: Any,
    alert_level: Any,
    mag: Any = None,
    sig: Any = None,
    category: Any = None,
    activation_time: Any = None,
    source_event_time: Any = None,
    source_url: Any = None,
    centroid_policy_version: Any = None,
) -> str | None:
    """Why an emergency evidence group is inconsistent, or None when valid.

    The single owner of the all-or-nothing rule: the domain payload, the
    session's pre-generation check, and the API schema all delegate here.
    """
    cems = dict(category=category, activation_time=activation_time,
                source_event_time=source_event_time, source_url=source_url,
                centroid_policy_version=centroid_policy_version)
    if source != "cems" and any(value is not None for value in cems.values()):
        return "CEMS evidence requires source cems"
    if source == "cems":
        for field in ("category", "activation_time", "source_url", "centroid_policy_version"):
            if not isinstance(cems[field], str) or not cems[field].strip():
                return f"CEMS evidence requires nonempty {field}"
        if alert_level != "unknown" or mag is not None or sig is not None:
            return "CEMS evidence requires unknown alert and no earthquake magnitude/significance"
        if centroid_policy_version != "cems-centroid-v1":
            return "unsupported CEMS centroid policy version"
        moments = {}
        for field in ("activation_time", "source_event_time"):
            value = cems[field]
            if value is None:
                continue
            try:
                moment = datetime.fromisoformat(value)
                if moment.utcoffset() != timedelta(0):
                    return f"CEMS {field} must be a UTC timestamp"
                moments[field] = moment
            except (TypeError, ValueError):
                return f"CEMS {field} must be a UTC timestamp"
        if source_event_time is not None and moments["source_event_time"] > moments["activation_time"]:
            return "CEMS source event time must not follow activation time"
        try:
            url = urlsplit(source_url)
            if url.scheme != "https" or not url.hostname or url.username or url.password:
                return "CEMS source_url must be a public HTTPS source URL"
        except ValueError:
            return "CEMS source_url must be a public HTTPS source URL"
    core = {"source": source, "source_event_id": source_event_id, "alert_level": alert_level}
    missing = [field for field, value in core.items() if value is None]
    if missing and len(missing) != len(core):
        return (
            "emergency evidence requires source, source_event_id, and alert_level together; "
            f"missing {', '.join(missing)}"
        )
    if missing:
        optional = [field for field, value in (("mag", mag), ("sig", sig)) if value is not None]
        if optional:
            return (
                f"emergency evidence {', '.join(optional)} requires source, "
                "source_event_id, and alert_level"
            )
        return None
    for field in ("source", "source_event_id"):
        value = core[field]
        if not isinstance(value, str) or not value.strip():
            return f"emergency evidence {field} must be a nonempty string"
    if alert_level not in CUE_ALERT_LEVELS:
        return (
            f"emergency evidence alert_level must be one of {', '.join(CUE_ALERT_LEVELS)}; "
            f"got {alert_level!r}"
        )
    for field, value in (("mag", mag), ("sig", sig)):
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            return f"emergency evidence {field} must be a finite number when present"
    return None


@dataclass(frozen=True)
class EmergencyRequestPayload:
    """The request and windows recorded by the ``EMERGENCY_TASK`` wire event.

    A manual arrival carries no evidence. A cue arrival (ADR-0015) also
    carries ``source``, ``source_event_id`` and ``alert_level`` together,
    with optional ``mag`` (source-reported earthquake magnitude, unitless
    USGS ``mag``) and ``sig`` (USGS significance score, 0-1000+, unitless);
    the planner never reads them.
    """

    request: ObservationRequest
    windows: tuple[ObservationWindow, ...]
    source: str | None = None
    source_event_id: str | None = None
    alert_level: AlertLevel | None = None
    mag: float | None = None
    sig: float | None = None
    category: str | None = None
    activation_time: str | None = None
    source_event_time: str | None = None
    source_url: str | None = None
    centroid_policy_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        # Evidence keys are omitted when absent, so evidence-free payloads
        # keep their exact serialized shape.
        result: dict[str, Any] = {
            "request": self.request.to_dict(),
            "windows": [window.to_dict() for window in self.windows],
        }
        for field in ("source", "source_event_id", "alert_level", "mag", "sig", *CEMS_EVIDENCE_FIELDS):
            value = getattr(self, field)
            if value is not None:
                result[field] = value
        return result

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "EmergencyRequestPayload":
        return EmergencyRequestPayload(
            request=ObservationRequest.from_dict(data["request"]),
            windows=tuple(
                ObservationWindow.from_dict(window) for window in data["windows"]
            ),
            source=data.get("source"),
            source_event_id=data.get("source_event_id"),
            alert_level=data.get("alert_level"),
            mag=data.get("mag"),
            sig=data.get("sig"),
            **{field: data.get(field) for field in CEMS_EVIDENCE_FIELDS},
        )

    @property
    def has_evidence(self) -> bool:
        """True only for a complete, valid evidence group.

        A partial or malformed group is not evidence: ``evidence_error()``
        rejects it, and this property reports False for it.
        """
        return self.source is not None and self.evidence_error() is None

    def evidence_error(self) -> str | None:
        """Why the evidence group is inconsistent, or None when it is valid."""
        return emergency_evidence_error(
            self.source, self.source_event_id, self.alert_level, self.mag, self.sig,
            **{field: getattr(self, field) for field in CEMS_EVIDENCE_FIELDS},
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
