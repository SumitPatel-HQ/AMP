"""Errors raised by the AMIS application layer."""

from __future__ import annotations

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    INVALID_SCENARIO = "INVALID_SCENARIO"
    INVALID_EVENT = "INVALID_EVENT"
    CONSTRAINT_VIOLATION = "CONSTRAINT_VIOLATION"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    SIMULATION_STATE_ERROR = "SIMULATION_STATE_ERROR"
    PLAN_VERSION_CONFLICT = "PLAN_VERSION_CONFLICT"


class ApplicationError(Exception):
    code: ErrorCode

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


class InvalidScenarioError(ApplicationError, ValueError):
    """The supplied scenario is malformed or conflicts with a stored one."""

    code = ErrorCode.INVALID_SCENARIO


class SimulationStateError(ApplicationError, RuntimeError):
    """The requested operation is invalid for the simulation's current state."""

    code = ErrorCode.SIMULATION_STATE_ERROR


class InvalidEventError(ApplicationError, ValueError):
    """The event type or payload is invalid for the current scenario."""

    code = ErrorCode.INVALID_EVENT


class PlanVersionConflictError(ApplicationError, RuntimeError):
    """The caller replanned against a plan version that is no longer current."""

    code = ErrorCode.PLAN_VERSION_CONFLICT


class ConstraintViolationError(ApplicationError, ValueError):
    """A submitted operation directly violates a mission constraint."""

    code = ErrorCode.CONSTRAINT_VIOLATION


class ResourceNotFoundError(ApplicationError, LookupError):
    """A requested persisted resource does not exist."""

    code = ErrorCode.RESOURCE_NOT_FOUND
