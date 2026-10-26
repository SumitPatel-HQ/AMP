"""Developer archive-builder seam; synthetic STAC responses are labelled here."""

import hashlib
import json
from datetime import datetime, timezone

import pytest

from amis.archive_check import fetch_archive, load_archive


URL = "https://stac.dataspace.copernicus.eu/v1/search?collections=sentinel-2-l2a&limit=1"
NOW = datetime(2026, 10, 26, 6, tzinfo=timezone.utc)


def page(items, next_url=None):
    return json.dumps({"type": "FeatureCollection", "features": items,
                       "numberReturned": len(items), "links": [] if next_url is None else [
                           {"rel": "next", "href": next_url, "method": "GET"}]}).encode()


def test_complete_search_preserves_original_pages_and_verifies_all_checksums(tmp_path):
    next_url = URL + "&token=next"
    raw = {URL: page([{"id": "synthetic-1"}], next_url), next_url: page([{"id": "synthetic-2"}])}
    calls = []

    def fetch(url):
        calls.append(url)
        return raw[url]

    manifest = fetch_archive(URL, tmp_path / "archive", fetch=fetch, clock=lambda: NOW)
    data = json.loads(manifest.read_bytes())
    assert calls == [URL, next_url]
    assert data["pagination_complete"] is True
    assert data["item_count"] == 2
    assert data["pages"][0]["sha256"] == hashlib.sha256(raw[URL]).hexdigest()
    assert (manifest.parent / data["pages"][0]["file"]).read_bytes() == raw[URL]
    assert len(load_archive(manifest).pages) == 2


def test_failed_pagination_never_publishes_an_archive(tmp_path):
    destination = tmp_path / "archive"

    def fetch(url):
        if url != URL:
            raise OSError("synthetic second-page failure")
        return page([], URL + "&token=next")

    with pytest.raises(OSError, match="second-page"):
        fetch_archive(URL, destination, fetch=fetch, clock=lambda: NOW)
    assert not destination.exists()


def synthetic_item(item_id="synthetic-scene", **properties):
    return {"type": "Feature", "id": item_id, "collection": "sentinel-2-l2a",
            "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]]},
            "properties": {"datetime": "2026-09-08T09:00:00Z", "eo:cloud_cover": 10, "gsd": 10, **properties},
            "links": [{"rel": "self", "href": "https://stac.dataspace.copernicus.eu/v1/collections/sentinel-2-l2a/items/" + item_id}]}


def scenario_and_requirements():
    from datetime import timedelta
    from amis.domain import ObservationRequest, Satellite, Scenario

    scenario = Scenario("SCN-SYNTHETIC", "Synthetic archive test", NOW, NOW + timedelta(hours=2),
                        satellite=Satellite("SAT-1", 100, 100, 1000, 0),
                        requests=(ObservationRequest("OBS-1", 1, 1, 4, 600, NOW + timedelta(hours=1), 10, 10),))
    requirements = {"OBS-1": {"injection_time": "2026-10-26T06:05:00Z", "profile": {
        "version": "synthetic-profile-v1", "allowed_collections": ["sentinel-2-l2a"],
        "acquisition_start": "2026-09-01T00:00:00Z", "acquisition_end": "2026-09-10T23:59:59Z",
        "max_cloud_cover_pct": 20, "max_gsd_m": 10,
        "sensor_product_assertion": "Synthetic author accepts this optical product"}}}
    return scenario, requirements


def archive_items(tmp_path, *items):
    raw = page(list(items))
    return fetch_archive(URL, tmp_path / "archive", fetch=lambda _: raw, clock=lambda: NOW)


def test_builder_selects_a_qualifying_item_with_self_contained_offline_evidence(tmp_path):
    from amis.archive_check import build_archive_inputs
    from amis.domain import ArchiveSatisfactionPayload

    manifest = archive_items(tmp_path, synthetic_item())
    scenario, requirements = scenario_and_requirements()
    artifact = build_archive_inputs(manifest, scenario, requirements)
    entry, = artifact["inputs"]
    assert entry["event_type"] == "REQUEST_SATISFIED_BY_ARCHIVE"
    assert entry["injection_time"] == "2026-10-26T06:05:00+00:00"
    assert entry["payload"]["item_id"] == "synthetic-scene"
    assert entry["payload"]["source_response_sha256"] == json.loads(manifest.read_bytes())["pages"][0]["sha256"]
    ArchiveSatisfactionPayload.from_dict(entry["payload"]).validate(datetime.fromisoformat(entry["injection_time"]))
    assert artifact["results"][0]["outcome"] == "selected"


@pytest.mark.parametrize("properties,reason", [
    ({"gsd": None}, "gsd_m"), ({"eo:cloud_cover": None}, "cloud_cover_pct"),
    ({"eo:cloud_cover": 20.01}, "quality"), ({"gsd": 10.01}, "quality"),
    ({"eo:cloud_cover": True}, "finite"), ({"gsd": "10"}, "finite"),
    ({"datetime": "2027-01-01T00:00:00Z"}, "acquisition"),
    ({"start_datetime": "2026-08-31T23:59:59Z", "end_datetime": "2026-09-08T09:00:00Z"}, "acquisition"),
    ({"start_datetime": "2026-09-08T09:00:00Z", "end_datetime": None}, "isoformat"),
])
def test_required_metadata_and_threshold_failures_produce_explained_no_match(tmp_path, properties, reason):
    from amis.archive_check import build_archive_inputs

    manifest = archive_items(tmp_path, synthetic_item(**properties))
    result = build_archive_inputs(manifest, *scenario_and_requirements())
    assert result["inputs"] == []
    assert result["results"][0]["outcome"] == "no_match"
    assert reason in result["results"][0]["rejections"][0]["reason"]


def test_ranking_uses_interval_end_then_cloud_then_collection_and_item_with_duplicate_collapse(tmp_path):
    from amis.archive_check import build_archive_inputs

    older = synthetic_item("older-clear", **{"datetime": "2026-09-06T00:00:00Z", "eo:cloud_cover": 0})
    cloudy = synthetic_item("newest-cloudier", **{"eo:cloud_cover": 11})
    high_id = synthetic_item("z-scene")
    winner = synthetic_item("a-scene", **{"datetime": None, "start_datetime": "2026-09-07T00:00:00Z", "end_datetime": "2026-09-08T09:00:00Z"})
    other_collection = synthetic_item("a-scene")
    other_collection["collection"] = "sentinel-2-l1c"
    other_collection["links"][0]["href"] = other_collection["links"][0]["href"].replace("sentinel-2-l2a", "sentinel-2-l1c")
    scenario, requirements = scenario_and_requirements()
    requirements["OBS-1"]["profile"]["allowed_collections"].append("sentinel-2-l1c")
    # Collection L1C sorts before L2A when acquisition end and cloud tie.
    manifest = archive_items(tmp_path, older, cloudy, high_id, winner, winner, other_collection)
    result = build_archive_inputs(manifest, scenario, requirements)
    assert result["inputs"][0]["payload"]["collection_id"] == "sentinel-2-l1c"
    assert result["inputs"][0]["payload"]["item_id"] == "a-scene"
    assert result["results"][0]["qualifying_count"] == 5


def test_conflicting_qualifying_identity_fails_instead_of_choosing_favorable_metadata(tmp_path):
    from amis.archive_check import build_archive_inputs

    manifest = archive_items(tmp_path, synthetic_item(), synthetic_item(**{"eo:cloud_cover": 90}))
    with pytest.raises(ValueError, match="conflicting selected"):
        build_archive_inputs(manifest, *scenario_and_requirements())


def test_geographic_boundary_passes_while_bbox_only_and_unsupported_geometry_are_diagnosed(tmp_path):
    from amis.archive_check import build_archive_inputs

    boundary = synthetic_item("boundary")
    boundary["geometry"]["coordinates"] = [[[1, 0], [2, 0], [2, 2], [1, 2], [1, 0]]]
    outside = synthetic_item("bbox-only")
    outside["geometry"]["coordinates"] = [[[0, 0], [2, 0], [0, 1.5], [0, 0]]]
    unsupported = synthetic_item("unsupported")
    unsupported["geometry"] = {"type": "MultiPolygon", "coordinates": [boundary["geometry"]["coordinates"]]}
    invalid = synthetic_item("invalid")
    invalid["geometry"]["coordinates"] = [[[0, 0], [2, 2], [0, 2], [2, 0], [0, 0]]]
    result = build_archive_inputs(archive_items(tmp_path, boundary, outside, unsupported, invalid), *scenario_and_requirements())
    assert result["inputs"][0]["payload"]["item_id"] == "boundary"
    assert {r["item_id"] for r in result["results"][0]["rejections"]} == {"bbox-only", "unsupported", "invalid"}


@pytest.mark.parametrize("properties,expected", [
    ({"view:incidence_angle": 2}, 2),
    ({"view:incidence_angle": 2, "view:off_nadir": 50}, 2),
    ({"view:off_nadir": 3}, 3),
    ({"view:incidence_angle": None, "view:off_nadir": 3}, 3),
])
def test_view_requirement_prefers_sentinel_incidence_with_off_nadir_fallback(tmp_path, properties, expected):
    from amis.archive_check import build_archive_inputs

    manifest = archive_items(tmp_path, synthetic_item(**properties))
    scenario, requirements = scenario_and_requirements()
    requirements["OBS-1"]["profile"]["max_view_angle_deg"] = 10
    result = build_archive_inputs(manifest, scenario, requirements)
    assert result["inputs"][0]["payload"]["view_angle_deg"] == expected


def test_invalid_incidence_is_not_replaced_with_a_more_favorable_off_nadir_value(tmp_path):
    from amis.archive_check import build_archive_inputs

    manifest = archive_items(tmp_path, synthetic_item(**{"view:incidence_angle": 20, "view:off_nadir": 2}))
    scenario, requirements = scenario_and_requirements()
    requirements["OBS-1"]["profile"]["max_view_angle_deg"] = 10
    result = build_archive_inputs(manifest, scenario, requirements)
    assert result["inputs"] == []
    assert "view angle" in result["results"][0]["rejections"][0]["reason"]


def test_required_view_angle_is_not_invented_when_both_catalogue_fields_are_missing(tmp_path):
    from amis.archive_check import build_archive_inputs

    manifest = archive_items(tmp_path, synthetic_item())
    scenario, requirements = scenario_and_requirements()
    requirements["OBS-1"]["profile"]["max_view_angle_deg"] = 10
    result = build_archive_inputs(manifest, scenario, requirements)
    assert result["inputs"] == []
    assert "view angle" in result["results"][0]["rejections"][0]["reason"]


@pytest.mark.parametrize("mode", ["cycle", "missing-last-page", "post-next", "count-mismatch", "foreign-host", "nonfinite"])
def test_incomplete_or_unsupported_search_never_publishes_complete_evidence(tmp_path, mode):
    destination = tmp_path / "archive"
    data = json.loads(page([synthetic_item()]))
    if mode == "cycle":
        data["links"] = [{"rel": "next", "href": URL}]
    elif mode == "missing-last-page":
        data["numberMatched"] = 2
    elif mode == "post-next":
        data["links"] = [{"rel": "next", "href": URL + "&token=next", "method": "POST"}]
    elif mode == "foreign-host":
        data["links"] = [{"rel": "next", "href": "https://example.org/next"}]
    elif mode == "nonfinite":
        data["features"][0]["properties"]["gsd"] = float("nan")
    else:
        data["numberReturned"] = 2
    with pytest.raises(ValueError):
        fetch_archive(URL, destination, fetch=lambda _: json.dumps(data).encode(), clock=lambda: NOW)
    assert not destination.exists()


def test_all_checksums_are_verified_even_when_first_page_already_has_a_match(tmp_path):
    from amis.archive_check import build_archive_inputs

    next_page = URL + "&token=last"
    responses = {URL: page([synthetic_item()], next_page), next_page: page([synthetic_item("unused")])}
    manifest = fetch_archive(URL, tmp_path / "archive", fetch=responses.__getitem__, clock=lambda: NOW)
    (manifest.parent / "page-0002.json").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        build_archive_inputs(manifest, *scenario_and_requirements())


def test_availability_and_scenario_dates_fail_without_clipping_or_replacing_output(tmp_path):
    from amis.archive_check import write_archive_inputs

    manifest = archive_items(tmp_path, synthetic_item())
    scenario, requirements = scenario_and_requirements()
    output = tmp_path / "inputs.json"
    output.write_bytes(b"previous complete output")
    for injection in ("2026-10-26T05:59:59Z", "2026-10-26T08:00:00Z"):
        requirements["OBS-1"]["injection_time"] = injection
        with pytest.raises(ValueError):
            write_archive_inputs(output, manifest, scenario, requirements)
        assert output.read_bytes() == b"previous complete output"


def test_full_search_must_be_available_even_if_selected_item_page_was_retrieved_earlier(tmp_path):
    from datetime import timedelta
    from amis.archive_check import build_archive_inputs

    next_page = URL + "&token=last"
    responses = {URL: page([synthetic_item()], next_page), next_page: page([])}
    times = iter([NOW, NOW + timedelta(minutes=10)])
    manifest = fetch_archive(URL, tmp_path / "archive", fetch=responses.__getitem__, clock=lambda: next(times))
    with pytest.raises(ValueError, match="retrieval"):
        build_archive_inputs(manifest, *scenario_and_requirements())


def test_invalid_profile_fails_even_for_an_empty_search_and_atomic_output_is_stable(tmp_path):
    from amis.archive_check import write_archive_inputs

    manifest = archive_items(tmp_path)
    scenario, requirements = scenario_and_requirements()
    output = tmp_path / "inputs.json"
    artifact = write_archive_inputs(output, manifest, scenario, requirements)
    before = output.read_bytes()
    assert artifact["inputs"] == []
    assert artifact["results"][0]["outcome"] == "no_match"
    write_archive_inputs(output, manifest, scenario, requirements)
    assert output.read_bytes() == before
    requirements["OBS-1"]["profile"]["max_gsd_m"] = 0
    with pytest.raises(ValueError):
        write_archive_inputs(output, manifest, scenario, requirements)
    assert output.read_bytes() == before


def test_emergency_requirement_must_follow_its_recorded_pool_arrival(tmp_path):
    from dataclasses import replace
    from datetime import timedelta
    from amis.archive_check import build_archive_inputs
    from amis.domain import EmergencyRequestPayload, EventType, MissionEvent

    manifest = archive_items(tmp_path, synthetic_item())
    scenario, requirements = scenario_and_requirements()
    incoming = replace(scenario.requests[0], id="OBS-ARRIVAL")
    arrival = MissionEvent("EVT-ARRIVAL", scenario.id, EventType.EMERGENCY_TASK,
                           NOW + timedelta(minutes=10), EmergencyRequestPayload(incoming, ()))
    requirements = {incoming.id: requirements["OBS-1"]}
    with pytest.raises(ValueError, match="arrival"):
        build_archive_inputs(manifest, scenario, requirements, arrival_events=(arrival,))
    requirements[incoming.id]["injection_time"] = "2026-10-26T06:10:00Z"
    artifact = build_archive_inputs(manifest, scenario, requirements, arrival_events=(arrival,))
    assert artifact["inputs"][0]["payload"]["request_id"] == incoming.id


def test_interval_and_quality_boundaries_are_inclusive_and_preserved(tmp_path):
    from amis.archive_check import build_archive_inputs

    item = synthetic_item(**{"datetime": None, "start_datetime": "2026-09-01T00:00:00Z",
                             "end_datetime": "2026-09-10T23:59:59Z", "eo:cloud_cover": 20,
                             "view:off_nadir": 10})
    manifest = archive_items(tmp_path, item)
    scenario, requirements = scenario_and_requirements()
    requirements["OBS-1"]["profile"]["max_view_angle_deg"] = 10
    payload = build_archive_inputs(manifest, scenario, requirements)["inputs"][0]["payload"]
    assert payload["acquisition_start"] == "2026-09-01T00:00:00+00:00"
    assert payload["acquisition_end"] == "2026-09-10T23:59:59+00:00"
    assert payload["cloud_cover_pct"] == 20
    assert payload["view_angle_deg"] == 10


@pytest.mark.parametrize("reverse", [False, True])
def test_item_id_tie_is_independent_of_response_order(tmp_path, reverse):
    from amis.archive_check import build_archive_inputs

    items = [synthetic_item("z-item"), synthetic_item("a-item")]
    if reverse:
        items.reverse()
    artifact = build_archive_inputs(archive_items(tmp_path, *items), *scenario_and_requirements())
    assert artifact["inputs"][0]["payload"]["item_id"] == "a-item"


def test_one_invalid_selected_request_cannot_replace_previous_complete_artifact(tmp_path):
    from amis.archive_check import write_archive_inputs

    manifest = archive_items(tmp_path, synthetic_item())
    scenario, requirements = scenario_and_requirements()
    output = tmp_path / "inputs.json"
    write_archive_inputs(output, manifest, scenario, requirements)
    original = output.read_bytes()
    requirements["UNKNOWN-REQUEST"] = requirements["OBS-1"]
    with pytest.raises(ValueError, match="unknown request"):
        write_archive_inputs(output, manifest, scenario, requirements)
    assert output.read_bytes() == original
