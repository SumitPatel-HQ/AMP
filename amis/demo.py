"""Multi request mission demo from planning through simulated execution.

Run with: python -m amis.demo
"""

from __future__ import annotations

from datetime import datetime, timezone

from amis.domain import MissionState, ObservationRequest, Satellite, Scenario
from amis.session import MissionSession

START = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
END = datetime(2026, 1, 2, 0, 0, tzinfo=timezone.utc)


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


if __name__ == "__main__":
    main()
