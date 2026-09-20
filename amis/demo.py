"""Walking-skeleton demo: one request through to a printed plan.

Run with: python -m amis.demo
"""

from __future__ import annotations

from datetime import datetime, timezone

from amis.domain import ObservationRequest, Satellite, Scenario
from amis.session import MissionSession


def build_demo_scenario() -> Scenario:
    satellite = Satellite(
        id="SAT-001",
        battery_capacity_wh=1000.0,
        battery_charge_wh=1000.0,
        storage_capacity_mb=2000.0,
        storage_usage_mb=0.0,
        available=True,
    )
    request = ObservationRequest(
        id="OBS-A",
        target_lat=12.97,
        target_lon=77.59,
        priority=5,
        duration_s=300.0,
        deadline=datetime(2026, 1, 2, 0, 0, tzinfo=timezone.utc),
        energy_cost_wh=50.0,
        storage_cost_mb=100.0,
    )
    return Scenario(
        id="SCN-001",
        name="Walking skeleton demo",
        start_time=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 2, 0, 0, tzinfo=timezone.utc),
        satellite=satellite,
        requests=(request,),
    )


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


if __name__ == "__main__":
    main()
