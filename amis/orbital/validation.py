"""Mission preview and hard orbital input checks, without persistence."""

from datetime import timedelta, timezone
from dataclasses import replace
import math
from typing import Any

from amis.domain import Scenario
from amis.orbital.elements import omm_hash
from amis.windows.selection import ScenarioWindowProvider


def preview(scenario: Scenario, provider: ScenarioWindowProvider | None = None, *, include_track: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    policy = scenario.window_policy
    orbit = scenario.satellite.orbit
    if policy is not None:
        if policy.provider not in ("synthetic", "canonical_demo", "orbital"):
            errors.append(f"Unknown window provider: {policy.provider}.")
        if not 0 <= policy.max_off_nadir_deg <= 60:
            errors.append("Maximum off-nadir angle must be within 0 to 60 degrees.")
        if policy.min_sun_elevation_deg is not None and not -10 <= policy.min_sun_elevation_deg <= 60:
            errors.append("Minimum sun elevation must be within -10 to 60 degrees or null.")
    if policy and policy.provider == "orbital":
        if orbit is None:
            errors.append("Orbital missions require satellite elements.")
        else:
            age = max(abs((scenario.start_time - orbit.epoch).total_seconds()), abs((scenario.end_time - orbit.epoch).total_seconds()))
            if age > 14 * 86400:
                errors.append("Mission must be within 14 days of the element epoch.")
            elif age > 7 * 86400:
                warnings.append("Elements are more than 7 days from part of this mission.")
            if orbit.sha256 != omm_hash(orbit.omm):
                errors.append("Orbital element checksum does not match its OMM fields.")
            try:
                from skyfield.api import EarthSatellite, load
                satellite = EarthSatellite.from_omm(load.timescale(builtin=True), orbit.omm)
                for instant in (scenario.start_time, scenario.end_time):
                    position = satellite.at(load.timescale(builtin=True).from_datetime(instant)).position.km
                    if not all(math.isfinite(float(value)) for value in position):
                        raise ValueError("propagation returned a nonfinite position")
            except (ValueError, KeyError, TypeError) as error:
                errors.append(f"Orbital elements cannot be propagated: {error}")
        if scenario.end_time - scenario.start_time > timedelta(days=7):
            errors.append("Orbital mission horizon cannot exceed 7 days.")
        if (policy.min_sun_elevation_deg is not None or policy.recharge_rate_w > 0) and not (
            scenario.start_time.astimezone(timezone.utc).date().isoformat() >= "2026-09-20"
            and scenario.end_time.astimezone(timezone.utc).date().isoformat() <= "2026-10-14"
        ):
            errors.append("Bundled Sun ephemeris covers 2026-09-20 through 2026-10-14.")
    if errors:
        return {"errors": errors, "warnings": warnings, "windows": [], "window_counts": {request.id: 0 for request in scenario.requests}, "ground_track": []}
    try:
        selected_provider = provider or ScenarioWindowProvider()
        windows = selected_provider.generate(scenario, scenario.requests)
    except (ValueError, KeyError, TypeError, OSError) as error:
        return {"errors": [f"Window generation failed: {error}"], "warnings": warnings, "windows": [], "window_counts": {request.id: 0 for request in scenario.requests}, "ground_track": []}
    counts = {request.id: sum(window.request_id == request.id for window in windows) for request in scenario.requests}
    possible_lengths: dict[str, float] = {}
    if policy and policy.provider == "orbital" and scenario.requests:
        short_requests = tuple(replace(request, duration_s=1) for request in scenario.requests)
        possible = selected_provider.generate(scenario, short_requests)
        possible_lengths = {request.id: max(((window.end - window.start).total_seconds() for window in possible if window.request_id == request.id), default=0) for request in scenario.requests}
    for request in scenario.requests:
        if request.deadline < scenario.start_time:
            warnings.append(f"{request.id}: deadline is before mission start.")
        elif request.deadline > scenario.end_time:
            warnings.append(f"{request.id}: deadline is after mission end.")
        if request.energy_cost_wh > scenario.satellite.battery_charge_wh:
            warnings.append(f"{request.id}: energy cost exceeds available battery.")
        if request.storage_cost_mb > scenario.satellite.storage_capacity_mb - scenario.satellite.storage_usage_mb:
            warnings.append(f"{request.id}: storage cost exceeds free storage.")
        if policy and policy.provider == "orbital" and counts[request.id] == 0:
            warnings.append(f"{request.id}: no observation window; check field of regard, sunlight, and duration.")
        if policy and policy.provider == "orbital" and possible_lengths[request.id] > 0 and request.duration_s > possible_lengths[request.id]:
            warnings.append(f"{request.id}: duration exceeds its longest geometric window ({possible_lengths[request.id]:.0f} s).")
    track = []
    if include_track and policy and policy.provider == "orbital":
        from amis.orbital.track import ground_track
        track = ground_track(scenario, scenario.start_time, scenario.end_time, 120)
    return {"errors": errors, "warnings": warnings, "windows": [window.to_dict() for window in windows], "window_counts": counts, "ground_track": track}
