"""Slew: a pairwise setup time between consecutive imaging actions (ADR-0013).

Simplified angle-rate model, documented as approximate: the slew angle
between two targets is the angle their surface chord subtends at the
orbit altitude above the chord midpoint, and slew time is that angle
over a constant slew rate. It ignores the satellite's own motion between
the two looks, acceleration limits, and Earth curvature under the chord,
so it is a planning estimate rather than an attitude simulation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from math import asin, atan, cos, degrees, radians, sin, sqrt
from typing import Iterable

from amis.domain import ObservationRequest, Scenario
from amis.orbital.geometry import EARTH_RADIUS_KM, mean_altitude_km


def slew_angle_deg(
    lat_a: float, lon_a: float, lat_b: float, lon_b: float, altitude_km: float
) -> float:
    """Approximate pointing change between two ground targets, in degrees."""
    half_lat = radians(lat_b - lat_a) / 2
    half_lon = radians(lon_b - lon_a) / 2
    haversine = sin(half_lat) ** 2 + cos(radians(lat_a)) * cos(radians(lat_b)) * sin(half_lon) ** 2
    central = 2 * asin(min(1.0, sqrt(haversine)))
    chord_km = 2 * EARTH_RADIUS_KM * sin(central / 2)
    return degrees(2 * atan(chord_km / (2 * altitude_km)))


@dataclass(frozen=True)
class SlewModel:
    """Required gap between two actions: settling time plus slew time."""

    settling_time_s: float = 0.0
    slew_rate_deg_s: float = 0.0
    altitude_km: float = 0.0
    targets: dict[str, tuple[float, float]] = field(default_factory=dict)

    @staticmethod
    def from_scenario(scenario: Scenario, requests: Iterable[ObservationRequest]) -> "SlewModel":
        policy = scenario.window_policy
        orbit = scenario.satellite.orbit
        if policy is None:
            return SlewModel()
        # No orbit means no altitude to slew at: slew is zero, settling stays.
        altitude_km = mean_altitude_km(float(orbit.omm["MEAN_MOTION"])) if orbit else 0.0
        return SlewModel(
            settling_time_s=policy.settling_time_s,
            slew_rate_deg_s=policy.slew_rate_deg_s if orbit else 0.0,
            altitude_km=altitude_km,
            targets={request.id: (request.target_lat, request.target_lon) for request in requests},
        )

    def slew_time_s(self, request_a: str | None, request_b: str | None) -> float:
        if self.slew_rate_deg_s <= 0 or request_a is None or request_b is None:
            return 0.0
        a, b = self.targets.get(request_a), self.targets.get(request_b)
        if a is None or b is None:
            return 0.0
        return slew_angle_deg(*a, *b, self.altitude_km) / self.slew_rate_deg_s

    def gap_s(self, request_a: str | None, request_b: str | None) -> float:
        return self.settling_time_s + self.slew_time_s(request_a, request_b)

    def max_gap_s(self, request_ids: Iterable[str]) -> float:
        """Largest pairwise gap; the conservative fixed gap CP-SAT uses."""
        ids = sorted(set(request_ids))
        return max(
            (self.gap_s(a, b) for a, b in combinations(ids, 2)),
            default=self.settling_time_s,
        )
