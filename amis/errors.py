"""Errors raised by the AMIS application layer."""

from __future__ import annotations

from typing import Any


class SimulationStateError(RuntimeError):
    """The requested operation is invalid for the simulation's current state."""

    code = "SIMULATION_STATE_ERROR"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


class InvalidEventError(ValueError):
    """The event type or payload is invalid for the current scenario."""

    code = "INVALID_EVENT"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


class PlanVersionConflictError(RuntimeError):
    """The caller replanned against a plan version that is no longer current."""

    code = "PLAN_VERSION_CONFLICT"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}
