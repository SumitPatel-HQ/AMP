"""Satellite availability: one of the constraint engine's checks.

No MVP event produces an unavailable satellite yet, but the check is
required and stays reachable for the deferred event that will.
"""

from __future__ import annotations

from typing import Optional

from amis.domain import ReasonCode, Violation


def check_satellite_availability(
    request_id: str,
    available: bool,
) -> Optional[Violation]:
    if not available:
        return Violation(reason_code=ReasonCode.SATELLITE_UNAVAILABLE, request_id=request_id)

    return None
