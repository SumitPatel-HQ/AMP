from datetime import datetime, timedelta, timezone

from amis.constraints import check_overlap
from amis.domain import ActionStatus, ReasonCode, ScheduledAction

WINDOW_START = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)


def _other_action() -> ScheduledAction:
    return ScheduledAction(
        id="ACT-001",
        request_id="OBS-A",
        satellite_id="SAT-001",
        window_id="WIN-OBS-A-1",
        start=WINDOW_START,
        end=WINDOW_START + timedelta(minutes=10),
        energy_cost_wh=50.0,
        storage_cost_mb=100.0,
        status=ActionStatus.PLANNED,
    )


def test_non_overlapping_action_passes():
    other = _other_action()

    violation = check_overlap(
        "OBS-B",
        start=other.end,
        end=other.end + timedelta(minutes=10),
        other_actions=[other],
    )

    assert violation is None


def test_overlapping_action_fails():
    other = _other_action()

    violation = check_overlap(
        "OBS-B",
        start=other.start + timedelta(minutes=5),
        end=other.end + timedelta(minutes=5),
        other_actions=[other],
    )

    assert violation is not None
    assert violation.reason_code is ReasonCode.TIME_OVERLAP
    assert violation.request_id == "OBS-B"
