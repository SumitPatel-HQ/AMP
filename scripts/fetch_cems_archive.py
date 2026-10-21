"""Explicit developer fetch of one public, non-sensitive CEMS detail response.

python -m scripts.fetch_cems_archive EMSR933 amis/data/cues/crete-emsr933-20261004
"""
from __future__ import annotations
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen
from amis.cues.archive import store_archive
from amis.cues.cems import normalize_cems


def fetch_archive(code: str, directory: Path) -> Path:
    if not re.fullmatch(r'EMSR[0-9]+', code):
        raise ValueError('activation code must be EMSR followed by digits')
    if directory.exists():
        raise ValueError(f'archive already exists: {directory}; choose a new directory')
    url = f'https://rapidmapping.emergency.copernicus.eu/backend/dashboard-api/public-activations/?code={code}'
    with urlopen(url, timeout=30) as response:
        raw = response.read()
    retrieved_at = datetime.now(timezone.utc)
    # Do not write sensitive or unknown-visibility bytes, even temporarily.
    records = normalize_cems(json.loads(raw))
    if len(records) != 1 or records[0]['code'] != code:
        raise ValueError('detail response must contain only the requested public activation')
    return store_archive(directory, raw, source='cems', source_url=url, retrieved_at=retrieved_at)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('code')
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    try:
        print(fetch_archive(args.code, args.directory))
    except (OSError, TypeError, ValueError) as error:
        parser.exit(2, f'CEMS fetch failed: {error}\n')

if __name__ == '__main__':
    main()
