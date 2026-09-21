"""Emergency requests extend the request pool without changing the scenario."""

from dataclasses import replace
from datetime import timedelta

import pytest

from amis.demo import (
    CanonicalWindowProvider,
    REPLAN_START,
    build_emergency_replan_fixture,
)
from amis.domain import (
    EmergencyRequestPayload,
    EventType,
    MissionEvent,
    ObservationWindow,
    PlanChangeType,
    ReasonCode,
)
from amis.errors import InvalidEventError
from amis.session import MissionSession


class _CountingWindowProvider(CanonicalWindowProvider):
    def __init__(self) -> None:
        self.call_count = 0

    def generate(self, scenario, requests):
        self.call_count += 1
        return super().generate(scenario, requests)


def _planned_session():
    provider = _CountingWindowProvider()
    scenario, payload = build_emergency_replan_fixture()
    session = MissionSession(window_provider=provider)
    session.load_scenario(scenario)
    session.generate_windows()
    version_one = session.plan()
    session.step(300)
    return session, provider, scenario, payload, version_one


def _plan_signature(plan):
    return {
        "actions": [
            (action.request_id, action.window_id, action.start, action.end, action.status)
            for action in plan.actions
        ],
        "unscheduled": [
            (entry.request_id, entry.reason_code) for entry in plan.unscheduled
        ],
        "mission_utility": plan.mission_utility,
        "violation_count": plan.violation_count,
    }


def test_emergency_event_carries_the_complete_request_and_explicit_windows():
    session, provider, scenario, payload, _ = _planned_session()
    scenario_before = scenario.to_dict()

    event = session.inject_event(EventType.EMERGENCY_TASK, payload.to_dict())

    assert event.event_type is EventType.EMERGENCY_TASK
    assert event.payload == payload
    assert MissionEvent.from_dict(event.to_dict()) == event
    assert provider.call_count == 1
    assert session.get_scenario().to_dict() == scenario_before
    assert session.get_scenario().requests == scenario.requests
    assert session.get_request_pool()[-1] == payload.request
    assert session.get_windows()[-1:] == payload.windows
    assert session.get_state().active_event_ids == (event.id,)


def test_request_pool_is_the_scenario_requests_plus_every_applied_emergency_request():
    session, _, scenario, first_payload, _ = _planned_session()
    session.inject_emergency_request(first_payload.request, first_payload.windows)

    second_request = replace(first_payload.request, id="OBS-EMERGENCY-2")
    second_window = replace(
        first_payload.windows[0],
        id="WIN-OBS-EMERGENCY-2-1",
        request_id=second_request.id,
        start=REPLAN_START + timedelta(minutes=60),
        end=REPLAN_START + timedelta(minutes=75),
    )
    session.inject_emergency_request(second_request, (second_window,))

    assert [request.id for request in session.get_request_pool()] == [
        *(request.id for request in scenario.requests),
        first_payload.request.id,
        second_request.id,
    ]


def test_priority_tie_uses_deadline_and_explains_the_displaced_request():
    session, _, _, payload, version_one = _planned_session()
    event = session.inject_emergency_request(payload.request, payload.windows)

    version_two = session.replan()
    comparison = session.compare_versions(version_one.version, version_two.version)

    assert payload.request.priority == 5
    displaced_request = next(
        request for request in session.get_request_pool() if request.id == "OBS-C"
    )
    assert displaced_request.priority == payload.request.priority
    assert payload.request.deadline < displaced_request.deadline
    assert payload.request.id in {action.request_id for action in version_two.actions}
    assert "OBS-C" not in {action.request_id for action in version_two.actions}

    displaced = comparison.entry_for("OBS-C")
    assert displaced.change_type is PlanChangeType.DROPPED
    assert displaced.reason_code is ReasonCode.DISPLACED_BY_COMPETING_REQUEST
    trace = next(
        trace for trace in session.get_traces(version_two.id) if trace.request_id == "OBS-C"
    )
    assert trace.event_id == event.id
    assert trace.reason_code is ReasonCode.DISPLACED_BY_COMPETING_REQUEST
    assert trace.constraint_name == "overlap"
    assert "a competing request took its window" in trace.message


def test_metrics_and_comparison_report_the_changed_request_pool():
    session, _, scenario, payload, version_one = _planned_session()
    session.inject_emergency_request(payload.request, payload.windows)
    version_two = session.replan()

    metrics_before = session.get_metrics(version_one.id)
    metrics_after = session.get_metrics(version_two.id)
    comparison = session.compare_versions(1, 2)

    assert metrics_before.request_pool_size == len(scenario.requests)
    assert metrics_after.request_pool_size == len(scenario.requests) + 1
    assert metrics_before.request_pool_ids == {request.id for request in scenario.requests}
    assert metrics_after.request_pool_ids == {
        *(request.id for request in scenario.requests),
        payload.request.id,
    }
    assert comparison.metrics_before == metrics_before
    assert comparison.metrics_after == metrics_after
    assert comparison.request_pool_mismatch is True
    assert comparison.to_dict()["request_pool_mismatch"] is True


def test_reapplying_the_event_log_to_the_untouched_scenario_reproduces_the_mission():
    original, _, scenario, payload, _ = _planned_session()
    scenario_before = scenario.to_dict()
    original_event = original.inject_emergency_request(payload.request, payload.windows)
    original_plan = original.replan()

    replay = MissionSession(window_provider=CanonicalWindowProvider())
    replay.load_scenario(scenario)
    replay.generate_windows()
    replay.plan()
    replay.step((original_event.event_time - scenario.start_time).total_seconds())
    for recorded_event in original.get_events():
        restored = MissionEvent.from_dict(recorded_event.to_dict())
        replay.inject_event(restored.event_type, restored.payload)
    replay_plan = replay.replan()

    assert scenario.to_dict() == scenario_before
    assert replay.get_scenario().to_dict() == scenario_before
    assert replay.get_events() == original.get_events()
    assert replay.get_request_pool() == original.get_request_pool()
    assert replay.get_windows() == original.get_windows()
    assert replay.get_state() == original.get_state()
    assert _plan_signature(replay_plan) == _plan_signature(original_plan)
    assert replay.compare_versions(1, 2).entries == original.compare_versions(1, 2).entries


def test_invalid_emergency_windows_are_rejected_without_partial_changes():
    session, _, _, payload, _ = _planned_session()
    wrong_window = replace(
        payload.windows[0],
        request_id="OBS-SOMEONE-ELSE",
    )
    windows_before = session.get_windows()
    request_pool_before = session.get_request_pool()

    with pytest.raises(InvalidEventError, match="does not belong"):
        session.inject_emergency_request(payload.request, (wrong_window,))

    assert session.get_events() == ()
    assert session.get_windows() == windows_before
    assert session.get_request_pool() == request_pool_before


def test_fixture_has_the_expected_competing_window():
    scenario, payload = build_emergency_replan_fixture()
    original_window = next(
        window
        for window in CanonicalWindowProvider().generate(scenario, scenario.requests)
        if window.request_id == "OBS-C"
    )

    assert payload.request.priority == 5
    assert next(request for request in scenario.requests if request.id == "OBS-C").priority == 5
    assert payload.windows == (
        ObservationWindow(
            id="WIN-OBS-EMERGENCY-1",
            request_id="OBS-EMERGENCY",
            satellite_id=scenario.satellite.id,
            start=original_window.start,
            end=original_window.end,
        ),
    )
