"""SYNTHETIC timetag generator (EvidenceKind.SYNTHETIC). Never experimental evidence.

Builds archives with the same layout/format as Zenodo 7979319 (established by inspection)
but with fully known ground truth: pair counts, error counts and channel assignment.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import numpy as np

SYNTHETIC_TAG = "SYNTHETIC qmint test fixture - not experimental data"


def synth_pairs(
    n: int,
    *,
    client_basis: str,
    n_errors_by_state: dict[int, int],
    seed: int = 0,
    rate_hz: float = 1e4,
    jitter_ns: float = 0.4,
    bin_ns: float = 3.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Row-paired (ttp_ch, ttp_t, client_ch, client_t) with exactly the requested errors.

    TTP channels cycle 2,3,4,5 (H,V,+,-). Matched-basis states get ``n_errors_by_state[ch]``
    errors (client bit == TTP bit, since the source is |Psi^->); all other rows are correct
    (anticorrelated) or, for mismatched basis, random. Every pair is in the same 3-ns bin.
    """
    rng = np.random.default_rng(seed)
    gaps = rng.exponential(1e9 / rate_hz, size=n) + 10.0
    t = np.cumsum(gaps) + 1e9
    t = (np.rint(t / bin_ns)) * bin_ns  # bin centres, so jitter < bin/2 keeps pairs in-bin
    ttp_ch = np.tile(np.array([2, 3, 4, 5], np.uint8), n // 4 + 1)[:n]
    bit = {2: 0, 3: 1, 4: 0, 5: 1}
    matched = {"Z": (2, 3), "X": (4, 5)}[client_basis]
    cbit = np.array([1 - bit[int(c)] for c in ttp_ch], np.uint8)
    for ch, k in n_errors_by_state.items():
        assert ch in matched
        idx = np.flatnonzero(ttp_ch == ch)[:k]
        cbit[idx] = bit[ch]
    mism = ~np.isin(ttp_ch, matched)
    cbit[mism] = rng.integers(0, 2, size=int(mism.sum()))
    client_ch = np.where(cbit == 0, 2, 4).astype(np.uint8)
    dt = rng.uniform(-jitter_ns, jitter_ns, size=n)
    return ttp_ch, t, client_ch, t + dt


def tsv_bytes(ch: np.ndarray, t: np.ndarray, extra_lines: list[str] | None = None) -> bytes:
    buf = io.StringIO()
    buf.write("channel\ttag\n")
    for c, x in zip(ch, t, strict=True):
        buf.write(f"{int(c)}\t{x:.7f}\n")
    for ln in extra_lines or []:
        buf.write(ln)
    return buf.getvalue().encode("ascii")


def write_archive(path: Path, runs: dict[tuple[str, int], tuple]) -> Path:
    """runs: {(folder, chunk): (ttp_ch, ttp_t, client_ch, client_t)} -> deterministic ZIP."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(zipfile.ZipInfo("README", date_time=(2023, 5, 28, 0, 0, 0)), SYNTHETIC_TAG)
        for (folder, chunk), (tc, tt, cc, ct) in sorted(runs.items()):
            for side, ch, t in (("ttp", tc, tt), ("client", cc, ct)):
                info = zipfile.ZipInfo(f"{folder}/{side}_chunk{chunk:02d}.tsv", date_time=(2023, 5, 28, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(info, tsv_bytes(ch, t))
    return path


def standard_archive(path: Path) -> Path:
    """Two runs per basis, known errors: Z runs 1+2 / 2+3 errors, X runs 4+0 / 1+1 errors."""
    spec = {
        ("linear", 0): dict(client_basis="Z", n_errors_by_state={2: 1, 3: 2}, seed=1),
        ("linear", 1): dict(client_basis="Z", n_errors_by_state={2: 2, 3: 3}, seed=2),
        ("diagonal", 0): dict(client_basis="X", n_errors_by_state={4: 4, 5: 0}, seed=3),
        ("diagonal", 1): dict(client_basis="X", n_errors_by_state={4: 1, 5: 1}, seed=4),
    }
    return write_archive(path, {k: synth_pairs(400, **v) for k, v in spec.items()})
