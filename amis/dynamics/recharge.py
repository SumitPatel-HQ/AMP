"""Sunlight recharge from orbit geometry (ADR-0013).

The battery gains ``recharge_rate_w`` watts whenever the satellite is
outside Earth's shadow. Sunlit intervals come from the stored orbit and
the bundled DE421 ephemeris, sampled every 30 seconds and refined to the
second by bisection, so the model stays offline and deterministic.
Missions without an orbit, or with a zero rate, gain nothing.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from amis.domain import OrbitalElements, Satellite, Scenario

_SAMPLE_S = 30

Interval = tuple[datetime, datetime]


@dataclass(frozen=True)
class RechargeModel:
    recharge_rate_w: float = 0.0
    sunlit: tuple[Interval, ...] = ()

    def gain_wh(self, start: datetime, end: datetime) -> float:
        """Energy gained over ``[start, end]``: rate times sunlit hours."""
        if self.recharge_rate_w <= 0 or end <= start:
            return 0.0
        sunlit_s = sum(
            max(0.0, (min(end, lit_end) - max(start, lit_start)).total_seconds())
            for lit_start, lit_end in self.sunlit
        )
        return self.recharge_rate_w * sunlit_s / 3600


NO_RECHARGE = RechargeModel()


def recharge_model(scenario: Scenario, satellite: Satellite | None = None) -> RechargeModel:
    """Sunlight recharge for one satellite (Wave 7, ADR-0014): each
    satellite's own orbit decides when it is in sunlight.

    ``satellite`` defaults to the first satellite so single-satellite
    callers keep working unchanged.
    """
    resolved = satellite or scenario.satellite
    policy = scenario.window_policy
    orbit = resolved.orbit
    rate = policy.recharge_rate_w if policy else 0.0
    if rate <= 0 or orbit is None:
        return NO_RECHARGE
    return RechargeModel(rate, sunlit_intervals(orbit, scenario.start_time, scenario.end_time))


def sunlit_intervals(orbit: OrbitalElements, start: datetime, end: datetime) -> tuple[Interval, ...]:
    return _sunlit_intervals(_OrbitKey(orbit), start.astimezone(timezone.utc), end.astimezone(timezone.utc))


class _OrbitKey:
    """Carries the OMM into the cache while hashing by element checksum."""

    def __init__(self, orbit: OrbitalElements) -> None:
        self.orbit = orbit

    def __hash__(self) -> int:
        return hash(self.orbit.sha256)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _OrbitKey) and other.orbit.sha256 == self.orbit.sha256


@lru_cache(maxsize=32)
def _sunlit_intervals(key: _OrbitKey, start: datetime, end: datetime) -> tuple[Interval, ...]:
    from skyfield.api import EarthSatellite, load, load_file  # type: ignore[import-untyped]

    from amis.windows.orbital import EPHEMERIS

    digest = hashlib.sha256(EPHEMERIS.read_bytes()).hexdigest()
    expected = json.loads((EPHEMERIS.parent / "manifest.json").read_text(encoding="utf-8"))["sha256"]
    if digest != expected:
        raise ValueError("bundled Sun ephemeris checksum mismatch")
    ts = load.timescale(builtin=True)
    satellite = EarthSatellite.from_omm(ts, key.orbit.omm)
    eph = load_file(str(EPHEMERIS))
    try:
        def lit(instant: datetime) -> bool:
            return bool(satellite.at(ts.from_datetime(instant)).is_sunlit(eph))

        span_s = int((end - start).total_seconds())
        offsets = list(range(0, span_s, _SAMPLE_S)) + [span_s]
        instants = [start + timedelta(seconds=offset) for offset in offsets]
        flags = [bool(flag) for flag in satellite.at(ts.from_datetimes(instants)).is_sunlit(eph)]

        def edge(before: datetime, after: datetime) -> datetime:
            # First whole second whose state matches ``after``.
            target = lit(after)
            while (after - before).total_seconds() > 1:
                middle = before + timedelta(seconds=int((after - before).total_seconds()) // 2)
                if lit(middle) == target:
                    after = middle
                else:
                    before = middle
            return after

        intervals: list[Interval] = []
        opened = start if flags[0] else None
        for index in range(1, len(instants)):
            if flags[index] == flags[index - 1]:
                continue
            at = edge(instants[index - 1], instants[index])
            if flags[index]:
                opened = at
            elif opened is not None:
                intervals.append((opened, at))
                opened = None
        if opened is not None:
            intervals.append((opened, end))
        return tuple(intervals)
    finally:
        eph.close()
