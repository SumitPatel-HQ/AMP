from datetime import datetime, timedelta, timezone

from amis.constraints import check_deadline
from amis.domain import ReasonCode

DEADLINE = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_action_ending_before_deadline_passes():
    violation = check_deadline("OBS-A", DEADLINE, end=DEADLINE - timedelta(minutes=1))

    assert violation is None


def test_action_ending_after_deadline_fails():
    violation = check_deadline("OBS-A", DEADLINE, end=DEADLINE + timedelta(minutes=1))

    assert violation is not None
    assert violation.reason_code is ReasonCode.DEADLINE_VIOLATION
    assert violation.request_id == "OBS-A"
