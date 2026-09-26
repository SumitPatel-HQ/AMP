"""Developer-only Open-Meteo refresh; never imported by the application.

Fetches hourly archived cloud cover for the demo targets and writes a
dated raw file plus manifest under amis/data/weather/. Open-Meteo
needs no key for non-commercial use; its archive API serves reanalysis
back to 1940 with a few days of delay, so date the mission inside the
retrieved span.

Run: python scripts/fetch_weather_archive.py --start-date 2026-09-20 --end-date 2026-09-25
Inspect the dated JSON and manifest diff before committing a refresh.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from amis.weather.archive import location_key, record_hash

ROOT = Path(__file__).resolve().parents[1] / "amis" / "data" / "weather"

# Demo targets: Bengaluru and Delhi, matching the sample archive.
TARGETS = ((12.97, 77.59), (28.61, 77.21))


def fetch_target(lat: float, lon: float, start_date: str, end_date: str) -> tuple[dict, str]:
    query = urlencode(
        {
            "latitude": lat,
            "longitude": lon,
            "hourly": "cloud_cover",
            "start_date": start_date,
            "end_date": end_date,
            "timezone": "UTC",
        }
    )
    url = f"https://archive-api.open-meteo.com/v1/archive?{query}"
    with urlopen(url, timeout=30) as response:
        record = json.load(response)
    return {"latitude": lat, "longitude": lon, "hourly": record["hourly"]}, url


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        metavar="LAT,LON",
        help="extra target; repeatable (default: the demo targets)",
    )
    args = parser.parse_args()

    targets = list(TARGETS)
    for extra in args.target:
        lat, lon = (float(part) for part in extra.split(","))
        targets.append((lat, lon))

    retrieved = datetime.now(timezone.utc)
    records = []
    hashes = {}
    sources = {}
    for lat, lon in targets:
        record, url = fetch_target(lat, lon, args.start_date, args.end_date)
        records.append(record)
        key = location_key(lat, lon)
        hashes[key] = record_hash(record)
        sources[key] = url

    ROOT.mkdir(parents=True, exist_ok=True)
    filename = f"{retrieved.date().isoformat()}.json"
    (ROOT / filename).write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    (ROOT / "manifest.json").write_text(
        json.dumps(
            {
                "file": filename,
                "source_url": "https://archive-api.open-meteo.com/v1/archive",
                "retrieved_at": retrieved.isoformat(),
                "sample": False,
                "hashes": hashes,
                "sources": sources,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {filename} with {len(records)} location(s)")


if __name__ == "__main__":
    main()
