"""Developer-only CelesTrak refresh; never imported by the application.

Run: python -m scripts.fetch_orbital_elements
Inspect the dated JSON and manifest diff before committing a refresh.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

from amis.orbital.elements import from_omm

IDS = (39084, 40697, 49260)  # Landsat 8, Sentinel-2A, Landsat 9
ROOT = Path(__file__).resolve().parents[1] / "amis" / "data" / "elements"


def main() -> None:
    retrieved = datetime.now(timezone.utc)
    records = []
    hashes = {}
    sources = {}
    for norad_id in IDS:
        url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={norad_id}&FORMAT=json"
        with urlopen(url, timeout=30) as response:
            record = json.load(response)[0]
        item = from_omm(record, source=url, retrieved_at=retrieved)
        records.append(record)
        hashes[str(norad_id)] = item.sha256
        sources[str(norad_id)] = url
    ROOT.mkdir(parents=True, exist_ok=True)
    filename = f"{retrieved.date().isoformat()}.json"
    (ROOT / filename).write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    (ROOT / "manifest.json").write_text(json.dumps({
        "file": filename,
        "source_url": "https://celestrak.org/NORAD/elements/gp.php",
        "retrieved_at": retrieved.isoformat(),
        "hashes": hashes,
        "sources": sources,
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
