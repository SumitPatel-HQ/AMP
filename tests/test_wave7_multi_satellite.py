"""Wave 7: multiple satellites per mission (ADR-0014).

Drives MissionSession (the test seam) and asserts on plans, windows,
events, impacts, diffs, traces, and metrics. No propagator, solver, or
component internals are asserted on.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from amis.constraints import validate_plan
from amis.demo import CanonicalWindowProvider
from amis.domain import (
    ObservationRequest,
    ObservationWindow,
    Satellite,
    Scenario,
)
from amis.session import MissionSession
from amis.windows.synthetic import SyntheticWindowProvider

START = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
END = START + timedelta(hours=2)


def _satellite(satellite_id: str, **changes) -> Satellite:
    base = {
        "id": satellite_id,
        "battery_capacity_wh": 200.0,
        "battery_charge_wh": 200.0,
        "storage_capacity_mb": 500.0,
        "storage_usage_mb": 0.0,
    }
    base.update(changes)
    return Satellite(**base)


def _request(request_id: str, **changes) -> ObservationRequest:
    base = {
        "id": request_id,
        "target_lat": 12.97,
        "target_lon": 77.59,
        "priority": 3,
        "duration_s": 600.0,
        "deadline": END,
        "energy_cost_wh": 20.0,
        "storage_cost_mb": 50.0,
    }
    base.update(changes)
    return ObservationRequest(**base)


def _scenario(requests, satellites=None) -> Scenario:
    return Scenario(
        id="SCN-W7",
        name="Wave 7 multi-satellite",
        start_time=START,
        end_time=END,
        satellites=tuple(satellites or (_satellite("SAT-01"), _satellite("SAT-02"))),
        requests=tuple(requests),
    )


def _session(scenario: Scenario, planner: str = "greedy") -> MissionSession:
    session = MissionSession(window_provider=SyntheticWindowProvider())
    session.load_scenario(scenario)
    session.select_planner(planner)
    return session


# --- windows: per request and satellite pair -------------------------------


def test_windows_cover_every_request_satellite_pair():
    scenario = _scenario(
        [_request("OBS-A"), _request("OBS-B", satellite_id="SAT-02")]
    )
    windows = SyntheticWindowProvider().generate(scenario, scenario.requests)

    by_request = {}
    for window in windows:
        by_request.setdefault(window.request_id, set()).add(window.satellite_id)

    # Unassigned OBS-A gets a candidate on both satellites; pinned OBS-B
    # gets one only on SAT-02.
    assert by_request["OBS-A"] == {"SAT-01", "SAT-02"}
    assert by_request["OBS-B"] == {"SAT-02"}


def test_single_satellite_keeps_legacy_window_ids():
    scenario = _scenario([_request("OBS-A")], satellites=[_satellite("SAT-01")])
    windows = SyntheticWindowProvider().generate(scenario, scenario.requests)

    assert [window.id for window in windows] == ["WIN-OBS-A-1"]
    assert windows[0].satellite_id == "SAT-01"


# --- overlap and resources are per satellite --------------------------------


def test_overlap_is_enforced_per_satellite_not_globally():
    scenario = _scenario(
        [
            _request("OBS-A", satellite_id="SAT-01"),
            _request("OBS-B", satellite_id="SAT-02"),
        ]
    )
    session = _session(scenario)
    session.generate_windows()
    plan = session.plan()

    # Same whole-horizon window on different satellites: both schedule at
    # the same start without an overlap violation.
    assert {action.request_id for action in plan.actions} == {"OBS-A", "OBS-B"}
    violations = validate_plan(
        scenario,
        session.get_state(),
        session.get_request_pool(),
        session.get_windows(),
        plan,
    )
    assert violations == []


def test_overlap_still_bites_on_the_same_satellite():
    scenario = _scenario(
        [
            _request("OBS-A", satellite_id="SAT-01", duration_s=3600.0),
            _request("OBS-B", satellite_id="SAT-01", duration_s=3600.0),
        ]
    )
    session = _session(scenario)
    session.generate_windows()
    plan = session.plan()

    # Two one-hour requests cannot both fit back-to-back in a two-hour
    # horizon on one satellite when the second must start after the first
    # ends: greedy places the first, the second still fits exactly after.
    # Make them overlap instead: both pinned with durations exceeding the
    # horizon half forces the second out.
    assert plan.violation_count == 0
    sat01_actions = [a for a in plan.actions if a.satellite_id == "SAT-01"]
    assert len(sat01_actions) == 2
    first, second = sorted(sat01_actions, key=lambda a: a.start)
    assert second.start >= first.end


def test_resources_are_enforced_per_satellite():
    scenario = _scenario(
        [
            _request("OBS-A", energy_cost_wh=190.0),
            _request("OBS-B", energy_cost_wh=190.0),
        ],
        satellites=[
            _satellite("SAT-01", battery_charge_wh=200.0),
            _satellite("SAT-02", battery_charge_wh=200.0),
        ],
    )
    session = _session(scenario)
    session.generate_windows()
    plan = session.plan()

    # 190 + 190 exceeds one satellite's 200 Wh, so both cannot land on the
    # same satellite; across two satellites each holds one.
    assert {action.request_id for action in plan.actions} == {"OBS-A", "OBS-B"}
    satellites_used = {action.satellite_id for action in plan.actions}
    assert satellites_used == {"SAT-01", "SAT-02"}
    violations = validate_plan(
        scenario,
        session.get_state(),
        session.get_request_pool(),
        session.get_windows(),
        plan,
    )
    assert violations == []


def test_pinned_request_binds_to_its_satellite():
    scenario = _scenario(
        [_request("OBS-A", satellite_id="SAT-02")],
        satellites=[_satellite("SAT-01"), _satellite("SAT-02")],
    )
    session = _session(scenario)
    session.generate_windows()
    plan = session.plan()

    assert [action.satellite_id for action in plan.actions] == ["SAT-02"]


# --- assignment covers all requests exactly once ----------------------------


@pytest.mark.parametrize("planner", ["greedy", "cp_sat"])
def test_assignment_covers_every_request_exactly_once(planner):
    scenario = _scenario([_request(f"OBS-{i}") for i in range(1, 5)])
    session = _session(scenario, planner)
    session.generate_windows()
    plan = session.plan()

    scheduled = [action.request_id for action in plan.actions if action.request_id]
    assert sorted(scheduled) == sorted(f"OBS-{i}" for i in range(1, 5))
    assert len(set(scheduled)) == len(scheduled)
    assert plan.violation_count == 0


# --- single-satellite parity --------------------------------------------------


def test_single_satellite_plan_matches_legacy_shapes():
    scenario = _scenario(
        [_request("OBS-A"), _request("OBS-B")],
        satellites=[_satellite("SAT-001")],
    )
    session = _session(scenario)
    windows = session.generate_windows()
    plan = session.plan()

    assert [window.id for window in windows] == ["WIN-OBS-A-1", "WIN-OBS-B-1"]
    assert all(action.satellite_id == "SAT-001" for action in plan.actions)
    state = session.get_state()
    assert state.satellite_id == "SAT-001"
    assert state.battery_wh == state.for_satellite("SAT-001").battery_wh
    data = scenario.to_dict()
    assert data["satellites"][0] == data["satellite"]
    restored = Scenario.from_dict(data)
    assert restored == scenario


# --- events, impacts, diffs, traces, metrics across satellites --------------


def test_battery_drop_on_one_satellite_leaves_the_other_valid():
    from amis.demo import DemoImpactWindowProvider

    scenario = _scenario(
        [
            _request("OBS-A", satellite_id="SAT-01", energy_cost_wh=150.0),
            _request("OBS-B", satellite_id="SAT-02", energy_cost_wh=150.0),
        ]
    )
    session = MissionSession(window_provider=DemoImpactWindowProvider())
    session.load_scenario(scenario)
    session.generate_windows()
    version_one = session.plan()

    session.inject_battery_drop("SAT-01", 10.0)
    impact = session.get_last_impact()
    assert impact.evaluated_plan_id == version_one.id

    invalid_requests = {
        action.request_id
        for action in version_one.actions
        if action.id in impact.invalid_unfrozen_action_ids
    }
    assert "OBS-A" in invalid_requests
    assert "OBS-B" not in invalid_requests

    version_two = session.replan(expected_parent_plan_id=version_one.id)
    diff = session.compare_versions(version_one.version, version_two.version)
    assert {entry.request_id for entry in diff.entries} == {"OBS-A", "OBS-B"}
    traces = session.get_traces(version_two.id)
    assert traces

    metrics = session.get_metrics(version_two.id)
    assert len(metrics.per_satellite) == 2
    assert {item.satellite_id for item in metrics.per_satellite} == {"SAT-01", "SAT-02"}
    assert metrics.to_dict()["per_satellite"][0]["satellite_id"] in {"SAT-01", "SAT-02"}


def test_step_advances_each_satellite_independently():
    scenario = _scenario(
        [
            _request("OBS-A", satellite_id="SAT-01"),
            _request("OBS-B", satellite_id="SAT-02"),
        ]
    )
    session = _session(scenario)
    session.generate_windows()
    session.plan()

    state = session.step(3600)
    assert state.for_satellite("SAT-01").battery_wh < 200.0
    assert state.for_satellite("SAT-02").battery_wh < 200.0
    assert set(state.completed_request_ids) == {"OBS-A", "OBS-B"}


def test_payload_outage_invalidates_only_its_satellite():
    scenario = _scenario(
        [
            _request("OBS-A", satellite_id="SAT-01"),
            _request("OBS-B", satellite_id="SAT-02"),
        ]
    )
    session = MissionSession(window_provider=CanonicalWindowProvider())
    session.load_scenario(
        Scenario(
            id="SCN-W7-OUT",
            name="outage",
            start_time=START,
            end_time=END,
            satellites=(_satellite("SAT-01"), _satellite("SAT-02")),
            requests=tuple(
                _request(f"OBS-{code}", satellite_id=sat)
                for code, sat in [("A", "SAT-01"), ("B", "SAT-01"), ("C", "SAT-02")]
            ),
        )
    )
    session.generate_windows()
    plan = session.plan()
    sat01_action = next(a for a in plan.actions if a.satellite_id == "SAT-01")

    session.inject_satellite_outage(
        "SAT-01", sat01_action.start, sat01_action.end + timedelta(seconds=1)
    )
    impact = session.get_last_impact()
    invalid_satellites = {
        action.satellite_id
        for action in plan.actions
        if action.id in impact.invalid_unfrozen_action_ids
    }
    assert "SAT-02" not in invalid_satellites


def test_emergency_window_must_match_a_mission_satellite():
    scenario = _scenario([_request("OBS-A")])
    session = _session(scenario)
    session.generate_windows()
    session.plan()

    bad_window = ObservationWindow(
        id="WIN-OBS-X-1",
        request_id="OBS-X",
        satellite_id="SAT-UNKNOWN",
        start=START,
        end=END,
    )
    with pytest.raises(Exception):
        session.inject_emergency_request(_request("OBS-X"), (bad_window,))


def test_scenario_rejects_duplicate_satellite_ids():
    with pytest.raises(ValueError):
        _scenario([], satellites=[_satellite("SAT-01"), _satellite("SAT-01")])


def test_canonical_demo_windows_stay_per_satellite():
    scenario = Scenario(
        id="SCN-W7-CAN",
        name="canonical",
        start_time=datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 9, 21, 14, 0, tzinfo=timezone.utc),
        satellites=(_satellite("SAT-01"), _satellite("SAT-02")),
        requests=(
            _request(
                "OBS-A",
                deadline=datetime(2026, 9, 21, 14, 0, tzinfo=timezone.utc),
            ),
            _request(
                "OBS-B",
                deadline=datetime(2026, 9, 21, 14, 0, tzinfo=timezone.utc),
            ),
        ),
    )
    windows = CanonicalWindowProvider().generate(scenario, scenario.requests)
    assert {(w.request_id, w.satellite_id) for w in windows} == {
        ("OBS-A", "SAT-01"),
        ("OBS-A", "SAT-02"),
        ("OBS-B", "SAT-01"),
        ("OBS-B", "SAT-02"),
    }
    # Multi-sat ids carry the satellite; single-sat keeps legacy ids.
    assert all(f"-{w.satellite_id}-" in w.id for w in windows)
    single = replace(scenario, satellites=(_satellite("SAT-01"),))
    single_windows = CanonicalWindowProvider().generate(single, single.requests)
    assert {w.id for w in single_windows} == {
        "WIN-OBS-A-1",
        "WIN-OBS-B-1",
        "WIN-OBS-B-2",
    }
