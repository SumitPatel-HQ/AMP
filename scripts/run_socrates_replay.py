"""Offline dated SOCRATES Example. Injection and --replan are separate operations."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from amis.examples import socrates_flock_example
from amis.repositories import MissionSessionStore, Repositories
from amis.windows.selection import ScenarioWindowProvider

BUNDLE = Path(__file__).resolve().parents[1] / 'amis/data/examples/socrates-flock-2026-10-27'


def run(*, replan: bool = False, database: Path | None = None) -> dict[str, Any]:
    engine = None
    if database is None:
        repositories = Repositories.in_memory()
    else:
        from sqlalchemy import create_engine
        from amis.db.repositories import build_repositories
        from amis.db.schema import metadata

        if database.exists():
            raise ValueError('replay database already exists; choose a new file')
        engine = create_engine(f'sqlite:///{database}')
        metadata.create_all(engine)
        repositories = build_repositories(engine)
    try:
        scenario = socrates_flock_example()
        artifact = json.loads((BUNDLE / 'conjunction-inputs.json').read_bytes())
        if artifact['metadata']['scenario_id'] != scenario.id or not artifact['inputs']:
            raise ValueError('conjunction inputs do not describe this Example')
        store = MissionSessionStore(repositories, window_provider=ScenarioWindowProvider())
        session = store.create(scenario)
        session.generate_windows()
        baseline = session.plan()
        baseline_at_injection = None
        impacts = []
        for entry in artifact['inputs']:
            if entry['event_type'] != 'SATELLITE_UNAVAILABLE' or not entry['payload'].get('conjunction'):
                raise ValueError('SOCRATES Example accepts conjunction outages only')
            intended = datetime.fromisoformat(entry['injection_time'])
            seconds = (intended - session.get_state().simulated_time).total_seconds()
            if seconds < 0:
                raise RuntimeError('refusing to inject late: intended instant precedes current clock')
            if seconds:
                session.step(seconds)
            if session.get_state().simulated_time != intended:
                raise RuntimeError('refusing to inject late: clock missed intended instant')
            if baseline_at_injection is None:
                baseline_at_injection = session.get_plan().to_dict()
            session.inject_event(entry['event_type'], entry['payload'])
            impacts.append(session.get_last_impact().to_dict())
        store.save(session)
        session = store.load(scenario.id)
        result: dict[str, Any] = {
            'notice': 'Archived prediction plus assumed payload outage; no maneuver, fuel, delta-v, or trajectory change modeled.',
            'baseline_plan': baseline.to_dict(), 'active_plan': session.get_plan().to_dict(),
            'baseline_at_injection': baseline_at_injection,
            'events': [event.to_dict() for event in session.get_events()], 'impacts': impacts,
            'state_at_injection': session.get_state().to_dict(),
        }
        if replan:
            revised = session.replan(expected_parent_plan_id=baseline.id)
            store.save(session, expected_current_plan_id=baseline.id)
            session = store.load(scenario.id)
            result.update(replanned_plan=session.get_plan().to_dict(),
                          traces=[trace.to_dict() for trace in session.get_traces(revised.id)],
                          diff=session.compare_versions(1, 2).to_dict())
        result['state_after'] = session.get_state().to_dict()
        return result
    finally:
        if engine is not None:
            engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replan', action='store_true')
    parser.add_argument('--database', type=Path)
    args = parser.parse_args()
    try:
        result = run(replan=args.replan, database=args.database)
    except (OSError, KeyError, TypeError, ValueError, RuntimeError) as error:
        parser.exit(2, f'SOCRATES replay failed: {error}\n')
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
