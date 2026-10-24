"""Synthetic CEMS training arrival; no historical activation is represented.

Run from the repository root with `python -m scripts.run_synthetic_cems_replay`.
Only stored orbital inputs and existing MissionSession lifecycle operations are used.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

from amis.cues.rules import ImagingProfile, request_identifier
from amis.domain import ObservationRequest, RequestStatus, Scenario
from amis.examples import orbital_example
from amis.session import MissionSession
from amis.windows.selection import ScenarioWindowProvider


def synthetic_inputs() -> tuple[Scenario, dict[str, Any]]:
    scenario = replace(orbital_example(), id="SCN-SYNTHETIC-CEMS",
                       name="SYNTHETIC CEMS centroid training (not historical evidence)")
    activation = scenario.start_time + timedelta(minutes=5)
    profile = ImagingProfile(duration_s=30, energy_cost_wh=20, storage_cost_mb=100)
    request = ObservationRequest(
        id=request_identifier("cems", "SYNTHETIC-CEMS-001"),
        target_lat=12.97, target_lon=77.59, target_name="SYNTHETIC flood centroid",
        priority=5, deadline=activation + timedelta(hours=24),
        status=RequestStatus.PENDING, **profile.to_dict(),
    )
    return scenario, {
        "event_type": "EMERGENCY_TASK",
        "payload": {
            "request": request.to_dict(), "source": "cems",
            "source_event_id": "SYNTHETIC-CEMS-001", "alert_level": "unknown",
            "category": "SYNTHETIC flood (not historical evidence)",
            "activation_time": activation.isoformat(),
            "source_event_time": scenario.start_time.isoformat(),
            # This is a service homepage, not evidence of an activation.
            "source_url": "https://mapping.emergency.copernicus.eu/",
            "centroid_policy_version": "cems-centroid-v1",
        },
    }


def run(*, replan: bool = False) -> dict[str, Any]:
    scenario, body = synthetic_inputs()
    session = MissionSession(window_provider=ScenarioWindowProvider())
    session.load_scenario(scenario)
    session.generate_windows()
    baseline = session.plan()
    activation = scenario.start_time + timedelta(minutes=5)
    state = session.step((activation - session.get_state().simulated_time).total_seconds())
    if state.simulated_time != activation:
        raise RuntimeError("clock did not reach the exact synthetic activation instant")
    event = session.inject_event(body["event_type"], body["payload"])
    result: dict[str, Any] = {
        "notice": "SYNTHETIC fixture; no historical CEMS activation or area coverage is represented.",
        "scenario": scenario.to_dict(), "baseline_plan": baseline.to_dict(),
        "event": event.to_dict(), "impact": session.get_last_impact().to_dict(),
    }
    if replan:
        plan = session.replan(expected_parent_plan_id=baseline.id)
        result.update(replanned_plan=plan.to_dict(),
                      diff=session.compare_versions(1, 2).to_dict(),
                      traces=[trace.to_dict() for trace in session.get_traces(plan.id)])
    result["metrics"] = session.get_metrics().to_dict()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replan", action="store_true", help="explicitly replan after injection")
    parser.add_argument("--export-dir", type=Path, help="write pristine Scenario and event API bodies into a new directory")
    args = parser.parse_args()
    if args.export_dir is not None:
        scenario, body = synthetic_inputs()
        args.export_dir.mkdir(parents=True, exist_ok=False)
        (args.export_dir / "scenario.json").write_text(json.dumps(scenario.to_dict(), indent=2) + "\n", encoding="utf-8")
        (args.export_dir / "event.json").write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    else:
        print(json.dumps(run(replan=args.replan), indent=2))


if __name__ == "__main__":
    main()
