from datetime import datetime, timedelta, timezone

from amis.domain import MissionState, ObservationRequest, ObservationWindow, ReasonCode, Satellite, Scenario
from amis.planning import GreedyPlanner
from amis.windows import SyntheticWindowProvider

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 1, 2, tzinfo=timezone.utc)


def _satellite(**overrides) -> Satellite:
    defaults = dict(
        id="SAT-001",
        battery_capacity_wh=1000.0,
        battery_charge_wh=1000.0,
        storage_capacity_mb=2000.0,
        storage_usage_mb=0.0,
        available=True,
    )
    defaults.update(overrides)
    return Satellite(**defaults)


def _request(**overrides) -> ObservationRequest:
    defaults = dict(
        id="OBS-A",
        target_lat=12.97,
        target_lon=77.59,
        priority=5,
        duration_s=300.0,
        deadline=END,
        energy_cost_wh=50.0,
        storage_cost_mb=100.0,
    )
    defaults.update(overrides)
    return ObservationRequest(**defaults)


def _scenario(satellite: Satellite, requests: tuple[ObservationRequest, ...]) -> Scenario:
    return Scenario(
        id="SCN-001",
        name="Greedy planner test",
        start_time=START,
        end_time=END,
        satellite=satellite,
        requests=requests,
    )


def _window(request_id: str, start: datetime = START, end: datetime = END) -> ObservationWindow:
    return ObservationWindow(
        id=f"WIN-{request_id}-1",
        request_id=request_id,
        satellite_id="SAT-001",
        start=start,
        end=end,
    )


def test_greedy_planner_schedules_the_one_request_into_the_one_window():
    scenario = _scenario(_satellite(), (_request(),))
    windows = SyntheticWindowProvider().generate(scenario, scenario.requests)
    mission_state = MissionState.initial(scenario)

    plan = GreedyPlanner().plan(scenario, mission_state, scenario.requests, windows)

    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.request_id == "OBS-A"
    assert action.window_id == windows[0].id
    assert plan.unscheduled == ()
    assert plan.mission_utility == 5


def test_greedy_planner_reports_unscheduled_reason_when_no_window_exists():
    scenario = _scenario(_satellite(), (_request(),))
    mission_state = MissionState.initial(scenario)

    plan = GreedyPlanner().plan(scenario, mission_state, scenario.requests, windows=[])

    assert plan.actions == ()
    assert len(plan.unscheduled) == 1
    assert plan.unscheduled[0].request_id == "OBS-A"
    assert plan.mission_utility == 0


def test_greedy_planner_sorts_by_priority_then_deadline_then_duration_then_id():
    satellite = _satellite(battery_charge_wh=10.0)  # only one action affordable
    requests = (
        _request(id="OBS-LOW", priority=1, energy_cost_wh=8.0),
        _request(id="OBS-HIGH", priority=5, energy_cost_wh=5.0),
    )
    scenario = _scenario(satellite, requests)
    windows = [
        _window("OBS-LOW", start=START + timedelta(minutes=30)),
        _window("OBS-HIGH"),
    ]
    mission_state = MissionState.initial(scenario)

    plan = GreedyPlanner().plan(scenario, mission_state, requests, windows)

    assert len(plan.actions) == 1
    assert plan.actions[0].request_id == "OBS-HIGH"
    assert plan.unscheduled[0].request_id == "OBS-LOW"
    assert plan.unscheduled[0].reason_code is ReasonCode.INSUFFICIENT_BATTERY
    # A dropped request is not a constraint violation in the resulting
    # plan (SRD 17) -- the plan itself is fully valid.
    assert plan.violation_count == 0


def test_greedy_planner_breaks_a_priority_tie_on_earlier_deadline():
    # Both requests share one wide window. The tie-break decides who is
    # tried (and lands) first; since the window is wide enough for both,
    # the second no longer gets dropped (GAP-04) -- it is placed right
    # after the first one's slot instead.
    requests = (
        _request(id="OBS-EARLY", priority=3, deadline=START + timedelta(hours=1)),
        _request(id="OBS-LATE", priority=3, deadline=END),
    )
    scenario = _scenario(_satellite(), requests)
    windows = [_window("OBS-EARLY"), _window("OBS-LATE")]
    mission_state = MissionState.initial(scenario)

    plan = GreedyPlanner().plan(scenario, mission_state, requests, windows)

    assert plan.unscheduled == ()
    assert [action.request_id for action in plan.actions] == ["OBS-EARLY", "OBS-LATE"]
    assert plan.actions[1].start == plan.actions[0].end


def test_greedy_planner_breaks_a_deadline_tie_on_shorter_duration():
    requests = (
        _request(id="OBS-SHORT", priority=3, duration_s=100.0),
        _request(id="OBS-LONG", priority=3, duration_s=500.0),
    )
    scenario = _scenario(_satellite(), requests)
    windows = [_window("OBS-SHORT"), _window("OBS-LONG")]
    mission_state = MissionState.initial(scenario)

    plan = GreedyPlanner().plan(scenario, mission_state, requests, windows)

    assert plan.unscheduled == ()
    assert [action.request_id for action in plan.actions] == ["OBS-SHORT", "OBS-LONG"]
    assert plan.actions[1].start == plan.actions[0].end


def test_greedy_planner_breaks_a_duration_tie_on_ascending_request_id():
    requests = (
        _request(id="OBS-B", priority=3),
        _request(id="OBS-A", priority=3),
    )
    scenario = _scenario(_satellite(), requests)
    windows = [_window("OBS-B"), _window("OBS-A")]
    mission_state = MissionState.initial(scenario)

    plan = GreedyPlanner().plan(scenario, mission_state, requests, windows)

    assert plan.unscheduled == ()
    assert [action.request_id for action in plan.actions] == ["OBS-A", "OBS-B"]
    assert plan.actions[1].start == plan.actions[0].end


def test_greedy_planner_drops_the_tie_loser_when_the_window_has_no_room_for_both():
    # Same tie-break as above, but the window is only wide enough for one
    # request's duration, so the loser is genuinely unschedulable.
    requests = (
        _request(id="OBS-B", priority=3, duration_s=300.0),
        _request(id="OBS-A", priority=3, duration_s=300.0),
    )
    scenario = _scenario(_satellite(), requests)
    narrow_window_end = START + timedelta(seconds=300)
    windows = [
        _window("OBS-B", end=narrow_window_end),
        _window("OBS-A", end=narrow_window_end),
    ]
    mission_state = MissionState.initial(scenario)

    plan = GreedyPlanner().plan(scenario, mission_state, requests, windows)

    assert len(plan.actions) == 1
    assert plan.actions[0].request_id == "OBS-A"
    assert plan.unscheduled[0].request_id == "OBS-B"
    assert plan.unscheduled[0].reason_code is ReasonCode.TIME_OVERLAP


def test_five_actions_costing_20_wh_each_are_not_all_scheduled_when_only_25_wh_remains():
    satellite = _satellite(battery_charge_wh=25.0)
    requests = tuple(
        _request(id=f"OBS-{i}", priority=3, energy_cost_wh=20.0, duration_s=60.0)
        for i in range(5)
    )
    scenario = _scenario(satellite, requests)
    windows = [
        _window(request.id, start=START + timedelta(minutes=10 * i), end=END)
        for i, request in enumerate(requests)
    ]
    mission_state = MissionState.initial(scenario)

    plan = GreedyPlanner().plan(scenario, mission_state, requests, windows)

    assert len(plan.actions) == 1
    assert len(plan.unscheduled) == 4
    assert all(entry.reason_code is ReasonCode.INSUFFICIENT_BATTERY for entry in plan.unscheduled)


def test_greedy_planner_never_commits_a_later_higher_priority_action_the_earlier_one_cannot_afford():
    # Regression for GAP-03: the planner commits in priority order, not
    # time order, so a later-starting, higher-priority action can pass
    # its own candidate check before an earlier-starting, lower-priority
    # one is even considered. The chronological re-check
    # (ResourceProjection.check_commit) must reject the earlier action
    # instead of letting both through and producing a plan that
    # validate_plan() would reject.
    satellite = _satellite(battery_charge_wh=15.0)
    requests = (
        _request(id="OBS-HI", priority=5, energy_cost_wh=10.0, duration_s=60.0, deadline=END),
        _request(id="OBS-LO", priority=1, energy_cost_wh=10.0, duration_s=60.0, deadline=END),
    )
    scenario = _scenario(satellite, requests)
    windows = [
        _window("OBS-HI", start=START + timedelta(hours=2), end=START + timedelta(hours=3)),
        _window("OBS-LO", start=START, end=START + timedelta(hours=1)),
    ]
    mission_state = MissionState.initial(scenario)

    plan = GreedyPlanner().plan(scenario, mission_state, requests, windows)

    scheduled_ids = {action.request_id for action in plan.actions}
    assert scheduled_ids == {"OBS-HI"}
    assert plan.unscheduled[0].request_id == "OBS-LO"
    assert plan.unscheduled[0].reason_code is ReasonCode.INSUFFICIENT_BATTERY
    # The resulting plan is fully valid -- battery is never overdrawn in
    # chronological order -- so validate_plan finds no violations and
    # violation_count must agree (GAP-09).
    assert plan.violation_count == 0


def test_nothing_fits_produces_an_empty_plan_with_a_reason_per_request_and_raises_no_error():
    satellite = _satellite(battery_charge_wh=0.0)
    requests = (_request(id="OBS-A"), _request(id="OBS-B"))
    scenario = _scenario(satellite, requests)
    windows = [_window("OBS-A"), _window("OBS-B", start=START + timedelta(minutes=10))]
    mission_state = MissionState.initial(scenario)

    plan = GreedyPlanner().plan(scenario, mission_state, requests, windows)

    assert plan.actions == ()
    assert {entry.request_id for entry in plan.unscheduled} == {"OBS-A", "OBS-B"}
    assert all(entry.reason_code is ReasonCode.INSUFFICIENT_BATTERY for entry in plan.unscheduled)
    assert plan.mission_utility == 0


def test_two_runs_of_the_same_scenario_produce_identical_plans():
    scenario = _scenario(
        _satellite(battery_charge_wh=60.0),
        (
            _request(id="OBS-A", priority=5, energy_cost_wh=30.0),
            _request(id="OBS-B", priority=3, energy_cost_wh=30.0),
            _request(id="OBS-C", priority=1, energy_cost_wh=30.0),
        ),
    )
    windows = [
        _window("OBS-A"),
        _window("OBS-B", start=START + timedelta(minutes=10)),
        _window("OBS-C", start=START + timedelta(minutes=20)),
    ]
    mission_state = MissionState.initial(scenario)

    first = GreedyPlanner().plan(scenario, mission_state, scenario.requests, windows)
    second = GreedyPlanner().plan(scenario, mission_state, scenario.requests, windows)

    assert first.actions == second.actions
    assert first.unscheduled == second.unscheduled
    assert first.mission_utility == second.mission_utility
