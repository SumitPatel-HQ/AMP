"""Downlink reservations shared by every planner (ADR-0011).

Before imaging placement a planner reserves one downlink per valid contact
that ends after the current simulated time. After imaging placement the
reservations that free nothing under the resource walk are pruned and the
rest are numbered after the imaging actions.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from amis.constraints.resources import ResourceProjection
from amis.domain import (
    ActionKind,
    ContactWindow,
    MissionState,
    Scenario,
    ScheduledAction,
)
from amis.ids import ACTION_ID_PREFIX, format_id

_PENDING_PREFIX = "DL-PENDING-"


def reserve_downlinks(
    scenario: Scenario,
    mission_state: MissionState,
    contacts: Iterable[ContactWindow],
    frozen_actions: Iterable[ScheduledAction] = (),
) -> list[ScheduledAction]:
    policy = scenario.window_policy
    rate = policy.downlink_rate_mb_s if policy else 0.0
    if rate <= 0:
        return []
    used_contacts = {action.window_id for action in frozen_actions if action.is_downlink}
    reservations: list[ScheduledAction] = []
    for contact in sorted(contacts, key=lambda item: (item.start, item.id)):
        if not contact.valid or contact.id in used_contacts:
            continue
        start = max(contact.start, mission_state.simulated_time)
        if contact.end <= start:
            continue
        duration_s = (contact.end - start).total_seconds()
        reservations.append(ScheduledAction(
            id=f"{_PENDING_PREFIX}{len(reservations) + 1:04d}",
            request_id=None,
            satellite_id=scenario.satellite.id,
            window_id=contact.id,
            start=start,
            end=contact.end,
            energy_cost_wh=0.0,
            storage_cost_mb=-round(rate * duration_s, 6),
            kind=ActionKind.DOWNLINK,
            station_id=contact.station_id,
        ))
    return reservations


def finalize_downlinks(
    reservations: Iterable[ScheduledAction],
    projection: ResourceProjection,
    first_action_number: int,
) -> list[ScheduledAction]:
    """Drop reservations that free nothing; give the rest real action ids."""
    freed = projection.freed_by_downlinks()
    kept = [action for action in reservations if freed.get(action.id, 0.0) > 1e-9]
    return [
        replace(action, id=format_id(ACTION_ID_PREFIX, number))
        for number, action in enumerate(kept, first_action_number)
    ]
