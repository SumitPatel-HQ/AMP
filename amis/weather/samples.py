"""Normalized cloud-coverage samples: one cloud fraction per target and time.

A sample is what the archive normaliser hands the threshold rule. It
carries no planning meaning on its own; the planner never sees samples,
only the recorded ``CLOUD_BLOCK`` events the rule derives from them
(ADR-0012).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class CloudSample:
    target_lat: float
    target_lon: float
    time: datetime
    cloud_cover_pct: float
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_lat": self.target_lat,
            "target_lon": self.target_lon,
            "time": self.time.isoformat(),
            "cloud_cover_pct": self.cloud_cover_pct,
            "source": self.source,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "CloudSample":
        return CloudSample(
            target_lat=data["target_lat"],
            target_lon=data["target_lon"],
            time=datetime.fromisoformat(data["time"]),
            cloud_cover_pct=data["cloud_cover_pct"],
            source=data["source"],
        )
