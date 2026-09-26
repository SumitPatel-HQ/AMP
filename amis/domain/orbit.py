"""Immutable orbital inputs carried by a mission, never fetched at runtime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class OrbitalElements:
    norad_id: int
    name: str
    international_designator: str
    epoch: datetime
    omm: dict[str, Any]
    source: str
    retrieved_at: datetime
    sha256: str
    tle_line1: str | None = None
    tle_line2: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "norad_id": self.norad_id, "name": self.name,
            "international_designator": self.international_designator,
            "epoch": self.epoch.isoformat(), "omm": self.omm,
            "source": self.source, "retrieved_at": self.retrieved_at.isoformat(),
            "sha256": self.sha256,
        }
        if self.tle_line1 is not None:
            result["tle_line1"] = self.tle_line1
            result["tle_line2"] = self.tle_line2
        return result

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "OrbitalElements":
        return OrbitalElements(
            norad_id=int(data["norad_id"]), name=data["name"],
            international_designator=data["international_designator"],
            epoch=datetime.fromisoformat(data["epoch"]), omm=data["omm"],
            source=data["source"], retrieved_at=datetime.fromisoformat(data["retrieved_at"]),
            sha256=data["sha256"], tle_line1=data.get("tle_line1"),
            tle_line2=data.get("tle_line2"),
        )


@dataclass(frozen=True)
class WindowPolicy:
    provider: str
    max_off_nadir_deg: float = 30.0
    min_sun_elevation_deg: float | None = 10.0
    settling_time_s: float = 0.0
    culmination_placement: bool = False
    # Wave 4 (ADR-0011): stations to compute contacts at, and the downlink
    # rate in megabytes per second. No stations means no contacts or downlink.
    ground_station_ids: tuple[str, ...] = ()
    downlink_rate_mb_s: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "max_off_nadir_deg": self.max_off_nadir_deg,
            "min_sun_elevation_deg": self.min_sun_elevation_deg,
            "settling_time_s": self.settling_time_s,
            "culmination_placement": self.culmination_placement,
            "ground_station_ids": list(self.ground_station_ids),
            "downlink_rate_mb_s": self.downlink_rate_mb_s,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "WindowPolicy":
        return WindowPolicy(
            provider=data["provider"],
            max_off_nadir_deg=data.get("max_off_nadir_deg", 30.0),
            min_sun_elevation_deg=data.get("min_sun_elevation_deg", 10.0),
            settling_time_s=data.get("settling_time_s", 0.0),
            culmination_placement=data.get("culmination_placement", False),
            ground_station_ids=tuple(data.get("ground_station_ids") or ()),
            downlink_rate_mb_s=data.get("downlink_rate_mb_s", 0.0),
        )
