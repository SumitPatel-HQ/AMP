"""Copyable scenario templates. The three legacy demos keep their builders."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from amis.demo import build_canonical_replan_scenario, build_emergency_replan_fixture
from amis.domain import ObservationRequest, OrbitalElements, Satellite, Scenario, WindowPolicy

_CUE_EXAMPLE_DIR = Path(__file__).resolve().parent / "data" / "examples" / "usgs-vanuatu-2026-10-08"
LANDSAT_8_NORAD_ID = 39084


def _agile_imager_satellite(orbit: OrbitalElements) -> Satellite:
    """The hypothetical agile imager shared by the orbital Example builders."""
    return Satellite("SAT-EO", 1000, 1000, 4000, 0, orbit=orbit)


def cloud_example() -> Scenario:
    cloud = build_canonical_replan_scenario()
    return replace(cloud, window_policy=WindowPolicy("canonical_demo"))


def legacy_examples() -> dict[str, Scenario]:
    cloud = build_canonical_replan_scenario()
    emergency, _ = build_emergency_replan_fixture()
    return {
        "cloud": replace(cloud, window_policy=WindowPolicy("canonical_demo")),
        "battery": replace(cloud, id="SCN-EX-BATTERY", name="Battery drop demo", window_policy=WindowPolicy("canonical_demo")),
        "emergency": replace(emergency, id="SCN-EX-EMERGENCY", window_policy=WindowPolicy("canonical_demo")),
    }


def examples() -> dict[str, Scenario]:
    result = legacy_examples()
    # Each bundled orbital Example is guarded independently: the optional
    # orbital stack (skyfield/sgp4) failing to load one must not silently
    # withhold an unrelated Example that would otherwise have built fine.
    try:
        result["orbital"] = orbital_example()
    except ModuleNotFoundError:
        # Legacy demo routes must keep working without the orbital stack.
        pass
    try:
        result["usgs-vanuatu-2026-10-08"] = usgs_vanuatu_example()
    except ModuleNotFoundError:
        pass
    return result


@lru_cache(maxsize=1)
def example_briefings() -> dict[str, str]:
    """Trainee-facing briefing text for Examples that bundle one.

    Loading never touches the network: the briefing is a committed file
    read offline, matching the rest of the bundled Example (ticket 03).
    Cached because every ``/examples`` list request would otherwise reread
    the same static file.
    """
    return {"usgs-vanuatu-2026-10-08": (_CUE_EXAMPLE_DIR / "briefing.md").read_text(encoding="utf-8")}


def orbital_example() -> Scenario:
    from amis.orbital.elements import catalogue

    orbit = catalogue()[0]
    start = orbit.epoch.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    end = start + timedelta(days=4)
    targets = (
        ("Bengaluru", 12.97, 77.59), ("Delhi", 28.61, 77.21),
        ("Mumbai", 19.08, 72.88), ("Chennai", 13.08, 80.27),
        ("Kolkata", 22.57, 88.36), ("Hyderabad", 17.38, 78.49),
        ("Jaipur", 26.91, 75.79), ("South Pacific", -40.0, -160.0),
    )
    return Scenario(
        id="SCN-EX-ORBITAL", name="Hypothetical agile imager on Landsat 8 orbit",
        start_time=start, end_time=end,
        satellite=_agile_imager_satellite(orbit),
        requests=tuple(ObservationRequest(
            id=f"OBS-{index}", target_lat=lat, target_lon=lon,
            priority=max(1, 5 - index // 2), duration_s=30,
            deadline=end, energy_cost_wh=20, storage_cost_mb=100,
            target_name=name,
        ) for index, (name, lat, lon) in enumerate(targets, 1)),
        window_policy=WindowPolicy("orbital", 30, 10),
    )


def usgs_vanuatu_example() -> Scenario:
    """Ticket 03: a dated, offline replay of a real archived USGS earthquake.

    Routine baseline demand only; the earthquake itself is not part of
    this pristine Scenario. ``scripts/run_usgs_vanuatu_replay.py``
    injects the bundled cue at its exact recorded time using existing
    mission lifecycle operations, after a baseline plan already exists.
    See ``amis/data/examples/usgs-vanuatu-2026-10-08/README.md``.
    """
    from amis.orbital.elements import catalogue

    orbit = next(item for item in catalogue() if item.norad_id == LANDSAT_8_NORAD_ID)
    # Both ends must stay within 14 days of the stored element epoch
    # (amis/orbital/validation.py); the epoch is ~2 weeks before this
    # earthquake, so the mission horizon is capped at the epoch's +14-day
    # boundary rather than a round multi-day span.
    start = datetime(2026, 10, 7, 12, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 8, 22, 30, 0, tzinfo=timezone.utc)
    targets = (
        ("Suva", -18.1416, 178.4419, 2),
        ("Honiara", -9.4280, 159.9498, 3),
        ("Noumea", -22.2758, 166.4580, 2),
    )
    return Scenario(
        id="SCN-EX-USGS-VANUATU", name="USGS M6.3 Vanuatu earthquake replay (2026-10-08)",
        start_time=start, end_time=end,
        satellite=_agile_imager_satellite(orbit),
        requests=tuple(ObservationRequest(
            id=f"OBS-{name.upper()}", target_lat=lat, target_lon=lon,
            priority=priority, duration_s=30, deadline=end,
            energy_cost_wh=20, storage_cost_mb=100, target_name=name,
        ) for name, lat, lon, priority in targets),
        # Wider off-nadir than orbital_example's: a hypothetical
        # wide-slew agile imager, named as hypothetical in the briefing,
        # so this real geometry has a daylight window before the cue's
        # policy deadline.
        window_policy=WindowPolicy("orbital", 60, 10),
    )
