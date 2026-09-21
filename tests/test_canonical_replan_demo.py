"""The canonical demonstration, asserted end to end and for repeatability."""

from typing import Any

from amis.demo import run_canonical_replan_demo

_WALL_CLOCK_FIELDS = ("created_at", "planning_time_ms")


def _without_wall_clock(value: Any) -> Any:
    """Creation timestamps and timing measurements are real, so they differ."""

    if isinstance(value, dict):
        return {
            key: _without_wall_clock(item)
            for key, item in value.items()
            if key not in _WALL_CLOCK_FIELDS
        }
    if isinstance(value, list):
        return [_without_wall_clock(item) for item in value]
    return value


def test_the_blocked_request_moves_from_1020_to_1115_and_says_why():
    record = run_canonical_replan_demo()
    version_one, version_two = record["plans"]

    start_by_request = {
        plan["version"]: {
            action["request_id"]: action["start"] for action in plan["actions"]
        }
        for plan in (version_one, version_two)
    }
    assert start_by_request[1]["OBS-B"] == "2026-09-21T10:20:00+00:00"
    assert start_by_request[2]["OBS-B"] == "2026-09-21T11:15:00+00:00"

    moved = next(
        entry
        for entry in record["comparison"]["entries"]
        if entry["request_id"] == "OBS-B"
    )
    assert moved["change_type"] == "MOVED"
    assert moved["reason_code"] == "WINDOW_INVALIDATED"
    assert moved["old_start"] == "2026-09-21T10:20:00+00:00"
    assert moved["new_start"] == "2026-09-21T11:15:00+00:00"

    assert len(record["traces"]) == 1
    trace = record["traces"][0]
    assert trace["request_id"] == "OBS-B"
    assert trace["reason_code"] == "WINDOW_INVALIDATED"
    assert trace["event_id"] == record["event"]["id"]
    assert trace["constraint_name"] == "window_containment"
    assert trace["previous_action"]["window_id"] == "WIN-OBS-B-1"
    assert trace["new_action"]["window_id"] == "WIN-OBS-B-2"
    assert "invalidated" in trace["message"]


def test_coverage_reaches_one_and_the_blocked_request_is_the_only_thing_that_moved():
    record = run_canonical_replan_demo()
    metrics_after = record["metrics"][1]

    assert metrics_after["explanation_coverage"] == 1.0
    # One of the four unfrozen actions moved, and the fixture holds five
    # requests, so a quarter is the smallest non-zero churn it can report.
    assert metrics_after["plan_churn"] == 1 / 4
    assert [
        entry["request_id"]
        for entry in record["comparison"]["entries"]
        if entry["change_type"] != "UNCHANGED"
    ] == ["OBS-B"]


def test_the_second_version_names_the_first_as_its_parent_and_keeps_it_intact():
    record = run_canonical_replan_demo()
    version_one, version_two = record["plans"]

    assert version_two["parent_plan_id"] == version_one["id"]
    assert version_two["version"] == 2

    frozen = [
        action
        for action in version_one["actions"]
        if action["request_id"] == "OBS-A"
    ]
    assert frozen == [
        action for action in version_two["actions"] if action["request_id"] == "OBS-A"
    ]


def test_two_runs_of_the_demo_produce_identical_json():
    first = _without_wall_clock(run_canonical_replan_demo())
    second = _without_wall_clock(run_canonical_replan_demo())

    assert first == second
