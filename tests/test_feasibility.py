"""Ticket 05: window-only feasibility (ADR-0015).

Drives MissionSession and the HTTP route. A stub provider fixes the
candidate's windows so selection, policy, and ordering rules are exact;
one test uses the real orbital provider over a bundled Example.
"""

from __future__ import annotations

import asyncio
import math
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from amis.api import create_app
from amis.domain import (
    FeasibilityReason,
    ObservationRequest,
    ObservationWindow,
    Satellite,
    Scenario,
    WindowPolicy,
)
from amis.errors import InvalidScenarioError
from amis.examples import orbital_example
from amis.ids import (
    ACTION_ID_PREFIX,
    EVENT_ID_PREFIX,
    IMPACT_ID_PREFIX,
    PLAN_ID_PREFIX,
    TRACE_ID_PREFIX,
    next_id,
)
from amis.repositories import MissionSessionStore, Repositories
from amis.session import FEASIBILITY_REQUEST_ID, MissionSession
from amis.windows.orbital import OrbitalWindowProvider

START = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
END = START + timedelta(hours=4)
DEADLINE = END


def _at(minutes: float) -> datetime:
    return START + timedelta(minutes=minutes)


def _satellite(satellite_id: str, available: bool = True) -> Satellite:
    return Satellite(
        id=satellite_id,
        battery_capacity_wh=200.0,
        battery_charge_wh=200.0,
        storage_capacity_mb=500.0,
        storage_usage_mb=0.0,
        available=available,
    )


def _scenario(satellites=None, policy: WindowPolicy | None = None) -> Scenario:
    request = ObservationRequest(
        id="OBS-1",
        target_lat=10.0,
        target_lon=20.0,
        priority=3,
        duration_s=300.0,
        deadline=END,
        energy_cost_wh=10.0,
        storage_cost_mb=10.0,
    )
    return Scenario(
        id="SCN-FEAS",
        name="Feasibility",
        start_time=START,
        end_time=END,
        satellites=tuple(satellites or (_satellite("SAT-A"), _satellite("SAT-B"), _satellite("SAT-C"))),
        requests=(request,),
        window_policy=policy or WindowPolicy("orbital"),
    )


def _window(window_id: str, satellite_id: str, start: float, end: float, peak: float | None = None,
            request_id: str = FEASIBILITY_REQUEST_ID) -> ObservationWindow:
    return ObservationWindow(
        id=window_id,
        request_id=request_id,
        satellite_id=satellite_id,
        start=_at(start),
        end=_at(end),
        peak_time=_at(peak) if peak is not None else None,
    )


class _StubProvider:
    """Fixed windows: the Scenario's own, and a fixed set for any candidate."""

    def __init__(self, candidate_windows: tuple[ObservationWindow, ...]) -> None:
        self.candidate_windows = candidate_windows
        self.candidates: list[ObservationRequest] = []

    def generate(self, scenario, requests):
        requests = tuple(requests)
        if requests == scenario.requests:
            return [_window("WIN-OBS-1-1", "SAT-A", 30, 60, request_id="OBS-1")]
        self.candidates.extend(requests)
        return [
            window for window in self.candidate_windows
            if requests[0].satellite_id in (None, window.satellite_id)
        ]


CANDIDATE_WINDOWS = (
    _window("W-A-1", "SAT-A", 60, 70, peak=65),
    _window("W-B-1", "SAT-B", 20, 40, peak=30),
    _window("W-C-1", "SAT-C", 20, 30, peak=25),
)


def _session(scenario=None, windows=CANDIDATE_WINDOWS):
    provider = _StubProvider(windows)
    session = MissionSession(window_provider=provider)
    session.load_scenario(scenario or _scenario())
    return session, provider


def _snapshot(session: MissionSession):
    return (
        session.get_scenario(),
        session.get_state(),
        session.get_request_pool(),
        session.get_events(),
        session.get_windows(),
        session.get_plans(),
        session.get_traces(),
        session.get_impacts(),
    )


# --- selection and ordering ------------------------------------------------


def test_every_satellite_gets_one_row_sorted_by_earliest_start_then_id():
    session, _ = _session()

    result = session.get_feasibility(10.0, 20.0, 300.0, DEADLINE)

    assert result.scope == "window_only"
    assert [row.satellite_id for row in result.results] == ["SAT-B", "SAT-C", "SAT-A"]
    assert result.earliest_satellite_id == "SAT-B"
    first = result.results[0]
    assert (first.window_id, first.window_start, first.window_end) == ("W-B-1", _at(20), _at(40))
    assert first.earliest_start == _at(20)
    assert first.latest_finish == _at(40)
    assert all(row.reason is None for row in result.results)


def test_search_interval_starts_at_scenario_start_and_ends_at_the_earlier_bound():
    session, _ = _session()

    clipped = session.get_feasibility(10.0, 20.0, 300.0, _at(90))
    open_ended = session.get_feasibility(10.0, 20.0, 300.0, END + timedelta(days=2))

    assert (clipped.search_start, clipped.search_end) == (START, _at(90))
    assert (open_ended.search_start, open_ended.search_end) == (START, END)


def test_latest_finish_clips_to_deadline_and_action_must_fit_before_it():
    session, _ = _session()

    # SAT-B's window runs to 40 but the deadline is 30: a 5-minute action
    # still fits from 20, a 15-minute one does not.
    fits = session.get_feasibility(10.0, 20.0, 300.0, _at(30), satellite_id="SAT-B")
    too_long = session.get_feasibility(10.0, 20.0, 900.0, _at(30), satellite_id="SAT-B")

    assert fits.results[0].latest_finish == _at(30)
    assert fits.results[0].earliest_start + timedelta(seconds=300) <= fits.results[0].latest_finish
    assert too_long.results[0].reason is FeasibilityReason.NO_SUITABLE_WINDOW
    assert too_long.earliest_satellite_id is None


def test_earliest_suitable_window_is_selected_not_merely_the_earliest_window():
    windows = (
        _window("W-A-1", "SAT-A", 10, 12, peak=11),
        _window("W-A-2", "SAT-A", 50, 70, peak=60),
    )
    session, _ = _session(_scenario(satellites=(_satellite("SAT-A"),)), windows)

    row = session.get_feasibility(10.0, 20.0, 600.0, DEADLINE).results[0]

    assert (row.window_id, row.earliest_start, row.latest_finish) == ("W-A-2", _at(50), _at(70))


def test_culmination_policy_centres_the_start_and_rejects_windows_that_cannot_hold_it():
    policy = WindowPolicy("orbital", culmination_placement=True)
    windows = (
        # Long enough in total (20 minutes for 10), but the culmination sits
        # 2 minutes in, so the centred action would start before the window.
        _window("W-A-1", "SAT-A", 10, 30, peak=12),
        _window("W-A-2", "SAT-A", 50, 80, peak=60),
    )
    scenario = _scenario(satellites=(_satellite("SAT-A"),), policy=policy)
    session, _ = _session(scenario, windows)

    row = session.get_feasibility(10.0, 20.0, 600.0, DEADLINE).results[0]

    assert row.window_id == "W-A-2"
    assert row.earliest_start == _at(55)
    assert row.earliest_start + timedelta(seconds=600) <= row.latest_finish


def test_culmination_start_must_also_finish_before_the_deadline():
    policy = WindowPolicy("orbital", culmination_placement=True)
    scenario = _scenario(satellites=(_satellite("SAT-A"),), policy=policy)
    session, _ = _session(scenario, (_window("W-A-1", "SAT-A", 10, 40, peak=30),))

    # The window start would fit before a 25-minute deadline; the centred
    # start (25 to 35) does not.
    row = session.get_feasibility(10.0, 20.0, 600.0, _at(25)).results[0]

    assert row.reason is FeasibilityReason.NO_SUITABLE_WINDOW


def test_culmination_without_a_peak_uses_window_start_only_when_the_action_fits():
    scenario = _scenario(
        satellites=(_satellite("SAT-A"),),
        policy=WindowPolicy("orbital", culmination_placement=True),
    )
    session, _ = _session(scenario, (_window("W-A-1", "SAT-A", 10, 30),))

    suitable = session.get_feasibility(10.0, 20.0, 600.0, DEADLINE).results[0]
    unsuitable = session.get_feasibility(10.0, 20.0, 1800.0, DEADLINE).results[0]

    assert suitable.reason is None
    assert suitable.earliest_start == suitable.window_start == _at(10)
    assert unsuitable.reason is FeasibilityReason.NO_SUITABLE_WINDOW
    assert unsuitable.earliest_start is None


def test_unsuitable_and_unavailable_satellites_are_listed_with_null_fields():
    satellites = (_satellite("SAT-C", available=False), _satellite("SAT-B"), _satellite("SAT-A"))
    windows = (_window("W-B-1", "SAT-B", 20, 40), _window("W-C-1", "SAT-C", 5, 40))
    session, _ = _session(_scenario(satellites=satellites), windows)

    result = session.get_feasibility(10.0, 20.0, 300.0, DEADLINE)

    assert [(row.satellite_id, row.reason) for row in result.results] == [
        ("SAT-B", None),
        ("SAT-A", FeasibilityReason.NO_SUITABLE_WINDOW),
        ("SAT-C", FeasibilityReason.SATELLITE_UNAVAILABLE),
    ]
    for row in result.results[1:]:
        assert row.to_dict() == {
            "satellite_id": row.satellite_id, "window_id": None, "window_start": None,
            "window_end": None, "earliest_start": None, "latest_finish": None,
            "reason": row.reason.value,
        }


def test_no_suitable_satellite_gives_a_null_earliest_satellite():
    session, _ = _session(windows=())

    result = session.get_feasibility(10.0, 20.0, 300.0, DEADLINE)

    assert result.earliest_satellite_id is None
    assert [row.satellite_id for row in result.results] == ["SAT-A", "SAT-B", "SAT-C"]


def test_finite_duration_beyond_the_search_horizon_has_no_suitable_window():
    session, _ = _session()

    result = session.get_feasibility(10.0, 20.0, 1e300, DEADLINE)

    assert result.earliest_satellite_id is None
    assert all(row.reason is FeasibilityReason.NO_SUITABLE_WINDOW for row in result.results)


def test_equal_earliest_starts_break_ties_by_satellite_id():
    windows = (_window("W-C-1", "SAT-C", 20, 40), _window("W-B-1", "SAT-B", 20, 40), _window("W-A-1", "SAT-A", 20, 40))
    session, _ = _session(windows=windows)

    result = session.get_feasibility(10.0, 20.0, 300.0, DEADLINE)

    assert [row.satellite_id for row in result.results] == ["SAT-A", "SAT-B", "SAT-C"]
    assert result.earliest_satellite_id == "SAT-A"


def test_satellite_filter_returns_only_that_row_and_asks_only_for_it():
    session, provider = _session()

    result = session.get_feasibility(10.0, 20.0, 300.0, DEADLINE, satellite_id="SAT-A")

    assert [row.satellite_id for row in result.results] == ["SAT-A"]
    assert result.satellite_id == "SAT-A"
    assert provider.candidates[-1].satellite_id == "SAT-A"
    assert provider.candidates[-1].deadline == DEADLINE


# --- read-only behaviour ---------------------------------------------------


def test_queries_change_no_session_state_and_ignore_clock_and_replan():
    session, _ = _session()
    session.generate_windows()
    session.plan()
    before_clock = session.get_feasibility(10.0, 20.0, 300.0, DEADLINE)
    snapshot = _snapshot(session)

    repeated = session.get_feasibility(10.0, 20.0, 300.0, DEADLINE)
    assert _snapshot(session) == snapshot
    assert repeated == before_clock
    assert FEASIBILITY_REQUEST_ID not in {request.id for request in session.get_request_pool()}

    # The search starts at Scenario start, so a window that has already
    # passed on the mission clock is still the earliest suitable one.
    session.step(45 * 60)
    session.replan(session.get_plan().id)
    assert session.get_feasibility(10.0, 20.0, 300.0, DEADLINE) == before_clock


def test_all_satellite_and_filtered_queries_preserve_the_next_identifier_sequence():
    session, _ = _session()
    session.generate_windows()
    session.plan()

    def next_identifiers():
        plans = session.get_plans()
        return (
            next_id(PLAN_ID_PREFIX, [plan.id for plan in plans]),
            next_id(ACTION_ID_PREFIX, [action.id for plan in plans for action in plan.actions]),
            next_id(EVENT_ID_PREFIX, [event.id for event in session.get_events()]),
            next_id(IMPACT_ID_PREFIX, [impact.id for impact in session.get_impacts()]),
            next_id(TRACE_ID_PREFIX, [trace.id for trace in session.get_traces()]),
        )

    before = next_identifiers()
    session.get_feasibility(10.0, 20.0, 300.0, DEADLINE)
    session.get_feasibility(10.0, 20.0, 300.0, DEADLINE, satellite_id="SAT-B")

    assert next_identifiers() == before


# --- validation ------------------------------------------------------------


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ((math.nan, 20.0, 300.0, DEADLINE), "finite"),
        ((91.0, 20.0, 300.0, DEADLINE), "bounds"),
        ((10.0, -181.0, 300.0, DEADLINE), "bounds"),
        ((10.0, 20.0, 0.0, DEADLINE), "positive"),
        ((10.0, 20.0, math.inf, DEADLINE), "finite"),
        ((10.0, 20.0, 300.0, DEADLINE.replace(tzinfo=None)), "timezone"),
        ((10.0, 20.0, 300.0, START), "after the scenario start"),
    ],
)
def test_invalid_inputs_are_rejected_without_calling_the_provider(args, message):
    session, provider = _session()

    with pytest.raises(InvalidScenarioError, match=message):
        session.get_feasibility(*args)
    assert provider.candidates == []


def test_unknown_satellite_and_non_orbital_policy_are_domain_errors():
    session, _ = _session()
    with pytest.raises(InvalidScenarioError, match="no satellite"):
        session.get_feasibility(10.0, 20.0, 300.0, DEADLINE, satellite_id="SAT-Z")

    synthetic, _ = _session(_scenario(policy=WindowPolicy("synthetic")))
    with pytest.raises(InvalidScenarioError, match="orbital window policies only"):
        synthetic.get_feasibility(10.0, 20.0, 300.0, DEADLINE)


# --- real orbital provider -------------------------------------------------


def test_real_orbital_windows_produce_a_policy_compatible_earliest_start():
    scenario = orbital_example()
    request = scenario.requests[0]
    session = MissionSession(window_provider=OrbitalWindowProvider())
    session.load_scenario(scenario)

    result = session.get_feasibility(request.target_lat, request.target_lon, 30.0, scenario.end_time)

    row = result.results[0]
    assert row.reason is None, row
    assert scenario.start_time <= row.window_start <= row.earliest_start
    assert row.earliest_start + timedelta(seconds=30) <= row.latest_finish <= row.window_end
    assert session.get_windows() == ()


# --- HTTP ------------------------------------------------------------------


def _http(provider, scenario: Scenario):
    # Seeded through the store: POST /scenarios previews orbital missions
    # against a stored orbit, which the stub Scenario does not carry.
    repositories = Repositories.in_memory()
    MissionSessionStore(repositories, window_provider=provider).create(scenario)
    app = create_app(repositories, window_provider=provider)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _query(**changes):
    params = {"lat": 10.0, "lon": 20.0, "duration": 300.0, "deadline": DEADLINE.isoformat()}
    params.update(changes)
    return {key: value for key, value in params.items() if value is not None}


def test_http_returns_the_window_only_answer_and_saves_nothing():
    async def run() -> None:
        scenario = _scenario()
        async with _http(_StubProvider(CANDIDATE_WINDOWS), scenario) as client:
            await client.post(f"/scenarios/{scenario.id}/windows/generate")
            await client.post(f"/scenarios/{scenario.id}/plan")
            paths = ("state", "events", "windows", "plans", "requests")
            before = [(await client.get(f"/scenarios/{scenario.id}/{path}")).json() for path in paths]

            first = await client.get(f"/scenarios/{scenario.id}/feasibility", params=_query())
            second = await client.get(f"/scenarios/{scenario.id}/feasibility", params=_query())

            assert first.status_code == 200, first.text
            body = first.json()
            assert body == second.json()
            assert body["scope"] == "window_only"
            assert body["earliest_satellite_id"] == "SAT-B"
            assert datetime.fromisoformat(body["search_start"]) == START
            assert datetime.fromisoformat(body["search_end"]) == END
            assert set(body["results"][0]) == {
                "satellite_id", "window_id", "window_start", "window_end",
                "earliest_start", "latest_finish", "reason",
            }
            after = [(await client.get(f"/scenarios/{scenario.id}/{path}")).json() for path in paths]
            assert after == before

            filtered = await client.get(
                f"/scenarios/{scenario.id}/feasibility", params=_query(satellite_id="SAT-C")
            )
            assert [row["satellite_id"] for row in filtered.json()["results"]] == ["SAT-C"]

    asyncio.run(run())


@pytest.mark.parametrize(
    "changes",
    [
        {"lat": 90.5},
        {"lon": "nan"},
        {"duration": 0},
        {"duration": "inf"},
        {"deadline": DEADLINE.replace(tzinfo=None).isoformat()},
        {"deadline": None},
        {"satellite_id": ""},
    ],
)
def test_http_malformed_inputs_use_the_validation_envelope(changes):
    async def run() -> None:
        scenario = _scenario()
        async with _http(_StubProvider(CANDIDATE_WINDOWS), scenario) as client:
            response = await client.get(f"/scenarios/{scenario.id}/feasibility", params=_query(**changes))
            assert response.status_code == 422, response.text
            assert response.json()["error"]["message"] == "request validation failed"

    asyncio.run(run())


def test_http_unknown_scenario_and_domain_errors():
    async def run() -> None:
        scenario = _scenario()
        async with _http(_StubProvider(CANDIDATE_WINDOWS), scenario) as client:

            missing = await client.get("/scenarios/SCN-MISSING/feasibility", params=_query())
            assert missing.status_code == 404
            assert missing.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

            early = await client.get(
                f"/scenarios/{scenario.id}/feasibility", params=_query(deadline=START.isoformat())
            )
            assert early.status_code == 400
            assert early.json()["error"]["code"] == "INVALID_SCENARIO"

            unknown = await client.get(
                f"/scenarios/{scenario.id}/feasibility", params=_query(satellite_id="SAT-Z")
            )
            assert unknown.status_code == 400
            assert unknown.json()["error"]["details"] == {"satellite_id": "SAT-Z"}

    asyncio.run(run())
