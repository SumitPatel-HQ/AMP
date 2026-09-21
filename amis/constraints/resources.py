"""Projected battery and projected storage: two of the constraint engine's checks.

The planner projects resources forward along the plan in time order.
Battery never recharges, idle drain is zero, storage never frees, and
accounting floors at zero. A candidate action is checked against the
projection at its own start time, not against the satellite's current
totals, so an earlier-starting action cannot be validated against
resources a later-committed but earlier-starting action has already
claimed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from amis.domain import ReasonCode, ScheduledAction, Violation


def check_projected_battery(
    request_id: str,
    energy_cost_wh: float,
    battery_wh: float,
) -> Optional[Violation]:
    if energy_cost_wh > battery_wh:
        return Violation(
            reason_code=ReasonCode.INSUFFICIENT_BATTERY,
            request_id=request_id,
            details={"required_wh": energy_cost_wh, "available_wh": battery_wh},
        )

    return None


def check_projected_storage(
    request_id: str,
    storage_cost_mb: float,
    storage_used_mb: float,
    storage_capacity_mb: float,
) -> Optional[Violation]:
    if storage_used_mb + storage_cost_mb > storage_capacity_mb:
        return Violation(
            reason_code=ReasonCode.INSUFFICIENT_STORAGE,
            request_id=request_id,
            details={
                "required_mb": storage_cost_mb,
                "used_mb": storage_used_mb,
                "capacity_mb": storage_capacity_mb,
            },
        )

    return None


class ResourceProjection:
    def __init__(self, initial_battery_wh: float, initial_storage_used_mb: float) -> None:
        self._initial_battery_wh = initial_battery_wh
        self._initial_storage_used_mb = initial_storage_used_mb
        self._committed: list[ScheduledAction] = []

    def available_at(self, at: datetime) -> tuple[float, float]:
        battery_wh = self._initial_battery_wh
        storage_used_mb = self._initial_storage_used_mb
        for action in self._committed:
            if action.start <= at:
                battery_wh = max(0.0, battery_wh - action.energy_cost_wh)
                storage_used_mb = max(0.0, storage_used_mb + action.storage_cost_mb)
        return battery_wh, storage_used_mb

    def commit(self, action: ScheduledAction) -> None:
        self._committed.append(action)
