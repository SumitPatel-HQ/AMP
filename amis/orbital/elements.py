"""Validated offline OMM and TLE input plus checksummed catalogue snapshots."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from amis.domain.orbit import OrbitalElements

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "elements"


def omm_hash(omm: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(omm, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def from_omm(omm: dict[str, Any], *, source: str, retrieved_at: datetime) -> OrbitalElements:
    from skyfield.api import EarthSatellite, load

    required = ("NORAD_CAT_ID", "OBJECT_NAME", "OBJECT_ID", "EPOCH", "MEAN_MOTION", "ECCENTRICITY", "INCLINATION", "RA_OF_ASC_NODE", "ARG_OF_PERICENTER", "MEAN_ANOMALY", "BSTAR", "MEAN_MOTION_DOT", "MEAN_MOTION_DDOT")
    if any(key not in omm for key in required):
        raise ValueError("OMM is missing required propagation fields")
    epoch = datetime.fromisoformat(str(omm["EPOCH"]).replace("Z", "+00:00"))
    if epoch.tzinfo is None:
        epoch = epoch.replace(tzinfo=timezone.utc)
    EarthSatellite.from_omm(load.timescale(builtin=True), omm)
    return OrbitalElements(
        norad_id=int(omm["NORAD_CAT_ID"]), name=str(omm["OBJECT_NAME"]),
        international_designator=str(omm["OBJECT_ID"]), epoch=epoch,
        omm=omm, source=source, retrieved_at=retrieved_at,
        sha256=omm_hash(omm),
    )


def from_tle(line1: str, line2: str, *, name: str, retrieved_at: datetime) -> OrbitalElements:
    from sgp4.exporter import export_omm
    from sgp4.api import Satrec
    from skyfield.api import EarthSatellite, load

    if len(line1) != 69 or len(line2) != 69 or not line1.startswith("1 ") or not line2.startswith("2 "):
        raise ValueError("TLE requires two 69-character element lines")
    for line in (line1, line2):
        checksum = sum(int(char) for char in line[:68] if char.isdigit()) + line[:68].count("-")
        if checksum % 10 != int(line[68]):
            raise ValueError("TLE checksum is invalid")
    if line1[2:7] != line2[2:7]:
        raise ValueError("TLE satellite identifiers disagree")
    satellite = EarthSatellite(line1, line2, name, load.timescale(builtin=True))
    omm = export_omm(Satrec.twoline2rv(line1, line2), name)
    result = from_omm(omm, source="pasted TLE", retrieved_at=retrieved_at)
    return OrbitalElements(**{**result.__dict__, "epoch": satellite.epoch.utc_datetime(), "tle_line1": line1, "tle_line2": line2})


def catalogue() -> list[OrbitalElements]:
    manifest = json.loads((DATA_DIR / "manifest.json").read_text(encoding="utf-8"))
    records = json.loads((DATA_DIR / manifest["file"]).read_text(encoding="utf-8"))
    retrieved_at = datetime.fromisoformat(manifest["retrieved_at"])
    result = []
    for record in records:
        item = from_omm(record, source=manifest.get("sources", {}).get(str(record["NORAD_CAT_ID"]), manifest["source_url"]), retrieved_at=retrieved_at)
        if manifest["hashes"].get(str(item.norad_id)) != item.sha256:
            raise ValueError(f"snapshot checksum mismatch for {item.norad_id}")
        result.append(item)
    return result
