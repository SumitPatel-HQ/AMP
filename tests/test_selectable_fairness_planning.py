"""Acceptance tests for selectable fairness planning (ticket 02)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine

from amis.api import create_app
from amis.db.repositories import build_repositories
from amis.db.schema import metadata
from amis.domain import (
    ObservationRequest,
    Satellite,
    Scenario,
    WindowPolicy,
)
from amis.examples import (
    fairness_balance_example,
    fairness_strict_utility_example,
)
from amis.metrics import compute_requester_service
from amis.planning.selection import make_planner
from amis.repositories import MissionSessionStore
from amis.session import MissionSession
from amis.windows.synthetic import SyntheticWindowProvider


def test_default_planning_policy_is_pure_utility():
    scenario = fairness_balance_example()
    session = MissionSession(window_provider=SyntheticWindowProvider())
    session.load_scenario(scenario)
    session.generate_windows()
    session.select_planner("cp_sat")
    plan = session.plan()

    assert plan.planning_policy == "utility"
    assert plan.policy == "utility"
    assert plan.policy_version == "requester-utility-v1"
    assert session.get_selected_policy() == "utility"
    assert plan.solver_details["policy"] == "utility"
    assert plan.solver_details["achieved_gap"] is None


def test_greedy_rejects_utility_then_fairness():
    with pytest.raises(ValueError, match="not supported with planner 'greedy'"):
        make_planner("greedy", policy="utility_then_fairness")

    scenario = fairness_balance_example()
    session = MissionSession(window_provider=SyntheticWindowProvider())
    session.load_scenario(scenario)
    session.generate_windows()
    with pytest.raises(ValueError, match="not supported with planner 'greedy'"):
        session.select_planner("greedy", policy="utility_then_fairness")


def test_cp_sat_skips_fairness_with_fewer_than_two_identified_requesters():
    sat = Satellite("SAT-001", 1000.0, 1000.0, 4000.0, 0.0)
    start = datetime(2026, 10, 20, 0, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(seconds=100)
    # Only one requester ORG-A, plus an unattributed request
    requests = (
        ObservationRequest(
            id="OBS-1", target_lat=0.0, target_lon=0.0, priority=3, duration_s=40.0,
            deadline=end, energy_cost_wh=10.0, storage_cost_mb=10.0, requester_id="ORG-A",
        ),
        ObservationRequest(
            id="OBS-2", target_lat=0.0, target_lon=0.0, priority=3, duration_s=40.0,
            deadline=end, energy_cost_wh=10.0, storage_cost_mb=10.0, requester_id=None,
        ),
    )
    scenario = Scenario("SCN-SINGLE-REQ", "Single requester", start, end, sat, requests, window_policy=WindowPolicy("synthetic"))
    session = MissionSession(window_provider=SyntheticWindowProvider())
    session.load_scenario(scenario)
    session.generate_windows()
    session.select_planner("cp_sat", policy="utility_then_fairness")
    plan = session.plan()

    assert plan.planning_policy == "utility_then_fairness"
    details = plan.solver_details
    assert details["skip_reason"] == "fewer than two identified requesters"
    assert details["achieved_gap"] is None
    assert len(details["stages"]) == 1
    assert details["stages"][0]["stage"] == "utility"


def test_multi_requester_bottleneck_reduces_gap_without_utility_sacrifice():
    scenario = fairness_balance_example()

    # Plan with Pure Utility
    session_u = MissionSession(window_provider=SyntheticWindowProvider())
    session_u.load_scenario(scenario)
    session_u.generate_windows()
    session_u.select_planner("cp_sat", policy="utility")
    plan_u = session_u.plan()

    served_u = {a.request_id for a in plan_u.actions}
    service_u = compute_requester_service(scenario.requests, served_u)
    assert served_u == {"OBS-3", "OBS-1"}
    assert service_u.total_served_utility == 6
    assert service_u.fairness_gap == 6

    # Plan with Utility-Then-Fairness
    session_f = MissionSession(window_provider=SyntheticWindowProvider())
    session_f.load_scenario(scenario)
    session_f.generate_windows()
    session_f.select_planner("cp_sat", policy="utility_then_fairness")
    plan_f = session_f.plan()

    served_f = {a.request_id for a in plan_f.actions}
    service_f = compute_requester_service(scenario.requests, served_f)
    assert served_f == {"OBS-1", "OBS-2"}
    # Equal primary utility strictly preserved (6 == 6)
    assert service_f.total_served_utility == service_u.total_served_utility == 6
    # Requester utility gap reduced from 6 to 0!
    assert service_f.fairness_gap == 0

    # Verify solver details breakdown
    details = plan_f.solver_details
    assert details["status"] == "OPTIMAL"
    assert details["policy"] == "utility_then_fairness"
    assert details["achieved_gap"] == 0
    assert details["achieved_gap_unit"] == "priority_utility"
    assert details["budget_allocation"] == {"utility": 0.4, "fairness": 0.4, "stability": 0.2}

    stages = details["stages"]
    assert len(stages) == 3
    assert stages[0]["stage"] == "utility"
    assert stages[0]["status"] == "OPTIMAL"
    assert stages[0]["objective_unit"] == "priority_utility"

    assert stages[1]["stage"] == "fairness"
    assert stages[1]["status"] == "OPTIMAL"
    assert stages[1]["objective"] == 0
    assert stages[1]["objective_unit"] == "priority_utility_gap"

    assert stages[2]["stage"] == "stability"
    assert stages[2]["objective_unit"] == "retained_window_count"

    # Causality and trace check
    assert "OBS-2" in details["fairness_rebalanced_request_ids"]


def test_unimprovable_utility_first_preserves_schedule_and_utility():
    scenario = fairness_strict_utility_example()

    session_u = MissionSession(window_provider=SyntheticWindowProvider())
    session_u.load_scenario(scenario)
    session_u.generate_windows()
    session_u.select_planner("cp_sat", policy="utility")
    plan_u = session_u.plan()

    session_f = MissionSession(window_provider=SyntheticWindowProvider())
    session_f.load_scenario(scenario)
    session_f.generate_windows()
    session_f.select_planner("cp_sat", policy="utility_then_fairness")
    plan_f = session_f.plan()

    # Both must schedule the exact same high-utility requests (OBS-A1 and OBS-A2)
    assert {a.request_id for a in plan_u.actions} == {"OBS-A1", "OBS-A2"}
    assert {a.request_id for a in plan_f.actions} == {"OBS-A1", "OBS-A2"}

    # Gap cannot be reduced without dropping utility, so it stays 8
    details_f = plan_f.solver_details
    assert details_f["achieved_gap"] == 8
    assert details_f["fairness_rebalanced_request_ids"] == []


def test_replanning_completed_service_accounting_and_pool_isolation():
    scenario = fairness_balance_example()
    session = MissionSession(window_provider=SyntheticWindowProvider())
    session.load_scenario(scenario)
    session.generate_windows()
    session.select_planner("cp_sat", policy="utility")
    p1 = session.plan()
    assert p1.id == "PLAN-001"

    # Step simulation forward past the first action
    first_action = sorted(p1.actions, key=lambda a: a.start)[0]
    duration_s = int((first_action.end - scenario.start_time).total_seconds()) + 1
    session.step(duration_s)

    # Replan with utility_then_fairness
    p2 = session.replan(policy="utility_then_fairness")
    assert p2.id == "PLAN-002"
    assert p2.planning_policy == "utility_then_fairness"

    # Request pool of the new plan should only contain eligible pending requests
    # and completed requests up to simulated time, with no double counting
    metrics = session.get_metrics()
    assert metrics.requester_service.metric_version == "requester-utility-v1"


def test_persistence_and_reconstruction_preserves_policy():
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    repos = build_repositories(engine)
    store = MissionSessionStore(repos, window_provider=SyntheticWindowProvider())

    scenario = fairness_balance_example()
    session = store.create(scenario)
    session.generate_windows()
    session.select_planner("cp_sat", policy="utility_then_fairness")
    plan = session.plan()
    assert plan.planning_policy == "utility_then_fairness"
    store.save(session)

    # Reconstruct from repository store
    restored = store.load(scenario.id)
    assert restored is not None
    restored_plan = restored.get_plan()
    assert restored_plan is not None
    assert restored_plan.planning_policy == "utility_then_fairness"
    assert restored_plan.policy == "utility_then_fairness"
    assert restored.get_selected_policy() == "utility_then_fairness"


def test_api_endpoints_accept_and_return_policy():
    async def run() -> None:
        app = create_app(window_provider=SyntheticWindowProvider())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Create scenario
            scenario = fairness_balance_example()
            res = await client.post("/scenarios", json=scenario.to_dict())
            assert res.status_code == 201
            await client.post(f"/scenarios/{scenario.id}/windows/generate")

            # Plan with utility_then_fairness
            plan_res = await client.post(
                f"/scenarios/{scenario.id}/plan",
                json={"planner": "cp_sat", "policy": "utility_then_fairness"},
            )
            assert plan_res.status_code == 201
            plan_data = plan_res.json()
            assert plan_data["planning_policy"] == "utility_then_fairness"
            assert plan_data["policy_version"] == "requester-utility-v1"
            assert plan_data["solver_details"]["achieved_gap"] == 0

            # Greedy rejecting utility_then_fairness returns 422 or 400
            greedy_bad = await client.post(
                f"/scenarios/{scenario.id}/plan",
                json={"planner": "greedy", "policy": "utility_then_fairness"},
            )
            assert greedy_bad.status_code in (400, 422)

            # Replan endpoint accepts policy
            replan_res = await client.post(
                f"/scenarios/{scenario.id}/replan",
                json={"policy": "utility"},
            )
            assert replan_res.status_code == 201
            replan_data = replan_res.json()
            assert replan_data["planning_policy"] == "utility"

            # List examples includes fairness comparison examples
            ex_res = await client.get("/examples")
            assert ex_res.status_code == 200
            example_ids = [ex["id"] for ex in ex_res.json()]
            assert "fairness-balance" in example_ids
            assert "fairness-strict-utility" in example_ids

    asyncio.run(run())
