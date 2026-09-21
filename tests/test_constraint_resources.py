from datetime import datetime, timedelta, timezone

from amis.constraints import ResourceProjection, check_projected_battery, check_projected_storage
from amis.domain import ActionStatus, ReasonCode, ScheduledAction

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_action_within_available_battery_passes():
    violation = check_projected_battery("OBS-A", energy_cost_wh=20.0, battery_wh=25.0)

    assert violation is None


def test_action_exceeding_available_battery_fails():
    violation = check_projected_battery("OBS-A", energy_cost_wh=30.0, battery_wh=25.0)

    assert violation is not None
    assert violation.reason_code is ReasonCode.INSUFFICIENT_BATTERY
    assert violation.request_id == "OBS-A"


def test_action_within_available_storage_passes():
    violation = check_projected_storage(
        "OBS-A", storage_cost_mb=50.0, storage_used_mb=900.0, storage_capacity_mb=1000.0
    )

    assert violation is None


def test_action_exceeding_available_storage_fails():
    violation = check_projected_storage(
        "OBS-A", storage_cost_mb=150.0, storage_used_mb=900.0, storage_capacity_mb=1000.0
    )

    assert violation is not None
    assert violation.reason_code is ReasonCode.INSUFFICIENT_STORAGE
    assert violation.request_id == "OBS-A"


def _action(id: str, start: datetime, energy_cost_wh: float, storage_cost_mb: float) -> ScheduledAction:
    return ScheduledAction(
        id=id,
        request_id=id,
        satellite_id="SAT-001",
        window_id=f"WIN-{id}-1",
        start=start,
        end=start + timedelta(minutes=5),
        energy_cost_wh=energy_cost_wh,
        storage_cost_mb=storage_cost_mb,
        status=ActionStatus.PLANNED,
    )


def test_projection_charges_battery_only_for_actions_starting_at_or_before_the_query_time():
    projection = ResourceProjection(initial_battery_wh=100.0, initial_storage_used_mb=0.0)
    projection.commit(_action("A", START, energy_cost_wh=40.0, storage_cost_mb=0.0))

    battery_before, _ = projection.available_at(START - timedelta(minutes=1))
    battery_after, _ = projection.available_at(START)

    assert battery_before == 100.0
    assert battery_after == 60.0


def test_battery_never_recharges_and_floors_at_zero():
    projection = ResourceProjection(initial_battery_wh=30.0, initial_storage_used_mb=0.0)
    projection.commit(_action("A", START, energy_cost_wh=50.0, storage_cost_mb=0.0))

    battery, _ = projection.available_at(START + timedelta(hours=1))

    assert battery == 0.0


def test_five_actions_costing_20_wh_are_rejected_once_25_wh_remains():
    projection = ResourceProjection(initial_battery_wh=25.0, initial_storage_used_mb=0.0)
    results = []

    for index in range(5):
        start = START + timedelta(minutes=10 * index)
        battery_wh, _ = projection.available_at(start)
        violation = check_projected_battery(f"OBS-{index}", energy_cost_wh=20.0, battery_wh=battery_wh)
        results.append(violation)
        if violation is None:
            projection.commit(_action(f"OBS-{index}", start, energy_cost_wh=20.0, storage_cost_mb=0.0))

    assert results[0] is None
    assert all(violation is not None for violation in results[1:])
    assert all(violation.reason_code is ReasonCode.INSUFFICIENT_BATTERY for violation in results[1:])
