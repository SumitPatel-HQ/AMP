"""Offline SOCRATES report conversion; publishes one complete artifact exclusively."""
import argparse
import json
from pathlib import Path

from amis.conjunctions.archive import instant, load_archive
from amis.conjunctions.builder import build_inputs
from amis.domain import Scenario


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--scenario', type=Path, required=True)
    parser.add_argument('--injection-time', required=True)
    parser.add_argument('--pre-padding-s', type=float, required=True)
    parser.add_argument('--post-padding-s', type=float, required=True)
    parser.add_argument('--threshold', type=float, default=0.0001)
    parser.add_argument('--satellite', action='append')
    parser.add_argument('--encounter', action='append')
    parser.add_argument('--mapping', type=Path, help='JSON object mapping NORAD ids to Scenario Satellite ids')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        mapping = {int(k): v for k, v in json.loads(args.mapping.read_bytes()).items()} if args.mapping else None
        result = build_inputs(load_archive(args.manifest), Scenario.from_dict(json.loads(args.scenario.read_bytes())),
                              injection_time=instant(args.injection_time), pre_padding_s=args.pre_padding_s,
                              post_padding_s=args.post_padding_s, threshold=args.threshold,
                              satellite_ids=tuple(args.satellite) if args.satellite else None,
                              encounter_ids=tuple(args.encounter) if args.encounter else None,
                              identity_mapping=mapping)
        publish(args.output, result)
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(2, f'SOCRATES conversion failed: {error}\n')


def publish(path: Path, artifact: dict) -> None:
    """Build/serialize first; hard-link a complete sibling file without overwriting."""
    import os
    import tempfile

    raw = (json.dumps(artifact, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.socrates-inputs-', dir=path.parent)
    stage = Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
        os.link(stage, path)
    finally:
        stage.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
