"""Overlap: one of the constraint engine's checks.

The satellite executes one observation at a time, so a candidate action
that overlaps any already scheduled action is rejected. With a slew model
(ADR-0013) the required gap is pairwise: settling time plus the slew time
between the two targets. A slew conflict reports ``TIME_OVERLAP`` with the
required gap in its details.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable, Optional

from amis.domain import ReasonCode, ScheduledAction, Violation
from amis.dynamics.slew import SlewModel


def check_overlap(
    request_id: str,
    start: datetime,
    end: datetime,
    other_actions: Iterable[ScheduledAction],
    min_gap_s: float = 0.0,
    slew: Optional[SlewModel] = None,
) -> Optional[Violation]:
    """One observation at a time, plus the mission settling gap.

    ``min_gap_s`` is the fixed settling time between observations: two
    actions conflict unless each starts at least the gap after the other
    ends. A zero gap is the historical overlap rule. ``slew``, when given,
    replaces the fixed gap with its pairwise gap.
    """
    for other in other_actions:
        # Downlink uses the communication subsystem, not the payload (ADR-0011).
        if other.is_downlink:
            continue
        gap_s = slew.gap_s(request_id, other.request_id) if slew else min_gap_s
        gap = timedelta(seconds=gap_s)
        if start < other.end + gap and other.start < end + gap:
            details: dict[str, object] = {
                "conflicting_action_id": other.id,
                "conflicting_request_id": other.request_id,
            }
            if slew and slew.slew_time_s(request_id, other.request_id) > 0:
                details["required_gap_s"] = round(gap_s, 3)
            return Violation(
                reason_code=ReasonCode.TIME_OVERLAP,
                subject_key=request_id,
                details=details,
            )

    return None
