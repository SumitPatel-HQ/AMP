"""Decision traces: a reason code, its cause, and a sentence built from both."""

from datetime import datetime, timedelta, timezone

import pathlib
import re

from amis.diff import CHANGED_CHANGE_TYPES, compare_plans
from amis.domain import (
    MissionPlan,
    PlanChangeType,
    ReasonCode,
    ScheduledAction,
    UnscheduledEntry,
)
from amis.trace import build_traces, render_message

START = datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc)


def _action(request_id: str, action_id: str, offset_minutes: int, window_id: str | None = None):
    start = START + timedelta(minutes=offset_minutes)
    return ScheduledAction(
        id=action_id,
        request_id=request_id,
        satellite_id="SAT-001",
        window_id=window_id or f"WIN-{request_id}-1",
        start=start,
        end=start + timedelta(minutes=10),
        energy_cost_wh=10.0,
        storage_cost_mb=10.0,
    )


def _plan(plan_id, version, actions, unscheduled=()):
    return MissionPlan(
        id=plan_id,
        scenario_id="SCN-001",
        version=version,
        created_at=START,
        actions=actions,
        unscheduled=unscheduled,
        mission_utility=0.0,
        violation_count=len(unscheduled),
        planning_time_ms=0.0,
    )


def _cloud_block_versions():
    previous = _plan(
        "PLAN-001",
        1,
        (
            _action("OBS-A", "ACT-001", 0),
            _action("OBS-B", "ACT-002", 20, "WIN-OBS-B-1"),
            _action("OBS-D", "ACT-003", 60),
        ),
        (UnscheduledEntry("OBS-C", ReasonCode.TIME_OVERLAP),),
    )
    current = _plan(
        "PLAN-002",
        2,
        (
            _action("OBS-A", "ACT-001", 0),
            _action("OBS-B", "ACT-004", 75, "WIN-OBS-B-2"),
            _action("OBS-C", "ACT-005", 40),
        ),
        (UnscheduledEntry("OBS-D", ReasonCode.INSUFFICIENT_BATTERY),),
    )
    return previous, current


def test_every_moved_inserted_and_dropped_result_carries_a_full_trace():
    previous, current = _cloud_block_versions()
    diff = compare_plans(
        previous, current, reasons_by_request={"OBS-B": ReasonCode.WINDOW_INVALIDATED}
    )

    traces = build_traces(previous, current, diff, event_id="EVT-001")

    changed = {
        entry.request_id
        for entry in diff.entries
        if entry.change_type
        in (PlanChangeType.MOVED, PlanChangeType.INSERTED, PlanChangeType.DROPPED)
    }
    assert {trace.request_id for trace in traces} == changed == {"OBS-B", "OBS-C", "OBS-D"}
    assert [trace.id for trace in traces] == ["TRACE-001", "TRACE-002", "TRACE-003"]
    assert all(trace.plan_id == "PLAN-002" for trace in traces)
    assert all(trace.event_id == "EVT-001" for trace in traces)

    by_request = {trace.request_id: trace for trace in traces}

    moved = by_request["OBS-B"]
    assert moved.reason_code is ReasonCode.WINDOW_INVALIDATED
    assert moved.constraint_name == "window_containment"
    assert moved.previous_action.id == "ACT-002"
    assert moved.new_action.id == "ACT-004"
    assert moved.metadata["change_type"] == "MOVED"
    assert moved.message == (
        "OBS-B moved from 2026-09-21 10:20 to 2026-09-21 11:15 because its "
        "observation window was invalidated."
    )

    inserted = by_request["OBS-C"]
    assert inserted.previous_action is None
    assert inserted.new_action.id == "ACT-005"
    assert inserted.message == (
        "OBS-C was scheduled at 2026-09-21 10:40 because an alternative window "
        "was available."
    )

    dropped = by_request["OBS-D"]
    assert dropped.reason_code is ReasonCode.INSUFFICIENT_BATTERY
    assert dropped.constraint_name == "projected_battery"
    assert dropped.previous_action.id == "ACT-003"
    assert dropped.new_action is None
    assert dropped.message == (
        "OBS-D was dropped because the projected battery could not cover it."
    )


def test_unchanged_and_completed_results_get_no_trace():
    previous = _plan("PLAN-001", 1, (_action("OBS-A", "ACT-001", 0),))
    current = _plan("PLAN-002", 2, (_action("OBS-A", "ACT-001", 0),))

    assert build_traces(previous, current, compare_plans(previous, current)) == ()


def test_trace_ids_continue_from_the_traces_already_recorded():
    previous, current = _cloud_block_versions()
    diff = compare_plans(previous, current)

    traces = build_traces(previous, current, diff, first_trace_number=8)

    assert [trace.id for trace in traces] == ["TRACE-008", "TRACE-009", "TRACE-010"]


def test_every_reason_code_renders_a_message_from_a_template():
    for reason_code in ReasonCode:
        for change_type in CHANGED_CHANGE_TYPES:
            message = render_message(
                request_id="OBS-A",
                change_type=change_type,
                reason_code=reason_code,
                old_start=START,
                new_start=START + timedelta(minutes=10),
            )
            assert message.startswith("OBS-A ")
            assert message.endswith(".")
            assert "{" not in message


def test_trace_serialises_to_a_plain_dict():
    previous, current = _cloud_block_versions()
    diff = compare_plans(previous, current)

    payload = build_traces(previous, current, diff, event_id="EVT-001")[0].to_dict()

    assert payload["id"] == "TRACE-001"
    assert payload["event_id"] == "EVT-001"
    assert payload["new_action"]["id"] == "ACT-004"
    assert payload["previous_action"]["id"] == "ACT-002"
    assert isinstance(payload["message"], str)


def test_no_language_model_is_imported_anywhere_in_the_codebase():
    banned = re.compile(
        r"\b(?:import|from)\s+(?:openai|anthropic|transformers|llama_cpp|langchain|ollama|cohere|google\.generativeai)\b"
    )
    sources = list(pathlib.Path("amis").rglob("*.py")) + list(
        pathlib.Path("tests").rglob("*.py")
    )

    offenders = [
        str(path) for path in sources if banned.search(path.read_text(encoding="utf-8"))
    ]

    assert offenders == []
