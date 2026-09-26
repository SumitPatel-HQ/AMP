"""Ground-station catalogue with a hash-checked manifest (ADR-0011)."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from amis.domain import GroundStation

STATIONS_DIR = Path(__file__).resolve().parents[1] / "data" / "stations"


def stations_hash(stations: list[dict[str, Any]]) -> str:
    """Hash of the canonical JSON, so line-ending changes never break the check."""
    canonical = json.dumps(stations, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def station_catalogue() -> tuple[GroundStation, ...]:
    raw = json.loads((STATIONS_DIR / "stations.json").read_text(encoding="utf-8"))["stations"]
    manifest = json.loads((STATIONS_DIR / "manifest.json").read_text(encoding="utf-8"))
    if stations_hash(raw) != manifest["sha256"]:
        raise ValueError("ground-station catalogue checksum mismatch")
    return tuple(GroundStation.from_dict(entry) for entry in raw)


def stations_by_ids(ids: tuple[str, ...] | list[str]) -> tuple[GroundStation, ...]:
    catalogue = {station.id: station for station in station_catalogue()}
    missing = [station_id for station_id in ids if station_id not in catalogue]
    if missing:
        raise ValueError(f"unknown ground station ids: {', '.join(missing)}")
    return tuple(catalogue[station_id] for station_id in ids)
