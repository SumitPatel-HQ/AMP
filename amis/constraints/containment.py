"""Window containment: one of the constraint engine's checks.

Rejects a candidate placement that falls outside its observation
window, or whose window is itself invalid. Returns a structured
Violation rather than a bare boolean, so the explanation layer has
something authoritative to read.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from amis.domain import ObservationWindow, ReasonCode, Violation


def check_window_containment(
    request_id: str,
    window: ObservationWindow,
    start: datetime,
    end: datetime,
) -> Optional[Violation]:
    if not window.valid:
        return Violation(
            reason_code=ReasonCode.WINDOW_INVALIDATED,
            request_id=request_id,
            details={"window_id": window.id, "invalid_reason": window.invalid_reason},
        )

    if start < window.start or end > window.end:
        return Violation(
            reason_code=ReasonCode.WINDOW_INVALIDATED,
            request_id=request_id,
            details={
                "window_id": window.id,
                "window_start": window.start.isoformat(),
                "window_end": window.end.isoformat(),
                "candidate_start": start.isoformat(),
                "candidate_end": end.isoformat(),
            },
        )

    return None
