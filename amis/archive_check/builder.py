"""Pure offline archive-point-v1 selection and atomic developer input output."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote, urlsplit

from amis.archive_check.archive import SOURCE, ArchivePage, checked_url, load_archive
from amis.time import parse_utc_iso_timestamp
from amis.domain import ArchiveSatisfactionPayload, EmergencyRequestPayload, EventType, MissionEvent, ObservationRequest, RequestStatus, Scenario
from amis.domain.archive import validate_suitability_profile


POLICY = "archive-point-v1"


def _identity(item: dict[str, Any]) -> tuple[str, str]:
    collection, item_id = item.get("collection"), item.get("id")
    if not isinstance(collection, str) or not collection.strip() or not isinstance(item_id, str) or not item_id.strip():
        raise ValueError("STAC item requires explicit collection and item identities")
    return collection, item_id


def _payload(item: dict[str, Any], page: ArchivePage, request: ObservationRequest, profile: dict[str, Any], retrieved_at: str) -> ArchiveSatisfactionPayload:
    collection, item_id = _identity(item)
    if collection not in {"sentinel-2-l1c", "sentinel-2-l2a"}:
        raise ValueError("unsupported collection: initial adapter qualifies Sentinel-2 L1C/L2A only")
    if item.get("type") != "Feature":
        raise ValueError("STAC item must be a Feature")
    properties = item["properties"]
    if properties.get("start_datetime") is not None or properties.get("end_datetime") is not None:
        start, end = properties["start_datetime"], properties["end_datetime"]
    else:
        start = end = properties["datetime"]
    start = parse_utc_iso_timestamp(start)
    end = parse_utc_iso_timestamp(end)
    links = item["links"]
    source_links = [link["href"] for link in links if link.get("rel") == "self"]
    if len(source_links) != 1:
        raise ValueError("STAC item requires one unambiguous source self link")
    source_url = checked_url(source_links[0])
    if unquote(urlsplit(source_url).path) != f"/v1/collections/{collection}/items/{item_id}":
        raise ValueError("STAC self link does not match the collection/item identity")
    view_angle = properties.get("view:incidence_angle")
    if view_angle is None:
        view_angle = properties.get("view:off_nadir")
    return ArchiveSatisfactionPayload(
        request_id=request.id, catalogue_source=SOURCE, collection_id=collection, item_id=item_id,
        source_url=source_url, source_response_sha256=page.sha256,
        source_credit=f"Copernicus Sentinel data {end.year}; Copernicus Data Space Ecosystem catalogue metadata",
        acquisition_start=start.isoformat(), acquisition_end=end.isoformat(), retrieved_at=retrieved_at,
        target_lat=request.target_lat, target_lon=request.target_lon, footprint=item["geometry"],
        cloud_cover_pct=properties["eo:cloud_cover"], gsd_m=properties["gsd"],
        view_angle_deg=view_angle, profile=profile, policy_version=POLICY,
    )


def build_archive_inputs(
    manifest_path: Path, scenario: Scenario, requirements: dict[str, Any], *,
    arrival_events: Iterable[MissionEvent] = (),
) -> dict[str, Any]:
    """Verify all pages before conservative qualification; never access a network.

    Requirements are keyed by request ID and carry an explicit injection_time
    and profile. Optional accepted EMERGENCY_TASK records establish pool arrival.
    Candidate failures are explained in results; invalid author inputs fail the
    entire build. Conflicting identities fail if any variant would be selected.
    """
    archive = load_archive(manifest_path)
    if not isinstance(requirements, dict) or not requirements:
        raise ValueError("provide explicit per-request archive requirements")
    pool = {r.id: (r, scenario.start_time) for r in scenario.requests}
    for event in arrival_events:
        if (event.scenario_id != scenario.id or event.event_type is not EventType.EMERGENCY_TASK
                or not isinstance(event.payload, EmergencyRequestPayload)
                or not scenario.start_time <= event.event_time < scenario.end_time):
            raise ValueError("arrival inputs must be accepted emergency events within this Scenario")
        request = event.payload.request
        if request.id in pool:
            raise ValueError("arrival request identity already exists")
        pool[request.id] = (request, event.event_time)
    # Stable order and exact-duplicate collapse, independent of page ordering.
    candidates: dict[tuple[str, str], dict[str, tuple[dict[str, Any], ArchivePage]]] = {}
    malformed = []
    for page in archive.pages:
        for item in json.loads(page.raw)["features"]:
            try:
                identity = _identity(item)
            except ValueError as error:
                malformed.append(str(error))
                continue
            encoded = json.dumps(item, sort_keys=True, separators=(",", ":"), allow_nan=False)
            variants = candidates.setdefault(identity, {})
            previous = variants.get(encoded)
            if previous is None or (page.sha256, page.url) < (previous[1].sha256, previous[1].url):
                variants[encoded] = (item, page)
    inputs: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for request_id, requirement in sorted(requirements.items()):
        if request_id not in pool:
            raise ValueError(f"archive requirement names unknown request {request_id}")
        if not isinstance(requirement, dict) or set(requirement) != {"injection_time", "profile"}:
            raise ValueError("each archive requirement needs only injection_time and profile")
        request, arrival_time = pool[request_id]
        injection = parse_utc_iso_timestamp(requirement["injection_time"])
        if (request.validation_error() is not None or request.status not in (RequestStatus.PENDING, RequestStatus.SCHEDULED)
                or not scenario.start_time <= injection < scenario.end_time
                or injection < arrival_time or injection > request.deadline):
            raise ValueError("archive injection must follow request arrival, precede expiry, and be within the Scenario")
        if archive.retrieved_at > injection:
            raise ValueError("archived search retrieval must be no later than satisfaction; historical availability is unknown")
        profile = requirement["profile"]
        validate_suitability_profile(profile)
        qualified, rejections = [], [{"reason": reason} for reason in sorted(set(malformed))]
        for identity, variants in sorted(candidates.items()):
            qualifying_variants = []
            for item, page in variants.values():
                try:
                    payload = _payload(item, page, request, profile, archive.retrieved_at.isoformat())
                    payload.validate(injection)
                    qualifying_variants.append(payload)
                except (KeyError, TypeError, ValueError, AttributeError, OverflowError) as error:
                    rejections.append({"collection_id": identity[0], "item_id": identity[1], "reason": str(error)})
            if qualifying_variants and len(variants) > 1:
                raise ValueError(f"conflicting selected catalogue identity: {identity[0]}/{identity[1]}")
            qualified.extend(qualifying_variants)
        # Three stable sorts avoid timestamp float precision and retain full intervals.
        qualified.sort(key=lambda p: (p.collection_id, p.item_id))
        qualified.sort(key=lambda p: p.cloud_cover_pct)
        qualified.sort(key=lambda p: parse_utc_iso_timestamp(p.acquisition_end), reverse=True)
        if qualified:
            selected = qualified[0]
            inputs.append({"injection_time": injection.isoformat(), "event_type": EventType.REQUEST_SATISFIED_BY_ARCHIVE.value,
                           "payload": selected.to_dict()})
        results.append({"request_id": request_id, "outcome": "selected" if qualified else "no_match",
                        "qualifying_count": len(qualified),
                        "rejections": sorted(rejections, key=lambda r: (r.get("collection_id", ""), r.get("item_id", ""), r["reason"]))})
    inputs.sort(key=lambda e: (e["injection_time"], e["payload"]["request_id"]))
    return {"metadata": {"artifact_type": "developer-archive-inputs", "scenario_id": scenario.id,
                         "policy_version": POLICY, "catalogue_source": SOURCE,
                         "archive_retrieved_at": archive.retrieved_at.isoformat(),
                         "page_sha256": sorted(p.sha256 for p in archive.pages)},
            "inputs": inputs, "results": results}


def write_archive_inputs(output: Path, manifest_path: Path, scenario: Scenario, requirements: dict[str, Any], *,
                         arrival_events: Iterable[MissionEvent] = ()) -> dict[str, Any]:
    """Build everything before atomically publishing deterministic UTF-8 bytes."""
    archive_dir = manifest_path.resolve().parent
    if output.resolve().is_relative_to(archive_dir):
        raise ValueError("generated inputs must not replace archive evidence")
    artifact = build_archive_inputs(manifest_path, scenario, requirements, arrival_events=arrival_events)
    encoded = (json.dumps(artifact, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix=f".{output.name}.", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(encoded)
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return artifact
