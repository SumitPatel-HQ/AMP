"""Raw-byte cue archives. Only the explicit developer fetch uses a network."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

USGS_SOURCE = "usgs"


@dataclass(frozen=True)
class CueArchive:
    response: dict[str, Any]
    source: str
    source_url: str
    retrieved_at: datetime
    file: str
    sha256: str


def store_archive(
    directory: Path,
    raw: bytes,
    *,
    source_url: str,
    retrieved_at: datetime,
) -> Path:
    """Store original USGS bytes in a new directory, never replacing an archive."""
    if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
        raise ValueError("archive retrieval time must include a timezone")
    if not isinstance(source_url, str) or not source_url.strip():
        raise ValueError("archive source_url must be nonempty")
    manifest = {
        "source": USGS_SOURCE,
        "source_url": source_url,
        "retrieved_at": retrieved_at.isoformat(),
        "file": "response.geojson",
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    try:
        directory.mkdir(parents=True, exist_ok=False)
    except FileExistsError as error:
        raise ValueError(f"archive already exists: {directory}; choose a new directory") from error
    response_path = directory / manifest["file"]
    manifest_path = directory / "manifest.json"
    try:
        response_path.write_bytes(raw)
        manifest_path.write_bytes((json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    except OSError:
        response_path.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
        directory.rmdir()
        raise
    return manifest_path


def load_archive(manifest_path: Path) -> CueArchive:
    """Check the manifest and raw-byte integrity before parsing the response."""
    try:
        manifest = json.loads(manifest_path.read_bytes())
    except (OSError, ValueError) as error:
        raise ValueError(f"cannot read cue archive manifest {manifest_path}: {error}") from error
    if not isinstance(manifest, dict):
        raise ValueError(f"cue archive manifest {manifest_path} must be an object")
    for field in ("source", "source_url", "retrieved_at", "file", "sha256"):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            raise ValueError(f"cue archive manifest {manifest_path} is missing a valid {field} entry")
    if manifest["source"] != USGS_SOURCE:
        raise ValueError(f"cue archive source must be {USGS_SOURCE!r}")
    filename = manifest["file"]
    if Path(filename).name != filename or filename in (".", "..") or "/" in filename or "\\" in filename:
        raise ValueError("cue archive file entry must be a filename inside the archive directory")
    try:
        retrieved_at = datetime.fromisoformat(manifest["retrieved_at"])
    except ValueError as error:
        raise ValueError("cue archive retrieved_at must be an ISO-8601 datetime") from error
    if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
        raise ValueError("cue archive retrieved_at must include a timezone")
    response_path = manifest_path.parent / filename
    try:
        raw = response_path.read_bytes()
    except OSError as error:
        raise ValueError(f"cannot read cue archive response {response_path}: {error}") from error
    checksum = hashlib.sha256(raw).hexdigest()
    if checksum != manifest["sha256"]:
        raise ValueError(
            f"cue archive checksum mismatch for {response_path}; "
            f"expected {manifest['sha256']}, got {checksum}. Restore the original response."
        )
    try:
        response = json.loads(raw)
    except ValueError as error:
        raise ValueError(f"cue archive response {response_path} is not valid JSON: {error}") from error
    if not isinstance(response, dict):
        raise ValueError(f"cue archive response {response_path} must be a GeoJSON object")
    return CueArchive(
        response=response,
        source=manifest["source"],
        source_url=manifest["source_url"],
        retrieved_at=retrieved_at,
        file=filename,
        sha256=checksum,
    )
