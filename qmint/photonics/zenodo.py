"""Reproducible Zenodo fetcher: metadata first, resumable download, dual checksums.

Zenodo publishes an MD5 per file (``"md5:<hex>"``). We verify it exactly and
record it verbatim as ``ManifestEntry.upstream_checksum``; independently we
compute the local SHA-256, which is the hash every derived QMint record cites.
The two are never conflated.

Raw data live in a shared cache OUTSIDE the repository (default
``/Users/udsy/PycharmProjects/qmint-data-cache``; override with the
``QMINT_DATA_CACHE`` environment variable). Raw archives are not committed.
"""

from __future__ import annotations

import hashlib
import os
import platform
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from qmint.core.contracts import EvidenceKind, EvidenceManifest, ManifestEntry
from qmint.core.serialization import file_sha256

ZENODO_API = "https://zenodo.org/api/records"
DEFAULT_CACHE = Path("/Users/udsy/PycharmProjects/qmint-data-cache")


def data_cache_dir() -> Path:
    """Shared raw-data cache directory (not inside any git worktree)."""
    return Path(os.environ.get("QMINT_DATA_CACHE", str(DEFAULT_CACHE)))


class ChecksumMismatch(RuntimeError):
    """Downloaded bytes do not match the upstream (Zenodo) checksum."""


@dataclass(frozen=True)
class ZenodoFile:
    record_id: int
    key: str
    size: int
    upstream_checksum: str  # exactly as published, e.g. "md5:fd70..."
    url: str


def _session() -> Any:
    import requests

    s = requests.Session()
    s.headers["User-Agent"] = "qmint-photonics/0.1 (research reproduction)"
    return s


def fetch_record(record_id: int, *, retries: int = 4, timeout: float = 60.0) -> dict[str, Any]:
    """GET the public Zenodo record JSON (no auth)."""
    s = _session()
    last: Exception | None = None
    for attempt in range(retries):
        try:
            r = s.get(f"{ZENODO_API}/{record_id}", timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # network errors are retried
            last = exc
            time.sleep(2**attempt)
    raise RuntimeError(f"could not fetch Zenodo record {record_id}: {last}")


def record_files(record: dict[str, Any]) -> list[ZenodoFile]:
    out = []
    for f in record.get("files", []):
        out.append(
            ZenodoFile(
                record_id=int(record["id"]),
                key=f["key"],
                size=int(f["size"]),
                upstream_checksum=f["checksum"],
                url=f["links"]["self"],
            )
        )
    return out


def verify_upstream_checksum(path: str | Path, upstream_checksum: str) -> None:
    """Verify a file against a Zenodo ``"<algo>:<hex>"`` checksum; raise on mismatch."""
    algo, _, expected = upstream_checksum.partition(":")
    if not expected:
        raise ValueError(f"malformed upstream checksum {upstream_checksum!r}")
    h = hashlib.new(algo)
    with open(path, "rb") as fh:
        while block := fh.read(1 << 20):
            h.update(block)
    if h.hexdigest() != expected.lower():
        raise ChecksumMismatch(f"{path}: {algo} {h.hexdigest()} != upstream {expected}")


def download(
    zf: ZenodoFile,
    dest_dir: str | Path,
    *,
    retries: int = 6,
    chunk: int = 1 << 20,
    timeout: float = 60.0,
) -> Path:
    """Resumable (HTTP Range) download with retries, then upstream checksum verification.

    A partial file ``<key>.part`` is resumed; on checksum failure the file is removed
    and :class:`ChecksumMismatch` raised. An existing verified file is reused.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    final = dest_dir / zf.key
    if final.exists() and final.stat().st_size == zf.size:
        verify_upstream_checksum(final, zf.upstream_checksum)
        return final
    part = dest_dir / (zf.key + ".part")
    s = _session()
    for attempt in range(retries):
        have = part.stat().st_size if part.exists() else 0
        if have >= zf.size:
            break
        headers = {"Range": f"bytes={have}-"} if have else {}
        try:
            with s.get(zf.url, headers=headers, stream=True, timeout=timeout) as r:
                if r.status_code not in (200, 206):
                    r.raise_for_status()
                mode = "ab" if (have and r.status_code == 206) else "wb"
                with open(part, mode) as fh:
                    for block in r.iter_content(chunk_size=chunk):
                        fh.write(block)
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2**attempt)
    if part.stat().st_size != zf.size:
        raise RuntimeError(f"size mismatch for {zf.key}: {part.stat().st_size} != {zf.size}")
    try:
        verify_upstream_checksum(part, zf.upstream_checksum)
    except ChecksumMismatch:
        part.unlink()
        raise
    part.rename(final)
    return final


def download_manifest(
    files: list[tuple[ZenodoFile, Path]],
    *,
    manifest_id: str,
    command: str,
    git_sha: str,
    retrieved_utc: str | None = None,
) -> EvidenceManifest:
    """C6 EvidenceManifest for downloaded originals: Zenodo MD5 + local SHA-256."""
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    entries = [
        ManifestEntry(
            path_or_uri=zf.url,
            sha256=file_sha256(p),
            role="input",
            original_or_derived="original",
            upstream_checksum=zf.upstream_checksum,
        )
        for zf, p in files
    ]
    return EvidenceManifest(
        manifest_id=manifest_id,
        created_utc=now,
        source_urls=[f"{ZENODO_API}/{zf.record_id}" for zf, _ in files],
        retrieved_utc=retrieved_utc or now,
        command=command,
        git_sha=git_sha,
        environment={"python": platform.python_version(), "platform": platform.platform()},
        evidence_kind=EvidenceKind.PHOTON_EXPERIMENT,
        entries=entries,
    )
