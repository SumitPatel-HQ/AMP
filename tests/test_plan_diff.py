"""Plan comparison: keyed by request id, never by list position."""

from datetime import datetime, timedelta, timezone

from amis.diff import compare_plans
from amis.domain import (
    ActionStatus,
    MissionPlan,
    PlanChangeType,
    ReasonCode,
    ScheduledAction,
    UnscheduledEntry,
)

START = datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc)


def _action(
    request_id: str,
    action_id: str,
    offset_minutes: int,
    window_id: str | None = None,
    status: ActionStatus = ActionStatus.PLANNED,
) -> ScheduledAction:
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
        status=status,
    )


def _plan(
    plan_id: str,
    version: int,
    actions: tuple[ScheduledAction, ...],
    unscheduled: tuple[UnscheduledEntry, ...] = (),
) -> MissionPlan:
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


def test_every_request_is_classified_with_a_reason_code_and_both_start_times_on_a_move():
    previous = _plan(
        "PLAN-001",
        1,
        (
            _action("OBS-A", "ACT-001", 0, status=ActionStatus.COMPLETED),
            _action("OBS-B", "ACT-002", 20, window_id="WIN-OBS-B-1"),
            _action("OBS-C", "ACT-003", 40),
            _action("OBS-D", "ACT-004", 60),
        ),
        (UnscheduledEntry("OBS-E", ReasonCode.INSUFFICIENT_BATTERY),),
    )
    current = _plan(
        "PLAN-002",
        2,
        (
            _action("OBS-A", "ACT-001", 0, status=ActionStatus.COMPLETED),
            _action("OBS-B", "ACT-005", 75, window_id="WIN-OBS-B-2"),
            _action("OBS-C", "ACT-006", 40),
            _action("OBS-F", "ACT-007", 100),
        ),
        (
            UnscheduledEntry("OBS-D", ReasonCode.TIME_OVERLAP),
            UnscheduledEntry("OBS-E", ReasonCode.INSUFFICIENT_BATTERY),
        ),
    )

    diff = compare_plans(
        previous, current, reasons_by_request={"OBS-B": ReasonCode.WINDOW_INVALIDATED}
    )

    assert diff.from_plan_id == "PLAN-001"
    assert diff.to_plan_id == "PLAN-002"
    assert [entry.request_id for entry in diff.entries] == [
        "OBS-A",
        "OBS-B",
        "OBS-C",
        "OBS-D",
        "OBS-E",
        "OBS-F",
    ]
    assert all(entry.reason_code is not None for entry in diff.entries)

    by_request = {entry.request_id: entry for entry in diff.entries}
    assert by_request["OBS-A"].change_type is PlanChangeType.COMPLETED
    assert by_request["OBS-C"].change_type is PlanChangeType.UNCHANGED
    assert by_request["OBS-C"].reason_code is ReasonCode.REQUEST_UNCHANGED
    assert by_request["OBS-E"].change_type is PlanChangeType.UNCHANGED

    moved = by_request["OBS-B"]
    assert moved.change_type is PlanChangeType.MOVED
    assert moved.old_start == START + timedelta(minutes=20)
    assert moved.new_start == START + timedelta(minutes=75)
    assert moved.reason_code is ReasonCode.WINDOW_INVALIDATED

    dropped = by_request["OBS-D"]
    assert dropped.change_type is PlanChangeType.DROPPED
    assert dropped.old_start == START + timedelta(minutes=60)
    assert dropped.new_start is None
    assert dropped.reason_code is ReasonCode.TIME_OVERLAP

    inserted = by_request["OBS-F"]
    assert inserted.change_type is PlanChangeType.INSERTED
    assert inserted.old_start is None
    assert inserted.new_start == START + timedelta(minutes=100)


def test_reordering_a_plans_action_list_does_not_change_the_comparison():
    actions = (
        _action("OBS-A", "ACT-001", 0),
        _action("OBS-B", "ACT-002", 20),
        _action("OBS-C", "ACT-003", 40),
    )
    previous = _plan("PLAN-001", 1, actions)
    current = _plan("PLAN-002", 2, tuple(reversed(actions)))

    diff = compare_plans(previous, current)

    assert all(
        entry.change_type is PlanChangeType.UNCHANGED for entry in diff.entries
    )
    assert compare_plans(_plan("PLAN-001", 1, tuple(reversed(actions))), current) == diff.__class__(
        from_plan_id="PLAN-001", to_plan_id="PLAN-002", entries=diff.entries
    )


def test_comparison_works_between_two_non_adjacent_versions():
    version_one = _plan("PLAN-001", 1, (_action("OBS-A", "ACT-001", 0),))
    version_three = _plan(
        "PLAN-003", 3, (_action("OBS-A", "ACT-009", 90, window_id="WIN-OBS-A-2"),)
    )

    diff = compare_plans(version_one, version_three)

    assert diff.from_plan_id == "PLAN-001"
    assert diff.to_plan_id == "PLAN-003"
    entry = diff.entry_for("OBS-A")
    assert entry.change_type is PlanChangeType.MOVED
    assert entry.reason_code is ReasonCode.ALTERNATIVE_WINDOW_AVAILABLE


def test_a_request_keeping_its_start_but_changing_window_is_a_move():
    previous = _plan("PLAN-001", 1, (_action("OBS-A", "ACT-001", 0, "WIN-OBS-A-1"),))
    current = _plan("PLAN-002", 2, (_action("OBS-A", "ACT-002", 0, "WIN-OBS-A-2"),))

    entry = compare_plans(previous, current).entry_for("OBS-A")

    assert entry.change_type is PlanChangeType.MOVED
    assert entry.old_start == entry.new_start


def test_diff_serialises_to_a_plain_dict():
    previous = _plan("PLAN-001", 1, (_action("OBS-A", "ACT-001", 0),))
    current = _plan("PLAN-002", 2, (), (UnscheduledEntry("OBS-A", ReasonCode.NO_ALTERNATIVE_WINDOW),))

    payload = compare_plans(previous, current).to_dict()

    assert payload["entries"] == [
        {
            "request_id": "OBS-A",
            "change_type": "DROPPED",
            "reason_code": "NO_ALTERNATIVE_WINDOW",
            "old_start": START.isoformat(),
            "new_start": None,
        }
    ]
