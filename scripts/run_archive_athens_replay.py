"""Replay real Athens archive evidence; --replan explicitly releases capacity.

Only Scenario and generated inputs are read, never catalogue/archive files.
Optional --database persists the mission and reloads it through the usual store.
"""

import argparse
import json
from pathlib import Path
from typing import Any

from amis.domain import EventType
from amis.examples import archive_athens_example
from amis.repositories import MissionSessionStore, Repositories
from amis.windows.selection import ScenarioWindowProvider
from datetime import datetime


INPUTS_PATH = Path(__file__).resolve().parents[1] / "amis/data/examples/archive-athens-2026-10-26/archive-inputs.json"


def run(*, replan: bool, database: Path | None = None) -> dict[str, Any]:
    engine = None
    if database is None:
        repositories = Repositories.in_memory()
    else:
        from sqlalchemy import create_engine
        from amis.db.repositories import build_repositories
        from amis.db.schema import metadata

        if database.exists():
            raise ValueError("replay database already exists; choose a new file")
        engine = create_engine(f"sqlite:///{database}")
        metadata.create_all(engine)
        repositories = build_repositories(engine)
    try:
        store = MissionSessionStore(repositories, window_provider=ScenarioWindowProvider())
        scenario = archive_athens_example()
        artifact = json.loads(INPUTS_PATH.read_bytes())
        if artifact["metadata"]["scenario_id"] != scenario.id or not artifact["inputs"]:
            raise ValueError("archive inputs do not describe this Example")
        session = store.create(scenario)
        session.generate_windows()
        baseline = session.plan()
        metrics_before = session.get_metrics().to_dict()
        for entry in artifact["inputs"]:
            if entry["event_type"] != EventType.REQUEST_SATISFIED_BY_ARCHIVE.value:
                raise ValueError("archive Example accepts archive-satisfaction inputs only")
            intended = datetime.fromisoformat(entry["injection_time"])
            seconds = (intended - session.get_state().simulated_time).total_seconds()
            if seconds < 0:
                raise RuntimeError("refusing to inject late: archive time precedes the current clock")
            if seconds:
                session.step(seconds)
            if session.get_state().simulated_time != intended:
                raise RuntimeError("refusing to inject late: clock did not reach the exact archive time")
            session.inject_event(entry["event_type"], entry["payload"])
        state_at_injection = session.get_state().to_dict()
        store.save(session)
        session = store.load(scenario.id)
        result = {"baseline_plan": baseline.to_dict(), "active_plan": session.get_plan().to_dict(),
                  "events": [e.to_dict() for e in session.get_events()], "impact": session.get_last_impact().to_dict(),
                  "metrics_before": metrics_before, "state_at_injection": state_at_injection}
        if replan:
            revised = session.replan(expected_parent_plan_id=baseline.id)
            store.save(session, expected_current_plan_id=baseline.id)
            session = store.load(scenario.id)
            result.update(replanned_plan=session.get_plan().to_dict(), diff=session.compare_versions(1, 2).to_dict(),
                          traces=[t.to_dict() for t in session.get_traces(revised.id)])
        result.update(metrics_after=session.get_metrics().to_dict(), state_after=session.get_state().to_dict())
        return result
    finally:
        if engine is not None:
            engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replan", action="store_true")
    parser.add_argument("--database", type=Path, help="optional new SQLite file")
    args = parser.parse_args()
    try:
        result = run(replan=args.replan, database=args.database)
    except (OSError, KeyError, TypeError, ValueError, RuntimeError) as error:
        parser.exit(2, f"archive replay failed: {error}\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
