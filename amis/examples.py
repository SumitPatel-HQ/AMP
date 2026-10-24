"""Copyable scenario templates. The three legacy demos keep their builders."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
import json

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
    result["fairness-balance"] = fairness_balance_example()
    result["fairness-strict-utility"] = fairness_strict_utility_example()
    result["cems-crete-2026-10-04"] = cems_crete_example()
    return result


@lru_cache(maxsize=1)
def example_briefings() -> dict[str, str]:
    """Trainee-facing briefing text for Examples that bundle one.

    Loading never touches the network: the briefing is a committed file
    read offline, matching the rest of the bundled Example (ticket 03).
    Cached because every ``/examples`` list request would otherwise reread
    the same static file.
    """
    briefings = {
        "usgs-vanuatu-2026-10-08": (_CUE_EXAMPLE_DIR / "briefing.md").read_text(encoding="utf-8"),
        "cems-crete-2026-10-04": (_CUE_EXAMPLE_DIR.parent / "cems-crete-2026-10-04" / "briefing.md").read_text(encoding="utf-8"),
    }
    briefings["fairness-balance"] = (
        "# Requester Fairness Balance Comparison\n\n"
        "This scenario demonstrates a multi-requester bottleneck where multiple distinct maximum-utility plans exist.\n\n"
        "## Expected Behavior\n\n"
        "- Under **Pure Utility (`utility`)**, the solver maximizes mission utility (6 priority units) by selecting OBS-3 and OBS-1, both from ORG-A, leaving ORG-B unserved with a fairness gap of 6.\n"
        "- Under **Utility-Then-Fairness (`utility_then_fairness`)**, the solver proves optimal total utility (6 priority units) in Stage 1, holds it fixed, and in Stage 2 minimizes the requester utility gap down to 0 by scheduling OBS-1 (ORG-A) and OBS-2 (ORG-B) without any loss of primary utility.\n"
        "- OBS-2 replaces OBS-3 with reason code `REBALANCED_FOR_REQUESTER_SHARE`.\n"
    )
    briefings["fairness-strict-utility"] = (
        "# Utility-Fixed Fairness Comparison\n\n"
        "This scenario demonstrates that primary mission utility is strictly held fixed before balancing requester utility.\n\n"
        "## Expected Behavior\n\n"
        "- Two high/medium-priority requests from ORG-A (OBS-A2 with priority 5, OBS-A1 with priority 3) compete against a lower-priority request from ORG-B (OBS-B1 with priority 2) in a 2-slot window.\n"
        "- Under **Pure Utility (`utility`)**, the solver schedules OBS-A2 and OBS-A1 for maximum total utility 8 (all ORG-A, fairness gap 8).\n"
        "- Under **Utility-Then-Fairness (`utility_then_fairness`)**, Stage 1 proves maximum utility is 8. Serving OBS-B1 would reduce total utility to 7 (OBS-A2 + OBS-B1) or 5. Because Stage 2 strictly constrains primary utility to the Stage 1 optimum (8), no rebalancing occurs.\n"
        "- The schedule preserves total utility 8 and the solver details report achieved gap 8 with zero rebalanced requests.\n"
    )
    return briefings


def cems_crete_example() -> Scenario:
    """Load the dated Scenario with its own stored orbital snapshot offline."""
    path = _CUE_EXAMPLE_DIR.parent / "cems-crete-2026-10-04" / "scenario.json"
    return Scenario.from_dict(json.loads(path.read_bytes()))


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


def fairness_balance_example() -> Scenario:
    """A scenario with multiple equal-utility plans exhibiting different requester shares.

    Demonstrates how ``utility_then_fairness`` reduces the requester fairness gap from 6
    to 0 without any sacrifice of total primary mission utility (holding fixed at 6).
    """
    satellite = Satellite("SAT-001", 1000.0, 1000.0, 4000.0, 0.0)
    start = datetime(2026, 10, 20, 0, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(seconds=100)
    requests = (
        ObservationRequest(
            id="OBS-1", target_lat=0.0, target_lon=0.0, priority=3, duration_s=40.0,
            deadline=end, energy_cost_wh=10.0, storage_cost_mb=10.0, requester_id="ORG-A",
            target_name="Alpha Priority Area 1",
        ),
        ObservationRequest(
            id="OBS-2", target_lat=0.0, target_lon=0.0, priority=3, duration_s=40.0,
            deadline=end, energy_cost_wh=10.0, storage_cost_mb=10.0, requester_id="ORG-B",
            target_name="Bravo Priority Area 1",
        ),
        ObservationRequest(
            id="OBS-3", target_lat=0.0, target_lon=0.0, priority=3, duration_s=40.0,
            deadline=end, energy_cost_wh=10.0, storage_cost_mb=10.0, requester_id="ORG-A",
            target_name="Alpha Priority Area 2",
        ),
    )
    return Scenario(
        id="SCN-EX-FAIRNESS-BALANCE",
        name="Requester fairness balance comparison",
        start_time=start,
        end_time=end,
        satellite=satellite,
        requests=requests,
        window_policy=WindowPolicy("synthetic"),
    )


def fairness_strict_utility_example() -> Scenario:
    """A scenario where fairness cannot be improved because utility is held fixed.

    Demonstrates that ``utility_then_fairness`` strictly holds proven primary utility
    (8 priority units: OBS-A2 + OBS-A1) fixed, refusing to balance requester service
    with OBS-B1 because doing so would reduce primary mission utility to 7.
    """
    satellite = Satellite("SAT-001", 1000.0, 1000.0, 4000.0, 0.0)
    start = datetime(2026, 10, 20, 0, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(seconds=100)
    requests = (
        ObservationRequest(
            id="OBS-A1", target_lat=0.0, target_lon=0.0, priority=3, duration_s=40.0,
            deadline=end, energy_cost_wh=10.0, storage_cost_mb=10.0, requester_id="ORG-A",
            target_name="Alpha Medium-Priority Zone",
        ),
        ObservationRequest(
            id="OBS-A2", target_lat=0.0, target_lon=0.0, priority=5, duration_s=40.0,
            deadline=end, energy_cost_wh=10.0, storage_cost_mb=10.0, requester_id="ORG-A",
            target_name="Alpha High-Priority Zone",
        ),
        ObservationRequest(
            id="OBS-B1", target_lat=0.0, target_lon=0.0, priority=2, duration_s=40.0,
            deadline=end, energy_cost_wh=10.0, storage_cost_mb=10.0, requester_id="ORG-B",
            target_name="Bravo Low-Priority Zone",
        ),
    )
    return Scenario(
        id="SCN-EX-FAIRNESS-STRICT-UTILITY",
        name="Utility-fixed fairness comparison",
        start_time=start,
        end_time=end,
        satellite=satellite,
        requests=requests,
        window_policy=WindowPolicy("synthetic"),
    )
