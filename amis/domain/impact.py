"""Stored impact produced when a mission event is injected."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from amis.domain.enums import ReasonCode


@dataclass(frozen=True)
class Impact:
    id: str
    event_id: str
    evaluated_plan_id: str
    frozen_action_ids: tuple[str, ...]
    valid_unfrozen_action_ids: tuple[str, ...]
    invalid_unfrozen_action_ids: tuple[str, ...]
    reason_codes: dict[str, tuple[ReasonCode, ...]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "event_id": self.event_id,
            "evaluated_plan_id": self.evaluated_plan_id,
            "frozen_action_ids": list(self.frozen_action_ids),
            "valid_unfrozen_action_ids": list(self.valid_unfrozen_action_ids),
            "invalid_unfrozen_action_ids": list(self.invalid_unfrozen_action_ids),
            "reason_codes": {
                action_id: [reason.value for reason in reasons]
                for action_id, reasons in self.reason_codes.items()
            },
        }
