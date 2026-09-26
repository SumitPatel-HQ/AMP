"""validate_plan: the constraint engine's aggregate check.

Runs every check against every action in one call and returns every
violation found, rather than stopping at the first. See ADR-0003 for
the frozen-action exemption. A started or completed action is frozen:
its resource cost is already reflected in mission_state, so it is
skipped for checks and for resource projection, but it still occupies
time for the overlap check against unfrozen actions.

Downlink actions (ADR-0011) are judged only against their contact: it
must still exist, be valid, and contain the action. Their violations use
the action id as the subject key. Every planned downlink is committed to
the projection before imaging is walked, so releases land at contact end.

Wave 6 (ADR-0013): overlap uses the pairwise slew gap and the battery walk
includes sunlight recharge, exactly as the planners do.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from amis.constraints.availability import check_satellite_availability
from amis.constraints.containment import check_window_containment
from amis.constraints.deadline import check_deadline
from amis.constraints.overlap import check_overlap
from amis.dynamics.slew import SlewModel
from amis.constraints.resources import (
    ResourceProjection,
    check_projected_battery,
    check_projected_storage,
)
from amis.domain import (
    ActionStatus,
    ContactWindow,
    MissionPlan,
    ReasonCode,
    MissionState,
    ObservationRequest,
    ObservationWindow,
    Scenario,
    Violation,
)


def validate_plan(
    scenario: Scenario,
    mission_state: MissionState,
    requests: Iterable[ObservationRequest],
    windows: Iterable[ObservationWindow],
    plan: MissionPlan,
    outage_intervals: Iterable[tuple[datetime, datetime]] = (),
    contacts: Iterable[ContactWindow] = (),
) -> list[Violation]:
    requests_by_id = {request.id: request for request in requests}
    windows_by_id = {window.id: window for window in windows}
    ordered_actions = sorted(plan.actions, key=lambda action: (action.start, action.id))
    outages = tuple(outage_intervals)
    slew = SlewModel.from_scenario(scenario, requests_by_id.values())

    contacts_by_id = {contact.id: contact for contact in contacts}

    projection = ResourceProjection.for_mission(scenario, mission_state)
    violations: list[Violation] = []

    for action in ordered_actions:
        if action.is_downlink and action.status is ActionStatus.PLANNED:
            projection.commit(action)
            contact = contacts_by_id.get(action.window_id)
            if (
                contact is None
                or not contact.valid
                or action.start < contact.start
                or action.end > contact.end
            ):
                violations.append(Violation(
                    reason_code=ReasonCode.WINDOW_INVALIDATED,
                    subject_key=action.subject_key,
                    details={"contact_id": action.window_id, "station_id": action.station_id},
                ))

    for index, action in enumerate(ordered_actions):
        if action.status is not ActionStatus.PLANNED or action.is_downlink:
            continue

        request = requests_by_id[action.request_id]
        window = windows_by_id[action.window_id]
        other_actions = ordered_actions[:index] + ordered_actions[index + 1 :]
        battery_wh, storage_used_mb = projection.available_at(action.start)

        checks = (
            check_window_containment(action.request_id, window, action.start, action.end),
            check_deadline(action.request_id, request.deadline, action.end),
            check_satellite_availability(
                action.request_id, mission_state.available, action.start, action.end, outages
            ),
            check_projected_battery(action.request_id, action.energy_cost_wh, battery_wh),
            check_projected_storage(
                action.request_id,
                action.storage_cost_mb,
                storage_used_mb,
                scenario.satellite.storage_capacity_mb,
            ),
            check_overlap(action.request_id, action.start, action.end, other_actions, slew=slew),
        )
        violations.extend(violation for violation in checks if violation is not None)
        projection.commit(action)

    return violations
