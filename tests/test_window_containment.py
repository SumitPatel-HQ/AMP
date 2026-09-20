from datetime import datetime, timedelta, timezone

from amis.constraints import check_window_containment
from amis.domain import ObservationWindow, ReasonCode

WINDOW_START = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc)


def _window(valid: bool = True) -> ObservationWindow:
    return ObservationWindow(
        id="WIN-OBS-A-1",
        request_id="OBS-A",
        satellite_id="SAT-001",
        start=WINDOW_START,
        end=WINDOW_END,
        valid=valid,
    )


def test_action_inside_window_passes():
    violation = check_window_containment(
        "OBS-A",
        _window(),
        start=WINDOW_START,
        end=WINDOW_START + timedelta(minutes=10),
    )

    assert violation is None


def test_action_ending_after_window_fails():
    violation = check_window_containment(
        "OBS-A",
        _window(),
        start=WINDOW_START,
        end=WINDOW_END + timedelta(minutes=1),
    )

    assert violation is not None
    assert violation.reason_code is ReasonCode.WINDOW_INVALIDATED
    assert violation.request_id == "OBS-A"


def test_invalid_window_fails_even_when_action_fits_the_span():
    violation = check_window_containment(
        "OBS-A",
        _window(valid=False),
        start=WINDOW_START,
        end=WINDOW_START + timedelta(minutes=10),
    )

    assert violation is not None
    assert violation.reason_code is ReasonCode.WINDOW_INVALIDATED
