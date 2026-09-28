"""Wave 3: richer spacecraft — payload outages, derived costs, settling time,
culmination placement (ADR-0010).

Drives MissionSession and the constraint checks; never asserts on
propagator, solver, or component internals.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from amis.constraints import check_overlap, check_satellite_availability
from amis.costs import derive_energy_wh, derive_storage_mb
from amis.demo import (
    REPLAN_START,
    CanonicalWindowProvider,
    build_canonical_replan_scenario,
)
from amis.domain import ObservationWindow, ReasonCode, WindowPolicy
from amis.planning.greedy import _culmination_start
from amis.session import MissionSession


def _with_policy(scenario, **changes):
    base = {"provider": "canonical"}
    if scenario.window_policy is not None:
        base.update(scenario.window_policy.to_dict())
    base.update(changes)
    return replace(scenario, window_policy=WindowPolicy(**base))


def _canonical_session(scenario=None, planner="greedy"):
    session = MissionSession(window_provider=CanonicalWindowProvider())
    session.load_scenario(scenario or build_canonical_replan_scenario())
    session.generate_windows()
    session.select_planner(planner)
    return session


def test_outage_invalidates_exactly_the_actions_in_span():
    session = _canonical_session()
    plan = session.plan()
    by_request = {action.request_id: action for action in plan.actions}

    outage_start = by_request["OBS-B"].start
    outage_end = by_request["OBS-B"].end
    session.inject_satellite_outage("SAT-001", outage_start, outage_end)

    impact = session.get_last_impact()
    assert set(impact.invalid_unfrozen_action_ids) == {by_request["OBS-B"].id}
    assert impact.reason_codes[by_request["OBS-B"].id] == (ReasonCode.SATELLITE_UNAVAILABLE,)

    replanned = session.replan()
    assert replanned.violation_count == 0
    # OBS-B's first window is blocked but its 11:15 alternative is open,
    # so the replan moves it there instead of dropping it.
    moved = next(action for action in replanned.actions if action.request_id == "OBS-B")
    assert moved.window_id == "WIN-OBS-B-2"
    for request_id in ("OBS-A", "OBS-C", "OBS-D", "OBS-E"):
        assert request_id in {action.request_id for action in replanned.actions}


def test_frozen_actions_stay_exempt_from_a_later_outage():
    session = _canonical_session()
    session.plan()
    session.step(300)  # OBS-A has started: it is frozen from here on
    frozen_id = next(
        action.id for action in session.get_plan().actions if action.request_id == "OBS-A"
    )

    scenario = session.get_scenario()
    session.inject_satellite_outage("SAT-001", scenario.start_time, scenario.end_time)

    impact = session.get_last_impact()
    assert frozen_id not in impact.invalid_unfrozen_action_ids

    replanned = session.replan()
    assert frozen_id in {action.id for action in replanned.actions}


def test_outage_check_rejects_only_overlapping_intervals():
    t0 = datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc)
    span = (t0 + timedelta(minutes=20), t0 + timedelta(minutes=35))

    inside = check_satellite_availability(
        "OBS-B", True, span[0], span[1], (span,),
    )
    outside = check_satellite_availability(
        "OBS-C", True, t0 + timedelta(minutes=40), t0 + timedelta(minutes=50), (span,),
    )
    touching_end = check_satellite_availability(
        "OBS-D", True, span[1], span[1] + timedelta(minutes=10), (span,),
    )

    assert inside is not None and inside.reason_code is ReasonCode.SATELLITE_UNAVAILABLE
    assert inside.subject_key == "OBS-B"
    assert outside is None
    assert touching_end is None


def test_outage_leaves_windows_untouched_for_replay():
    session = _canonical_session()
    windows_before = [(window.id, window.valid) for window in session.get_windows()]
    session.plan()
    scenario = session.get_scenario()
    session.inject_satellite_outage("SAT-001", scenario.start_time, scenario.end_time)

    assert [(window.id, window.valid) for window in session.get_windows()] == windows_before


def test_derived_costs_match_hand_computed_values():
    assert derive_energy_wh(100.0, 600.0) == 100.0 * 600.0 / 3600.0
    assert derive_storage_mb(10.0, 600.0) == 10.0 * 600.0 / 8.0
    assert derive_energy_wh(5.0, 3600.0) == 5.0
    assert derive_storage_mb(8.0, 8.0) == 8.0


def test_derived_helpers_stay_out_of_planner_and_constraints():
    backend = Path(__file__).resolve().parent.parent / "amis"
    offenders = [
        path for path in (*backend.rglob("planning/*.py"), *backend.rglob("constraints/*.py"))
        if "amis.costs" in path.read_text() or "derive_energy" in path.read_text()
        or "derive_storage" in path.read_text()
    ]

    assert offenders == []


def test_settling_gap_is_enforced_through_the_overlap_rule():
    t0 = datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc)
    existing = [_action("ACT-1", "OBS-A", t0, t0 + timedelta(minutes=10))]

    back_to_back = check_overlap(
        "OBS-B", t0 + timedelta(minutes=10), t0 + timedelta(minutes=20), existing, min_gap_s=60.0,
    )
    with_gap = check_overlap(
        "OBS-B", t0 + timedelta(minutes=11), t0 + timedelta(minutes=21), existing, min_gap_s=60.0,
    )
    without_gap = check_overlap(
        "OBS-B", t0 + timedelta(minutes=10), t0 + timedelta(minutes=20), existing, min_gap_s=0.0,
    )

    assert back_to_back is not None and back_to_back.reason_code is ReasonCode.TIME_OVERLAP
    assert with_gap is None
    assert without_gap is None  # zero gap is the historical overlap rule


def test_settling_gap_blocks_back_to_back_plans_but_not_spaced_ones():
    t0 = REPLAN_START
    scenario = build_canonical_replan_scenario()
    requests = scenario.requests[:2]  # OBS-A (pri 5), OBS-B (pri 4)
    adjacent = (
        ObservationWindow(
            id="WIN-ADJ-1", request_id="OBS-A", satellite_id="SAT-001",
            start=t0, end=t0 + timedelta(minutes=10),
        ),
        ObservationWindow(
            id="WIN-ADJ-2", request_id="OBS-B", satellite_id="SAT-001",
            start=t0 + timedelta(minutes=10), end=t0 + timedelta(minutes=20),
        ),
    )
    tight = _with_policy(replace(scenario, requests=requests), settling_time_s=120.0)

    for planner in ("greedy", "cp_sat"):
        session = MissionSession(window_provider=_FixedWindows(adjacent))
        session.load_scenario(tight)
        session.generate_windows()
        session.select_planner(planner)
        plan = session.plan()

        assert plan.violation_count == 0
        # OBS-B can no longer start at 10:10: the 120 s gap after OBS-A's
        # 10:10 end pushes it past its window, so only OBS-A is scheduled.
        assert {action.request_id for action in plan.actions} == {"OBS-A"}
        assert plan.unscheduled[0].request_id == "OBS-B"
        assert plan.unscheduled[0].reason_code is ReasonCode.TIME_OVERLAP


def test_durations_exclude_the_settling_gap():
    t0 = datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc)
    existing = [_action("ACT-1", "OBS-A", t0, t0 + timedelta(minutes=10))]

    # The gap lives between actions: an action may start exactly gap after
    # the previous end even though its own duration is unchanged.
    assert check_overlap(
        "OBS-B", t0 + timedelta(minutes=10, seconds=30), t0 + timedelta(minutes=20, seconds=30),
        existing, min_gap_s=30.0,
    ) is None


def test_culmination_start_is_peak_centered_when_it_fits():
    t0 = datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc)
    window = ObservationWindow(
        id="WIN-1", request_id="OBS-A", satellite_id="SAT-001",
        start=t0, end=t0 + timedelta(minutes=30),
        peak_time=t0 + timedelta(minutes=15),
    )

    assert _culmination_start(window, 600.0) == t0 + timedelta(minutes=10)


def test_culmination_start_falls_back_without_a_usable_peak():
    t0 = datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc)
    no_peak = ObservationWindow(
        id="WIN-1", request_id="OBS-A", satellite_id="SAT-001",
        start=t0, end=t0 + timedelta(minutes=30),
    )
    edge_peak = ObservationWindow(
        id="WIN-2", request_id="OBS-A", satellite_id="SAT-001",
        start=t0, end=t0 + timedelta(minutes=30),
        peak_time=t0 + timedelta(minutes=29),
    )

    assert _culmination_start(no_peak, 600.0) is None
    assert _culmination_start(edge_peak, 600.0) is None


def test_greedy_prefers_the_peak_centered_start():
    t0 = REPLAN_START
    scenario = _with_policy(build_canonical_replan_scenario(), culmination_placement=True)
    single = replace(scenario, requests=scenario.requests[:1])
    request = single.requests[0]
    window = ObservationWindow(
        id="WIN-CULM-1", request_id=request.id, satellite_id="SAT-001",
        start=t0, end=t0 + timedelta(hours=2),
        peak_time=t0 + timedelta(hours=1),
    )

    session = MissionSession(window_provider=_FixedWindows((window,)))
    session.load_scenario(single)
    session.generate_windows()
    plan = session.plan()

    assert len(plan.actions) == 1
    assert plan.actions[0].start == t0 + timedelta(minutes=55)


def test_culmination_keeps_the_stability_rule_on_replan():
    scenario = _with_policy(build_canonical_replan_scenario(), culmination_placement=True)
    session = _canonical_session(scenario)
    first = session.plan()
    first_starts = {action.request_id: (action.window_id, action.start) for action in first.actions}

    session.inject_cloud_block("OBS-D", "WIN-OBS-D-1")
    second = session.replan()

    assert second.violation_count == 0
    for action in second.actions:
        if action.request_id in first_starts and action.request_id != "OBS-D":
            assert (action.window_id, action.start) == first_starts[action.request_id]


def test_culmination_never_displaces_utility_between_planners():
    scenario = _with_policy(build_canonical_replan_scenario(), culmination_placement=True)

    greedy = _canonical_session(scenario, "greedy").plan()
    cp_sat = _canonical_session(scenario, "cp_sat").plan()

    assert cp_sat.violation_count == 0
    assert cp_sat.mission_utility >= greedy.mission_utility


class _FixedWindows:
    """Yield a fixed window list regardless of scenario or requests."""

    def __init__(self, windows):
        self._windows = tuple(windows)

    def generate(self, scenario, requests):
        wanted = {request.id for request in requests}
        return [window for window in self._windows if window.request_id in wanted]


def _action(action_id, request_id, start, end):
    from amis.domain import ScheduledAction

    return ScheduledAction(
        action_id, request_id, "SAT-001", f"WIN-{request_id}-1", start, end, 1.0, 1.0,
    )


def test_window_policy_defaults_keep_the_historical_overlap_rule():
    from amis.domain import WindowPolicy

    assert WindowPolicy(provider="canonical").settling_time_s == 0.0
    assert WindowPolicy(provider="canonical").culmination_placement is False
