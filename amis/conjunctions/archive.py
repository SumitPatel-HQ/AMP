"""Immutable original-byte archives; loading never contacts the provider."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any

SOURCE_URL = 'https://celestrak.org/SOCRATES/sort-minRange.csv'
POLICY_URL = 'https://celestrak.org/usage-policy.php'


def instant(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError('instant must include a timezone')
    return result.astimezone(timezone.utc)


@dataclass(frozen=True)
class ReportArchive:
    raw: bytes
    metadata: dict[str, Any]

    @property
    def available_at(self) -> datetime:
        # Publication is only used when independently established by the provider.
        return instant(self.metadata.get('published_at') or self.metadata['retrieved_at'])


def store_archive(directory: Path, raw: bytes, *, source_url: str,
                  retrieved_at: datetime, response_filename: str,
                  published_at: datetime | None = None,
                  coverage_start: datetime | None = None,
                  coverage_end: datetime | None = None,
                  response_headers: dict[str, str] | None = None,
                  next_allowed_fetch_at: datetime | None = None) -> Path:
    retrieved_at = instant(retrieved_at.isoformat())
    next_fetch = instant((next_allowed_fetch_at or retrieved_at).isoformat())
    if next_fetch < retrieved_at:
        raise ValueError('next allowed fetch time cannot precede retrieval')
    if source_url != SOURCE_URL:
        raise ValueError('unsupported SOCRATES source URL')
    metadata: dict[str, Any] = {
        'source': 'CelesTrak SOCRATES Plus (Dr. T.S. Kelso)',
        'source_url': source_url, 'retrieved_at': retrieved_at.isoformat(),
        'file': 'report.csv', 'response_filename': response_filename,
        'sha256': hashlib.sha256(raw).hexdigest(),
        'next_allowed_fetch_at': next_fetch.isoformat(),
        'usage_policy_url': POLICY_URL, 'usage_policy_verified_on': '2026-10-26',
        'response_headers': response_headers or {},
    }
    for name, value in [('published_at', published_at), ('coverage_start', coverage_start), ('coverage_end', coverage_end)]:
        metadata[name] = instant(value.isoformat()).isoformat() if value else None
    if published_at and instant(published_at.isoformat()) > retrieved_at:
        raise ValueError('publication cannot follow retrieval')
    if (coverage_start is None) != (coverage_end is None):
        raise ValueError('coverage requires both bounds')
    if coverage_start and coverage_end and coverage_start >= coverage_end:
        raise ValueError('coverage start must precede end')
    directory.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.socrates-', dir=directory.parent))
    try:
        (stage / 'report.csv').write_bytes(raw)
        (stage / 'manifest.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
        if directory.exists():
            raise ValueError(f'archive already exists: {directory}')
        # A nonempty destination cannot be silently replaced, including a racing publisher.
        stage.rename(directory)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return directory / 'manifest.json'


def load_archive(path: Path) -> ReportArchive:
    try:
        metadata = json.loads(path.read_bytes())
        if not isinstance(metadata, dict):
            raise ValueError('manifest must be an object')
        for key in ('source', 'source_url', 'retrieved_at', 'sha256', 'response_filename', 'next_allowed_fetch_at'):
            if not isinstance(metadata.get(key), str) or not metadata[key].strip():
                raise ValueError(f'manifest missing a valid {key}')
        if metadata.get('file') != 'report.csv' or metadata['source_url'] != SOURCE_URL:
            raise ValueError('unsupported report file or source URL')
        retrieved = instant(metadata['retrieved_at'])
        if instant(metadata['next_allowed_fetch_at']) < retrieved:
            raise ValueError('invalid next allowed fetch time')
        if metadata.get('published_at') and instant(metadata['published_at']) > retrieved:
            raise ValueError('publication cannot follow retrieval')
        start, end = metadata.get('coverage_start'), metadata.get('coverage_end')
        if bool(start) != bool(end) or (start and end and instant(start) >= instant(end)):
            raise ValueError('invalid coverage bounds')
        raw = (path.parent / 'report.csv').read_bytes()
        if hashlib.sha256(raw).hexdigest() != metadata['sha256']:
            raise ValueError('SOCRATES checksum mismatch; restore original bytes')
        return ReportArchive(raw, metadata)
    except (OSError, KeyError, TypeError) as error:
        raise ValueError(f'cannot load SOCRATES archive: {error}') from error
