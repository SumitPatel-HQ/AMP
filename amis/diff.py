"""compare_plans: classify every request across two plan versions.

The comparison keys on request id rather than list position, so two
plans that hold the same placements in a different order compare equal.
It reads only the two plans, so any two versions compare, not just
adjacent ones.

A move and an insert need a reason the plans alone do not carry, so the
caller passes the reason codes the stored impact recorded against the
previous plan. The fallbacks below apply when no impact explains the
change, which is the case for a comparison drawn long after the event.
"""

from __future__ import annotations

from typing import Mapping, Optional

from amis.domain import (
    ActionStatus,
    MissionPlan,
    PlanChangeType,
    PlanDiff,
    PlanDiffEntry,
    ReasonCode,
    ScheduledAction,
)

CHANGED_CHANGE_TYPES = (
    PlanChangeType.MOVED,
    PlanChangeType.INSERTED,
    PlanChangeType.DROPPED,
)


def rebuilt_actions(
    previous: MissionPlan, current: MissionPlan
) -> tuple[ScheduledAction, ...]:
    """The earlier version's unfrozen actions: the ones replanning rebuilt.

    A frozen action is carried into the next version unchanged, its id
    included, while every rebuilt action is minted afresh. An action of
    the earlier version that the later version does not hold is therefore
    one replanning was free to move or drop.

    Deriving the split this way rather than from the current simulated
    time is what keeps plan churn fixed once it has been measured. Read
    against the live clock, the same pair of versions would report a
    smaller churn as the mission runs on, because actions would drift out
    of the denominator one by one.
    """

    carried_over_ids = {action.id for action in current.actions}
    return tuple(
        action for action in previous.actions if action.id not in carried_over_ids
    )


def compare_plans(
    previous: MissionPlan,
    current: MissionPlan,
    reasons_by_request: Optional[Mapping[str, ReasonCode]] = None,
) -> PlanDiff:
    reasons = dict(reasons_by_request or {})
    previous_actions = {action.request_id: action for action in previous.actions}
    current_actions = {action.request_id: action for action in current.actions}
    current_unscheduled = {
        entry.request_id: entry.reason_code for entry in current.unscheduled
    }

    request_ids = sorted(
        set(previous_actions)
        | set(current_actions)
        | {entry.request_id for entry in previous.unscheduled}
        | set(current_unscheduled)
    )

    entries = tuple(
        _classify(
            request_id,
            previous_actions.get(request_id),
            current_actions.get(request_id),
            reasons.get(request_id),
            current_unscheduled.get(request_id),
        )
        for request_id in request_ids
    )
    return PlanDiff(
        from_plan_id=previous.id, to_plan_id=current.id, entries=entries
    )


def _classify(
    request_id: str,
    before: Optional[ScheduledAction],
    after: Optional[ScheduledAction],
    recorded_reason: Optional[ReasonCode],
    unscheduled_reason: Optional[ReasonCode],
) -> PlanDiffEntry:
    old_start = before.start if before else None
    new_start = after.start if after else None

    if after is not None and after.status is ActionStatus.COMPLETED:
        change_type = PlanChangeType.COMPLETED
        reason_code = ReasonCode.REQUEST_UNCHANGED
    elif before is not None and after is not None:
        if _is_same_placement(before, after):
            change_type = PlanChangeType.UNCHANGED
            reason_code = ReasonCode.REQUEST_UNCHANGED
        else:
            change_type = PlanChangeType.MOVED
            reason_code = recorded_reason or ReasonCode.ALTERNATIVE_WINDOW_AVAILABLE
    elif after is not None:
        change_type = PlanChangeType.INSERTED
        reason_code = recorded_reason or ReasonCode.ALTERNATIVE_WINDOW_AVAILABLE
    elif before is not None:
        change_type = PlanChangeType.DROPPED
        reason_code = (
            unscheduled_reason or recorded_reason or ReasonCode.NO_ALTERNATIVE_WINDOW
        )
    else:
        # Unscheduled in both versions. The request did not change, and the
        # plan's own unscheduled list still carries why it is not there.
        change_type = PlanChangeType.UNCHANGED
        reason_code = ReasonCode.REQUEST_UNCHANGED

    return PlanDiffEntry(
        request_id=request_id,
        change_type=change_type,
        reason_code=reason_code,
        old_start=old_start,
        new_start=new_start,
    )


def _is_same_placement(before: ScheduledAction, after: ScheduledAction) -> bool:
    return before.start == after.start and before.window_id == after.window_id
