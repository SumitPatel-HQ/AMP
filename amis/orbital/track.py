"""Read-only ground-track samples from the mission's stored element set."""

from datetime import datetime, timedelta, timezone

from amis.domain import Scenario


def ground_track(scenario: Scenario, start: datetime, end: datetime, step_s: int) -> list[dict[str, object]]:
    from skyfield.api import EarthSatellite, load, wgs84

    if scenario.satellite.orbit is None:
        raise ValueError("scenario has no orbit")
    ts = load.timescale(builtin=True)
    satellite = EarthSatellite.from_omm(ts, scenario.satellite.orbit.omm)
    samples = []
    current = start.astimezone(timezone.utc)
    end = end.astimezone(timezone.utc)
    while current <= end:
        point = wgs84.subpoint(satellite.at(ts.from_datetime(current)))
        samples.append({
            "time": current.isoformat(), "lat": round(float(point.latitude.degrees), 6),
            "lon": round(float(point.longitude.degrees), 6),
            "altitude_km": round(float(point.elevation.km), 3),
        })
        current += timedelta(seconds=step_s)
    return samples
