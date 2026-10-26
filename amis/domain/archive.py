"""Recorded point-imagery evidence. Validation is entirely offline.

Coverage uses straight edges in geographic longitude/latitude coordinates,
including the boundary. This initial runtime supports simple Polygon rings
without holes, spanning less than 180 degrees longitude. Other geometries
fail closed; D-02 owns catalogue normalization and candidate selection.
"""

from __future__ import annotations

import copy
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, fields
from datetime import datetime
from types import MappingProxyType
from typing import Any
from urllib.parse import urlsplit

from amis.time import parse_utc_iso_timestamp


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    return value


def _number(value: Any, name: str, low: float, high: float = math.inf) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be an explicit finite number")
    if not low <= value <= high:
        raise ValueError(f"{name} is outside its valid bounds")
    return value


def _require_non_empty_str(value: Any, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"archive evidence requires nonempty {name}")


def validate_suitability_profile(profile: Mapping[str, Any]) -> None:
    """One owner for explicit author requirements, including no-match builds."""
    profile = _freeze(profile)
    required = {"version", "allowed_collections", "acquisition_start", "acquisition_end",
                "max_cloud_cover_pct", "max_gsd_m", "sensor_product_assertion"}
    if not isinstance(profile, Mapping) or not required <= profile.keys() or profile.keys() - required - {"max_view_angle_deg"}:
        raise ValueError("archive profile has missing or unsupported requirements")
    _require_non_empty_str(profile["version"], "profile version")
    _require_non_empty_str(profile["sensor_product_assertion"], "sensor/product assertion")
    collections = profile["allowed_collections"]
    if not isinstance(collections, tuple) or not collections:
        raise ValueError("archive profile requires allowed collections")
    for collection in collections:
        _require_non_empty_str(collection, "allowed collection")
    if parse_utc_iso_timestamp(profile["acquisition_start"]) > parse_utc_iso_timestamp(profile["acquisition_end"]):
        raise ValueError("archive profile acquisition interval is reversed")
    _number(profile["max_cloud_cover_pct"], "max_cloud_cover_pct", 0, 100)
    if _number(profile["max_gsd_m"], "max_gsd_m", 0) <= 0:
        raise ValueError("archive profile max_gsd_m must be positive")
    if "max_view_angle_deg" in profile:
        _number(profile["max_view_angle_deg"], "max_view_angle_deg", 0, 90)


@dataclass(frozen=True)
class ArchiveSatisfactionPayload:
    request_id: str
    catalogue_source: str
    collection_id: str
    item_id: str
    source_url: str
    source_response_sha256: str
    source_credit: str
    acquisition_start: str
    acquisition_end: str
    retrieved_at: str
    target_lat: float
    target_lon: float
    footprint: Mapping[str, Any]
    cloud_cover_pct: float
    gsd_m: float
    profile: Mapping[str, Any]
    policy_version: str
    view_angle_deg: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "footprint", _freeze(self.footprint))
        object.__setattr__(self, "profile", _freeze(self.profile))

    def to_dict(self) -> dict[str, Any]:
        result = {field.name: _json_value(getattr(self, field.name)) for field in fields(self)}
        if self.view_angle_deg is None:
            result.pop("view_angle_deg")
        return result

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ArchiveSatisfactionPayload:
        # Own the nested evidence: callers cannot rewrite accepted provenance.
        return ArchiveSatisfactionPayload(**copy.deepcopy(data))

    def validate(self, satisfaction_time: datetime) -> None:
        for field in ("request_id", "catalogue_source", "collection_id", "item_id", "source_credit"):
            _require_non_empty_str(getattr(self, field), field)
        _require_non_empty_str(self.source_url, "source_url")
        url = urlsplit(self.source_url)
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ValueError("archive source_url must be an HTTPS URL without credentials")
        if not isinstance(self.source_response_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", self.source_response_sha256):
            raise ValueError("archive source_response_sha256 must be a lowercase SHA-256 digest")
        if self.policy_version != "archive-point-v1":
            raise ValueError("unsupported archive policy version")
        profile = self.profile
        validate_suitability_profile(profile)
        collections = profile["allowed_collections"]
        if self.collection_id not in collections:
            raise ValueError("archive collection is not allowed by the profile")
        start, end = parse_utc_iso_timestamp(self.acquisition_start), parse_utc_iso_timestamp(self.acquisition_end)
        allowed_start, allowed_end = parse_utc_iso_timestamp(profile["acquisition_start"]), parse_utc_iso_timestamp(profile["acquisition_end"])
        if not allowed_start <= start <= end <= allowed_end or end > satisfaction_time:
            raise ValueError("archive acquisition must fall wholly within the profile and precede satisfaction")
        if not end <= parse_utc_iso_timestamp(self.retrieved_at) <= satisfaction_time:
            raise ValueError("archive retrieval must demonstrate availability by satisfaction time")
        cloud = _number(self.cloud_cover_pct, "cloud_cover_pct", 0, 100)
        max_cloud = _number(profile["max_cloud_cover_pct"], "max_cloud_cover_pct", 0, 100)
        gsd = _number(self.gsd_m, "gsd_m", 0)
        max_gsd = _number(profile["max_gsd_m"], "max_gsd_m", 0)
        if gsd <= 0 or max_gsd <= 0 or cloud > max_cloud or gsd > max_gsd:
            raise ValueError("archive measured quality fails the suitability thresholds")
        if self.view_angle_deg is not None:
            _number(self.view_angle_deg, "view_angle_deg", 0, 90)
        if "max_view_angle_deg" in profile:
            limit = _number(profile["max_view_angle_deg"], "max_view_angle_deg", 0, 90)
            if self.view_angle_deg is None or self.view_angle_deg > limit:
                raise ValueError("archive requires a measured view angle within the profile limit")
        _number(self.target_lat, "target_lat", -90, 90)
        _number(self.target_lon, "target_lon", -180, 180)
        if not _covers(self.footprint, self.target_lon, self.target_lat):
            raise ValueError("archive footprint does not cover the target point")


def _cross(a: list[float], b: list[float], c: list[float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: list[float], b: list[float], p: list[float]) -> bool:
    return (_cross(a, b, p) == 0 and min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
            and min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))


def _intersects(a: list[float], b: list[float], c: list[float], d: list[float]) -> bool:
    return (any((_on_segment(a, b, c), _on_segment(a, b, d), _on_segment(c, d, a), _on_segment(c, d, b)))
            or (_cross(a, b, c) * _cross(a, b, d) < 0 and _cross(c, d, a) * _cross(c, d, b) < 0))


def _covers(geometry: Mapping[str, Any], x: float, y: float) -> bool:
    if not isinstance(geometry, Mapping) or geometry.get("type") != "Polygon":
        raise ValueError("archive coverage supports simple geographic Polygon footprints only")
    rings = geometry.get("coordinates")
    if not isinstance(rings, tuple) or len(rings) != 1 or not isinstance(rings[0], tuple):
        raise ValueError("archive coverage requires one exterior ring without holes")
    ring = rings[0]
    if len(ring) < 4 or ring[0] != ring[-1]:
        raise ValueError("archive footprint must be a closed polygon")
    for point in ring:
        if not isinstance(point, tuple) or len(point) != 2:
            raise ValueError("archive footprint positions must contain longitude and latitude")
        _number(point[0], "footprint longitude", -180, 180)
        _number(point[1], "footprint latitude", -90, 90)
    if max(p[0] for p in ring) - min(p[0] for p in ring) >= 180:
        raise ValueError("archive footprints spanning 180 degrees are unsupported")
    edges = list(zip(ring, ring[1:]))
    if any(a == b for a, b in edges) or sum(a[0] * b[1] - b[0] * a[1] for a, b in edges) == 0:
        raise ValueError("archive footprint is degenerate")
    for i, (a, b) in enumerate(edges):
        c = edges[(i + 1) % len(edges)][1]
        if _cross(a, b, c) == 0 and (b[0] - a[0]) * (c[0] - b[0]) + (b[1] - a[1]) * (c[1] - b[1]) < 0:
            raise ValueError("archive footprint has overlapping adjacent edges")
    for i, (a, b) in enumerate(edges):
        for j, (c, d) in enumerate(edges[i + 1:], i + 1):
            if j == i + 1 or (i == 0 and j == len(edges) - 1):
                continue
            if _intersects(a, b, c, d):
                raise ValueError("archive footprint is self-intersecting")
    inside = False
    for a, b in edges:
        if _on_segment(a, b, [x, y]):
            return True
        if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
            inside = not inside
    return inside
