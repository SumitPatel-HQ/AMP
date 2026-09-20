import json
from datetime import datetime, timezone

from amis.domain import ObservationRequest, Satellite, Scenario


def _build_scenario() -> Scenario:
    satellite = Satellite(
        id="SAT-001",
        battery_capacity_wh=1000.0,
        battery_charge_wh=875.5,
        storage_capacity_mb=2000.0,
        storage_usage_mb=120.0,
        available=True,
    )
    request = ObservationRequest(
        id="OBS-A",
        target_lat=12.97,
        target_lon=77.59,
        priority=5,
        duration_s=300.0,
        deadline=datetime(2026, 1, 2, 0, 0, tzinfo=timezone.utc),
        energy_cost_wh=50.0,
        storage_cost_mb=100.0,
    )
    return Scenario(
        id="SCN-001",
        name="Round trip scenario",
        start_time=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 2, 0, 0, tzinfo=timezone.utc),
        satellite=satellite,
        requests=(request,),
    )


def test_scenario_survives_json_round_trip():
    scenario = _build_scenario()

    serialised = json.dumps(scenario.to_dict())
    restored = Scenario.from_dict(json.loads(serialised))

    assert restored == scenario
