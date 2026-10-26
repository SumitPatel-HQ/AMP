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
from typing import Mapping, Optional

from amis.diff import CHANGED_CHANGE_TYPES
from amis.domain import (
    DecisionTrace,
    MissionPlan,
    PlanChangeType,
    PlanDiff,
    ReasonCode,
    ScheduledAction,
    imaging_actions,
)
from amis.ids import TRACE_ID_PREFIX, format_id

_TIME_FORMAT = "%Y-%m-%d %H:%M"

_FRAME_BY_CHANGE_TYPE: dict[PlanChangeType, str] = {
    PlanChangeType.SATISFIED_BY_ARCHIVE: "{request_id} was satisfied by archive imagery",
    PlanChangeType.MOVED: "{request_id} moved from {old_start} to {new_start}",
    PlanChangeType.INSERTED: "{request_id} was scheduled at {new_start}",
    PlanChangeType.DROPPED: "{request_id} was dropped",
}

_CAUSE_BY_REASON_CODE: dict[ReasonCode, str] = {
    ReasonCode.SATISFIED_BY_ARCHIVE: "recorded evidence meets its explicit suitability profile",
    ReasonCode.WINDOW_INVALIDATED: "its observation window was invalidated",
    ReasonCode.INSUFFICIENT_BATTERY: "the projected battery could not cover it",
    ReasonCode.INSUFFICIENT_STORAGE: "the projected storage could not hold its data",
    ReasonCode.DEADLINE_VIOLATION: "no remaining window ends before its deadline",
    ReasonCode.TIME_OVERLAP: "every remaining window overlapped an action already scheduled",
    ReasonCode.COLLISION_AVOIDANCE_OUTAGE: "a conjunction-derived simulated payload outage overlaps its previous imaging placement",
    ReasonCode.SATELLITE_UNAVAILABLE: "the satellite is unavailable",
    ReasonCode.DISPLACED_BY_COMPETING_REQUEST: "a competing request took its window",
    ReasonCode.ALTERNATIVE_WINDOW_AVAILABLE: "an alternative window was available",
    ReasonCode.NO_ALTERNATIVE_WINDOW: "no other window fits it",
    ReasonCode.NO_OBSERVATION_WINDOW: "no observation window exists for its target during the mission",
    ReasonCode.REQUEST_UNCHANGED: "nothing the event changed affected it",
    ReasonCode.HIGHER_PRIORITY_TASK_INSERTED: "it entered the pool and was scheduled",
    ReasonCode.REBALANCED_FOR_REQUESTER_SHARE: "capacity was rebalanced for requester share at equal utility",
}

_CONSTRAINT_BY_REASON_CODE: dict[ReasonCode, Optional[str]] = {
    ReasonCode.WINDOW_INVALIDATED: "window_containment",
    ReasonCode.NO_ALTERNATIVE_WINDOW: "window_containment",
    ReasonCode.NO_OBSERVATION_WINDOW: "window_containment",
    ReasonCode.INSUFFICIENT_BATTERY: "projected_battery",
    ReasonCode.INSUFFICIENT_STORAGE: "projected_storage",
    ReasonCode.DEADLINE_VIOLATION: "deadline",
    ReasonCode.TIME_OVERLAP: "overlap",
    ReasonCode.DISPLACED_BY_COMPETING_REQUEST: "overlap",
    ReasonCode.COLLISION_AVOIDANCE_OUTAGE: "satellite_availability",
    ReasonCode.SATELLITE_UNAVAILABLE: "satellite_availability",
    ReasonCode.REBALANCED_FOR_REQUESTER_SHARE: "requester_share",
}


def build_traces(
    previous: MissionPlan,
    current: MissionPlan,
    diff: PlanDiff,
    event_id: Optional[str] = None,
    event_ids_by_request: Optional[Mapping[str, str]] = None,
    first_trace_number: int = 1,
    requester_ids_by_request: Optional[Mapping[str, str]] = None,
) -> tuple[DecisionTrace, ...]:
    """``event_id`` is the fallback (the overall triggering event, or the
    only event there is). ``event_ids_by_request`` overrides it per
    request when more than one event occurred since ``previous`` and a
    specific event can be attributed to that request's change (GAP-08);
    a request absent from the mapping (for example a newly arrived
    request with no previous action to check) keeps the fallback.
    """

    # Downlinks carry no request and produce no traces (ADR-0011).
    previous_actions = {action.request_id: action for action in imaging_actions(previous.actions)}
    current_actions = {action.request_id: action for action in imaging_actions(current.actions)}

    traces: list[DecisionTrace] = []
    for offset, entry in enumerate(
        entry for entry in diff.entries if entry.change_type in CHANGED_CHANGE_TYPES
    ):
        previous_action = previous_actions.get(entry.request_id)
        new_action = current_actions.get(entry.request_id)
        requester_id = (requester_ids_by_request or {}).get(entry.request_id)
        traces.append(
            DecisionTrace(
                id=format_id(TRACE_ID_PREFIX, first_trace_number + offset),
                plan_id=current.id,
                event_id=(event_ids_by_request or {}).get(entry.request_id, event_id),
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
                    requester_id=requester_id,
                ),
                metadata=_metadata(entry.change_type, previous_action, new_action, requester_id=requester_id),
            )
        )
    return tuple(traces)


def render_message(
    request_id: str,
    change_type: PlanChangeType,
    reason_code: ReasonCode,
    old_start: Optional[datetime] = None,
    new_start: Optional[datetime] = None,
    requester_id: Optional[str] = None,
) -> str:
    outcome = _FRAME_BY_CHANGE_TYPE[change_type].format(
        request_id=request_id,
        old_start=_format_time(old_start),
        new_start=_format_time(new_start),
    )
    if reason_code == ReasonCode.REBALANCED_FOR_REQUESTER_SHARE:
        if requester_id:
            return f"{outcome} because capacity was rebalanced for requester {requester_id} share at equal utility."
        return f"{outcome} because capacity was rebalanced for requester share at equal utility."
    return f"{outcome} because {_CAUSE_BY_REASON_CODE[reason_code]}."


def _metadata(
    change_type: PlanChangeType,
    previous_action: Optional[ScheduledAction],
    new_action: Optional[ScheduledAction],
    requester_id: Optional[str] = None,
) -> dict[str, object]:
    data: dict[str, object] = {
        "change_type": change_type.value,
        "previous_window_id": previous_action.window_id if previous_action else None,
        "new_window_id": new_action.window_id if new_action else None,
    }
    if requester_id is not None:
        data["requester_id"] = requester_id
    return data


def _format_time(value: Optional[datetime]) -> str:
    return value.strftime(_TIME_FORMAT) if value else "an unrecorded time"
