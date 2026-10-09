"""Window-only feasibility result types (ADR-0015).

A feasibility answer lists each satellite's earliest observation window
that can hold a hypothetical candidate. It is window-only: it ignores the
current MissionPlan, resources, pairwise slew, active outages, and
reservations, so it never promises that the Planner will schedule the
candidate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


FEASIBILITY_SCOPE = "window_only"


class FeasibilityReason(str, Enum):
    NO_SUITABLE_WINDOW = "no_suitable_window"
    SATELLITE_UNAVAILABLE = "satellite_unavailable"


@dataclass(frozen=True)
class SatelliteFeasibility:
    """One satellite's earliest suitable window, or why it has none.

    ``earliest_start`` is the WindowPolicy-compatible proposed start and
    ``latest_finish`` the usable finish boundary: the earliest of window
    end, Scenario end, and candidate deadline. Every window and
    acquisition field is null exactly when ``reason`` is set.
    """

    satellite_id: str
    window_id: str | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    earliest_start: datetime | None = None
    latest_finish: datetime | None = None
    reason: FeasibilityReason | None = None

    @property
    def suitable(self) -> bool:
        return self.reason is None

    def to_dict(self) -> dict[str, Any]:
        def iso(value: datetime | None) -> str | None:
            return value.isoformat() if value is not None else None

        return {
            "satellite_id": self.satellite_id,
            "window_id": self.window_id,
            "window_start": iso(self.window_start),
            "window_end": iso(self.window_end),
            "earliest_start": iso(self.earliest_start),
            "latest_finish": iso(self.latest_finish),
            "reason": self.reason.value if self.reason is not None else None,
        }


@dataclass(frozen=True)
class FeasibilityResult:
    """The whole answer, echoing its inputs and search interval.

    The search always starts at the Scenario's simulation start, never at
    the current mission clock, and ends at the earlier of Scenario end and
    candidate deadline.
    """

    scenario_id: str
    target_lat: float
    target_lon: float
    duration_s: float
    deadline: datetime
    satellite_id: str | None
    search_start: datetime
    search_end: datetime
    results: tuple[SatelliteFeasibility, ...]
    earliest_satellite_id: str | None
    scope: str = FEASIBILITY_SCOPE

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "scope": self.scope,
            "target_lat": self.target_lat,
            "target_lon": self.target_lon,
            "duration_s": self.duration_s,
            "deadline": self.deadline.isoformat(),
            "satellite_id": self.satellite_id,
            "search_start": self.search_start.isoformat(),
            "search_end": self.search_end.isoformat(),
            "earliest_satellite_id": self.earliest_satellite_id,
            "results": [result.to_dict() for result in self.results],
        }
