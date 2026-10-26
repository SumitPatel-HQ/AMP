"""Explicit developer-only complete CDSE STAC GET search archive."""

import argparse
from pathlib import Path

from amis.archive_check import fetch_archive


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-url", required=True, help="complete CDSE STAC GET search URL")
    parser.add_argument("--archive-dir", type=Path, required=True, help="new directory; never overwritten")
    parser.add_argument("--max-pages", type=int, default=100)
    args = parser.parse_args()
    try:
        manifest = fetch_archive(args.source_url, args.archive_dir, max_pages=args.max_pages)
    except (OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(2, f"imagery fetch failed: {error}\n")
    print(f"Archived complete search at {manifest}")


if __name__ == "__main__":
    main()
