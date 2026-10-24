"""Developer archive behavior using synthetic bytes, not historical evidence."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from amis.cues import load_archive, store_archive
from scripts.fetch_cue_archive import fetch_archive

SOURCE_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson"
RETRIEVED = datetime(2026, 10, 9, tzinfo=timezone.utc)
RAW = b'{ "type": "FeatureCollection", "features": [] }\r\n'


def archive_at(tmp_path: Path) -> Path:
    return store_archive(tmp_path / "archive", RAW, source_url=SOURCE_URL, retrieved_at=RETRIEVED)


def test_archive_preserves_original_bytes_and_complete_manifest(tmp_path):
    manifest_path = archive_at(tmp_path)
    manifest = json.loads(manifest_path.read_bytes())

    assert (manifest_path.parent / "response.geojson").read_bytes() == RAW
    assert manifest == {
        "source": "usgs", "source_url": SOURCE_URL,
        "retrieved_at": "2026-10-09T00:00:00+00:00",
        "file": "response.geojson", "sha256": hashlib.sha256(RAW).hexdigest(),
    }
    archive = load_archive(manifest_path)
    assert archive.response == {"type": "FeatureCollection", "features": []}
    assert archive.source == "usgs"
    assert archive.file == "response.geojson"
    assert archive.sha256 == manifest["sha256"]
    assert archive.source_url == SOURCE_URL
    assert archive.retrieved_at == RETRIEVED


def test_existing_archive_is_never_overwritten(tmp_path):
    manifest_path = archive_at(tmp_path)
    original = manifest_path.read_bytes()

    with pytest.raises(ValueError, match="archive already exists"):
        store_archive(manifest_path.parent, b"new data", source_url=SOURCE_URL, retrieved_at=RETRIEVED)

    assert manifest_path.read_bytes() == original
    assert (manifest_path.parent / "response.geojson").read_bytes() == RAW


def test_checksum_is_verified_before_response_is_parsed(tmp_path):
    manifest_path = archive_at(tmp_path)
    (manifest_path.parent / "response.geojson").write_bytes(b"not even JSON")

    with pytest.raises(ValueError, match="checksum mismatch.*Restore the original response"):
        load_archive(manifest_path)


@pytest.mark.parametrize("field", ["source", "source_url", "retrieved_at", "file", "sha256"])
def test_missing_manifest_entries_have_actionable_diagnostics(tmp_path, field):
    manifest_path = archive_at(tmp_path)
    manifest = json.loads(manifest_path.read_bytes())
    del manifest[field]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match=f"missing a valid {field} entry"):
        load_archive(manifest_path)


def test_missing_manifest_and_response_have_actionable_diagnostics(tmp_path):
    with pytest.raises(ValueError, match="cannot read cue archive manifest"):
        load_archive(tmp_path / "missing.json")
    manifest_path = archive_at(tmp_path)
    (manifest_path.parent / "response.geojson").unlink()
    with pytest.raises(ValueError, match="cannot read cue archive response.*response.geojson"):
        load_archive(manifest_path)


@pytest.mark.parametrize("field,value,diagnostic", [
    ("retrieved_at", "2026-10-09T00:00:00", "must include a timezone"),
    ("retrieved_at", "bad", "ISO-8601"),
    ("file", "../outside.json", "filename inside"),
    ("file", "..\\outside.json", "filename inside"),
    ("source", "another-feed", "source must be 'usgs'"),
])
def test_invalid_manifest_is_rejected(tmp_path, field, value, diagnostic):
    manifest_path = archive_at(tmp_path)
    manifest = json.loads(manifest_path.read_bytes())
    manifest[field] = value
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match=diagnostic):
        load_archive(manifest_path)


def test_invalid_json_with_matching_checksum_has_parse_diagnostic(tmp_path):
    manifest_path = store_archive(tmp_path / "archive", b"not JSON", source_url=SOURCE_URL, retrieved_at=RETRIEVED)
    with pytest.raises(ValueError, match="not valid JSON"):
        load_archive(manifest_path)


def test_store_requires_aware_retrieval_time(tmp_path):
    with pytest.raises(ValueError, match="retrieval time must include a timezone"):
        store_archive(tmp_path / "archive", RAW, source_url=SOURCE_URL, retrieved_at=datetime(2026, 10, 9))
    assert not (tmp_path / "archive").exists()


def test_explicit_fetch_stores_exact_transport_bytes_and_url(tmp_path, monkeypatch):
    calls = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return RAW

    def fetch(url, *, timeout):
        calls.append((url, timeout))
        return Response()

    monkeypatch.setattr("scripts.fetch_cue_archive.urlopen", fetch)
    manifest_path = fetch_archive(SOURCE_URL, tmp_path / "fetched")
    assert calls == [(SOURCE_URL, 30)]
    assert (manifest_path.parent / "response.geojson").read_bytes() == RAW
    assert load_archive(manifest_path).retrieved_at.utcoffset().total_seconds() == 0
    with pytest.raises(ValueError, match="archive already exists"):
        fetch_archive(SOURCE_URL, manifest_path.parent)
    assert calls == [(SOURCE_URL, 30)]


@pytest.mark.parametrize("url", ["http://earthquake.usgs.gov/example", "https://example.com/usgs", "https://user@earthquake.usgs.gov/example"])
def test_fetch_rejects_non_usgs_urls_without_network(tmp_path, monkeypatch, url):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid fetch must not touch the network")
    monkeypatch.setattr("scripts.fetch_cue_archive.urlopen", forbidden)
    with pytest.raises(ValueError, match="HTTPS earthquake.usgs.gov"):
        fetch_archive(url, tmp_path / "archive")
