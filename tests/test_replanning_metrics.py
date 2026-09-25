"""Replanning metrics: churn, explanation coverage, and replanning time."""

from datetime import timedelta

from amis.demo import (
    CanonicalWindowProvider,
    REPLAN_START,
    build_canonical_replan_scenario,
)
from amis.domain import ReasonCode
from amis.session import MissionSession


def _planned_session() -> MissionSession:
    session = MissionSession(window_provider=CanonicalWindowProvider())
    session.load_scenario(build_canonical_replan_scenario())
    session.generate_windows()
    session.plan()
    return session


def _blocked_session() -> MissionSession:
    session = _planned_session()
    session.step(300)
    session.inject_cloud_block("OBS-B", "WIN-OBS-B-1")
    return session


def test_churn_counts_changed_unfrozen_actions_and_coverage_reaches_one():
    session = _blocked_session()
    version_one = session.get_plan()
    unfrozen_before = [
        action
        for action in version_one.actions
        if action.start > session.get_state().simulated_time
    ]
    assert len(unfrozen_before) == 4

    version_two = session.replan()
    metrics = session.get_metrics(version_two.id)

    assert metrics.plan_churn == 1 / 4
    assert metrics.explanation_coverage == 1.0


def test_the_first_version_reports_no_churn_and_no_coverage():
    session = _planned_session()

    metrics = session.get_metrics()

    assert metrics.plan_churn is None
    assert metrics.explanation_coverage is None


def test_replanning_with_no_event_leaves_churn_at_zero():
    session = _planned_session()

    version_two = session.replan()
    metrics = session.get_metrics(version_two.id)

    assert metrics.plan_churn == 0.0
    assert all(
        entry.change_type.value in ("UNCHANGED", "COMPLETED")
        for entry in session.compare_versions(1, 2).entries
    )


def test_churn_and_coverage_are_null_rather_than_a_score_when_nothing_can_change():
    session = _planned_session()
    session.step(2 * 60 * 60)  # every action has started by 12:00
    assert all(
        action.start <= session.get_state().simulated_time
        for action in session.get_plan().actions
    )

    version_two = session.replan()
    metrics = session.get_metrics(version_two.id)

    assert metrics.plan_churn is None
    assert metrics.explanation_coverage is None


def test_replanning_time_is_recorded_apart_from_initial_planning_time():
    session = _blocked_session()
    version_one = session.get_plan()

    version_two = session.replan()

    assert session.get_metrics(version_one.id).planning_time_ms == version_one.planning_time_ms
    assert session.get_metrics(version_two.id).planning_time_ms == version_two.planning_time_ms
    assert version_two.planning_time_ms > 0.0


def test_metrics_for_a_later_version_still_name_the_request_pool_they_cover():
    session = _blocked_session()
    version_two = session.replan()

    metrics = session.get_metrics(version_two.id)

    assert metrics.request_pool_size == 5
    assert metrics.request_pool_ids == {
        request.id for request in session.get_request_pool()
    }
    assert metrics.to_dict()["plan_churn"] == 0.25


def test_the_moved_request_is_the_only_thing_the_comparison_reports_as_changed():
    session = _blocked_session()
    session.replan()

    comparison = session.compare_versions(1, 2)
    moved = comparison.entry_for("OBS-B")

    assert moved.old_start == REPLAN_START + timedelta(minutes=20)
    assert moved.new_start == REPLAN_START + timedelta(minutes=75)
    assert [
        entry.request_id
        for entry in comparison.entries
        if entry.change_type.value != "UNCHANGED"
    ] == ["OBS-B"]


def test_churn_does_not_drift_as_the_mission_runs_on_past_the_replan():
    session = _blocked_session()
    version_two = session.replan()
    churn_at_replan = session.get_metrics(version_two.id).plan_churn

    session.step(60 * 60)  # 11:05, so the moved action has now started

    assert churn_at_replan == 1 / 4
    assert session.get_metrics(version_two.id).plan_churn == churn_at_replan


def test_a_non_adjacent_comparison_keeps_the_reason_the_impact_recorded():
    session = _blocked_session()
    session.replan()
    session.replan()

    moved = session.compare_versions(1, 3).entry_for("OBS-B")

    assert moved.reason_code is ReasonCode.WINDOW_INVALIDATED


def test_both_sides_of_a_comparison_are_measured_at_the_same_instant():
    session = _blocked_session()
    version_two = session.replan()
    session.step(600)

    comparison = session.compare_versions(1, version_two.version)

    now = session.get_state().simulated_time
    assert comparison.metrics_before.measured_at == now
    assert comparison.metrics_after.measured_at == now
