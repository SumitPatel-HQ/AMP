"""DecisionTrace: the record that ties one plan change to its cause."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from amis.domain.enums import ReasonCode
from amis.domain.plan import ScheduledAction


@dataclass(frozen=True)
class DecisionTrace:
    id: str
    plan_id: str
    reason_code: ReasonCode
    message: str
    event_id: Optional[str] = None
    request_id: Optional[str] = None
    previous_action: Optional[ScheduledAction] = None
    new_action: Optional[ScheduledAction] = None
    constraint_name: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "event_id": self.event_id,
            "request_id": self.request_id,
            "reason_code": self.reason_code.value,
            "previous_action": (
                self.previous_action.to_dict() if self.previous_action else None
            ),
            "new_action": self.new_action.to_dict() if self.new_action else None,
            "constraint_name": self.constraint_name,
            "message": self.message,
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "DecisionTrace":
        previous_action = data.get("previous_action")
        new_action = data.get("new_action")
        return DecisionTrace(
            id=data["id"],
            plan_id=data["plan_id"],
            reason_code=ReasonCode(data["reason_code"]),
            message=data["message"],
            event_id=data.get("event_id"),
            request_id=data.get("request_id"),
            previous_action=(
                ScheduledAction.from_dict(previous_action) if previous_action else None
            ),
            new_action=ScheduledAction.from_dict(new_action) if new_action else None,
            constraint_name=data.get("constraint_name"),
            metadata=dict(data.get("metadata", {})),
        )
