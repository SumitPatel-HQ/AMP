"""Window-only feasibility: each satellite's earliest suitable window.

Pure over the Scenario and the candidate's provider windows (ADR-0015).
It reads no MissionPlan, MissionState, or event, so the answer does not
move with the mission clock or a replan.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

from amis.domain import (
    FeasibilityReason,
    FeasibilityResult,
    ObservationWindow,
    SatelliteFeasibility,
    Scenario,
)


def policy_start(
    scenario: Scenario, window: ObservationWindow, duration_s: float, latest_finish: datetime
) -> datetime | None:
    """The WindowPolicy-compatible start inside one window, or None.

    Under culmination placement the action is centred on the window's
    recorded culmination; a window that cannot hold that centred action is
    unsuitable even when it is long enough in total. Otherwise the action
    starts at the window start. Either way the action must finish by
    ``latest_finish``.
    """
    lower_bound = max(window.start, scenario.start_time)
    if duration_s > (latest_finish - lower_bound).total_seconds():
        return None
    duration = timedelta(seconds=duration_s)
    culmination = bool(scenario.window_policy and scenario.window_policy.culmination_placement)
    if culmination and window.peak_time is not None:
        # greedy._culmination_start bounds the centered action to the window;
        # cp_sat._ModelBuilder._prefer_culmination rounds and clamps its preference.
        # Feasibility instead requires containment through latest_finish.
        start = window.peak_time - duration / 2
    else:
        # Mirrors greedy._culmination_start's window-start fallback when no peak exists.
        # The Scenario start remains the lower bound for this read-only search.
        start = lower_bound
    if start < lower_bound or start + duration > latest_finish:
        return None
    return start


def assess_feasibility(
    scenario: Scenario,
    windows: Iterable[ObservationWindow],
    *,
    target_lat: float,
    target_lon: float,
    duration_s: float,
    deadline: datetime,
    satellite_id: str | None = None,
) -> FeasibilityResult:
    """One row per included satellite, suitable rows first.

    Suitable rows sort by earliest start then satellite id; unsuitable rows
    follow by satellite id. No satellite is omitted for lacking a window or
    being unavailable in the Scenario.
    """
    search_end = min(scenario.end_time, deadline)
    by_satellite: dict[str, list[ObservationWindow]] = {}
    for window in windows:
        if window.valid:
            by_satellite.setdefault(window.satellite_id, []).append(window)

    rows: list[SatelliteFeasibility] = []
    for satellite in scenario.satellites:
        if satellite_id is not None and satellite.id != satellite_id:
            continue
        if not satellite.available:
            rows.append(SatelliteFeasibility(satellite.id, reason=FeasibilityReason.SATELLITE_UNAVAILABLE))
            continue
        row = SatelliteFeasibility(satellite.id, reason=FeasibilityReason.NO_SUITABLE_WINDOW)
        for window in sorted(by_satellite.get(satellite.id, ()), key=lambda item: (item.start, item.id)):
            latest_finish = min(window.end, search_end)
            start = policy_start(scenario, window, duration_s, latest_finish)
            if start is not None:
                row = SatelliteFeasibility(
                    satellite_id=satellite.id,
                    window_id=window.id,
                    window_start=window.start,
                    window_end=window.end,
                    earliest_start=start,
                    latest_finish=latest_finish,
                )
                break
        rows.append(row)

    suitable = sorted(
        (row for row in rows if row.suitable),
        key=lambda row: (row.earliest_start, row.satellite_id),
    )
    unsuitable = sorted((row for row in rows if not row.suitable), key=lambda row: row.satellite_id)
    return FeasibilityResult(
        scenario_id=scenario.id,
        target_lat=target_lat,
        target_lon=target_lon,
        duration_s=duration_s,
        deadline=deadline,
        satellite_id=satellite_id,
        search_start=scenario.start_time,
        search_end=search_end,
        results=tuple(suitable + unsuitable),
        earliest_satellite_id=suitable[0].satellite_id if suitable else None,
    )
