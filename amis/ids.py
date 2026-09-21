"""Sequential id generation recovered from the records already stored.

Ids are deterministic and sequential per scenario, which is what lifts
the reproducibility claim from "the same plan" to "the same output". The
next number is recovered by reading the ids already present rather than
from a counter held on an object, because a session is rebuilt from the
repositories on every request and an in-memory counter would reset on
restart and collide.
"""

from __future__ import annotations

from typing import Iterable

PLAN_ID_PREFIX = "PLAN"
ACTION_ID_PREFIX = "ACT"
EVENT_ID_PREFIX = "EVT"
IMPACT_ID_PREFIX = "IMP"
TRACE_ID_PREFIX = "TRACE"

_NUMBER_WIDTH = 3


def format_id(prefix: str, number: int) -> str:
    return f"{prefix}-{number:0{_NUMBER_WIDTH}d}"


def next_number(prefix: str, existing_ids: Iterable[str]) -> int:
    highest = 0
    for existing_id in existing_ids:
        head, _, tail = existing_id.rpartition("-")
        if head == prefix and tail.isdigit():
            highest = max(highest, int(tail))
    return highest + 1


def next_id(prefix: str, existing_ids: Iterable[str]) -> str:
    return format_id(prefix, next_number(prefix, existing_ids))


FIRST_PLAN_ID = format_id(PLAN_ID_PREFIX, 1)
