"""Offline archived-weather storage with hash-checked manifests (ADR-0012).

Raw Open-Meteo-style responses are committed under
``amis/data/weather/`` with a manifest holding the source URL,
retrieval time, and a SHA-256 per location. The application never
fetches weather: only this module reads the archive, and only the
threshold rule turns its samples into recorded ``CLOUD_BLOCK`` events.
Only ``scripts/fetch_weather_archive.py`` (developer-run) touches the
network.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from amis.weather.samples import CloudSample

WEATHER_DIR = Path(__file__).resolve().parents[1] / "data" / "weather"

DEFAULT_SOURCE = "open-meteo-archive"


def location_key(lat: float, lon: float) -> str:
    """Manifest key for one archived location, stable across writes and reads."""
    return f"{lat:.4f},{lon:.4f}"


def record_hash(record: dict[str, Any]) -> str:
    """Hash of the canonical JSON, so formatting changes never break the check."""
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class WeatherArchive:
    records: tuple[dict[str, Any], ...]
    source_url: str
    retrieved_at: datetime


def load_archive(manifest_path: Path | None = None) -> WeatherArchive:
    """Read the committed archive, verifying every raw record against the manifest."""
    manifest_file = manifest_path or (WEATHER_DIR / "manifest.json")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    data_file = manifest_file.parent / manifest["file"]
    records = json.loads(data_file.read_text(encoding="utf-8"))
    hashes = manifest.get("hashes", {})
    verified = []
    for record in records:
        key = location_key(record["latitude"], record["longitude"])
        if hashes.get(key) != record_hash(record):
            raise ValueError(f"weather archive checksum mismatch for {key}")
        verified.append(record)
    return WeatherArchive(
        records=tuple(verified),
        source_url=manifest["source_url"],
        retrieved_at=datetime.fromisoformat(manifest["retrieved_at"]),
    )


def normalize_archive(
    records: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    *,
    source: str = DEFAULT_SOURCE,
) -> tuple[CloudSample, ...]:
    """Flatten raw hourly responses into one sample per location and time.

    Each record follows the Open-Meteo archive shape
    (``latitude``, ``longitude``, ``hourly.time[]``,
    ``hourly.cloud_cover[]``). Times must carry a timezone so a replay
    can never misread them; coverage is a percentage.
    """
    samples: list[CloudSample] = []
    for record in records:
        try:
            lat = float(record["latitude"])
            lon = float(record["longitude"])
            times = record["hourly"]["time"]
            cover = record["hourly"]["cloud_cover"]
        except (KeyError, TypeError) as error:
            raise ValueError("weather record is missing hourly cloud fields") from error
        if len(times) != len(cover):
            raise ValueError(
                "weather record time and cloud_cover series disagree in length"
            )
        for raw_time, raw_cover in zip(times, cover):
            try:
                moment = datetime.fromisoformat(raw_time)
            except (TypeError, ValueError) as error:
                raise ValueError(f"weather sample time is not ISO-8601: {raw_time!r}") from error
            if moment.tzinfo is None:
                raise ValueError(f"weather sample time needs a timezone: {raw_time!r}")
            coverage = float(raw_cover)
            if not math.isfinite(coverage) or coverage < 0 or coverage > 100:
                raise ValueError(f"weather cloud cover is not a percentage: {raw_cover!r}")
            samples.append(
                CloudSample(
                    target_lat=lat,
                    target_lon=lon,
                    time=moment,
                    cloud_cover_pct=coverage,
                    source=source,
                )
            )
    return tuple(samples)
