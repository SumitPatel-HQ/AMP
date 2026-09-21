from datetime import datetime, timedelta, timezone

import pytest

from amis.constraints import validate_plan
from amis.domain import (
    ActionStatus,
    BatteryDropPayload,
    EventType,
    ObservationRequest,
    ObservationWindow,
    ReasonCode,
    Satellite,
    Scenario,
)
from amis.errors import InvalidEventError, SimulationStateError
from amis.session import MissionSession

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = START + timedelta(minutes=30)


def _scenario(battery_charge_wh: float, requests: tuple[ObservationRequest, ...]) -> Scenario:
    return Scenario(
        id="SCN-001",
        name="Battery drop test",
        start_time=START,
        end_time=END,
        satellite=Satellite(
            id="SAT-001",
            battery_capacity_wh=max(battery_charge_wh, 200.0),
            battery_charge_wh=battery_charge_wh,
            storage_capacity_mb=1000.0,
            storage_usage_mb=0.0,
        ),
        requests=requests,
    )


def _request(request_id: str, priority: int, energy_cost_wh: float, duration_s: float = 60.0) -> ObservationRequest:
    return ObservationRequest(
        id=request_id,
        target_lat=0.0,
        target_lon=0.0,
        priority=priority,
        duration_s=duration_s,
        deadline=END,
        energy_cost_wh=energy_cost_wh,
        storage_cost_mb=1.0,
    )


class _WindowProvider:
    """One window per request, starting at the offset named for that request."""

    def __init__(self, offsets_s: dict[str, float]) -> None:
        self._offsets_s = offsets_s

    def generate(self, scenario: Scenario, requests):
        return [
            ObservationWindow(
                id=f"WIN-{request.id}-1",
                request_id=request.id,
                satellite_id=scenario.satellite.id,
                start=scenario.start_time + timedelta(seconds=self._offsets_s[request.id]),
                end=scenario.end_time,
            )
            for request in requests
        ]


def _session(scenario: Scenario, offsets_s: dict[str, float]) -> MissionSession:
    session = MissionSession(window_provider=_WindowProvider(offsets_s))
    session.load_scenario(scenario)
    session.generate_windows()
    return session


def test_battery_drop_names_satellite_and_sets_state_to_exact_value_without_clamping():
    scenario = _scenario(50.0, (_request("OBS-A", 5, 40.0, duration_s=300.0),))
    session = _session(scenario, {"OBS-A": 0.0})
    plan = session.plan()

    event = session.inject_battery_drop("SAT-001", 10.0)

    assert event.id == "EVT-001"
    assert event.scenario_id == scenario.id
    assert event.event_type is EventType.BATTERY_DROP
    assert event.payload == BatteryDropPayload(satellite_id="SAT-001", new_battery_wh=10.0)
    assert session.get_events() == (event,)
    assert session.get_state().active_event_ids == (event.id,)

    # The action in flight needs 40 Wh; the state still takes 10 exactly.
    assert session.get_state().battery_wh == 10.0

    impact = session.get_last_impact()
    assert impact.event_id == event.id
    assert impact.evaluated_plan_id == plan.id


def test_battery_drop_requires_a_plan_and_a_matching_satellite():
    scenario = _scenario(50.0, (_request("OBS-A", 5, 40.0, duration_s=300.0),))
    session = _session(scenario, {"OBS-A": 0.0})

    with pytest.raises(SimulationStateError, match="plan"):
        session.inject_battery_drop("SAT-001", 10.0)

    session.plan()

    with pytest.raises(InvalidEventError, match="satellite") as raised:
        session.inject_battery_drop("SAT-999", 10.0)
    assert raised.value.code == "INVALID_EVENT"
    assert session.get_events() == ()


@pytest.mark.parametrize("new_battery_wh", [-1.0, float("nan"), float("inf")])
def test_battery_drop_rejects_a_non_finite_or_negative_value(new_battery_wh):
    scenario = _scenario(50.0, (_request("OBS-A", 5, 40.0, duration_s=300.0),))
    session = _session(scenario, {"OBS-A": 0.0})
    session.plan()

    with pytest.raises(InvalidEventError):
        session.inject_battery_drop("SAT-001", new_battery_wh)


def test_battery_drop_rejects_a_value_above_battery_capacity():
    scenario = _scenario(50.0, (_request("OBS-A", 5, 40.0, duration_s=300.0),))
    session = _session(scenario, {"OBS-A": 0.0})
    session.plan()

    with pytest.raises(InvalidEventError, match="capacity"):
        session.inject_battery_drop("SAT-001", scenario.satellite.battery_capacity_wh + 1.0)


def test_frozen_in_flight_action_still_completes_and_battery_floors_at_zero():
    scenario = _scenario(50.0, (_request("OBS-A", 5, 40.0, duration_s=300.0),))
    session = _session(scenario, {"OBS-A": 0.0})
    plan = session.plan()
    action = plan.actions[0]
    assert action.start == session.get_state().simulated_time

    session.inject_battery_drop("SAT-001", 10.0)
    impact = session.get_last_impact()
    assert impact.frozen_action_ids == (action.id,)
    assert action.id not in impact.valid_unfrozen_action_ids
    assert action.id not in impact.invalid_unfrozen_action_ids

    state = session.step(300)
    assert state.battery_wh == 0.0
    assert "OBS-A" in state.completed_request_ids


def test_validating_the_plan_after_a_drop_does_not_fail_over_a_started_action():
    scenario = _scenario(50.0, (_request("OBS-A", 5, 40.0, duration_s=300.0),))
    session = _session(scenario, {"OBS-A": 0.0})
    session.plan()

    session.step(1)
    assert session.get_plan().actions[0].status is ActionStatus.STARTED

    session.inject_battery_drop("SAT-001", 2.0)
    assert session.get_state().battery_wh == 2.0

    violations = validate_plan(
        scenario,
        session.get_state(),
        session.get_request_pool(),
        session.get_windows(),
        session.get_plan(),
    )
    assert violations == []

    state = session.step(299)
    assert state.battery_wh == 2.0


def test_unfrozen_actions_that_no_longer_fit_become_invalid_with_insufficient_battery():
    requests = (
        _request("OBS-A", 5, 5.0, duration_s=30.0),
        _request("OBS-B", 4, 40.0, duration_s=30.0),
        _request("OBS-C", 3, 40.0, duration_s=30.0),
    )
    scenario = _scenario(200.0, requests)
    session = _session(scenario, {"OBS-A": 0.0, "OBS-B": 120.0, "OBS-C": 240.0})
    plan = session.plan()
    actions_by_request = {action.request_id: action.id for action in plan.actions}

    session.step(1)
    session.inject_battery_drop("SAT-001", 30.0)

    impact = session.get_last_impact()
    assert actions_by_request["OBS-A"] in impact.frozen_action_ids
    assert actions_by_request["OBS-B"] in impact.invalid_unfrozen_action_ids
    assert impact.reason_codes[actions_by_request["OBS-B"]] == (ReasonCode.INSUFFICIENT_BATTERY,)


def test_replan_after_battery_drop_never_raises_and_explains_every_drop():
    requests = (
        _request("OBS-A", 5, 40.0, duration_s=30.0),
        _request("OBS-B", 4, 40.0, duration_s=30.0),
        _request("OBS-C", 3, 40.0, duration_s=30.0),
    )
    scenario = _scenario(200.0, requests)
    session = _session(scenario, {"OBS-A": 60.0, "OBS-B": 120.0, "OBS-C": 180.0})
    session.plan()

    session.inject_battery_drop("SAT-001", 5.0)
    plan = session.replan()

    assert plan.actions == ()
    assert {entry.request_id for entry in plan.unscheduled} == {"OBS-A", "OBS-B", "OBS-C"}
    for entry in plan.unscheduled:
        assert entry.reason_code is ReasonCode.INSUFFICIENT_BATTERY


def test_fixture_tight_battery_drops_exactly_the_lowest_priority_request():
    requests = (
        _request("OBS-A", 5, 40.0, duration_s=30.0),
        _request("OBS-B", 4, 40.0, duration_s=30.0),
        _request("OBS-C", 3, 40.0, duration_s=30.0),
    )
    scenario = _scenario(200.0, requests)
    session = _session(scenario, {"OBS-A": 60.0, "OBS-B": 120.0, "OBS-C": 180.0})
    session.plan()

    session.inject_battery_drop("SAT-001", 90.0)
    plan = session.replan()

    scheduled_request_ids = {action.request_id for action in plan.actions}
    assert scheduled_request_ids == {"OBS-A", "OBS-B"}
    assert len(plan.unscheduled) == 1
    assert plan.unscheduled[0].request_id == "OBS-C"
    assert plan.unscheduled[0].reason_code is ReasonCode.INSUFFICIENT_BATTERY


def test_battery_drop_payload_accepts_a_plain_dict_and_round_trips():
    scenario = _scenario(50.0, (_request("OBS-A", 5, 40.0, duration_s=300.0),))
    session = _session(scenario, {"OBS-A": 0.0})
    session.plan()

    event = session.inject_event(
        "BATTERY_DROP",
        {"satellite_id": "SAT-001", "new_battery_wh": 12.5},
    )

    assert event.to_dict()["payload"] == {
        "satellite_id": "SAT-001",
        "new_battery_wh": 12.5,
    }
