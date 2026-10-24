"""Requester measurement through the confirmed MissionSession seam."""

from dataclasses import replace
from datetime import timedelta
import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine

from amis.api_schemas import MetricsSchema, ObservationRequestSchema
from amis.api import create_app
from amis.cues import ImagingProfile
from amis.db.repositories import build_repositories
from amis.db.schema import metadata
from amis.demo import CanonicalWindowProvider, build_emergency_replan_fixture
from amis.domain import EventType
from amis.repositories import MissionSessionStore
from amis.session import MissionSession


class RequesterWindowProvider(CanonicalWindowProvider):
    WINDOW_OFFSETS = {**CanonicalWindowProvider.WINDOW_OFFSETS,
                      "OBS-IMPOSSIBLE": (), "OBS-EXPIRED": ()}


def test_requester_demand_and_unique_service_preserve_case_distinctions():
    scenario, _ = build_emergency_replan_fixture()
    scenario = replace(scenario, requests=tuple(
        replace(request, requester_id="Agency" if index < 2 else "agency")
        for index, request in enumerate(scenario.requests)
    ))
    session = MissionSession(window_provider=RequesterWindowProvider())
    session.load_scenario(scenario)
    session.generate_windows()
    session.plan()
    metrics = session.get_metrics().to_dict()
    rows = metrics["requester_service"]["requesters"]
    assert [row["requester_id"] for row in rows] == ["Agency", "agency"]
    assert sum(row["demand_utility"] for row in rows) == sum(r.priority for r in scenario.requests)
    assert sum(row["served_utility"] for row in rows) == metrics["mission_utility"]
    assert sum(row["service_share"] for row in rows) == 1


def _attributed_scenario():
    scenario, payload = build_emergency_replan_fixture()
    requests = tuple(replace(request, requester_id={"OBS-A": "A", "OBS-B": "B"}.get(request.id))
                     for request in scenario.requests)
    impossible = replace(requests[0], id="OBS-IMPOSSIBLE", requester_id="A", priority=3)
    expired = replace(requests[0], id="OBS-EXPIRED", requester_id="C", priority=2,
                      deadline=scenario.start_time - timedelta(seconds=1))
    return replace(scenario, requests=(*requests, impossible, expired)), payload


def test_unequal_demand_infeasible_expired_and_unattributed_totals():
    scenario, _ = _attributed_scenario()
    session = MissionSession(window_provider=RequesterWindowProvider())
    session.load_scenario(scenario)
    session.generate_windows()
    session.plan()
    service = session.get_metrics().to_dict()["requester_service"]
    assert service["requesters"] == [
        dict(requester_id="A", request_count=2, demand_utility=8, served_request_count=1,
             served_utility=5, service_share=5/17, fulfillment_ratio=5/8),
        dict(requester_id="B", request_count=1, demand_utility=4, served_request_count=1,
             served_utility=4, service_share=4/17, fulfillment_ratio=1),
        dict(requester_id="C", request_count=1, demand_utility=2, served_request_count=0,
             served_utility=0, service_share=0, fulfillment_ratio=0),
    ]
    assert service["unattributed"] == dict(requester_id=None, request_count=3,
        demand_utility=8, served_request_count=3, served_utility=8,
        service_share=8/17, fulfillment_ratio=1)
    assert service["fairness_gap"] == 5
    assert service["zero_service_requester_count"] == 1


def test_no_service_has_null_shares_and_zero_gap_with_explicit_indicator():
    scenario, _ = _attributed_scenario()
    scenario = replace(scenario, satellite=replace(scenario.satellite, available=False))
    session = MissionSession(window_provider=RequesterWindowProvider())
    session.load_scenario(scenario)
    session.generate_windows()
    session.plan()
    service = session.get_metrics().requester_service
    assert service.no_service
    assert service.fairness_gap == 0
    assert service.zero_service_requester_count == 3
    assert all(row.service_share is None and row.fulfillment_ratio == 0 for row in service.requesters)
    assert service.unattributed.service_share is None


def test_completed_frozen_and_later_arrivals_remain_unique_after_sql_restart(tmp_path):
    scenario, payload = _attributed_scenario()
    engine = create_engine(f"sqlite:///{tmp_path / 'requesters.db'}")
    metadata.create_all(engine)
    store = MissionSessionStore(build_repositories(engine), window_provider=RequesterWindowProvider())
    session = store.create(scenario)
    session.generate_windows()
    first = session.plan()
    session.step(300)  # OBS-A is running and must remain frozen through replan.
    payload = replace(payload, request=replace(payload.request, requester_id="Arrival"))
    session.inject_event(EventType.EMERGENCY_TASK, payload.to_dict())
    session.replan()
    assert session.get_metrics(first.id).requester_service.total_served_utility == 17
    session.step(3600)  # Includes completed emergency imaging outside first's pool.
    session.replan()
    before = {plan.id: session.get_metrics(plan.id).to_dict() for plan in session.get_plans()}
    assert before[first.id]["requester_service"]["total_served_utility"] == 17
    assert "Arrival" not in [row["requester_id"] for row in before[first.id]["requester_service"]["requesters"]]
    latest = session.get_metrics().requester_service
    assert next(row for row in latest.requesters if row.requester_id == "A").served_utility == 5
    assert next(row for row in latest.requesters if row.requester_id == "Arrival").served_utility == 5
    store.save(session)
    engine.dispose()
    reopened = create_engine(f"sqlite:///{tmp_path / 'requesters.db'}")
    restored = MissionSessionStore(build_repositories(reopened), window_provider=RequesterWindowProvider()).load(scenario.id)
    for plan in restored.get_plans():
        assert restored.get_metrics(plan.id).requester_service.to_dict() == before[plan.id]["requester_service"]
        assert restored.get_metrics(plan.id).measured_at == session.get_metrics(plan.id).measured_at
    assert restored.get_scenario().requests[0].requester_id == "A"
    reopened.dispose()


@pytest.mark.parametrize("identity", ["", " ", " A", "A ", "A\n", 12])
def test_requester_identity_is_validated_without_normalization(identity):
    scenario, _ = build_emergency_replan_fixture()
    request = scenario.requests[0]
    with pytest.raises((ValueError, TypeError)):
        replace(request, requester_id=identity)
    with pytest.raises(ValueError):
        ObservationRequestSchema.model_validate({**request.to_dict(), "requester_id": identity})
    with pytest.raises(ValueError):
        ImagingProfile.from_dict(dict(duration_s=60, energy_cost_wh=10, storage_cost_mb=25, requester_id=identity))


def test_absent_identity_serialization_and_single_requester_gap():
    scenario, _ = build_emergency_replan_fixture()
    assert "requester_id" not in scenario.requests[0].to_dict()
    assert "requester_id" not in ImagingProfile(60, 10, 25).to_dict()
    session = MissionSession(window_provider=CanonicalWindowProvider())
    session.load_scenario(replace(scenario, requests=tuple(replace(r, requester_id="Only") for r in scenario.requests)))
    session.generate_windows()
    session.plan()
    metrics = session.get_metrics()
    assert metrics.requester_service.fairness_gap is None
    assert MetricsSchema.model_validate(metrics.to_dict()).requester_service.metric_version == "requester-utility-v1"


def test_api_validates_and_returns_attribution_and_requester_metrics():
    async def run():
        scenario, payload = _attributed_scenario()
        app = create_app(window_provider=RequesterWindowProvider())
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            invalid = scenario.to_dict()
            invalid["requests"][0]["requester_id"] = " A "
            assert (await client.post("/scenarios", json=invalid)).status_code == 422
            created = await client.post("/scenarios", json=scenario.to_dict())
            assert created.status_code == 201
            requests = created.json()["requests"]
            assert requests[0]["requester_id"] == "A"
            assert "requester_id" not in requests[2]
            assert (await client.post(f"/scenarios/{scenario.id}/windows/generate")).status_code == 200
            planned = await client.post(f"/scenarios/{scenario.id}/plan")
            assert planned.status_code == 201
            metrics = await client.get(f"/plans/{planned.json()['id']}/metrics")
            assert metrics.status_code == 200
            assert metrics.json()["requester_service"]["fairness_gap"] == 5
            request = replace(payload.request, requester_id="Emergency")
            arrival = await client.post(f"/scenarios/{scenario.id}/events", json={
                "event_type": "EMERGENCY_TASK", "payload": {**payload.to_dict(), "request": request.to_dict()}})
            assert arrival.status_code == 201
            assert arrival.json()["payload"]["request"]["requester_id"] == "Emergency"
    asyncio.run(run())
