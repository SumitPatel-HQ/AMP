"""Offline weather-to-event conversion; never touches the network.

Reads the committed weather archive and a scenario plus its generated
windows, applies the Wave 5 threshold rule, and writes CLOUD_BLOCK
event requests ready for POST /scenarios/{id}/events. The planner
never sees weather: each payload carries its source, coverage, and
threshold, so the event log stays the replay record (ADR-0012).

Run: python scripts/build_weather_events.py scenario.json windows.json --threshold 50 --out events.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from amis.domain import ObservationWindow, Scenario
from amis.weather import (
    cloud_block_payloads_for_windows,
    coverage_at,
    culmination_time,
    load_archive,
    normalize_archive,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", help="scenario JSON file")
    parser.add_argument("windows", help="observation windows JSON file (a list)")
    parser.add_argument("--threshold", type=float, required=True, help="cloud cover percent at or above which a window blocks")
    parser.add_argument("--tolerance-s", type=float, default=1800.0)
    parser.add_argument("--archive-manifest", default=None, help="weather manifest path (default: the committed archive)")
    parser.add_argument("--out", required=True, help="output event-request JSON file")
    args = parser.parse_args()

    scenario = Scenario.from_dict(json.loads(Path(args.scenario).read_text(encoding="utf-8")))
    windows = tuple(
        ObservationWindow.from_dict(entry)
        for entry in json.loads(Path(args.windows).read_text(encoding="utf-8"))
    )
    archive = load_archive(Path(args.archive_manifest) if args.archive_manifest else None)
    samples = normalize_archive(archive.records)

    requests_by_id = {request.id: request for request in scenario.requests}
    for window in sorted(windows, key=lambda item: (item.start, item.id)):
        if window.request_id not in requests_by_id:
            print(f"{window.id}: skipped (request not in the scenario file)")
            continue
        if not window.valid:
            print(f"{window.id}: skipped (already blocked)")
            continue
        request = requests_by_id[window.request_id]
        sample = coverage_at(
            samples,
            target_lat=request.target_lat,
            target_lon=request.target_lon,
            moment=culmination_time(window),
            tolerance_s=args.tolerance_s,
        )
        verdict = (
            "no sample"
            if sample is None
            else f"{sample.cloud_cover_pct:.0f}% vs {args.threshold:.0f}% -> {'BLOCK' if sample.cloud_cover_pct >= args.threshold else 'clear'}"
        )
        print(f"{window.id} @ {culmination_time(window).isoformat()}: {verdict}")

    payloads = cloud_block_payloads_for_windows(
        samples,
        scenario.requests,
        windows,
        threshold_pct=args.threshold,
        tolerance_s=args.tolerance_s,
    )
    events = [
        {"event_type": "CLOUD_BLOCK", "payload": payload.to_dict()}
        for payload in payloads
    ]
    Path(args.out).write_text(json.dumps(events, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(events)} cloud-block event(s) to {args.out}")


if __name__ == "__main__":
    main()
