"""Copyable scenario templates. The three legacy demos keep their builders."""

from dataclasses import replace
from datetime import timedelta

from amis.demo import build_canonical_replan_scenario, build_emergency_replan_fixture
from amis.domain import ObservationRequest, Satellite, Scenario, WindowPolicy


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
    try:
        result["orbital"] = orbital_example()
    except ModuleNotFoundError:
        # The orbital stack (skyfield/sgp4) is optional at runtime: legacy
        # demo routes must keep working without it.
        pass
    return result


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
        satellite=Satellite("SAT-EO", 1000, 1000, 4000, 0, orbit=orbit),
        requests=tuple(ObservationRequest(
            id=f"OBS-{index}", target_lat=lat, target_lon=lon,
            priority=max(1, 5 - index // 2), duration_s=30,
            deadline=end, energy_cost_wh=20, storage_cost_mb=100,
            target_name=name,
        ) for index, (name, lat, lon) in enumerate(targets, 1)),
        window_policy=WindowPolicy("orbital", 30, 10),
    )
