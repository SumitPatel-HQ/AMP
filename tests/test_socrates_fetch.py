"""Developer fetch seam; no requests to CelesTrak during tests."""
from datetime import datetime, timedelta, timezone
from email.message import Message
import json
from unittest.mock import patch
from urllib.error import HTTPError

import pytest

from scripts.fetch_socrates_archive import fetch_archive


def test_early_refresh_is_refused_across_archive_destinations(tmp_path):
    state = tmp_path / 'state.json'
    state.write_text(json.dumps({'next_allowed_fetch_at': (datetime.now(timezone.utc) + timedelta(hours=10)).isoformat()}))
    with patch('scripts.fetch_socrates_archive.build_opener') as network:
        with pytest.raises(ValueError, match='early refresh'):
            fetch_archive(tmp_path / 'new', state_path=state)
        network.assert_not_called()
    assert not (tmp_path / 'new').exists()
    assert not state.with_suffix('.lock').exists()


def test_error_is_one_attempt_and_retry_after_is_persisted(tmp_path):
    state = tmp_path / 'state.json'
    headers = Message()
    headers['Retry-After'] = '86400'
    with patch('scripts.fetch_socrates_archive.build_opener') as network:
        network.return_value.open.side_effect = HTTPError('https://celestrak.org', 503, 'unavailable', headers, None)
        with pytest.raises(HTTPError):
            fetch_archive(tmp_path / 'first', state_path=state)
        network.return_value.open.assert_called_once()
        with pytest.raises(ValueError, match='early refresh'):
            fetch_archive(tmp_path / 'second', state_path=state)
        network.return_value.open.assert_called_once()
    recorded = json.loads(state.read_bytes())
    assert recorded['status'] == 'failed'
    assert datetime.fromisoformat(recorded['next_allowed_fetch_at']) > datetime.now(timezone.utc) + timedelta(hours=23)
    assert not (tmp_path / 'first').exists()


def test_success_archives_once_and_preserves_headers(tmp_path):
    state = tmp_path / 'state.json'
    headers = Message()
    headers['Content-Disposition'] = 'attachment; filename="provider.csv"'
    with patch('scripts.fetch_socrates_archive.build_opener') as network:
        response = network.return_value.open.return_value.__enter__.return_value
        response.status = 200
        response.headers = headers
        response.read.return_value = b'original bytes'
        manifest = fetch_archive(tmp_path / 'report', state_path=state)
    assert json.loads(manifest.read_bytes())['response_filename'] == 'provider.csv'
    assert (manifest.parent / 'report.csv').read_bytes() == b'original bytes'
    assert json.loads(state.read_bytes())['status'] == 'archived'
