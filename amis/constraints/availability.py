"""Satellite availability: one of the constraint engine's checks.

No MVP event produces an unavailable satellite yet, but the check is
required and stays reachable for the deferred event that will.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from amis.domain import ReasonCode, Violation


def check_satellite_availability(
    request_id: str,
    available: bool,
    action_start: datetime | None = None,
    action_end: datetime | None = None,
    outage_intervals: Iterable[tuple[datetime, datetime]] = (),
) -> Optional[Violation]:
    if not available:
        return Violation(reason_code=ReasonCode.SATELLITE_UNAVAILABLE, subject_key=request_id)
    if action_start is not None and action_end is not None:
        for outage_start, outage_end in outage_intervals:
            if action_start < outage_end and outage_start < action_end:
                return Violation(
                    reason_code=ReasonCode.SATELLITE_UNAVAILABLE,
                    subject_key=request_id,
                )

    return None
