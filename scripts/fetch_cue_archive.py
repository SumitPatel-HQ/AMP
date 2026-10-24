"""Explicit developer-only USGS fetch. No application operation imports this script."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

from amis.cues import store_archive


def fetch_archive(source_url: str, directory: Path) -> Path:
    """Fetch once, preserve exact bytes, and refuse an existing archive directory."""
    url = urlsplit(source_url)
    if url.scheme != "https" or url.hostname != "earthquake.usgs.gov" or url.username is not None or url.password is not None:
        raise ValueError("source URL must be an HTTPS earthquake.usgs.gov URL")
    if directory.exists():
        raise ValueError(f"archive already exists: {directory}; choose a new directory")
    with urlopen(source_url, timeout=30) as response:
        raw = response.read()
    return store_archive(directory, raw, source_url=source_url, retrieved_at=datetime.now(timezone.utc))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-url", required=True, help="exact USGS GeoJSON URL to archive")
    parser.add_argument("--archive-dir", type=Path, required=True, help="new archive directory, usually under amis/data/cues/")
    args = parser.parse_args()
    try:
        manifest = fetch_archive(args.source_url, args.archive_dir)
    except (OSError, ValueError) as error:
        parser.exit(2, f"cue fetch failed: {error}\n")
    print(f"archived original USGS response with manifest at {manifest}")


if __name__ == "__main__":
    main()
