"""Offline EO visibility windows from a stored OMM and local Sun ephemeris."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from amis.domain import ObservationRequest, ObservationWindow, Scenario
from amis.orbital.geometry import mean_altitude_km, off_nadir_angle, target_elevation_threshold

EPHEMERIS = Path(__file__).resolve().parents[1] / "data" / "ephemeris" / "de421-2026-09.bsp"


def _ceil_second(value: datetime) -> datetime:
    value = value.astimezone(timezone.utc)
    return value.replace(microsecond=0) + (timedelta(seconds=1) if value.microsecond else timedelta())


def _floor_second(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(microsecond=0)


def pass_intervals(satellite, observer, t0, t1, threshold: float, start: datetime, end: datetime):
    """Rise-to-set intervals above ``threshold`` with their culmination samples.

    Shared by target windows and ground-station contacts so both come from
    the same event-search call (spec decision 25).
    """
    times, events = satellite.find_events(observer, t0, t1, altitude_degrees=threshold)
    initial_elevation = (satellite - observer).at(t0).altaz()[0].degrees
    opened: datetime | None = start if initial_elevation >= threshold else None
    peaks: list[tuple[datetime, float]] = []
    intervals: list[tuple[datetime, datetime, list[tuple[datetime, float]]]] = []
    for time, event in zip(times, events):
        instant = time.utc_datetime()
        if event == 0:
            opened = instant
            peaks = []
        elif event == 1 and opened is not None:
            elevation = (satellite - observer).at(time).altaz()[0].degrees
            peaks.append((instant, float(elevation)))
        elif event == 2 and opened is not None:
            intervals.append((opened, instant, peaks))
            opened, peaks = None, []
    if opened is not None:
        intervals.append((opened, end, peaks))
    return intervals


class OrbitalWindowProvider:
    def generate(self, scenario: Scenario, requests: Iterable[ObservationRequest]) -> list[ObservationWindow]:
        from skyfield import __version__ as skyfield_version
        from skyfield.api import EarthSatellite, load, load_file, wgs84
        from sgp4 import __version__ as sgp4_version

        policy = scenario.window_policy
        if policy is None or policy.provider != "orbital":
            raise ValueError("orbital windows require a stored orbit and orbital policy")
        satellites = tuple(scenario.satellites)
        if any(satellite.orbit is None for satellite in satellites):
            raise ValueError("orbital windows require a stored orbit and orbital policy")
        # Wave 7 (ADR-0014): each satellite propagates against its own
        # orbit. A single-satellite mission keeps the pre-Wave-7 window id
        # exactly (`WIN-{request}-{n}`), so old plans stay byte identical.
        single = len(satellites) == 1
        ts = load.timescale(builtin=True)
        eph_hash = "unused"
        eph = None
        if policy.min_sun_elevation_deg is not None:
            eph_hash = hashlib.sha256(EPHEMERIS.read_bytes()).hexdigest()
            expected_hash = json.loads((EPHEMERIS.parent / "manifest.json").read_text(encoding="utf-8"))["sha256"]
            if eph_hash != expected_hash:
                raise ValueError("bundled Sun ephemeris checksum mismatch")
            eph = load_file(str(EPHEMERIS))
        min_sun = policy.min_sun_elevation_deg
        start = scenario.start_time.astimezone(timezone.utc)
        end = scenario.end_time.astimezone(timezone.utc)
        t0, t1 = ts.from_datetime(start), ts.from_datetime(end)
        requests = tuple(requests)
        windows: list[ObservationWindow] = []
        try:
            for orbital_satellite in satellites:
                orbit = orbital_satellite.orbit
                assert orbit is not None  # validated above; keeps mypy narrow
                satellite = EarthSatellite.from_omm(ts, orbit.omm)
                altitude = mean_altitude_km(float(orbit.omm["MEAN_MOTION"]))
                threshold = target_elevation_threshold(policy.max_off_nadir_deg, altitude)
                source = (
                    f"orbital:skyfield-{skyfield_version}:sgp4-{sgp4_version}:"
                    f"elements-{orbit.sha256}:de421-{eph_hash}:"
                    f"off-nadir-{policy.max_off_nadir_deg}:sun-{policy.min_sun_elevation_deg}:"
                    f"threshold-{threshold:.6f}"
                )
                for request in requests:
                    if request.satellite_id not in (None, orbital_satellite.id):
                        continue
                    target = wgs84.latlon(request.target_lat, request.target_lon)
                    intervals = pass_intervals(satellite, target, t0, t1, threshold, start, end)
                    number = 1
                    for raw_start, raw_end, local_peaks in intervals:
                        edge_start, edge_end = _ceil_second(max(raw_start, start)), _floor_second(min(raw_end, end))
                        if (edge_end - edge_start).total_seconds() < request.duration_s:
                            continue
                        if local_peaks:
                            peak_time, peak_elevation = max(local_peaks, key=lambda item: item[1])
                        else:
                            peak_time = edge_start + (edge_end - edge_start) / 2
                            peak_elevation = float((satellite - target).at(ts.from_datetime(peak_time)).altaz()[0].degrees)
                        if not math.isfinite(peak_elevation) or peak_elevation < threshold - 1e-6:
                            continue
                        sun_elevation = None
                        if eph is not None:
                            # Wave 1 has no per-request sensor type, so every request
                            # is treated as an optical daylight request while a sun
                            # minimum is set; null min_sun_elevation_deg means a
                            # sensor that needs no daylight and skips this filter.
                            sun_elevation = float((eph["earth"] + target).at(ts.from_datetime(peak_time)).observe(eph["sun"]).apparent().altaz()[0].degrees)
                            if not math.isfinite(sun_elevation) or (min_sun is not None and sun_elevation < min_sun):
                                continue
                        window_id = (
                            f"WIN-{request.id}-{number}" if single
                            else f"WIN-{request.id}-{orbital_satellite.id}-{number}"
                        )
                        windows.append(ObservationWindow(
                            id=window_id, request_id=request.id,
                            satellite_id=orbital_satellite.id, start=edge_start, end=edge_end,
                            peak_elevation_deg=round(peak_elevation, 6), peak_time=peak_time,
                            min_off_nadir_deg=round(off_nadir_angle(peak_elevation, altitude), 6),
                            sun_elevation_deg=round(sun_elevation, 6) if sun_elevation is not None else None,
                            source=source,
                        ))
                        number += 1
        finally:
            if eph is not None:
                eph.close()
        return windows
