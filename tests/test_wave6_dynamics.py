"""Wave 6: slew between consecutive targets and sunlight recharge (ADR-0013)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from math import atan, degrees, radians, sin

import pytest

from amis.constraints import ResourceProjection, validate_plan
from amis.domain import ReasonCode, ScheduledAction
from amis.dynamics import RechargeModel, SlewModel, recharge_model, slew_angle_deg
from amis.examples import orbital_example
from amis.orbital.geometry import EARTH_RADIUS_KM
from amis.session import MissionSession
from amis.windows.orbital import OrbitalWindowProvider

T0 = datetime(2026, 9, 25, tzinfo=timezone.utc)


def _policy(scenario, **changes):
    return replace(scenario, window_policy=replace(scenario.window_policy, **changes))


def _session(scenario, planner="greedy"):
    session = MissionSession(window_provider=OrbitalWindowProvider())
    session.load_scenario(scenario)
    session.select_planner(planner)
    return session


def _imaging(plan):
    return sorted((a for a in plan.actions if not a.is_downlink), key=lambda a: a.start)


# --- slew ---------------------------------------------------------------


def test_slew_angle_matches_hand_computed_chord_geometry():
    # One degree of longitude on the equator seen from 500 km.
    chord_km = 2 * EARTH_RADIUS_KM * sin(radians(0.5))
    assert slew_angle_deg(0, 0, 0, 1, 500) == pytest.approx(degrees(2 * atan(chord_km / 1000)))
    assert slew_angle_deg(10, 20, 10, 20, 500) == 0


def test_slew_gap_is_settling_plus_angle_over_rate():
    model = SlewModel(settling_time_s=5, slew_rate_deg_s=2, altitude_km=500, targets={"A": (0, 0), "B": (0, 1)})
    assert model.gap_s("A", "B") == pytest.approx(5 + slew_angle_deg(0, 0, 0, 1, 500) / 2)
    assert model.gap_s("A", None) == 5


def test_slew_violations_are_caught_at_validation():
    session = _session(orbital_example())
    plan = session.plan()
    slewing = _policy(session.get_scenario(), slew_rate_deg_s=1.0)

    violations = validate_plan(
        slewing, session.get_state(), session.get_request_pool(), session.get_windows(), plan
    )

    slew_violations = [v for v in violations if "required_gap_s" in v.details]
    assert slew_violations
    assert all(v.reason_code is ReasonCode.TIME_OVERLAP for v in slew_violations)


@pytest.mark.parametrize("planner", ["greedy", "cp_sat"])
def test_planners_place_actions_with_the_pairwise_slew_gap(planner):
    scenario = _policy(orbital_example(), slew_rate_deg_s=1.0, settling_time_s=2.0)
    session = _session(scenario, planner)
    plan = session.plan()
    model = SlewModel.from_scenario(scenario, scenario.requests)

    assert plan.violation_count == 0
    actions = _imaging(plan)
    assert len(actions) >= 2
    for first, second in zip(actions, actions[1:]):
        gap_s = (second.start - first.end).total_seconds()
        assert gap_s >= model.gap_s(first.request_id, second.request_id) - 1e-6


# --- recharge -----------------------------------------------------------


def test_recharge_gain_matches_hand_computed_sunlit_overlap():
    model = RechargeModel(60.0, (
        (T0, T0 + timedelta(minutes=30)),
        (T0 + timedelta(minutes=60), T0 + timedelta(minutes=90)),
    ))
    # 15 lit minutes in each interval: 30 minutes at 60 W is 30 Wh.
    assert model.gain_wh(T0 + timedelta(minutes=15), T0 + timedelta(minutes=75)) == pytest.approx(30.0)
    assert model.gain_wh(T0 + timedelta(minutes=30), T0 + timedelta(minutes=60)) == 0
    assert RechargeModel().gain_wh(T0, T0 + timedelta(hours=1)) == 0


def test_projection_recharges_between_actions_and_caps_at_capacity():
    model = RechargeModel(60.0, ((T0, T0 + timedelta(hours=10)),))
    projection = ResourceProjection(50.0, 0.0, model, T0, battery_capacity_wh=100.0)
    projection.commit(ScheduledAction(
        "ACT-1", "R", "SAT", "W", T0 + timedelta(minutes=30), T0 + timedelta(minutes=31), 40.0, 0.0,
    ))
    # 50 + 30 Wh by the start, minus 40, then 30 more by the hour.
    assert projection.available_at(T0 + timedelta(minutes=30))[0] == pytest.approx(40.0)
    assert projection.available_at(T0 + timedelta(minutes=60))[0] == pytest.approx(70.0)
    assert projection.available_at(T0 + timedelta(hours=5))[0] == 100.0


def test_sunlit_intervals_agree_with_the_ephemeris_at_their_edges():
    from skyfield.api import EarthSatellite, load, load_file

    from amis.windows.orbital import EPHEMERIS

    scenario = _policy(orbital_example(), recharge_rate_w=10.0)
    intervals = recharge_model(scenario).sunlit
    ts = load.timescale(builtin=True)
    satellite = EarthSatellite.from_omm(ts, scenario.satellite.orbit.omm)
    eph = load_file(str(EPHEMERIS))
    try:
        def lit(instant):
            return bool(satellite.at(ts.from_datetime(instant)).is_sunlit(eph))

        assert len(intervals) > 40  # about 15 orbits a day over four days
        for start, end in intervals:
            assert lit(start + (end - start) / 2)
            if start > scenario.start_time:
                assert not lit(start - timedelta(seconds=2)) and lit(start + timedelta(seconds=1))
            if end < scenario.end_time:
                assert lit(end - timedelta(seconds=2)) and not lit(end + timedelta(seconds=1))
    finally:
        eph.close()


def _battery_bound(recharge_rate_w):
    scenario = orbital_example()
    satellite = replace(scenario.satellite, battery_capacity_wh=60, battery_charge_wh=60)
    return _policy(replace(scenario, satellite=satellite), recharge_rate_w=recharge_rate_w)


def test_multi_day_battery_stays_within_bounds_with_recharge():
    without = _session(_battery_bound(0.0)).plan()
    session = _session(_battery_bound(20.0))
    plan = session.plan()
    capacity = session.get_scenario().satellite.battery_capacity_wh

    assert plan.violation_count == 0
    assert len(_imaging(plan)) > len(_imaging(without))

    state = session.get_state()
    while not state.mission_complete:
        state = session.step(3600)
        assert 0 <= state.battery_wh <= capacity
    assert set(state.completed_request_ids) == {a.request_id for a in _imaging(plan)}


# --- review follow-ups --------------------------------------------------


def test_slew_fails_closed_on_an_unknown_target():
    model = SlewModel(settling_time_s=5, slew_rate_deg_s=2, altitude_km=500, targets={"A": (0, 0)})
    with pytest.raises(ValueError, match="Z"):
        model.gap_s("A", "Z")


def test_slew_targets_are_read_only():
    targets = {"A": (0.0, 0.0)}
    model = SlewModel(targets=targets)
    targets["B"] = (1.0, 1.0)
    assert "B" not in model.targets
    with pytest.raises(TypeError):
        model.targets["C"] = (2.0, 2.0)  # type: ignore[index]


def test_cp_sat_enforces_pairwise_slew_without_the_greedy_fallback():
    scenario = _policy(orbital_example(), slew_rate_deg_s=1.0, settling_time_s=2.0)
    plan = _session(scenario, "cp_sat").plan()

    assert plan.violation_count == 0
    assert plan.solver_details["fallback"] is False


def test_cp_sat_counts_sunlight_recharge_in_its_battery_budget():
    without = _session(_battery_bound(0.0), "cp_sat").plan()
    plan = _session(_battery_bound(20.0), "cp_sat").plan()

    assert plan.violation_count == 0
    assert plan.solver_details["fallback"] is False
    assert len(_imaging(plan)) > len(_imaging(without))
