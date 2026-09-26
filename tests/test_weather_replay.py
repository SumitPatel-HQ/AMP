"""Wave 5: weather-derived blocks flow through the unchanged loop and replay offline.

A threshold payload computed from the committed archive is injected as
an ordinary ``CLOUD_BLOCK``: impact, replan, diff, traces, and metrics
all behave as they do for a hand-injected block. Rebuilding from the
pristine scenario plus the recorded event log reproduces the plans with
no archive and no network.
"""

import contextlib
import socket
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from amis.api_schemas import CloudBlockPayloadSchema
from amis.domain import (
    EventType,
    ObservationRequest,
    ObservationWindow,
    ReasonCode,
    Satellite,
    Scenario,
)
from amis.errors import InvalidEventError
from amis.session import MissionSession
from amis.weather import (
    cloud_block_payloads_for_windows,
    load_archive,
    normalize_archive,
)

T0 = datetime(2026, 9, 25, 4, tzinfo=timezone.utc)
END = T0 + timedelta(hours=6)
PEAK = datetime(2026, 9, 25, 6, 30, tzinfo=timezone.utc)
THRESHOLD = 50.0


def _scenario() -> Scenario:
    targets = {"OBS-BLR": (12.97, 77.59, 5), "OBS-DEL": (28.61, 77.21, 4)}
    requests = tuple(
        ObservationRequest(
            id=request_id,
            target_lat=lat,
            target_lon=lon,
            priority=priority,
            duration_s=60.0,
            deadline=END,
            energy_cost_wh=10.0,
            storage_cost_mb=10.0,
        )
        for request_id, (lat, lon, priority) in targets.items()
    )
    return Scenario(
        id="SCN-WX",
        name="Weather replay test",
        start_time=T0,
        end_time=END,
        satellite=Satellite(
            id="SAT-001",
            battery_capacity_wh=100.0,
            battery_charge_wh=100.0,
            storage_capacity_mb=100.0,
            storage_usage_mb=0.0,
        ),
        requests=requests,
    )


class _WeatherWindowProvider:
    """One window per request, culminating when the archive turns cloudy over Bengaluru."""

    def generate(self, scenario, requests):
        return [
            ObservationWindow(
                id=f"WIN-{request.id}-1",
                request_id=request.id,
                satellite_id=scenario.satellite.id,
                start=PEAK - timedelta(minutes=5),
                end=PEAK + timedelta(minutes=5),
                peak_time=PEAK,
            )
            for request in requests
        ]


def _weather_payloads(session: MissionSession):
    samples = normalize_archive(load_archive().records)
    return cloud_block_payloads_for_windows(
        samples,
        session.get_request_pool(),
        session.get_windows(),
        threshold_pct=THRESHOLD,
    )


def _run_loop(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    """Drive the full loop from a pristine scenario and recorded-style payload dicts."""
    session = MissionSession(window_provider=_WeatherWindowProvider())
    scenario = session.load_scenario(_scenario().to_dict())
    session.generate_windows()
    first = session.plan()
    session.step(5)
    events = [
        session.inject_event(EventType.CLOUD_BLOCK, payload) for payload in payloads
    ]
    impact = session.get_last_impact()
    second = session.replan(expected_parent_plan_id=first.id)
    return {
        "scenario": scenario,
        "session": session,
        "events": events,
        "impact": impact,
        "first": first,
        "second": second,
    }


def _fingerprint(plan) -> dict[str, Any]:
    data = plan.to_dict()
    data.pop("planning_time_ms", None)
    data.pop("created_at", None)
    return data


def test_weather_blocks_reshape_the_plan_like_hand_injected_ones():
    session = MissionSession(window_provider=_WeatherWindowProvider())
    session.load_scenario(_scenario())
    session.generate_windows()
    first = session.plan()
    assert {action.request_id for action in first.actions} == {"OBS-BLR", "OBS-DEL"}

    payloads = _weather_payloads(session)
    assert [(payload.request_id, payload.cloud_cover_pct) for payload in payloads] == [
        ("OBS-BLR", 85.0)
    ]

    session.step(5)
    event = session.inject_event(EventType.CLOUD_BLOCK, payloads[0])
    assert event.payload.is_weather_derived

    impact = session.get_last_impact()
    actions_by_request = {action.request_id: action.id for action in first.actions}
    assert impact.invalid_unfrozen_action_ids == (actions_by_request["OBS-BLR"],)
    assert impact.valid_unfrozen_action_ids == (actions_by_request["OBS-DEL"],)

    second = session.replan(expected_parent_plan_id=first.id)
    assert {action.request_id for action in second.actions} == {"OBS-DEL"}
    # The blocked request held a placement and lost its only window, so
    # the replan reports no alternative -- the same reason a
    # hand-injected block produces on this shape.
    assert {
        entry.request_id: entry.reason_code for entry in second.unscheduled
    } == {"OBS-BLR": ReasonCode.NO_ALTERNATIVE_WINDOW}

    metrics = session.get_metrics(second.id)
    assert second.violation_count == 0
    assert metrics.explanation_coverage == 1.0


def test_replay_from_scenario_plus_event_log_reproduces_the_plans():
    session = MissionSession(window_provider=_WeatherWindowProvider())
    session.load_scenario(_scenario())
    session.generate_windows()
    session.plan()
    recorded_payloads = [payload.to_dict() for payload in _weather_payloads(session)]

    first_run = _run_loop(recorded_payloads)
    second_run = _run_loop(recorded_payloads)

    assert _fingerprint(second_run["first"]) == _fingerprint(first_run["first"])
    assert _fingerprint(second_run["second"]) == _fingerprint(first_run["second"])
    assert [event.to_dict() for event in second_run["events"]] == [
        event.to_dict() for event in first_run["events"]
    ]
    assert second_run["impact"].to_dict() == first_run["impact"].to_dict()


@contextlib.contextmanager
def _block_sockets():
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def _blocked(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError("network access is disabled during the weather replay")

    socket.socket.connect = _blocked  # type: ignore[method-assign]
    socket.socket.connect_ex = _blocked  # type: ignore[method-assign]
    try:
        yield
    finally:
        socket.socket.connect = original_connect  # type: ignore[method-assign]
        socket.socket.connect_ex = original_connect_ex  # type: ignore[method-assign]


def test_weather_loop_reproduces_without_network_or_archive():
    session = MissionSession(window_provider=_WeatherWindowProvider())
    session.load_scenario(_scenario())
    session.generate_windows()
    session.plan()
    # The archive is read once, offline, before the socket guard: everything
    # after this point replays recorded values only.
    recorded_payloads = [payload.to_dict() for payload in _weather_payloads(session)]

    with _block_sockets():
        guarded = _run_loop(recorded_payloads)
    unguarded = _run_loop(recorded_payloads)

    assert _fingerprint(guarded["second"]) == _fingerprint(unguarded["second"])


def test_weather_payload_passes_the_http_schema():
    payload = _weather_payloads(
        _planned_session_for_schema(),
    )[0]

    assert CloudBlockPayloadSchema.model_validate(payload.to_dict())


def _planned_session_for_schema() -> MissionSession:
    session = MissionSession(window_provider=_WeatherWindowProvider())
    session.load_scenario(_scenario())
    session.generate_windows()
    session.plan()
    return session


@pytest.mark.parametrize(
    "payload",
    [
        {"request_id": "OBS-BLR", "window_id": "WIN-OBS-BLR-1", "source": "open-meteo-archive"},
        {
            "request_id": "OBS-BLR",
            "window_id": "WIN-OBS-BLR-1",
            "source": "open-meteo-archive",
            "cloud_cover_pct": 85.0,
        },
        {
            "request_id": "OBS-BLR",
            "window_id": "WIN-OBS-BLR-1",
            "source": "open-meteo-archive",
            "cloud_cover_pct": 150.0,
            "threshold_pct": 50.0,
        },
    ],
)
def test_partial_or_wild_weather_evidence_is_rejected(payload):
    session = _planned_session_for_schema()

    with pytest.raises(InvalidEventError):
        session.inject_event(EventType.CLOUD_BLOCK, payload)
    with pytest.raises(ValueError):
        CloudBlockPayloadSchema.model_validate(payload)
