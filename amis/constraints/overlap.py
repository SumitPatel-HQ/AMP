"""Overlap: one of the constraint engine's checks.

The satellite executes one observation at a time, so a candidate action
that overlaps any already scheduled action is rejected.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from amis.domain import ReasonCode, ScheduledAction, Violation


def check_overlap(
    request_id: str,
    start: datetime,
    end: datetime,
    other_actions: Iterable[ScheduledAction],
) -> Optional[Violation]:
    for other in other_actions:
        if start < other.end and other.start < end:
            return Violation(
                reason_code=ReasonCode.TIME_OVERLAP,
                request_id=request_id,
                details={
                    "conflicting_action_id": other.id,
                    "conflicting_request_id": other.request_id,
                },
            )

    return None
