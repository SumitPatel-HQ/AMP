"""REST API tests for scenario reset and mission lifecycle."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from amis.api import create_app
from amis.demo import CanonicalWindowProvider, build_canonical_replan_scenario
from amis.domain import EventType, ObservationRequest, Satellite, Scenario


def _emergency_payload():
    request = {
        "id": "OBS-EMERGENCY",
        "target_lat": 34.05,
        "target_lon": -118.24,
        "priority": 5,
        "duration_s": 600.0,
        "deadline": "2026-09-21T10:50:00+00:00",
        "energy_cost_wh": 40.0,
        "storage_cost_mb": 100.0,
        "status": "pending",
    }
    window = {
        "id": "WIN-OBS-EMERGENCY-1",
        "request_id": "OBS-EMERGENCY",
        "satellite_id": "SAT-001",
        "start": "2026-09-21T10:40:00+00:00",
        "end": "2026-09-21T10:55:00+00:00",
        "valid": True,
        "invalid_reason": None,
    }
    return {
        "event_type": "EMERGENCY_TASK",
        "payload": {"request": request, "windows": [window]},
    }


def test_reset_route_resets_clock_plans_events_state_and_metrics():
    """Verify POST /scenarios/{scenario_id}/reset clears in-progress state,
    events, plans, and resets the clock to start_time.
    """
    async def run() -> None:
        app = create_app(window_provider=CanonicalWindowProvider())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            scenario = build_canonical_replan_scenario()
            await client.post("/scenarios", json=scenario.to_dict())
            await client.post(f"/scenarios/{scenario.id}/windows/generate")
            plan_res = await client.post(f"/scenarios/{scenario.id}/plan")
            plan_v1 = plan_res.json()

            # Advance clock and inject emergency event
            await client.post(
                f"/scenarios/{scenario.id}/simulation/step", json={"seconds": 300}
            )
            event_res = await client.post(
                f"/scenarios/{scenario.id}/events", json=_emergency_payload()
            )
            assert event_res.status_code == 201

            # Replan to version 2 incorporating the emergency
            replan_res = await client.post(
                f"/scenarios/{scenario.id}/replan",
                json={"expected_parent_plan_id": plan_v1["id"]},
            )
            plan_v2 = replan_res.json()

            # Step clock past the emergency acquisition start so it's achieved
            await client.post(
                f"/scenarios/{scenario.id}/simulation/step", json={"seconds": 2400}
            )

            # Check that metrics show achieved emergency response before reset
            metrics_before = (
                await client.get(f"/plans/{plan_v2['id']}/metrics")
            ).json()
            assert metrics_before["achieved_emergency_request_count"] == 1
            assert len(metrics_before["emergency_response"]) == 1

            # Ensure events and plans exist before reset
            events_before = (
                await client.get(f"/scenarios/{scenario.id}/events")
            ).json()
            assert len(events_before) == 1
            plans_before = (
                await client.get(f"/scenarios/{scenario.id}/plans")
            ).json()
            assert len(plans_before) == 2

            # Now perform RESET
            reset_res = await client.post(f"/scenarios/{scenario.id}/reset")
            assert reset_res.status_code == 200
            reset_state = reset_res.json()

            # 1. Clock is reset to scenario start_time
            assert datetime.fromisoformat(reset_state["simulated_time"]) == scenario.start_time
            assert reset_state["mission_complete"] is False
            assert reset_state["active_event_ids"] == []

            # 2. GET /scenarios/{scenario_id}/events returns []
            events_after = (
                await client.get(f"/scenarios/{scenario.id}/events")
            ).json()
            assert events_after == []

            # 3. GET /scenarios/{scenario_id}/plans returns []
            plans_after = (
                await client.get(f"/scenarios/{scenario.id}/plans")
            ).json()
            assert plans_after == []

            # 4. GET /scenarios/{scenario_id}/state reports initial state
            state_after = (
                await client.get(f"/scenarios/{scenario.id}/state")
            ).json()
            assert datetime.fromisoformat(state_after["simulated_time"]) == scenario.start_time
            assert state_after["mission_complete"] is False
            assert state_after["active_event_ids"] == []

            # 5. GET /scenarios/{scenario_id}/requests returns pristine scenario requests
            requests_after = (
                await client.get(f"/scenarios/{scenario.id}/requests")
            ).json()
            assert [r["id"] for r in requests_after] == [r.id for r in scenario.requests]

            # 6. Verify we can generate windows and plan anew after reset
            await client.post(f"/scenarios/{scenario.id}/windows/generate")
            new_plan_res = await client.post(f"/scenarios/{scenario.id}/plan")
            assert new_plan_res.status_code == 201
            new_plan = new_plan_res.json()
            new_metrics = (
                await client.get(f"/plans/{new_plan['id']}/metrics")
            ).json()
            # Emergency response metrics are cleared
            assert new_metrics["emergency_response"] == []
            assert new_metrics["emergency_request_count"] == 0
            assert new_metrics["achieved_emergency_request_count"] == 0

    asyncio.run(run())


def test_reset_route_completed_mission():
    """Verify resetting a completed mission restores mission_complete: false
    and pristine start_time.
    """
    async def run() -> None:
        app = create_app(window_provider=CanonicalWindowProvider())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            scenario = build_canonical_replan_scenario()
            await client.post("/scenarios", json=scenario.to_dict())
            await client.post(f"/scenarios/{scenario.id}/windows/generate")
            await client.post(f"/scenarios/{scenario.id}/plan")

            # Step until end of mission
            duration = (scenario.end_time - scenario.start_time).total_seconds()
            step_res = await client.post(
                f"/scenarios/{scenario.id}/simulation/step", json={"seconds": duration}
            )
            assert step_res.json()["mission_complete"] is True

            # Reset
            reset_res = await client.post(f"/scenarios/{scenario.id}/reset")
            assert reset_res.status_code == 200
            assert reset_res.json()["mission_complete"] is False
            assert datetime.fromisoformat(reset_res.json()["simulated_time"]) == scenario.start_time

            state = (await client.get(f"/scenarios/{scenario.id}/state")).json()
            assert state["mission_complete"] is False

    asyncio.run(run())


def test_reset_route_error_responses():
    """Verify 404 for unknown scenario and documented error status codes."""
    async def run() -> None:
        app = create_app(window_provider=CanonicalWindowProvider())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            missing = await client.post("/scenarios/NONEXISTENT/reset")
            assert missing.status_code == 404
            assert missing.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

    asyncio.run(run())
