"""Replay the bundled USGS Vanuatu earthquake Example offline (ticket 03).

Uses only existing mission lifecycle operations (``amis.session.MissionSession``):
load the bundled Scenario, create a baseline plan, advance the clock to the
cue's exact recorded instant, and inject it. No new exercise engine, no
network access, and no archive dependency -- the bundled Scenario plus the
committed cue input at
``amis/data/examples/usgs-vanuatu-2026-10-08/cue-inputs.json`` are enough.

    python scripts/run_usgs_vanuatu_replay.py
    python scripts/run_usgs_vanuatu_replay.py --replan

Injecting a cue never replans automatically (ADR-0015); pass ``--replan`` to
also perform the separate, explicit replan and print its PlanDiff summary.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from amis.examples import usgs_vanuatu_example
from amis.session import MissionSession
from amis.windows.selection import ScenarioWindowProvider

CUE_INPUTS_PATH = Path(__file__).resolve().parents[1] / "amis" / "data" / "examples" / "usgs-vanuatu-2026-10-08" / "cue-inputs.json"


def run(*, replan: bool) -> dict[str, Any]:
    scenario = usgs_vanuatu_example()
    artifact = json.loads(CUE_INPUTS_PATH.read_text(encoding="utf-8"))

    session = MissionSession(window_provider=ScenarioWindowProvider())
    session.load_scenario(scenario)
    session.generate_windows()
    baseline_plan = session.plan()

    events = []
    impacts = []
    for entry in artifact["inputs"]:
        injection_time = datetime.fromisoformat(entry["injection_time"])
        state = session.get_state()
        seconds = (injection_time - state.simulated_time).total_seconds()
        if seconds < 0:
            raise RuntimeError(
                f"cue at {injection_time.isoformat()} is earlier than the current simulated "
                f"time {state.simulated_time.isoformat()}; this replay cannot rewind the clock"
            )
        state = session.step(seconds) if seconds > 0 else state
        if state.simulated_time != injection_time:
            # step() clamps at the Scenario end; a clamp here means the clock
            # cannot reach the cue's exact recorded instant. Fail rather than
            # inject at the wrong time or rewrite the recorded time.
            raise RuntimeError(
                f"clock is at {state.simulated_time.isoformat()}, not the cue's exact "
                f"recorded time {injection_time.isoformat()}; refusing to inject late"
            )
        event = session.inject_event(entry["event_type"], entry["payload"])
        events.append(event)
        impacts.append(session.get_last_impact())

    result: dict[str, Any] = {
        "scenario_id": scenario.id,
        "baseline_plan": baseline_plan.to_dict(),
        "events": [event.to_dict() for event in events],
        "impacts": [impact.to_dict() for impact in impacts],
    }
    if replan:
        plan = session.replan(expected_parent_plan_id=baseline_plan.id)
        result["replanned_plan"] = plan.to_dict()
        result["traces"] = [trace.to_dict() for trace in session.get_traces(plan.id)]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replan", action="store_true", help="also perform the separate explicit replan")
    args = parser.parse_args()
    try:
        result = run(replan=args.replan)
    except (OSError, KeyError, ValueError, RuntimeError, ModuleNotFoundError) as error:
        parser.exit(2, f"USGS Vanuatu replay failed: {error}\n")
    print(json.dumps(result, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
