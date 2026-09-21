"""Multi request mission demo from planning through simulated execution.

Run with: python -m amis.demo
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from amis.domain import (
    MissionState,
    ObservationRequest,
    ObservationWindow,
    Satellite,
    Scenario,
)
from amis.session import MissionSession

START = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
END = datetime(2026, 1, 2, 0, 0, tzinfo=timezone.utc)
REPLAN_START = datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc)
REPLAN_END = datetime(2026, 9, 21, 14, 0, tzinfo=timezone.utc)


class DemoImpactWindowProvider:
    """Places demo windows in the future so cloud impact remains inspectable."""

    def generate(
        self,
        scenario: Scenario,
        requests: Iterable[ObservationRequest],
    ) -> list[ObservationWindow]:
        return [
            ObservationWindow(
                id=f"WIN-{request.id}-1",
                request_id=request.id,
                satellite_id=scenario.satellite.id,
                start=scenario.start_time + timedelta(minutes=10 * (index + 1)),
                end=scenario.end_time,
            )
            for index, request in enumerate(requests)
        ]


def build_demo_scenario() -> Scenario:
    satellite = Satellite(
        id="SAT-001",
        battery_capacity_wh=300.0,
        battery_charge_wh=120.0,
        storage_capacity_mb=1000.0,
        storage_usage_mb=900.0,
        available=True,
    )
    requests = (
        ObservationRequest(
            id="OBS-A",
            target_lat=12.97,
            target_lon=77.59,
            priority=5,
            duration_s=300.0,
            deadline=END,
            energy_cost_wh=80.0,
            storage_cost_mb=50.0,
        ),
        ObservationRequest(
            id="OBS-B",
            target_lat=28.61,
            target_lon=77.21,
            priority=4,
            duration_s=300.0,
            deadline=END,
            energy_cost_wh=60.0,
            storage_cost_mb=10.0,
        ),
        ObservationRequest(
            id="OBS-C",
            target_lat=19.08,
            target_lon=72.88,
            priority=3,
            duration_s=300.0,
            deadline=START,
            energy_cost_wh=10.0,
            storage_cost_mb=5.0,
        ),
        ObservationRequest(
            id="OBS-D",
            target_lat=13.08,
            target_lon=80.27,
            priority=2,
            duration_s=300.0,
            deadline=END,
            energy_cost_wh=10.0,
            storage_cost_mb=80.0,
        ),
        ObservationRequest(
            id="OBS-E",
            target_lat=22.57,
            target_lon=88.36,
            priority=1,
            duration_s=300.0,
            deadline=END,
            energy_cost_wh=10.0,
            storage_cost_mb=5.0,
        ),
        ObservationRequest(
            id="OBS-F",
            target_lat=17.38,
            target_lon=78.49,
            priority=1,
            duration_s=300.0,
            deadline=END,
            energy_cost_wh=10.0,
            storage_cost_mb=5.0,
        ),
    )
    return Scenario(
        id="SCN-001",
        name="Multi request planning demo",
        start_time=START,
        end_time=END,
        satellite=satellite,
        requests=requests,
    )


class CanonicalWindowProvider:
    """Windows for the canonical replan demo, in minutes after the start.

    `OBS-B` holds two windows, at 10:20 and 11:15, so blocking the first
    gives replanning somewhere to move it. Every other request holds one,
    so nothing else has anywhere to go and churn measures the disruption.
    """

    _WINDOW_OFFSETS: dict[str, tuple[tuple[int, int], ...]] = {
        "OBS-A": ((0, 15),),
        "OBS-B": ((20, 35), (75, 90)),
        "OBS-C": ((40, 55),),
        "OBS-D": ((100, 115),),
        "OBS-E": ((120, 135),),
    }

    def generate(
        self,
        scenario: Scenario,
        requests: Iterable[ObservationRequest],
    ) -> list[ObservationWindow]:
        return [
            ObservationWindow(
                id=f"WIN-{request.id}-{number}",
                request_id=request.id,
                satellite_id=scenario.satellite.id,
                start=scenario.start_time + timedelta(minutes=start_offset),
                end=scenario.start_time + timedelta(minutes=end_offset),
            )
            for request in requests
            for number, (start_offset, end_offset) in enumerate(
                self._WINDOW_OFFSETS[request.id], start=1
            )
        ]


def build_canonical_replan_scenario() -> Scenario:
    """The scenario the replanning demonstration is built on.

    Resources are generous so that the only thing a cloud block can
    disturb is the blocked window itself.
    """

    satellite = Satellite(
        id="SAT-001",
        battery_capacity_wh=500.0,
        battery_charge_wh=500.0,
        storage_capacity_mb=2000.0,
        storage_usage_mb=0.0,
        available=True,
    )
    targets = (
        ("OBS-A", 5, 12.97, 77.59),
        ("OBS-B", 4, 28.61, 77.21),
        ("OBS-C", 3, 19.08, 72.88),
        ("OBS-D", 2, 13.08, 80.27),
        ("OBS-E", 1, 22.57, 88.36),
    )
    requests = tuple(
        ObservationRequest(
            id=request_id,
            target_lat=target_lat,
            target_lon=target_lon,
            priority=priority,
            duration_s=600.0,
            deadline=REPLAN_END,
            energy_cost_wh=40.0,
            storage_cost_mb=100.0,
        )
        for request_id, priority, target_lat, target_lon in targets
    )
    return Scenario(
        id="SCN-002",
        name="Cloud block replanning demo",
        start_time=REPLAN_START,
        end_time=REPLAN_END,
        satellite=satellite,
        requests=requests,
    )


def print_state(label: str, session: MissionSession, state: MissionState) -> None:
    plan = session.get_plan()
    action_statuses = ", ".join(
        f"{action.request_id}={action.status.value}" for action in plan.actions
    )
    request_statuses = ", ".join(
        f"{request.id}={request.status.value}"
        for request in session.get_request_pool()
    )
    print(
        f"{label}: time={state.simulated_time.isoformat()} "
        f"battery={state.battery_wh:.1f}Wh "
        f"storage={state.storage_usage_mb:.1f}MB "
        f"complete={state.mission_complete}"
    )
    print(f"  Actions: {action_statuses or 'none'}")
    print(f"  Requests: {request_statuses}")


def main() -> None:
    session = MissionSession()
    session.load_scenario(build_demo_scenario())
    session.generate_windows()
    plan = session.plan()

    print(f"Plan {plan.id} v{plan.version} for scenario {plan.scenario_id}")
    print(f"Mission utility: {plan.mission_utility}")
    for action in plan.actions:
        print(
            f"  Scheduled {action.request_id} in window {action.window_id}: "
            f"{action.start.isoformat()} -> {action.end.isoformat()}"
        )
    for entry in plan.unscheduled:
        print(f"  Unscheduled {entry.request_id}: {entry.reason_code.value}")

    print_state("Initial state", session, session.get_state())
    print_state("After 1 second", session, session.step(1))
    print_state("After action completion", session, session.step(299))
    print_state("At mission end", session, session.step(24 * 60 * 60))
    print_metrics(session)
    print_cloud_block_impact()
    print_canonical_replan_demo()


def print_cloud_block_impact() -> None:
    session = MissionSession(window_provider=DemoImpactWindowProvider())
    session.load_scenario(build_demo_scenario())
    session.generate_windows()
    plan = session.plan()
    blocked_action = plan.actions[0]

    session.inject_cloud_block(blocked_action.request_id, blocked_action.window_id)
    impact = session.get_last_impact()

    for action_id in impact.invalid_unfrozen_action_ids:
        reason_codes = ", ".join(
            reason.value for reason in impact.reason_codes[action_id]
        )
        print(f"Cloud block broke action {action_id}: {reason_codes}")


def print_metrics(session: MissionSession) -> None:
    metrics = session.get_metrics()
    print(f"Metrics for plan {metrics.plan_id}:")
    print(f"  Mission utility: {metrics.mission_utility}")
    print(f"  Completion rate: {metrics.completion_rate:.2f}")
    print(f"  Violation count: {metrics.violation_count}")
    print(f"  Planning time: {metrics.planning_time_ms:.2f}ms")
    print(f"  Battery utilisation: {metrics.battery_utilisation:.2f}")
    print(f"  Storage utilisation: {metrics.storage_utilisation:.2f}")
    print(
        f"  Request pool: {metrics.request_pool_size} requests "
        f"{sorted(metrics.request_pool_ids)}"
    )
    print(f"  Plan churn: {metrics.plan_churn}")
    print(f"  Explanation coverage: {metrics.explanation_coverage}")


def run_canonical_replan_demo() -> dict[str, Any]:
    """The adaptive loop end to end, as one serialisable record.

    Plan, run the clock forward, block the 10:20 window, replan, then
    compare, explain, and measure. Two runs of this return the same
    structure once the creation timestamps and the timing measurements
    are removed, which is what makes the output diffable rather than
    only spot checkable.
    """

    session = MissionSession(window_provider=CanonicalWindowProvider())
    scenario = session.load_scenario(build_canonical_replan_scenario())
    session.generate_windows()

    version_one = session.plan()
    metrics_before = session.get_metrics(version_one.id)

    session.step(300)
    event = session.inject_cloud_block("OBS-B", "WIN-OBS-B-1")
    impact = session.get_last_impact()

    version_two = session.replan(expected_parent_plan_id=version_one.id)
    comparison = session.compare_versions(version_one.version, version_two.version)
    traces = session.get_traces(version_two.id)
    metrics_after = session.get_metrics(version_two.id)

    return {
        "scenario": scenario.to_dict(),
        "windows": [window.to_dict() for window in session.get_windows()],
        "event": event.to_dict(),
        "impact": impact.to_dict(),
        # Read back from the session, because running the clock forward
        # replaced version one with a copy carrying the action statuses.
        "plans": [plan.to_dict() for plan in session.get_plans()],
        "comparison": comparison.to_dict(),
        "traces": [trace.to_dict() for trace in traces],
        "metrics": [metrics_before.to_dict(), metrics_after.to_dict()],
    }


def print_canonical_replan_demo() -> None:
    record = run_canonical_replan_demo()
    version_one, version_two = record["plans"]

    print(f"Canonical replan demo for scenario {record['scenario']['id']}:")
    for plan in (version_one, version_two):
        placements = ", ".join(
            f"{action['request_id']}"
            f"@{datetime.fromisoformat(action['start']).strftime('%H:%M')}"
            for action in sorted(plan["actions"], key=lambda item: item["start"])
        )
        print(f"  Plan v{plan['version']} ({plan['id']}): {placements or 'none'}")
        for entry in plan["unscheduled"]:
            print(f"    Unscheduled {entry['request_id']}: {entry['reason_code']}")

    print(f"  Event {record['event']['id']} blocked {record['event']['payload']['window_id']}")
    for entry in record["comparison"]["entries"]:
        if entry["change_type"] == "UNCHANGED":
            continue
        print(f"    {entry['request_id']}: {entry['change_type']} ({entry['reason_code']})")
    for trace in record["traces"]:
        print(f"  {trace['id']}: {trace['message']}")

    metrics_after = record["metrics"][1]
    print(f"  Plan churn: {metrics_after['plan_churn']}")
    print(f"  Explanation coverage: {metrics_after['explanation_coverage']}")
    print(f"  Replanning time: {metrics_after['planning_time_ms']:.2f}ms")


if __name__ == "__main__":
    main()
