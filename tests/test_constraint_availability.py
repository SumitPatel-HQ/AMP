"""Unit tests for check_satellite_availability.

Drives the check through the Wave 3 payload-outage path (an
`SATELLITE_UNAVAILABLE` span) as well as the base availability flag.
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
    assert violation.subject_key == "OBS-A"
