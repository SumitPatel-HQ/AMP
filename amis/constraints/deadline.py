"""Deadline: one of the constraint engine's checks.

Rejects a candidate action that ends after its request's deadline.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from amis.domain import ReasonCode, Violation


def check_deadline(
    request_id: str,
    deadline: datetime,
    end: datetime,
) -> Optional[Violation]:
    if end > deadline:
        return Violation(
            reason_code=ReasonCode.DEADLINE_VIOLATION,
            request_id=request_id,
            details={"deadline": deadline.isoformat(), "end": end.isoformat()},
        )

    return None
