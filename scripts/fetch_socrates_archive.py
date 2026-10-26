"""Explicit developer fetch, one attempt, with a shared persistent cooldown."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, build_opener

from amis.conjunctions.archive import FETCH_INTERVAL, SOURCE_URL, instant, store_archive


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_archive(directory: Path, *, state_path: Path) -> Path:
    """State must be shared across destinations; failed attempts also consume cooldown."""
    if directory.exists():
        raise ValueError(f'archive already exists: {directory}')
    state_path.parent.mkdir(parents=True, exist_ok=True)
    lock = state_path.with_suffix('.lock')
    try:
        handle = lock.open('x')
    except FileExistsError as error:
        raise ValueError('fetch already active; investigate stale lock before retrying') from error
    try:
        now = datetime.now(timezone.utc)
        if state_path.exists():
            state = json.loads(state_path.read_bytes())
            if now < instant(state['next_allowed_fetch_at']):
                raise ValueError(f"early refresh refused until {state['next_allowed_fetch_at']}")
        state = {'source_url': SOURCE_URL, 'attempted_at': now.isoformat(),
                 'next_allowed_fetch_at': (now + FETCH_INTERVAL).isoformat(), 'status': 'started'}
        # Persist before network access; interruption must not enable a tight retry.
        state_path.write_text(json.dumps(state, indent=2) + '\n', encoding='utf-8')
        try:
            with build_opener(NoRedirect()).open(SOURCE_URL, timeout=60) as response:
                if response.status != 200:
                    raise ValueError(f'HTTP {response.status}; stop and investigate')
                raw = response.read()
                headers = dict(response.headers.items())
                filename = response.headers.get_filename() or 'sort-minRange.csv'
            retrieved = datetime.now(timezone.utc)
            manifest = store_archive(directory, raw, source_url=SOURCE_URL, retrieved_at=retrieved,
                                     response_filename=filename, response_headers=headers)
            state.update(status='archived', manifest=str(manifest),
                         next_allowed_fetch_at=(retrieved + FETCH_INTERVAL).isoformat())
        except Exception as error:
            state.update(status='failed', error=str(error))
            if isinstance(error, HTTPError) and error.headers.get('Retry-After'):
                retry = error.headers['Retry-After']
                try:
                    from datetime import timedelta
                    until = now + timedelta(seconds=int(retry))
                except ValueError:
                    until = parsedate_to_datetime(retry)
                if until > instant(state['next_allowed_fetch_at']):
                    state['next_allowed_fetch_at'] = until.isoformat()
            raise
        finally:
            state_path.write_text(json.dumps(state, indent=2) + '\n', encoding='utf-8')
        return manifest
    finally:
        handle.close()
        lock.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive-dir', type=Path, required=True)
    parser.add_argument('--state-file', type=Path, default=Path('outputs/socrates-fetch-state.json'))
    args = parser.parse_args()
    try:
        print(fetch_archive(args.archive_dir, state_path=args.state_file))
    except (OSError, ValueError) as error:
        parser.exit(2, f'SOCRATES fetch failed (no automatic retry): {error}\n')


if __name__ == '__main__':
    main()
