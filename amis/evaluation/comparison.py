"""Decision 19: compare planners over shared missions.

Runs both planners over the three legacy examples plus generated orbital
missions at several request counts, with and without a disruptive event,
and reports utility, scheduled/completed counts, violations, planning
time, churn, resource use, and optimality gap. Persisted alongside data
origin and library versions so reports stay comparable across months.
"""

from __future__ import annotations

import statistics
from dataclasses import replace
from typing import Any

from amis.examples import examples
from amis.session import MissionSession

PLANNERS = ("greedy", "cp_sat")
ORBITAL_REQUEST_COUNTS = (3, 6, 8)


def _library_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    try:
        import ortools

        versions["ortools"] = ortools.__version__
    except ModuleNotFoundError:
        pass
    try:
        from skyfield import __version__ as skyfield_version

        versions["skyfield"] = skyfield_version
    except ModuleNotFoundError:
        pass
    try:
        from sgp4 import __version__ as sgp4_version

        versions["sgp4"] = sgp4_version
    except ModuleNotFoundError:
        pass
    return versions


def _window_provider_for(scenario):
    from amis.windows.selection import ScenarioWindowProvider

    return ScenarioWindowProvider() if scenario.window_policy is not None else None


def _orbital_missions() -> list[Any]:
    try:
        from amis.examples import orbital_example
    except ModuleNotFoundError:
        return []
    try:
        base = orbital_example()
    except ModuleNotFoundError:
        return []
    return [
        replace(base, id=f"{base.id}-N{count}", requests=base.requests[:count])
        for count in ORBITAL_REQUEST_COUNTS
        if count <= len(base.requests)
    ]


def _run_once(scenario, planner_name: str, with_event: bool) -> dict[str, Any]:
    session = MissionSession(window_provider=_window_provider_for(scenario))
    session.load_scenario(scenario)
    session.generate_windows()
    session.select_planner(planner_name)
    plan = session.plan()
    churn = None
    if with_event and plan.actions:
        # The earliest-starting action can already be frozen (in flight) at
        # mission start, which a block can legitimately never unschedule
        # (ADR-0003's frozen-action exemption) -- block the latest action
        # instead so this measures ordinary replanning, not that edge case.
        blocked = plan.actions[-1]
        session.inject_cloud_block(blocked.request_id, blocked.window_id)
        session.select_planner(planner_name)
        plan = session.replan(expected_parent_plan_id=plan.id)
        churn = session.get_metrics(plan.id).plan_churn
    metrics = session.get_metrics(plan.id)
    return {
        "scenario_id": scenario.id,
        "planner": planner_name,
        "with_event": with_event,
        "mission_utility": plan.mission_utility,
        "scheduled_count": len(plan.actions),
        "completed_count": sum(
            1 for r in session.get_request_pool() if r.status.value == "completed"
        ),
        "violation_count": plan.violation_count,
        "planning_time_ms": plan.planning_time_ms,
        "plan_churn": churn,
        "battery_utilisation": metrics.battery_utilisation,
        "storage_utilisation": metrics.storage_utilisation,
        "optimality_gap": (plan.solver_details or {}).get("optimality_gap"),
    }


def run_comparison() -> dict[str, Any]:
    scenarios = list(examples().values()) + _orbital_missions()
    runs: list[dict[str, Any]] = []
    for scenario in scenarios:
        for planner_name in PLANNERS:
            for with_event in (False, True):
                try:
                    runs.append(_run_once(scenario, planner_name, with_event))
                except ModuleNotFoundError as error:
                    runs.append({
                        "scenario_id": scenario.id, "planner": planner_name,
                        "with_event": with_event, "skipped": f"missing dependency: {error.name}",
                    })

    summary = {}
    for planner_name in PLANNERS:
        rows = [r for r in runs if r.get("planner") == planner_name and "skipped" not in r]
        times = [r["planning_time_ms"] for r in rows]
        summary[planner_name] = {
            "runs": len(rows),
            "total_utility": sum(r["mission_utility"] for r in rows),
            "total_violations": sum(r["violation_count"] for r in rows),
            "planning_time_median_ms": statistics.median(times) if times else None,
        }

    return {
        "data_origin": "MissionSession runs over the three legacy examples plus generated orbital missions",
        "library_versions": _library_versions(),
        "runs": runs,
        "summary": summary,
    }
