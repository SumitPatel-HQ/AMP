"""Projected battery and projected storage: two of the constraint engine's checks.

The planner projects resources forward along the plan in time order.
Battery never recharges, idle drain is zero, storage never frees, and
accounting floors at zero. `ResourceProjection.check_commit` re-derives
the whole committed timeline in chronological order on every candidate
check, so a request accepted out of chronological order (the planner
commits in priority order, not time order) can never leave an
already-committed, later-starting action unaffordable: the check is run
before the commit happens, not after.
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

    def check_commit(
        self,
        request_id: str,
        start: datetime,
        energy_cost_wh: float,
        storage_cost_mb: float,
        storage_capacity_mb: float,
    ) -> Optional[Violation]:
        """Would committing this candidate keep the whole timeline affordable?

        Re-simulates every already-committed action plus the candidate in
        start-time order (not commit order) and floors/charges resources
        exactly like `available_at`/`commit` do. Returns the first
        violation found, whether it belongs to the candidate itself or to
        an action committed earlier but starting later, so the caller can
        reject this candidate placement before it corrupts an
        already-accepted action's feasibility.
        """
        ordered: list[tuple[datetime, str, float, float]] = [
            (action.start, action.id, action.energy_cost_wh, action.storage_cost_mb)
            for action in self._committed
        ]
        ordered.append((start, "", energy_cost_wh, storage_cost_mb))
        ordered.sort(key=lambda item: (item[0], item[1]))

        battery_wh = self._initial_battery_wh
        storage_used_mb = self._initial_storage_used_mb
        for _, _, item_energy_wh, item_storage_mb in ordered:
            if item_energy_wh > battery_wh:
                return Violation(
                    reason_code=ReasonCode.INSUFFICIENT_BATTERY,
                    request_id=request_id,
                    details={"required_wh": item_energy_wh, "available_wh": battery_wh},
                )
            if storage_used_mb + item_storage_mb > storage_capacity_mb:
                return Violation(
                    reason_code=ReasonCode.INSUFFICIENT_STORAGE,
                    request_id=request_id,
                    details={
                        "required_mb": item_storage_mb,
                        "used_mb": storage_used_mb,
                        "capacity_mb": storage_capacity_mb,
                    },
                )
            battery_wh = max(0.0, battery_wh - item_energy_wh)
            storage_used_mb = max(0.0, storage_used_mb + item_storage_mb)
        return None
