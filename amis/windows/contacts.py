"""Ground-station contact windows from the stored orbit (ADR-0011)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Iterable

from amis.domain import ContactWindow, GroundStation, Scenario
from amis.windows.orbital import _ceil_second, _floor_second, pass_intervals


def compute_contacts(scenario: Scenario, stations: Iterable[GroundStation]) -> list[ContactWindow]:
    """Contacts per station, ordered by start, from the same pass search as targets."""
    stations = tuple(stations)
    orbit = scenario.satellite.orbit
    if not stations or orbit is None:
        return []
    from sgp4 import __version__ as sgp4_version
    from skyfield import __version__ as skyfield_version
    from skyfield.api import EarthSatellite, load, wgs84

    ts = load.timescale(builtin=True)
    satellite = EarthSatellite.from_omm(ts, orbit.omm)
    start = scenario.start_time.astimezone(timezone.utc)
    end = scenario.end_time.astimezone(timezone.utc)
    t0, t1 = ts.from_datetime(start), ts.from_datetime(end)
    contacts: list[ContactWindow] = []
    for station in stations:
        site = wgs84.latlon(station.lat, station.lon, elevation_m=station.altitude_m)
        source = (
            f"contact:skyfield-{skyfield_version}:sgp4-{sgp4_version}:"
            f"elements-{orbit.sha256}:mask-{station.min_elevation_deg}"
        )
        number = 1
        for raw_start, raw_end, peaks in pass_intervals(
            satellite, site, t0, t1, station.min_elevation_deg, start, end
        ):
            edge_start, edge_end = _ceil_second(max(raw_start, start)), _floor_second(min(raw_end, end))
            if edge_end <= edge_start:
                continue
            if peaks:
                peak_time, peak_elevation = max(peaks, key=lambda item: item[1])
            else:
                peak_time = edge_start + (edge_end - edge_start) / 2
                peak_elevation = float((satellite - site).at(ts.from_datetime(peak_time)).altaz()[0].degrees)
            contacts.append(ContactWindow(
                id=f"CON-{station.id}-{number}", station_id=station.id,
                satellite_id=scenario.satellite.id, start=edge_start, end=edge_end,
                peak_elevation_deg=round(peak_elevation, 6), peak_time=peak_time, source=source,
            ))
            number += 1
    return sorted(contacts, key=lambda contact: (contact.start, contact.id))


def apply_communication_outages(
    contacts: Iterable[ContactWindow],
    outages: Iterable[tuple[str, datetime, datetime]],
) -> list[ContactWindow]:
    """Mark every contact at an outaged station that overlaps the span invalid."""
    outages = tuple(outages)
    result = []
    for contact in contacts:
        lost = any(
            station_id == contact.station_id and contact.start < outage_end and outage_start < contact.end
            for station_id, outage_start, outage_end in outages
        )
        result.append(replace(contact, valid=False, invalid_reason="WINDOW_INVALIDATED") if lost else contact)
    return result
