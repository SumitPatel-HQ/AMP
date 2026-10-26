"""Complete GET searches published as original bytes plus verified provenance."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qsl, quote, urljoin, urlsplit
from urllib.request import urlopen


SOURCE = "copernicus-data-space-stac"
FORMAT = "stac-get-archive-v1"


def timestamp(value: str) -> datetime:
    moment = datetime.fromisoformat(value)
    if moment.utcoffset() is None:
        raise ValueError("archive timestamps must include a timezone")
    return moment


def checked_url(value: str) -> str:
    url = urlsplit(value)
    if (url.scheme != "https" or url.hostname != "stac.dataspace.copernicus.eu"
            or url.username or url.password or url.port not in (None, 443)
            or url.fragment or not url.path.startswith("/v1/")):
        raise ValueError("archive search/pagination must stay on the HTTPS CDSE STAC v1 service")
    return quote(value, safe=":/?&=,%+@!$'()*;~.-_")


def _nonfinite(value: str) -> None:
    raise ValueError(f"STAC response contains a nonfinite JSON value: {value}")


def decode_page(raw: bytes) -> dict[str, Any]:
    data = json.loads(raw, parse_constant=_nonfinite)
    if (not isinstance(data, dict) or data.get("type") != "FeatureCollection"
            or not isinstance(data.get("features"), list)
            or any(not isinstance(item, dict) for item in data["features"])
            or not isinstance(data.get("links"), list)):
        raise ValueError("STAC page must be a complete FeatureCollection with features and links")
    if "numberReturned" in data and (type(data["numberReturned"]) is not int or data["numberReturned"] != len(data["features"])):
        raise ValueError("STAC numberReturned does not match the page")
    return data


def next_url(data: dict[str, Any], current_url: str) -> str | None:
    if any(not isinstance(link, dict) for link in data["links"]):
        raise ValueError("malformed STAC pagination link")
    links = [link for link in data["links"] if link.get("rel") == "next"]
    if not links:
        return None
    if len(links) != 1:
        raise ValueError("ambiguous STAC pagination: multiple next links")
    link = links[0]
    if (link.get("method", "GET") != "GET" or link.get("body") or link.get("headers") or link.get("merge")):
        raise ValueError("unsupported STAC pagination contract: only plain GET next links are supported")
    if not isinstance(link.get("href"), str) or not link["href"].strip():
        raise ValueError("STAC next link requires a URL")
    return checked_url(urljoin(current_url, link["href"]))


def _download(url: str) -> bytes:
    with urlopen(url, timeout=30) as response:
        # Refuse a redirected response from another service before accepting it.
        checked_url(response.geturl())
        return response.read()


@dataclass(frozen=True)
class ArchivePage:
    raw: bytes
    url: str
    retrieved_at: datetime
    sha256: str


@dataclass(frozen=True)
class ImageryArchive:
    pages: tuple[ArchivePage, ...]
    retrieved_at: datetime


def fetch_archive(
    source_url: str, directory: Path, *,
    fetch: Callable[[str], bytes] = _download,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    max_pages: int = 100,
) -> Path:
    """Explicit network operation; failed/partial searches publish no archive.

    ``fetch`` and ``clock`` are the transport/time boundary for deterministic
    developer-operation tests. Application lifecycle code never calls this.
    """
    directory = directory.resolve()
    if directory.exists():
        raise ValueError("archive already exists; choose a new directory")
    if type(max_pages) is not int or max_pages < 1:
        raise ValueError("max_pages must be a positive integer")
    source_url = checked_url(source_url)
    url: str | None = source_url
    records: list[dict[str, Any]] = []
    originals: list[bytes] = []
    seen: set[str] = set()
    previous_time: datetime | None = None
    while url is not None:
        if url in seen or len(records) >= max_pages:
            raise ValueError("pagination cycle or page limit: search is incomplete")
        seen.add(url)
        raw = fetch(url)
        data = decode_page(raw)
        retrieved = timestamp(clock().isoformat())
        if previous_time is not None and retrieved < previous_time:
            raise ValueError("archive retrieval clock moved backwards")
        previous_time = retrieved
        records.append({"file": f"page-{len(records) + 1:04d}.json", "url": url, "method": "GET",
                        "parameters": parse_qsl(urlsplit(url).query, keep_blank_values=True),
                        "retrieved_at": retrieved.isoformat(), "sha256": hashlib.sha256(raw).hexdigest()})
        originals.append(raw)
        url = next_url(data, url)
    manifest = {"format": FORMAT, "source": SOURCE, "source_url": source_url,
                "retrieved_at": records[-1]["retrieved_at"], "pages": records,
                "page_count": len(records), "item_count": sum(len(decode_page(raw)["features"]) for raw in originals),
                "pagination_complete": True, "completion_reason": "no-next-link"}
    directory.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{directory.name}.", dir=directory.parent))
    try:
        for record, raw in zip(records, originals):
            (staging / record["file"]).write_bytes(raw)
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        load_archive(staging / "manifest.json")
        if directory.exists():
            raise ValueError("archive destination appeared during fetching")
        os.rename(staging, directory)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return directory / "manifest.json"


def load_archive(manifest_path: Path) -> ImageryArchive:
    """Verify every raw page, chain, count and availability time before selection."""
    manifest = json.loads(manifest_path.read_bytes())
    if (not isinstance(manifest, dict) or manifest.get("format") != FORMAT or manifest.get("source") != SOURCE
            or manifest.get("pagination_complete") is not True
            or manifest.get("completion_reason") != "no-next-link"):
        raise ValueError("unsupported or incomplete STAC archive")
    records = manifest.get("pages")
    if (not isinstance(records, list) or not records or type(manifest.get("page_count")) is not int
            or manifest.get("page_count") != len(records)):
        raise ValueError("archive page list/count is incomplete")
    # Check all bytes before inspecting any candidate, including unused pages.
    pages = []
    for i, record in enumerate(records, 1):
        if not isinstance(record, dict):
            raise ValueError("archive page record must be an object")
        if record["file"] != f"page-{i:04d}.json":
            raise ValueError("archive pages must use ordered local filenames")
        raw = (manifest_path.parent / record["file"]).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != record["sha256"]:
            raise ValueError(f"archive checksum mismatch: {record['file']}")
        url = checked_url(record["url"])
        if record.get("method") != "GET" or record.get("parameters") != [list(p) for p in parse_qsl(urlsplit(url).query, keep_blank_values=True)]:
            raise ValueError("archive request parameters/method are inconsistent")
        pages.append(ArchivePage(raw, url, timestamp(record["retrieved_at"]), digest))
    expected: str | None = checked_url(manifest["source_url"])
    item_count, seen = 0, set()
    previous_time = pages[0].retrieved_at
    for page in pages:
        if page.url != expected or page.url in seen or page.retrieved_at < previous_time:
            raise ValueError("archive pagination chain or retrieval times are inconsistent")
        seen.add(page.url)
        previous_time = page.retrieved_at
        data = decode_page(page.raw)
        item_count += len(data["features"])
        expected = next_url(data, page.url)
    if expected is not None or type(manifest.get("item_count")) is not int or manifest.get("item_count") != item_count:
        raise ValueError("archive pagination ended prematurely or item count is inconsistent")
    for page in pages:
        matched = decode_page(page.raw).get("numberMatched")
        if matched is not None and (type(matched) is not int or matched != item_count):
            raise ValueError("archive result count does not match the completed search")
    retrieved = timestamp(manifest["retrieved_at"])
    if retrieved != pages[-1].retrieved_at:
        raise ValueError("archive completion time does not match the final retrieval")
    return ImageryArchive(tuple(pages), retrieved)
