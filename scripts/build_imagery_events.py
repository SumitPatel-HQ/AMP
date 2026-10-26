"""Verify archived STAC pages and build archive-satisfaction inputs offline."""

import argparse
import json
from pathlib import Path

from amis.archive_check import write_archive_inputs
from amis.domain import MissionEvent, Scenario


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", type=Path)
    parser.add_argument("--archive-manifest", type=Path, required=True)
    parser.add_argument("--requirements", type=Path, required=True, help="request IDs mapped to injection_time and explicit profile")
    parser.add_argument("--arrival-events", type=Path, help="optional JSON array of accepted emergency MissionEvent records")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        protected = {p.resolve() for p in (args.scenario, args.requirements, args.arrival_events) if p is not None}
        if args.out.resolve() in protected:
            raise ValueError("output must not replace Scenario, requirements or accepted arrival events")
        scenario = Scenario.from_dict(json.loads(args.scenario.read_bytes()))
        requirements = json.loads(args.requirements.read_bytes())
        arrivals = tuple(MissionEvent.from_dict(e) for e in json.loads(args.arrival_events.read_bytes())) if args.arrival_events else ()
        artifact = write_archive_inputs(args.out, args.archive_manifest, scenario, requirements, arrival_events=arrivals)
    except (OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(2, f"imagery build failed: {error}\n")
    print(f"Wrote {len(artifact['inputs'])} archive-satisfaction input(s); no-match results produce no event")


if __name__ == "__main__":
    main()
