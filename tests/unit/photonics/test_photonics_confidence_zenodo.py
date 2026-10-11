"""Confidence-interval and Zenodo-fetch tests (no network: the HTTP session is faked)."""

from __future__ import annotations

import hashlib

import numpy as np
import pytest

from qmint.core.contracts import EvidenceKind
from qmint.photonics import zenodo
from qmint.photonics.confidence import (
    block_bootstrap_ratio,
    clopper_pearson,
    contiguous_split,
    heterogeneity,
    two_proportion_z,
)


def test_clopper_pearson_reference_values():
    lo, hi = clopper_pearson(0, 10)
    assert lo == 0.0 and hi == pytest.approx(0.30849, abs=1e-5)
    lo, hi = clopper_pearson(5, 10)
    assert (lo, hi) == pytest.approx((0.18709, 0.81291), abs=1e-5)
    with pytest.raises(ValueError):
        clopper_pearson(3, 2)


def test_block_bootstrap_deterministic_and_covers():
    k = np.array([10, 12, 9, 11, 30])
    n = np.array([1000] * 5)
    a = block_bootstrap_ratio(k, n, seed=1)
    assert a == block_bootstrap_ratio(k, n, seed=1)
    assert a[1] <= a[0] <= a[2]


def test_heterogeneity_and_split():
    h = heterogeneity(np.array([10, 10, 10]), np.array([1000, 1000, 1000]))
    assert h.chi2 == pytest.approx(0.0) and h.p_value == pytest.approx(1.0)
    h2 = heterogeneity(np.array([10, 50]), np.array([1000, 1000]))
    assert h2.p_value < 1e-6
    assert contiguous_split(11, 0.5) == (slice(0, 6), slice(6, 11))
    z, p = two_proportion_z(10, 1000, 10, 1000)
    assert z == 0 and p == pytest.approx(1.0)


class _Resp:
    def __init__(self, data: bytes, status: int):
        self._d, self.status_code = data, status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        raise RuntimeError(self.status_code)

    def iter_content(self, chunk_size):
        for i in range(0, len(self._d), chunk_size):
            yield self._d[i : i + chunk_size]


class _Session:
    """Serves `payload`; the first full GET dies half-way to exercise resume via Range."""

    def __init__(self, payload: bytes):
        self.payload, self.calls = payload, []

    def get(self, url, headers=None, stream=False, timeout=None):
        headers = headers or {}
        self.calls.append(headers.get("Range"))
        if "Range" in headers:
            start = int(headers["Range"].split("=")[1].rstrip("-"))
            return _Resp(self.payload[start:], 206)
        if len(self.calls) == 1:
            return _Broken(self.payload[: len(self.payload) // 2])
        return _Resp(self.payload, 200)


class _Broken(_Resp):
    def __init__(self, data):
        super().__init__(data, 200)

    def iter_content(self, chunk_size):
        yield from super().iter_content(chunk_size)
        raise ConnectionError("dropped")


def _zf(payload: bytes, md5: str | None = None) -> zenodo.ZenodoFile:
    return zenodo.ZenodoFile(1, "f.bin", len(payload), md5 or "md5:" + hashlib.md5(payload).hexdigest(), "u")


def test_resumable_download_and_checksum(tmp_path, monkeypatch):
    payload = bytes(range(256)) * 1000
    s = _Session(payload)
    monkeypatch.setattr(zenodo, "_session", lambda: s)
    monkeypatch.setattr(zenodo.time, "sleep", lambda *_: None)
    p = zenodo.download(_zf(payload), tmp_path, chunk=4096)
    assert p.read_bytes() == payload
    assert s.calls[0] is None and s.calls[1] is not None and s.calls[1].startswith("bytes=")
    man = zenodo.download_manifest([(_zf(payload), p)], manifest_id="m", command="c", git_sha="g")
    e = man.entries[0]
    assert e.sha256 == hashlib.sha256(payload).hexdigest()
    assert e.upstream_checksum.startswith("md5:") and e.upstream_checksum[4:] != e.sha256
    assert man.evidence_kind == EvidenceKind.PHOTON_EXPERIMENT


def test_checksum_mismatch_removes_partial(tmp_path, monkeypatch):
    payload = b"x" * 5000
    monkeypatch.setattr(zenodo, "_session", lambda: _Session(payload))
    monkeypatch.setattr(zenodo.time, "sleep", lambda *_: None)
    with pytest.raises(zenodo.ChecksumMismatch):
        zenodo.download(_zf(payload, "md5:" + "0" * 32), tmp_path)
    assert not list(tmp_path.iterdir())


def test_record_files_parsing():
    rec = {"id": 7979319, "files": [{"key": "Archive.zip", "size": 153143236,
                                     "checksum": "md5:fd708578a613b63f57c31f986a56bf94",
                                     "links": {"self": "https://zenodo.org/x"}}]}
    (f,) = zenodo.record_files(rec)
    assert f.size == 153143236 and f.upstream_checksum == "md5:fd708578a613b63f57c31f986a56bf94"
