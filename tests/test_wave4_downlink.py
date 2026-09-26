"""Wave 4: ground-station contacts, downlink actions, communication outages (ADR-0011)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from amis.constraints import ResourceProjection
from amis.domain import ActionKind, ScheduledAction
from amis.domain.plan import MissionPlan
from amis.examples import orbital_example
from amis.session import MissionSession
from amis.windows.orbital import OrbitalWindowProvider

STATIONS = ("SVALSAT", "KIRUNA", "HBK")


def _tight_scenario(stations=STATIONS, rate=50.0):
    scenario = orbital_example()
    capacity = sum(request.storage_cost_mb for request in scenario.requests) / 3
    return replace(
        scenario,
        satellite=replace(scenario.satellite, storage_capacity_mb=capacity),
        window_policy=replace(
            scenario.window_policy, ground_station_ids=tuple(stations), downlink_rate_mb_s=rate
        ),
    )


def _session(scenario, planner="greedy"):
    session = MissionSession(window_provider=OrbitalWindowProvider())
    session.load_scenario(scenario)
    session.select_planner(planner)
    return session


@pytest.fixture(scope="module")
def downlink_session():
    session = _session(_tight_scenario())
    session.plan()
    return session


def test_contacts_open_and_close_at_the_station_mask(downlink_session):
    from skyfield.api import EarthSatellite, load, wgs84

    scenario = downlink_session.get_scenario()
    station = downlink_session.get_ground_stations()[0]
    ts = load.timescale(builtin=True)
    satellite = EarthSatellite.from_omm(ts, scenario.satellite.orbit.omm)
    site = wgs84.latlon(station.lat, station.lon, elevation_m=station.altitude_m)

    def elevation(instant):
        return (satellite - site).at(ts.from_datetime(instant)).altaz()[0].degrees

    contacts = [c for c in downlink_session.get_contacts() if c.station_id == station.id]
    assert contacts
    for contact in contacts:
        if contact.start > scenario.start_time:
            assert elevation(contact.start - timedelta(seconds=2)) < station.min_elevation_deg
            assert elevation(contact.start + timedelta(seconds=2)) >= station.min_elevation_deg
        assert contact.peak_elevation_deg >= station.min_elevation_deg


def test_downlink_release_floors_storage_at_zero():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    projection = ResourceProjection(100.0, 30.0)
    projection.commit(ScheduledAction(
        "ACT-1", None, "SAT", "CON-X-1", t0, t0 + timedelta(minutes=5), 0.0, -500.0,
        kind=ActionKind.DOWNLINK, station_id="X",
    ))
    assert projection.available_at(t0 + timedelta(minutes=1)) == (100.0, 30.0)
    assert projection.available_at(t0 + timedelta(minutes=5)) == (100.0, 0.0)
    assert projection.freed_by_downlinks() == {"ACT-1": 30.0}


@pytest.mark.parametrize("planner", ["greedy", "cp_sat"])
def test_downlink_keeps_a_storage_bound_mission_feasible(planner):
    without = _session(_tight_scenario(stations=()), planner).plan()
    session = _session(_tight_scenario(), planner)
    plan = session.plan()

    downlinks = [a for a in plan.actions if a.is_downlink]
    assert downlinks and plan.violation_count == 0
    assert plan.mission_utility > without.mission_utility
    assert all(a.request_id is None and a.station_id in STATIONS for a in downlinks)
    assert all(a.storage_cost_mb < 0 and a.energy_cost_wh == 0 for a in downlinks)


def test_storage_rises_on_imaging_and_falls_on_downlink_across_the_mission():
    session = _session(_tight_scenario())
    plan = session.plan()
    levels = []
    for action in sorted(plan.actions, key=lambda a: a.end):
        state = session.step((action.end - session.get_state().simulated_time).total_seconds() or 1)
        levels.append((action.kind, state.storage_usage_mb))
        assert state.storage_usage_mb >= 0
    rises = any(kind is ActionKind.IMAGING and level > 0 for kind, level in levels)
    falls = any(
        kind is ActionKind.DOWNLINK and level < prev
        for (_, prev), (kind, level) in zip(levels, levels[1:])
    )
    assert rises and falls


def test_communication_outage_invalidates_its_contact_and_replan_moves_on():
    session = _session(_tight_scenario())
    plan = session.plan()
    target = next(a for a in plan.actions if a.is_downlink)

    session.inject_communication_outage(target.station_id, target.start, target.end)

    lost = {c.id for c in session.get_contacts() if not c.valid}
    assert target.window_id in lost
    impact = session.get_last_impact()
    assert target.id in impact.invalid_unfrozen_action_ids
    assert [r.value for r in impact.reason_codes[target.id]] == ["WINDOW_INVALIDATED"]

    replanned = session.replan()
    assert replanned.violation_count == 0
    assert all(a.window_id not in lost for a in replanned.actions if a.is_downlink)
    diff = session.compare_versions(1, 2)
    assert all(entry.request_id is not None for entry in diff.entries)
    metrics = session.get_metrics()
    assert metrics.downlink_action_count == sum(a.is_downlink for a in replanned.actions)
    assert metrics.downlink_volume_mb > 0
    assert all(trace.request_id is not None for trace in session.get_traces())


def test_communication_outage_rejects_a_station_outside_the_mission(downlink_session):
    from amis.errors import InvalidEventError

    start = downlink_session.get_scenario().start_time
    with pytest.raises(InvalidEventError):
        downlink_session.inject_communication_outage("TROLLSAT", start, start + timedelta(hours=1))


def test_downlink_actions_round_trip_through_plan_serialisation(downlink_session):
    plan = downlink_session.get_plan()
    assert MissionPlan.from_dict(plan.to_dict()) == plan


def test_mission_without_stations_has_no_contacts_or_downlinks():
    session = _session(orbital_example())
    plan = session.plan()
    assert session.get_contacts() == ()
    assert not any(a.is_downlink for a in plan.actions)


def test_ground_station_catalogue_route_lists_the_hashed_catalogue():
    import asyncio

    from httpx import ASGITransport, AsyncClient

    from amis.api import create_app

    async def run():
        transport = ASGITransport(app=create_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/ground-stations")
        assert response.status_code == 200
        assert {"SVALSAT", "KIRUNA", "HBK"} <= {station["id"] for station in response.json()}

    asyncio.run(run())
