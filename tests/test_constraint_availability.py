"""Unit tests for check_satellite_availability.

No MVP event produces an unavailable satellite yet, so this test
builds the unavailable state by hand rather than driving it through
an event.
"""

from amis.constraints import check_satellite_availability
from amis.domain import ReasonCode


def test_available_satellite_passes():
    violation = check_satellite_availability("OBS-A", available=True)

    assert violation is None


def test_unavailable_satellite_fails():
    violation = check_satellite_availability("OBS-A", available=False)

    assert violation is not None
    assert violation.reason_code is ReasonCode.SATELLITE_UNAVAILABLE
    assert violation.request_id == "OBS-A"
