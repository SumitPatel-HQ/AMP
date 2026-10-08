"""Build developer emergency-arrival inputs from a verified USGS archive offline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from amis.cues import ImagingProfile, build_cue_inputs, load_archive, write_cue_inputs
from amis.domain import Scenario


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", type=Path, help="Scenario JSON file")
    parser.add_argument("--archive-manifest", type=Path, required=True)
    parser.add_argument("--imaging-profile", type=Path, required=True, help="explicit duration and resource costs JSON")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--event-id", action="append", help="source event id to include; repeatable")
    selection.add_argument("--all", action="store_true", help="explicitly select every archived earthquake")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        archive = load_archive(args.archive_manifest)
        protected = {
            path.resolve() for path in (
                args.archive_manifest, args.archive_manifest.parent / archive.file,
                args.scenario, args.imaging_profile,
            )
        }
        if args.out.resolve() in protected:
            raise ValueError("output must not replace an archive, Scenario, or imaging profile input")
        scenario = Scenario.from_dict(json.loads(args.scenario.read_bytes()))
        profile = ImagingProfile.from_dict(json.loads(args.imaging_profile.read_bytes()))
        artifact = build_cue_inputs(archive, scenario, profile, selected_event_ids=args.event_id)
        write_cue_inputs(args.out, artifact)
    except (OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(2, f"cue build failed: {error}\n")
    print(f"wrote {len(artifact['inputs'])} developer cue input(s) to {args.out}")


if __name__ == "__main__":
    main()
