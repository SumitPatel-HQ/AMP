"""Strict USGS point normalization, selection, and duplicate handling."""

from __future__ import annotations

import math
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from amis.cues.archive import USGS_SOURCE


@dataclass(frozen=True)
class CueSample:
    source: str
    source_event_id: str
    target_lon: float
    target_lat: float
    event_time: datetime
    alert_level: str
    mag: float | None = None
    sig: float | None = None
    place: str | None = None


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number")
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError(f"{field} must be a finite number") from error
    if not math.isfinite(result):
        raise ValueError(f"{field} must be a finite number")
    return result


def _normalize_feature(feature: Any) -> CueSample:
    if not isinstance(feature, dict) or feature.get("type") != "Feature":
        raise ValueError("selected record must be a GeoJSON Feature")
    event_id = feature.get("id")
    if not isinstance(event_id, str) or not event_id.strip():
        raise ValueError("source event identifier must be a nonempty string")
    event_id = event_id.strip()
    geometry = feature.get("geometry")
    if not isinstance(geometry, dict) or geometry.get("type") != "Point":
        raise ValueError("geometry must be a GeoJSON Point")
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) < 2:
        raise ValueError("point coordinates require longitude then latitude")
    lon = _finite_number(coordinates[0], "longitude")
    lat = _finite_number(coordinates[1], "latitude")
    if not -180 <= lon <= 180:
        raise ValueError("longitude must be within [-180, 180]")
    if not -90 <= lat <= 90:
        raise ValueError("latitude must be within [-90, 90]")
    properties = feature.get("properties")
    if not isinstance(properties, dict):
        raise ValueError("properties must contain an epoch-millisecond time")
    raw_time = properties.get("time")
    milliseconds = _finite_number(raw_time, "time")
    if milliseconds != math.trunc(milliseconds):
        raise ValueError("time must be an integer epoch-millisecond value")
    try:
        # Integer arithmetic keeps millisecond precision and accepts pre-1970 times.
        seconds, remainder = divmod(raw_time if isinstance(raw_time, int) else int(milliseconds), 1000)
        event_time = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(
            seconds=seconds, milliseconds=remainder
        )
    except OverflowError as error:
        raise ValueError("time is outside the supported UTC datetime range") from error
    raw_alert = properties.get("alert")
    if raw_alert is None:
        alert = "unknown"
    elif isinstance(raw_alert, str) and raw_alert in ("red", "orange", "yellow", "green"):
        alert = raw_alert
    else:
        raise ValueError("alert must be red, orange, yellow, green, or absent/null")
    mag = None if properties.get("mag") is None else _finite_number(properties["mag"], "mag")
    sig = None if properties.get("sig") is None else _finite_number(properties["sig"], "sig")
    place = properties.get("place")
    return CueSample(
        source=USGS_SOURCE,
        source_event_id=event_id,
        target_lon=lon,
        target_lat=lat,
        event_time=event_time,
        alert_level=alert,
        mag=mag,
        sig=sig,
        place=place.strip() if isinstance(place, str) and place.strip() else None,
    )


def normalize_usgs(
    response: dict[str, Any],
    *,
    selected_event_ids: Collection[str] | None = None,
) -> tuple[CueSample, ...]:
    """Normalize all records or only explicitly selected ids, then sort and deduplicate.

    Every occurrence of a selected id is validated. Selection cannot conceal an
    update conflicting with another occurrence of that same id.
    """
    if response.get("type") != "FeatureCollection" or not isinstance(response.get("features"), list):
        raise ValueError("USGS response must be a GeoJSON FeatureCollection with a features list")
    selected = None if selected_event_ids is None else set(selected_event_ids)
    if selected is not None and (
        not selected or any(not isinstance(item, str) or not item.strip() for item in selected)
    ):
        raise ValueError("selection must contain nonempty source event identifiers")
    if selected is not None:
        selected = {item.strip() for item in selected}
    records: dict[tuple[str, str], CueSample] = {}
    found: set[str] = set()
    for index, feature in enumerate(response["features"]):
        if selected is not None and (
            not isinstance(feature, dict) or not isinstance(feature.get("id"), str)
            or feature["id"].strip() not in selected
        ):
            continue
        try:
            sample = _normalize_feature(feature)
        except ValueError as error:
            identifier = feature.get("id") if isinstance(feature, dict) else None
            raise ValueError(f"selected USGS record {index} ({identifier!r}): {error}") from error
        key = (sample.source, sample.source_event_id)
        previous = records.get(key)
        if previous is not None and previous != sample:
            raise ValueError(f"conflicting normalized records for {sample.source}:{sample.source_event_id}")
        records[key] = sample
        found.add(sample.source_event_id)
    if selected is not None and selected - found:
        raise ValueError(f"selected USGS event identifiers are missing: {', '.join(sorted(selected - found))}")
    return tuple(sorted(records.values(), key=lambda cue: (cue.event_time, cue.source, cue.source_event_id)))
