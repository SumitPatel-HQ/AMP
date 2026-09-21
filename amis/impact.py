"""Impact analysis against the plan active when an event is injected."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from amis.constraints import validate_plan
from amis.domain import (
    Impact,
    MissionPlan,
    MissionState,
    ObservationRequest,
    ObservationWindow,
    ReasonCode,
    Scenario,
)


def analyze_impact(
    impact_id: str,
    event_id: str,
    scenario: Scenario,
    mission_state: MissionState,
    requests: Iterable[ObservationRequest],
    windows: Iterable[ObservationWindow],
    plan: MissionPlan,
) -> Impact:
    """Classify each action once and retain every reason for invalid actions."""

    violations = validate_plan(scenario, mission_state, requests, windows, plan)
    reasons_by_request: dict[str, list[ReasonCode]] = defaultdict(list)
    for violation in violations:
        reasons = reasons_by_request[violation.request_id]
        if violation.reason_code not in reasons:
            reasons.append(violation.reason_code)

    frozen_action_ids: list[str] = []
    valid_unfrozen_action_ids: list[str] = []
    invalid_unfrozen_action_ids: list[str] = []
    reason_codes: dict[str, tuple[ReasonCode, ...]] = {}

    for action in plan.actions:
        if action.start <= mission_state.simulated_time:
            frozen_action_ids.append(action.id)
            continue

        action_reasons = tuple(reasons_by_request.get(action.request_id, ()))
        if action_reasons:
            invalid_unfrozen_action_ids.append(action.id)
            reason_codes[action.id] = action_reasons
        else:
            valid_unfrozen_action_ids.append(action.id)

    return Impact(
        id=impact_id,
        event_id=event_id,
        evaluated_plan_id=plan.id,
        frozen_action_ids=tuple(frozen_action_ids),
        valid_unfrozen_action_ids=tuple(valid_unfrozen_action_ids),
        invalid_unfrozen_action_ids=tuple(invalid_unfrozen_action_ids),
        reason_codes=reason_codes,
    )
