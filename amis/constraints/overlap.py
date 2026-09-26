"""Overlap: one of the constraint engine's checks.

The satellite executes one observation at a time, so a candidate action
that overlaps any already scheduled action is rejected.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable, Optional

from amis.domain import ReasonCode, ScheduledAction, Violation


def check_overlap(
    request_id: str,
    start: datetime,
    end: datetime,
    other_actions: Iterable[ScheduledAction],
    min_gap_s: float = 0.0,
) -> Optional[Violation]:
    """One observation at a time, plus the mission settling gap.

    ``min_gap_s`` is the fixed settling time between observations: two
    actions conflict unless each starts at least the gap after the other
    ends. A zero gap is the historical overlap rule.
    """
    gap = timedelta(seconds=min_gap_s)
    for other in other_actions:
        # Downlink uses the communication subsystem, not the payload (ADR-0011).
        if other.is_downlink:
            continue
        if start < other.end + gap and other.start < end + gap:
            return Violation(
                reason_code=ReasonCode.TIME_OVERLAP,
                request_id=request_id,
                details={
                    "conflicting_action_id": other.id,
                    "conflicting_request_id": other.request_id,
                },
            )

    return None
