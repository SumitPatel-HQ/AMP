"""Wave 5: the committed weather archive is auditable and the normaliser is strict."""

import copy
import json
from datetime import datetime, timezone

import pytest

from amis.domain import CloudBlockPayload
from amis.weather import (
    WEATHER_DIR,
    CloudSample,
    load_archive,
    location_key,
    normalize_archive,
    record_hash,
)


def test_committed_archive_loads_with_retrieval_time_and_source():
    archive = load_archive()

    assert len(archive.records) == 2
    assert archive.source_url.startswith("https://archive-api.open-meteo.com/")
    assert archive.retrieved_at.tzinfo is not None


def test_archive_hashes_verify_every_record():
    archive = load_archive()
    manifest = json.loads(
        (WEATHER_DIR / "manifest.json").read_text(encoding="utf-8")
    )

    for record in archive.records:
        key = location_key(record["latitude"], record["longitude"])
        assert manifest["hashes"][key] == record_hash(record)


def test_tampered_record_fails_verification(tmp_path):
    archive = load_archive()
    raw = copy.deepcopy(list(archive.records))
    raw[0]["hourly"]["cloud_cover"][0] = 99.0

    data_file = tmp_path / "tampered.json"
    data_file.write_text(json.dumps(raw), encoding="utf-8")
    manifest = {
        "file": "tampered.json",
        "source_url": archive.source_url,
        "retrieved_at": archive.retrieved_at.isoformat(),
        "hashes": {
            location_key(record["latitude"], record["longitude"]): "0" * 64
            for record in raw
        },
    }
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="checksum mismatch"):
        load_archive(manifest_file)


def test_normaliser_maps_hourly_series_to_samples():
    archive = load_archive()

    samples = normalize_archive(archive.records)

    assert len(samples) == 12
    bengaluru = [sample for sample in samples if sample.target_lat == 12.97]
    assert [sample.cloud_cover_pct for sample in bengaluru] == [
        12.0,
        18.0,
        85.0,
        92.0,
        45.0,
        20.0,
    ]
    assert bengaluru[2].time == datetime(2026, 9, 25, 6, tzinfo=timezone.utc)
    assert all(sample.source == "open-meteo-archive" for sample in samples)


@pytest.mark.parametrize(
    "record",
    [
        {"latitude": 12.97, "longitude": 77.59},
        {
            "latitude": 12.97,
            "longitude": 77.59,
            "hourly": {
                "time": ["2026-09-25T06:00:00+00:00"],
                "cloud_cover": [10.0, 20.0],
            },
        },
        {
            "latitude": 12.97,
            "longitude": 77.59,
            "hourly": {
                "time": ["2026-09-25T06:00:00"],
                "cloud_cover": [10.0],
            },
        },
        {
            "latitude": 12.97,
            "longitude": 77.59,
            "hourly": {"time": ["not-a-time"], "cloud_cover": [10.0]},
        },
        {
            "latitude": 12.97,
            "longitude": 77.59,
            "hourly": {
                "time": ["2026-09-25T06:00:00+00:00"],
                "cloud_cover": [101.0],
            },
        },
        {
            "latitude": 12.97,
            "longitude": 77.59,
            "hourly": {
                "time": ["2026-09-25T06:00:00+00:00"],
                "cloud_cover": [float("nan")],
            },
        },
    ],
)
def test_normaliser_rejects_bad_records(record):
    with pytest.raises(ValueError):
        normalize_archive([record])


def test_cloud_sample_round_trip():
    sample = CloudSample(
        target_lat=12.97,
        target_lon=77.59,
        time=datetime(2026, 9, 25, 6, tzinfo=timezone.utc),
        cloud_cover_pct=85.0,
        source="open-meteo-archive",
    )

    assert CloudSample.from_dict(sample.to_dict()) == sample


def test_cloud_block_payload_keeps_its_pre_wave5_shape():
    assert CloudBlockPayload("OBS-B", "WIN-OBS-B-1").to_dict() == {
        "request_id": "OBS-B",
        "window_id": "WIN-OBS-B-1",
    }
    assert not CloudBlockPayload("OBS-B", "WIN-OBS-B-1").is_weather_derived


def test_weather_payload_round_trip_carries_its_evidence():
    payload = CloudBlockPayload(
        request_id="OBS-B",
        window_id="WIN-OBS-B-1",
        source="open-meteo-archive",
        cloud_cover_pct=85.0,
        threshold_pct=50.0,
    )

    assert CloudBlockPayload.from_dict(payload.to_dict()) == payload
    assert payload.is_weather_derived
