"""Decision traces and the templates their sentences render from.

A trace is written for every request the comparison classified as moved,
inserted, or dropped. The reason code is the authoritative record and
the sentence is presentation: the cause clause is keyed by reason code
and the change type selects the sentence frame it fills, so a message
cannot contradict the decision it describes. No language model takes
part, and the system must work with none present.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from amis.diff import CHANGED_CHANGE_TYPES
from amis.domain import (
    DecisionTrace,
    MissionPlan,
    PlanChangeType,
    PlanDiff,
    ReasonCode,
    ScheduledAction,
)
from amis.ids import TRACE_ID_PREFIX, format_id

_TIME_FORMAT = "%Y-%m-%d %H:%M"

_FRAME_BY_CHANGE_TYPE: dict[PlanChangeType, str] = {
    PlanChangeType.MOVED: "{request_id} moved from {old_start} to {new_start}",
    PlanChangeType.INSERTED: "{request_id} was scheduled at {new_start}",
    PlanChangeType.DROPPED: "{request_id} was dropped",
}

_CAUSE_BY_REASON_CODE: dict[ReasonCode, str] = {
    ReasonCode.WINDOW_INVALIDATED: "its observation window was invalidated",
    ReasonCode.INSUFFICIENT_BATTERY: "the projected battery could not cover it",
    ReasonCode.INSUFFICIENT_STORAGE: "the projected storage could not hold its data",
    ReasonCode.DEADLINE_VIOLATION: "no remaining window ends before its deadline",
    ReasonCode.TIME_OVERLAP: "every remaining window overlapped an action already scheduled",
    ReasonCode.SATELLITE_UNAVAILABLE: "the satellite is unavailable",
    ReasonCode.DISPLACED_BY_COMPETING_REQUEST: "a competing request took its window",
    ReasonCode.ALTERNATIVE_WINDOW_AVAILABLE: "an alternative window was available",
    ReasonCode.NO_ALTERNATIVE_WINDOW: "no other window fits it",
    ReasonCode.REQUEST_UNCHANGED: "nothing the event changed affected it",
}

_CONSTRAINT_BY_REASON_CODE: dict[ReasonCode, Optional[str]] = {
    ReasonCode.WINDOW_INVALIDATED: "window_containment",
    ReasonCode.NO_ALTERNATIVE_WINDOW: "window_containment",
    ReasonCode.INSUFFICIENT_BATTERY: "projected_battery",
    ReasonCode.INSUFFICIENT_STORAGE: "projected_storage",
    ReasonCode.DEADLINE_VIOLATION: "deadline",
    ReasonCode.TIME_OVERLAP: "overlap",
    ReasonCode.DISPLACED_BY_COMPETING_REQUEST: "overlap",
    ReasonCode.SATELLITE_UNAVAILABLE: "satellite_availability",
}


def build_traces(
    previous: MissionPlan,
    current: MissionPlan,
    diff: PlanDiff,
    event_id: Optional[str] = None,
    first_trace_number: int = 1,
) -> tuple[DecisionTrace, ...]:
    previous_actions = {action.request_id: action for action in previous.actions}
    current_actions = {action.request_id: action for action in current.actions}

    traces: list[DecisionTrace] = []
    for offset, entry in enumerate(
        entry for entry in diff.entries if entry.change_type in CHANGED_CHANGE_TYPES
    ):
        previous_action = previous_actions.get(entry.request_id)
        new_action = current_actions.get(entry.request_id)
        traces.append(
            DecisionTrace(
                id=format_id(TRACE_ID_PREFIX, first_trace_number + offset),
                plan_id=current.id,
                event_id=event_id,
                request_id=entry.request_id,
                reason_code=entry.reason_code,
                previous_action=previous_action,
                new_action=new_action,
                constraint_name=_CONSTRAINT_BY_REASON_CODE.get(entry.reason_code),
                message=render_message(
                    request_id=entry.request_id,
                    change_type=entry.change_type,
                    reason_code=entry.reason_code,
                    old_start=entry.old_start,
                    new_start=entry.new_start,
                ),
                metadata=_metadata(entry.change_type, previous_action, new_action),
            )
        )
    return tuple(traces)


def render_message(
    request_id: str,
    change_type: PlanChangeType,
    reason_code: ReasonCode,
    old_start: Optional[datetime] = None,
    new_start: Optional[datetime] = None,
) -> str:
    outcome = _FRAME_BY_CHANGE_TYPE[change_type].format(
        request_id=request_id,
        old_start=_format_time(old_start),
        new_start=_format_time(new_start),
    )
    return f"{outcome} because {_CAUSE_BY_REASON_CODE[reason_code]}."


def _metadata(
    change_type: PlanChangeType,
    previous_action: Optional[ScheduledAction],
    new_action: Optional[ScheduledAction],
) -> dict[str, object]:
    return {
        "change_type": change_type.value,
        "previous_window_id": previous_action.window_id if previous_action else None,
        "new_window_id": new_action.window_id if new_action else None,
    }


def _format_time(value: Optional[datetime]) -> str:
    return value.strftime(_TIME_FORMAT) if value else "an unrecorded time"
