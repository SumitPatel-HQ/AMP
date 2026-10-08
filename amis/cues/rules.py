"""Offline developer inputs, distinct from accepted MissionEvents and windows."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Collection
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

from amis.api_schemas import ObservationRequestSchema
from amis.cues.archive import CueArchive
from amis.cues.normalize import _finite_number, normalize_usgs
from amis.domain import ObservationRequest, Scenario

POLICY_VERSION = "usgs-earthquake-v1"
ALERT_POLICY = {
    "red": (5, 12),
    "orange": (4, 24),
    "yellow": (3, 48),
    "green": (2, 48),
    "unknown": (2, 48),
}


@dataclass(frozen=True)
class ImagingProfile:
    duration_s: float
    energy_cost_wh: float
    storage_cost_mb: float
    satellite_id: str | None = None
    target_name: str | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ImagingProfile:
        if not isinstance(data, dict):
            raise ValueError("imaging profile must be an object")
        required = {"duration_s", "energy_cost_wh", "storage_cost_mb"}
        allowed = required | {"satellite_id", "target_name"}
        missing = required - data.keys()
        if missing:
            raise ValueError(f"imaging profile is missing explicit values: {', '.join(sorted(missing))}")
        extra = data.keys() - allowed
        if extra:
            raise ValueError(f"unknown imaging profile fields: {', '.join(sorted(extra))}")
        for field in sorted(required):
            _finite_number(data[field], field)
        for field in ("satellite_id", "target_name"):
            if field in data and not isinstance(data[field], str):
                raise ValueError(f"{field} must be a string")
        return ImagingProfile(**data)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "duration_s": self.duration_s,
            "energy_cost_wh": self.energy_cost_wh,
            "storage_cost_mb": self.storage_cost_mb,
        }
        if self.satellite_id is not None:
            result["satellite_id"] = self.satellite_id
        if self.target_name is not None:
            result["target_name"] = self.target_name
        return result


def request_identifier(source: str, source_event_id: str) -> str:
    """Stable identity from the source/id pair, independent of policy and time."""
    identity = json.dumps([source, source_event_id], ensure_ascii=False, separators=(",", ":"))
    return "CUE-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()


def build_cue_inputs(
    archive: CueArchive,
    scenario: Scenario,
    profile: ImagingProfile,
    *,
    selected_event_ids: Collection[str] | None = None,
) -> dict[str, Any]:
    """Apply AMIS policy without touching the Scenario, session, planner, or network."""
    if any(moment.tzinfo is None or moment.utcoffset() is None for moment in (scenario.start_time, scenario.end_time)):
        raise ValueError("Scenario start and end must include a timezone")
    if scenario.end_time <= scenario.start_time:
        raise ValueError("Scenario end must be after start")
    if profile.satellite_id is not None and profile.satellite_id not in {satellite.id for satellite in scenario.satellites}:
        raise ValueError(f"imaging profile names an unknown satellite: {profile.satellite_id!r}")
    cues = normalize_usgs(archive.response, selected_event_ids=selected_event_ids)
    if not cues:
        raise ValueError("no selected USGS earthquakes to build")
    inputs = []
    for cue in cues:
        identifier = request_identifier(cue.source, cue.source_event_id)
        if not scenario.start_time <= cue.event_time < scenario.end_time:
            raise ValueError(
                f"USGS event {cue.source_event_id} at {cue.event_time.isoformat()} is outside "
                f"Scenario [{scenario.start_time.isoformat()}, {scenario.end_time.isoformat()}); select a smaller set"
            )
        if identifier in {request.id for request in scenario.requests}:
            raise ValueError(f"cue request identifier already exists in Scenario: {identifier}")
        target_name = profile.target_name if profile.target_name is not None else cue.place
        if not isinstance(target_name, str) or not target_name.strip() or target_name.strip() == identifier:
            raise ValueError(f"USGS event {cue.source_event_id} needs a nonempty descriptive target_name distinct from its request id")
        priority, deadline_hours = ALERT_POLICY[cue.alert_level]
        if cue.mag is not None and cue.mag >= 6:
            priority = 5
        try:
            deadline = cue.event_time + timedelta(hours=deadline_hours)
        except OverflowError as error:
            raise ValueError(f"USGS event {cue.source_event_id}: policy deadline is outside the supported datetime range") from error
        # Reuse the existing request validation, including finite costs and duration.
        validated = ObservationRequestSchema.model_validate({
            **profile.to_dict(),
            "id": identifier,
            "target_lat": cue.target_lat,
            "target_lon": cue.target_lon,
            "priority": priority,
            "deadline": deadline,
            "target_name": target_name.strip(),
        })
        request = ObservationRequest.from_dict(validated.model_dump(mode="json"))
        payload: dict[str, Any] = {
            "request": request.to_dict(),
            "source": cue.source,
            "source_event_id": cue.source_event_id,
            "alert_level": cue.alert_level,
        }
        if cue.mag is not None:
            payload["mag"] = cue.mag
        if cue.sig is not None:
            payload["sig"] = cue.sig
        inputs.append({
            "injection_time": cue.event_time.isoformat(),
            "event_type": "EMERGENCY_TASK",
            "payload": payload,
        })
    return {
        "metadata": {
            "artifact_type": "developer-cue-inputs",
            "scenario_id": scenario.id,
            "policy_version": POLICY_VERSION,
            "imaging_profile": profile.to_dict(),
            "archive": {
                "source": archive.source,
                "source_url": archive.source_url,
                "file": archive.file,
                "sha256": archive.sha256,
            },
        },
        "inputs": inputs,
    }


def write_cue_inputs(output: Path, artifact: dict[str, Any]) -> None:
    """Publish complete deterministic UTF-8 bytes through an atomic replacement."""
    encoded = (json.dumps(artifact, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix=f".{output.name}.", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(encoded)
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
