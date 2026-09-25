"""GAP-01/GAP-11 regression: the real production wiring, not a test provider.

Every other REST test explicitly injects `CanonicalWindowProvider`. This
one drives `amis.main.build_app()` -- exactly what `uvicorn amis.main:app`
serves -- so the canonical demo's actual production window provider
(`amis.demo.ProductionWindowProvider`) is exercised end to end, including
the cloud-block-moves-OBS-B story the product's demo depends on.
"""

from __future__ import annotations

import asyncio

from httpx import ASGITransport, AsyncClient

from amis.demo import build_canonical_replan_scenario
from amis.domain import ReasonCode, Scenario
from amis.main import build_app


def test_production_wiring_schedules_every_canonical_demo_request():
    async def run() -> None:
        app = build_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            scenario = build_canonical_replan_scenario()

            created = await client.post("/scenarios", json=scenario.to_dict())
            assert created.status_code == 201

            windows = await client.post(f"/scenarios/{scenario.id}/windows/generate")
            assert windows.status_code == 200
            # OBS-B holds two windows, everyone else holds one: 6 total.
            assert len(windows.json()) == 6

            planned = await client.post(f"/scenarios/{scenario.id}/plan")
            assert planned.status_code == 201
            plan = planned.json()

            scheduled_ids = {action["request_id"] for action in plan["actions"]}
            assert scheduled_ids == {"OBS-A", "OBS-B", "OBS-C", "OBS-D", "OBS-E"}
            assert plan["unscheduled"] == []

    asyncio.run(run())


def test_production_wiring_moves_obs_b_on_cloud_block_not_just_drops_it():
    async def run() -> None:
        app = build_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            scenario = build_canonical_replan_scenario()
            await client.post("/scenarios", json=scenario.to_dict())
            await client.post(f"/scenarios/{scenario.id}/windows/generate")
            planned = await client.post(f"/scenarios/{scenario.id}/plan")
            version_one = planned.json()

            obs_b_action = next(
                action for action in version_one["actions"] if action["request_id"] == "OBS-B"
            )
            assert obs_b_action["window_id"] == "WIN-OBS-B-1"

            await client.post(f"/scenarios/{scenario.id}/simulation/step", json={"seconds": 300})
            event = await client.post(
                f"/scenarios/{scenario.id}/events",
                json={
                    "event_type": "CLOUD_BLOCK",
                    "payload": {
                        "request_id": "OBS-B",
                        "window_id": obs_b_action["window_id"],
                    },
                },
            )
            assert event.status_code == 201

            replanned = await client.post(
                f"/scenarios/{scenario.id}/replan",
                json={"expected_parent_plan_id": version_one["id"]},
            )
            assert replanned.status_code == 201
            version_two = replanned.json()

            obs_b_after = next(
                action for action in version_two["actions"] if action["request_id"] == "OBS-B"
            )
            # Moved to the second canonical window, not dropped.
            assert obs_b_after["window_id"] == "WIN-OBS-B-2"
            assert {entry["request_id"] for entry in version_two["unscheduled"]} == set()

    asyncio.run(run())
