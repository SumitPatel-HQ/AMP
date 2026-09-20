"""Violation: the structured result every constraint check returns."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from amis.domain.enums import ReasonCode


@dataclass(frozen=True)
class Violation:
    reason_code: ReasonCode
    request_id: str
    details: dict[str, Any] = field(default_factory=dict)
