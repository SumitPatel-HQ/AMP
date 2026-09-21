"""PlanDiff and PlanDiffEntry: two plan versions compared by request id."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from amis.domain.enums import PlanChangeType, ReasonCode


@dataclass(frozen=True)
class PlanDiffEntry:
    request_id: str
    change_type: PlanChangeType
    reason_code: ReasonCode
    old_start: Optional[datetime] = None
    new_start: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "change_type": self.change_type.value,
            "reason_code": self.reason_code.value,
            "old_start": self.old_start.isoformat() if self.old_start else None,
            "new_start": self.new_start.isoformat() if self.new_start else None,
        }


@dataclass(frozen=True)
class PlanDiff:
    from_plan_id: str
    to_plan_id: str
    entries: tuple[PlanDiffEntry, ...]

    def entry_for(self, request_id: str) -> Optional[PlanDiffEntry]:
        return next(
            (entry for entry in self.entries if entry.request_id == request_id), None
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_plan_id": self.from_plan_id,
            "to_plan_id": self.to_plan_id,
            "entries": [entry.to_dict() for entry in self.entries],
        }
