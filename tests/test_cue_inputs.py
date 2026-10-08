"""Ticket 01 conversion contracts with explicitly synthetic earthquake records."""

import copy
import json
import socket
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from amis.cues import (
    ImagingProfile, build_cue_inputs, load_archive, normalize_usgs,
    request_identifier, store_archive, write_cue_inputs,
)
from amis.domain import ObservationRequest, Satellite, Scenario
from scripts.build_cue_events import main

TIME = datetime(2026, 9, 25, tzinfo=timezone.utc)
PROFILE = ImagingProfile(duration_s=60, energy_cost_wh=10, storage_cost_mb=25)


def feature(event_id="synthetic-a", **properties):
    return {
        "type": "Feature", "id": event_id,
        "geometry": {"type": "Point", "coordinates": [77.59, 12.97, 500]},
        "properties": {"time": 1790294400123, "place": "Synthetic test point", **properties},
    }


def response(*features):
    return {"type": "FeatureCollection", "features": list(features)}


@pytest.fixture
def scenario():
    return Scenario(
        id="synthetic-scenario", name="Synthetic cue test", start_time=TIME,
        end_time=TIME + timedelta(days=3),
        satellite=Satellite("SAT-1", 100, 100, 1000, 0),
    )


@pytest.fixture
def archive(tmp_path):
    def create(*features, directory="archive"):
        manifest = store_archive(
            tmp_path / directory, json.dumps(response(*features)).encode("utf-8"),
            source_url="https://earthquake.usgs.gov/synthetic-test-only",
            retrieved_at=datetime(2026, 10, 9, tzinfo=timezone.utc),
        )
        return load_archive(manifest)
    return create


def test_longitude_latitude_and_millisecond_utc_normalization_ignores_depth():
    record = feature(alert=None, mag=6.2, sig=100)
    cue, = normalize_usgs(response(record))
    assert (cue.target_lon, cue.target_lat) == (77.59, 12.97)
    assert cue.event_time == datetime(2026, 9, 25, 0, 0, 0, 123000, tzinfo=timezone.utc)
    assert cue.alert_level == "unknown"
    assert (cue.mag, cue.sig) == (6.2, 100)
    record["geometry"]["coordinates"][2] = "depth does not describe the imaging point"
    assert normalize_usgs(response(record)) == (cue,)


@pytest.mark.parametrize("milliseconds,expected", [
    (0, datetime(1970, 1, 1, tzinfo=timezone.utc)),
    (-1, datetime(1969, 12, 31, 23, 59, 59, 999000, tzinfo=timezone.utc)),
    (1790294400123, datetime(2026, 9, 25, 0, 0, 0, 123000, tzinfo=timezone.utc)),
])
def test_epoch_milliseconds_keep_exact_precision(milliseconds, expected):
    cue, = normalize_usgs(response(feature(time=milliseconds)))
    assert cue.event_time == expected


@pytest.mark.parametrize("alert,mag,priority,deadline", [
    ("red", None, 5, "2026-09-25T12:00:00.123000+00:00"),
    ("orange", None, 4, "2026-09-26T00:00:00.123000+00:00"),
    ("yellow", None, 3, "2026-09-27T00:00:00.123000+00:00"),
    ("green", None, 2, "2026-09-27T00:00:00.123000+00:00"),
    (None, None, 2, "2026-09-27T00:00:00.123000+00:00"),
    ("green", 6, 5, "2026-09-27T00:00:00.123000+00:00"),
    ("orange", 6.1, 5, "2026-09-26T00:00:00.123000+00:00"),
    ("yellow", 5.99, 3, "2026-09-27T00:00:00.123000+00:00"),
    (None, 6, 5, "2026-09-27T00:00:00.123000+00:00"),
])
def test_policy_matches_ticket_table_and_keeps_costs_explicit(archive, scenario, alert, mag, priority, deadline):
    original = scenario.to_dict()
    artifact = build_cue_inputs(archive(feature(alert=alert, mag=mag, sig=999999)), scenario, PROFILE)
    item, = artifact["inputs"]
    request = item["payload"]["request"]
    assert request["priority"] == priority
    assert request["deadline"] == deadline
    assert (request["duration_s"], request["energy_cost_wh"], request["storage_cost_mb"]) == (60, 10, 25)
    assert request["target_name"] == "Synthetic test point"
    assert request["target_name"] != request["id"]
    assert item["injection_time"] == "2026-09-25T00:00:00.123000+00:00"
    assert item["event_type"] == "EMERGENCY_TASK"
    assert item["payload"]["alert_level"] == (alert or "unknown")
    assert artifact["metadata"]["policy_version"] == "usgs-earthquake-v1"
    assert artifact["metadata"]["imaging_profile"] == {"duration_s": 60, "energy_cost_wh": 10, "storage_cost_mb": 25}
    assert artifact["metadata"]["artifact_type"] == "developer-cue-inputs"
    assert "windows" not in item["payload"]
    assert "id" not in item and "simulated_time" not in item
    assert scenario.to_dict() == original


def test_absent_evidence_is_omitted_and_significance_has_no_policy_effect(archive, scenario):
    first = build_cue_inputs(archive(feature()), scenario, PROFILE)
    second = build_cue_inputs(archive(feature(sig=999999), directory="other"), scenario, PROFILE)
    payload = first["inputs"][0]["payload"]
    assert payload["source"] == "usgs"
    assert payload["source_event_id"] == "synthetic-a"
    assert payload["alert_level"] == "unknown"
    assert "mag" not in payload and "sig" not in payload
    assert payload["request"] == second["inputs"][0]["payload"]["request"]


@pytest.mark.parametrize("coordinates", [[181, 0], [0, 91], [-181, 0], [0, -91], [float("nan"), 0], [0, float("inf")], ["77", 12], [True, 0], [0], None])
def test_invalid_selected_coordinates_fail(coordinates):
    record = feature()
    record["geometry"]["coordinates"] = coordinates
    with pytest.raises(ValueError, match="selected USGS record"):
        normalize_usgs(response(record))


@pytest.mark.parametrize("field,value", [
    ("time", None), ("time", "1790294400123"), ("time", float("nan")),
    ("time", float("inf")), ("time", True), ("time", 0.5), ("time", 10**25),
    ("alert", "unknown"), ("alert", "Red"), ("alert", "blue"), ("alert", 1),
    ("mag", "6.0"), ("mag", True), ("mag", float("nan")),
    ("sig", float("inf")), ("sig", "100"),
])
def test_invalid_selected_source_evidence_fails(field, value):
    with pytest.raises(ValueError, match="selected USGS record"):
        normalize_usgs(response(feature(**{field: value})))


@pytest.mark.parametrize("event_id", [None, "", "   ", 123])
def test_event_identifier_is_required(event_id):
    with pytest.raises(ValueError, match="source event identifier"):
        normalize_usgs(response(feature(event_id)))


def test_nonpoint_geometry_and_bad_geojson_fail():
    record = feature()
    record["geometry"]["type"] = "Polygon"
    with pytest.raises(ValueError, match="GeoJSON Point"):
        normalize_usgs(response(record))
    with pytest.raises(ValueError, match="FeatureCollection"):
        normalize_usgs({"type": "FeatureCollection", "features": None})


def test_equal_normalized_records_collapse_and_conflicts_fail():
    first = feature(mag=5.0)
    duplicate = copy.deepcopy(first)
    duplicate["geometry"]["coordinates"][2] = 999
    duplicate["properties"]["updated"] = 999
    assert len(normalize_usgs(response(first, duplicate))) == 1
    duplicate["properties"]["mag"] = 6
    with pytest.raises(ValueError, match="conflicting normalized records for usgs:synthetic-a"):
        normalize_usgs(response(first, duplicate), selected_event_ids=["synthetic-a"])


def test_selection_skips_unselected_invalid_records_and_reports_missing_ids():
    good = feature("selected")
    bad = feature("unselected", alert="invalid")
    assert len(normalize_usgs(response(bad, good), selected_event_ids=["selected"])) == 1
    with pytest.raises(ValueError, match="identifiers are missing: missing"):
        normalize_usgs(response(good), selected_event_ids=["missing"])


def test_generated_identity_is_stable_and_source_scoped():
    first = request_identifier("usgs", "synthetic-a")
    assert first == request_identifier("usgs", "synthetic-a")
    assert first != request_identifier("other", "synthetic-a")
    assert first != request_identifier("usgs", "synthetic-b")
    assert request_identifier("a:b", "c") != request_identifier("a", "b:c")


def test_build_sorting_duplicates_and_bytes_are_deterministic(archive, scenario, tmp_path):
    source = archive(
        feature("z", time=1790294400000), feature("late", time=1790294401000),
        feature("a", time=1790294400000), feature("z", time=1790294400000),
    )
    first = build_cue_inputs(source, scenario, PROFILE, selected_event_ids=["z", "a", "late"])
    second = build_cue_inputs(replace(source, retrieved_at=TIME), scenario, PROFILE, selected_event_ids=["late", "a", "z"])
    write_cue_inputs(tmp_path / "first.json", first)
    write_cue_inputs(tmp_path / "second.json", second)
    assert [item["payload"]["source_event_id"] for item in first["inputs"]] == ["a", "z", "late"]
    assert (tmp_path / "first.json").read_bytes() == (tmp_path / "second.json").read_bytes()
    assert b"retrieved_at" not in (tmp_path / "first.json").read_bytes()


@pytest.mark.parametrize("offset", [-1, 3 * 86400])
def test_out_of_range_cues_fail_without_clamping(archive, scenario, offset):
    with pytest.raises(ValueError, match="outside Scenario.*select a smaller set"):
        build_cue_inputs(archive(feature(time=1790294400000 + offset * 1000)), scenario, PROFILE)


def test_start_is_included_end_is_excluded_and_smaller_selection_is_allowed(archive, scenario):
    source = archive(feature("start", time=1790294400000), feature("end", time=1790553600000))
    with pytest.raises(ValueError, match="outside Scenario"):
        build_cue_inputs(source, scenario, PROFILE)
    built = build_cue_inputs(source, scenario, PROFILE, selected_event_ids=["start"])
    assert len(built["inputs"]) == 1


@pytest.mark.parametrize("missing", ["duration_s", "energy_cost_wh", "storage_cost_mb"])
def test_imaging_profile_never_guesses_missing_values(missing):
    values = PROFILE.to_dict()
    del values[missing]
    with pytest.raises(ValueError, match=f"missing explicit values: {missing}"):
        ImagingProfile.from_dict(values)


@pytest.mark.parametrize("changes", [
    {"duration_s": 0}, {"duration_s": float("inf")}, {"energy_cost_wh": -1},
    {"energy_cost_wh": float("nan")}, {"storage_cost_mb": -1},
    {"storage_cost_mb": float("inf")}, {"satellite_id": "missing"},
    {"target_name": "  "},
])
def test_generated_requests_apply_existing_validation(archive, scenario, changes):
    profile = replace(PROFILE, **changes)
    with pytest.raises(ValueError):
        build_cue_inputs(archive(feature()), scenario, profile)


def test_satellite_assignment_and_explicit_target_name_are_preserved(archive, scenario):
    profile = replace(PROFILE, satellite_id="SAT-1", target_name="Author supplied imaging point")
    artifact = build_cue_inputs(archive(feature(place=None)), scenario, profile)
    request = artifact["inputs"][0]["payload"]["request"]
    assert request["satellite_id"] == "SAT-1"
    assert request["target_name"] == "Author supplied imaging point"
    assert artifact["metadata"]["imaging_profile"] == profile.to_dict()


def test_target_name_is_required_and_cannot_be_the_request_identifier(archive, scenario):
    source = archive(feature(place=None))
    with pytest.raises(ValueError, match="descriptive target_name"):
        build_cue_inputs(source, scenario, PROFILE)
    profile = replace(PROFILE, target_name=request_identifier("usgs", "synthetic-a"))
    with pytest.raises(ValueError, match="distinct from its request id"):
        build_cue_inputs(source, scenario, profile)


def test_generated_request_identifier_cannot_duplicate_scenario_request(archive, scenario):
    source = archive(feature())
    built = build_cue_inputs(source, scenario, PROFILE)
    request = ObservationRequest.from_dict(built["inputs"][0]["payload"]["request"])
    with pytest.raises(ValueError, match="already exists in Scenario"):
        build_cue_inputs(source, replace(scenario, requests=(request,)), PROFILE)


def test_offline_cli_builds_without_network_and_failure_preserves_output(archive, scenario, tmp_path, monkeypatch):
    archive(feature("good"), feature("bad", alert="invalid"))
    scenario_file = tmp_path / "scenario.json"
    scenario_file.write_text(json.dumps(scenario.to_dict()), encoding="utf-8")
    profile_file = tmp_path / "profile.json"
    profile_file.write_text(json.dumps(PROFILE.to_dict()), encoding="utf-8")
    output = tmp_path / "inputs.json"
    argv = [
        "build_cue_events.py", str(scenario_file), "--archive-manifest", str(tmp_path / "archive" / "manifest.json"),
        "--imaging-profile", str(profile_file), "--out", str(output),
    ]
    def forbidden(*args, **kwargs):
        pytest.fail("offline cue builder attempted network access")
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr("sys.argv", [*argv, "--event-id", "good"])
    main()
    original = output.read_bytes()
    assert json.loads(original)["inputs"][0]["payload"]["source_event_id"] == "good"
    monkeypatch.setattr("sys.argv", [*argv, "--all"])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert output.read_bytes() == original
    output.unlink()
    with pytest.raises(SystemExit):
        main()
    assert not output.exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_publication_failure_leaves_previous_output_and_cleans_temporary_file(tmp_path, monkeypatch):
    output = tmp_path / "inputs.json"
    output.write_bytes(b"previous complete script")
    def fail(*args):
        raise OSError("synthetic replacement failure")
    monkeypatch.setattr("amis.cues.rules.os.replace", fail)
    with pytest.raises(OSError, match="replacement failure"):
        write_cue_inputs(output, {"inputs": []})
    assert output.read_bytes() == b"previous complete script"
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("output_name", ["archive/manifest.json", "archive/response.geojson", "scenario.json", "profile.json"])
def test_cli_cannot_overwrite_its_source_inputs(archive, scenario, tmp_path, monkeypatch, output_name):
    archive(feature())
    scenario_file = tmp_path / "scenario.json"
    scenario_file.write_text(json.dumps(scenario.to_dict()), encoding="utf-8")
    profile_file = tmp_path / "profile.json"
    profile_file.write_text(json.dumps(PROFILE.to_dict()), encoding="utf-8")
    output = tmp_path / output_name
    original = output.read_bytes()
    monkeypatch.setattr("sys.argv", [
        "build_cue_events.py", str(scenario_file), "--archive-manifest", str(tmp_path / "archive" / "manifest.json"),
        "--imaging-profile", str(profile_file), "--all", "--out", str(output),
    ])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert output.read_bytes() == original
