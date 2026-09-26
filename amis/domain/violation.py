"""Violation: the structured result every constraint check returns."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from amis.domain.enums import ReasonCode


@dataclass(frozen=True)
class Violation:
    """``subject_key`` is the request id for imaging, the action id for downlink (ADR-0011)."""

    reason_code: ReasonCode
    subject_key: str
    details: dict[str, Any] = field(default_factory=dict)
