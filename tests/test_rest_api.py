"""HTTP contract tests for the AMIS mission loop."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from httpx import ASGITransport, AsyncClient

from amis.api import create_app
from amis.demo import CanonicalWindowProvider, build_canonical_replan_scenario
from amis.domain import ObservationRequest, Satellite, Scenario


START = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)


def _scenario(scenario_id: str = "SCN-API") -> Scenario:
    satellite = Satellite(
        id="SAT-001",
        battery_capacity_wh=200.0,
        battery_charge_wh=200.0,
        storage_capacity_mb=500.0,
        storage_usage_mb=0.0,
    )
    requests = (
        ObservationRequest(
            id="OBS-A",
            target_lat=12.97,
            target_lon=77.59,
            priority=5,
            duration_s=600.0,
            deadline=START + timedelta(hours=1),
            energy_cost_wh=20.0,
            storage_cost_mb=50.0,
        ),
        ObservationRequest(
            id="OBS-B",
            target_lat=28.61,
            target_lon=77.21,
            priority=4,
            duration_s=600.0,
            deadline=START + timedelta(hours=1),
            energy_cost_wh=20.0,
            storage_cost_mb=50.0,
        ),
    )
    return Scenario(
        id=scenario_id,
        name="REST API test",
        start_time=START,
        end_time=START + timedelta(hours=1),
        satellite=satellite,
        requests=requests,
    )


def test_whole_mission_flow_runs_over_the_asgi_transport():
    async def run() -> None:
        app = create_app(window_provider=CanonicalWindowProvider())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            scenario = build_canonical_replan_scenario()

            created = await client.post("/scenarios", json=scenario.to_dict())
            assert created.status_code == 201
            assert Scenario.from_dict(created.json()) == scenario

            loaded = await client.get(f"/scenarios/{scenario.id}")
            assert loaded.status_code == 200
            assert Scenario.from_dict(loaded.json()) == scenario

            windows = await client.post(
                f"/scenarios/{scenario.id}/windows/generate"
            )
            assert windows.status_code == 200
            assert len(windows.json()) == 6

            planned = await client.post(f"/scenarios/{scenario.id}/plan")
            assert planned.status_code == 201
            version_one = planned.json()
            assert version_one["version"] == 1

            state = await client.get(f"/scenarios/{scenario.id}/state")
            assert state.status_code == 200
            assert datetime.fromisoformat(state.json()["simulated_time"]) == (
                scenario.start_time
            )

            stepped = await client.post(
                f"/scenarios/{scenario.id}/simulation/step",
                json={"seconds": 300},
            )
            assert stepped.status_code == 200
            assert datetime.fromisoformat(stepped.json()["simulated_time"]) == (
                scenario.start_time + timedelta(seconds=300)
            )

            started_action = next(
                action
                for action in version_one["actions"]
                if action["request_id"] == "OBS-A"
            )
            blocked_action = next(
                action
                for action in version_one["actions"]
                if action["request_id"] == "OBS-B"
            )
            injected = await client.post(
                f"/scenarios/{scenario.id}/events",
                json={
                    "event_type": "CLOUD_BLOCK",
                    "payload": {
                        "request_id": blocked_action["request_id"],
                        "window_id": blocked_action["window_id"],
                    },
                },
            )
            assert injected.status_code == 201
            assert injected.json()["event_type"] == "CLOUD_BLOCK"

            impact = await client.get(f"/scenarios/{scenario.id}/impact")
            assert impact.status_code == 200
            assert impact.json()["evaluated_plan_id"] == version_one["id"]
            assert impact.json()["frozen_action_ids"] == [started_action["id"]]
            assert impact.json()["invalid_unfrozen_action_ids"] == [
                blocked_action["id"]
            ]

            replanned = await client.post(
                f"/scenarios/{scenario.id}/replan",
                json={"expected_parent_plan_id": version_one["id"]},
            )
            assert replanned.status_code == 201
            version_two = replanned.json()
            assert version_two["version"] == 2
            assert version_two["parent_plan_id"] == version_one["id"]

            current_plan = await client.get(f"/plans/{version_two['id']}")
            assert current_plan.status_code == 200
            assert current_plan.json() == version_two

            metrics = await client.get(f"/plans/{version_two['id']}/metrics")
            assert metrics.status_code == 200
            assert metrics.json()["plan_id"] == version_two["id"]

            comparison = await client.get(
                f"/plans/{version_one['id']}/compare/{version_two['id']}"
            )
            assert comparison.status_code == 200
            assert comparison.json()["from_plan_id"] == version_one["id"]
            assert comparison.json()["to_plan_id"] == version_two["id"]

            traces = await client.get(f"/plans/{version_two['id']}/traces")
            assert traces.status_code == 200
            assert traces.json()
            assert all(
                trace["plan_id"] == version_two["id"] for trace in traces.json()
            )

    asyncio.run(run())


def test_api_returns_documented_errors_for_invalid_order_and_stale_replans():
    async def run() -> None:
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            scenario = _scenario("SCN-ERRORS")
            assert (
                await client.post("/scenarios", json=scenario.to_dict())
            ).status_code == 201

            before_windows = await client.post(f"/scenarios/{scenario.id}/plan")
            assert before_windows.status_code == 409
            assert before_windows.json() == {
                "error": {
                    "code": "SIMULATION_STATE_ERROR",
                    "message": "observation windows must be generated before planning",
                    "details": {},
                }
            }

            before_plan = await client.post(
                f"/scenarios/{scenario.id}/events",
                json={
                    "event_type": "CLOUD_BLOCK",
                    "payload": {"request_id": "OBS-A", "window_id": "WIN-OBS-A-1"},
                },
            )
            assert before_plan.status_code == 409
            assert before_plan.json()["error"]["code"] == "SIMULATION_STATE_ERROR"

            step_before_plan = await client.post(
                f"/scenarios/{scenario.id}/simulation/step",
                json={"seconds": 1},
            )
            assert step_before_plan.status_code == 409
            assert (
                step_before_plan.json()["error"]["code"]
                == "SIMULATION_STATE_ERROR"
            )

            missing = await client.get("/scenarios/DOES-NOT-EXIST")
            assert missing.status_code == 404
            assert missing.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

            await client.post(f"/scenarios/{scenario.id}/windows/generate")
            version_one = (await client.post(f"/scenarios/{scenario.id}/plan")).json()
            version_two_response = await client.post(
                f"/scenarios/{scenario.id}/replan",
                json={"expected_parent_plan_id": version_one["id"]},
            )
            assert version_two_response.status_code == 201

            stale = await client.post(
                f"/scenarios/{scenario.id}/replan",
                json={"expected_parent_plan_id": version_one["id"]},
            )
            assert stale.status_code == 409
            assert stale.json()["error"] == {
                "code": "PLAN_VERSION_CONFLICT",
                "message": "replan named a plan version that is no longer current",
                "details": {
                    "expected_parent_plan_id": version_one["id"],
                    "current_plan_id": version_two_response.json()["id"],
                },
            }

    asyncio.run(run())


def test_validation_errors_use_the_envelope_and_openapi_lists_all_six_codes():
    async def run() -> None:
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            invalid_scenario = _scenario("SCN-INVALID").to_dict()
            invalid_scenario["end_time"] = invalid_scenario["start_time"]
            response = await client.post("/scenarios", json=invalid_scenario)
            assert response.status_code == 422
            assert response.json()["error"]["code"] == "INVALID_SCENARIO"
            assert isinstance(response.json()["error"]["details"], dict)

            event_scenario = _scenario("SCN-EVENT-VALIDATION")
            await client.post("/scenarios", json=event_scenario.to_dict())
            windows = (
                await client.post(
                    f"/scenarios/{event_scenario.id}/windows/generate"
                )
            ).json()
            await client.post(f"/scenarios/{event_scenario.id}/plan")
            invalid_event = await client.post(
                f"/scenarios/{event_scenario.id}/events",
                json={
                    "event_type": "CLOUD_BLOCK",
                    "payload": {
                        "request_id": windows[0]["request_id"],
                        "window_id": windows[0]["id"],
                        "unexpected": True,
                    },
                },
            )
            assert invalid_event.status_code == 422
            assert invalid_event.json()["error"]["code"] == "INVALID_EVENT"

            schema = (await client.get("/openapi.json")).json()
            documented_codes = set(
                schema["components"]["schemas"]["ErrorCode"]["enum"]
            )
            assert documented_codes == {
                "INVALID_SCENARIO",
                "INVALID_EVENT",
                "CONSTRAINT_VIOLATION",
                "RESOURCE_NOT_FOUND",
                "SIMULATION_STATE_ERROR",
                "PLAN_VERSION_CONFLICT",
            }
            assert "PLAN_INFEASIBLE" not in str(schema)

            event_request_schema = schema["paths"][
                "/scenarios/{scenario_id}/events"
            ]["post"]["requestBody"]["content"]["application/json"]["schema"]
            assert event_request_schema["$ref"].endswith(
                "/MissionEventRequest"
            )
            cloud_payload_schema = schema["components"]["schemas"][
                "CloudBlockPayloadSchema"
            ]
            assert set(cloud_payload_schema["required"]) == {
                "request_id",
                "window_id",
            }
            assert cloud_payload_schema["additionalProperties"] is False

            create_responses = schema["paths"]["/scenarios"]["post"]["responses"]
            assert set(create_responses) == {"201", "400", "422"}
            event_responses = schema["paths"][
                "/scenarios/{scenario_id}/events"
            ]["post"]["responses"]
            assert set(event_responses) == {"201", "400", "404", "409", "422"}
            plan_read_responses = schema["paths"]["/plans/{plan_id}"]["get"][
                "responses"
            ]
            assert set(plan_read_responses) == {"200", "404", "422"}

    asyncio.run(run())


def test_cors_allows_the_configured_frontend_origin():
    async def run() -> None:
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/demo/scenario", headers={"Origin": "http://localhost:5173"}
            )
            assert (
                response.headers["access-control-allow-origin"]
                == "http://localhost:5173"
            )

    asyncio.run(run())


def test_cors_allows_a_vite_fallback_port_in_local_development(monkeypatch):
    monkeypatch.delenv("AMIS_CORS_ALLOWED_ORIGINS", raising=False)

    async def run() -> None:
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/demo/scenario", headers={"Origin": "http://localhost:5175"}
            )
            assert response.headers["access-control-allow-origin"] == (
                "http://localhost:5175"
            )

    asyncio.run(run())


def test_cors_explicit_allowlist_disables_the_local_development_pattern(monkeypatch):
    monkeypatch.setenv(
        "AMIS_CORS_ALLOWED_ORIGINS",
        "https://dashboard.example.com",
    )

    async def run() -> None:
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            configured = await client.get(
                "/demo/scenario",
                headers={"Origin": "https://dashboard.example.com"},
            )
            local = await client.get(
                "/demo/scenario", headers={"Origin": "http://localhost:5175"}
            )
            assert configured.headers["access-control-allow-origin"] == (
                "https://dashboard.example.com"
            )
            assert "access-control-allow-origin" not in local.headers

    asyncio.run(run())


def test_demo_scenario_route_returns_the_canonical_scenario_without_persisting_it():
    async def run() -> None:
        app = create_app(window_provider=CanonicalWindowProvider())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            demo = await client.get("/demo/scenario")
            assert demo.status_code == 200
            assert Scenario.from_dict(demo.json()) == build_canonical_replan_scenario()

            missing = await client.get(f"/scenarios/{demo.json()['id']}")
            assert missing.status_code == 404

    asyncio.run(run())


def test_events_route_lists_injected_events_for_the_state_panel():
    async def run() -> None:
        app = create_app(window_provider=CanonicalWindowProvider())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            scenario = _scenario("SCN-EVENTS")
            await client.post("/scenarios", json=scenario.to_dict())

            empty = await client.get(f"/scenarios/{scenario.id}/events")
            assert empty.status_code == 200
            assert empty.json() == []

            windows = (
                await client.post(f"/scenarios/{scenario.id}/windows/generate")
            ).json()
            await client.post(f"/scenarios/{scenario.id}/plan")
            injected = await client.post(
                f"/scenarios/{scenario.id}/events",
                json={
                    "event_type": "CLOUD_BLOCK",
                    "payload": {
                        "request_id": windows[0]["request_id"],
                        "window_id": windows[0]["id"],
                    },
                },
            )

            listed = await client.get(f"/scenarios/{scenario.id}/events")
            assert listed.status_code == 200
            assert listed.json() == [injected.json()]

            missing = await client.get("/scenarios/DOES-NOT-EXIST/events")
            assert missing.status_code == 404

    asyncio.run(run())


def test_plan_routes_remain_unambiguous_across_scenarios():
    async def run() -> None:
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            plan_ids: list[str] = []
            for scenario_id in ("SCN-FIRST", "SCN-SECOND"):
                scenario = _scenario(scenario_id)
                await client.post("/scenarios", json=scenario.to_dict())
                await client.post(f"/scenarios/{scenario_id}/windows/generate")
                plan = (await client.post(f"/scenarios/{scenario_id}/plan")).json()
                assert plan["scenario_id"] == scenario_id
                assert plan["id"] == f"{scenario_id}:PLAN-001"
                plan_ids.append(plan["id"])

            assert len(set(plan_ids)) == 2
            for scenario_id, plan_id in zip(
                ("SCN-FIRST", "SCN-SECOND"), plan_ids, strict=True
            ):
                response = await client.get(f"/plans/{plan_id}")
                assert response.status_code == 200
                assert response.json()["scenario_id"] == scenario_id

    asyncio.run(run())
