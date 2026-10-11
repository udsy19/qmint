"""Two-party coincidence matching, offset and drift estimation (independent implementation).

Convention: ``ta`` = TTP (station A) times, ``tb`` = Client (station B) times, both sorted, in
ns. ``offset_ns`` is defined by ``tb ~= ta + offset_ns``; residual ``dt = tb - ta - offset_ns``.

Two matching rules are provided, both strictly one-to-one (no event is counted twice):

* :func:`match_bins` -- the rule used by the authors' published code (Zenodo 8020667,
  ``03_a_coinc1_bb84.py``: ``np.around(t/coincidence_time)`` equality). A pair coincides iff
  both events fall in the same rounded bin of width ``bin_ns``. Rounding is half-to-even
  (``np.rint``, identical to ``np.around``), so a time exactly on a bin edge ``(k+1/2)*bin``
  goes to the even bin -- this is the boundary-tie rule. Bins occupied by more than one event
  on either side are *excluded* (reported as multi-occupancy) instead of resolved randomly
  (the authors' code keeps a random one on the Client side; we refuse hidden resampling).
  All 8,964,878 archived pairs satisfy ``rint(t/3) `` equality (verified), i.e. the archive's
  "3 ns window" is this 3-ns bin rule, not ``|dt| <= 3 ns``.
* :func:`match_window` -- symmetric sliding window ``|dt| <= half_width`` (or ``<`` with
  ``closed="open"``), resolved greedily by increasing ``|dt|`` with deterministic
  (index-based) tie-breaking.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np


@dataclass(frozen=True)
class Matches:
    ia: np.ndarray  # int64 indices into ta
    ib: np.ndarray  # int64 indices into tb
    dt: np.ndarray  # tb[ib] - ta[ia] - offset_ns
    n_multi_a: int = 0  # events excluded because their bin held >1 A event (bin rule only)
    n_multi_b: int = 0

    def __len__(self) -> int:
        return int(self.ia.shape[0])


def _check_sorted(t: np.ndarray, name: str) -> None:
    if t.ndim != 1:
        raise ValueError(f"{name} must be 1-D")
    if t.size > 1 and np.any(np.diff(t) < 0):
        raise ValueError(f"{name} must be sorted ascending")
    if not np.all(np.isfinite(t)):
        raise ValueError(f"{name} contains non-finite times")


def match_bins(ta: np.ndarray, tb: np.ndarray, bin_ns: float, offset_ns: float = 0.0) -> Matches:
    """One-to-one coincidences by rounded-bin equality (authors' rule); see module docstring."""
    ta = np.asarray(ta, np.float64)
    tb = np.asarray(tb, np.float64)
    _check_sorted(ta, "ta")
    _check_sorted(tb, "tb")
    if bin_ns <= 0:
        raise ValueError("bin_ns must be > 0")
    ba = np.rint(ta / bin_ns).astype(np.int64)
    bb = np.rint((tb - offset_ns) / bin_ns).astype(np.int64)

    def singles(b: np.ndarray) -> tuple[np.ndarray, int]:
        u, inv, cnt = np.unique(b, return_inverse=True, return_counts=True)
        keep = cnt[inv] == 1
        return keep, int(np.sum(~keep))

    ka, na = singles(ba)
    kb, nb = singles(bb)
    ia_all = np.flatnonzero(ka)
    ib_all = np.flatnonzero(kb)
    _, xa, xb = np.intersect1d(ba[ia_all], bb[ib_all], assume_unique=True, return_indices=True)
    ia, ib = ia_all[xa], ib_all[xb]
    order = np.argsort(ia, kind="stable")
    ia, ib = ia[order], ib[order]
    return Matches(ia, ib, tb[ib] - ta[ia] - offset_ns, na, nb)


def match_window(
    ta: np.ndarray,
    tb: np.ndarray,
    half_width_ns: float,
    offset_ns: float = 0.0,
    closed: Literal["both", "open"] = "both",
) -> Matches:
    """One-to-one sliding-window coincidences, greedy by smallest ``|dt|``.

    Ties in ``|dt|`` are broken by smaller A index, then smaller B index (deterministic).
    ``closed="both"`` accepts ``|dt| == half_width``; ``"open"`` rejects it.
    """
    ta = np.asarray(ta, np.float64)
    tb = np.asarray(tb, np.float64)
    _check_sorted(ta, "ta")
    _check_sorted(tb, "tb")
    if half_width_ns < 0:
        raise ValueError("half_width_ns must be >= 0")
    tbs = tb - offset_ns
    side_lo, side_hi = ("left", "right") if closed == "both" else ("right", "left")
    lo = np.searchsorted(tbs, ta - half_width_ns, side=side_lo)
    hi = np.searchsorted(tbs, ta + half_width_ns, side=side_hi)
    cnt = np.maximum(hi - lo, 0)
    if cnt.sum() == 0:
        e = np.empty(0, np.int64)
        return Matches(e, e, np.empty(0))
    ca = np.repeat(np.arange(ta.size, dtype=np.int64), cnt)
    starts = np.repeat(lo - np.concatenate([[0], np.cumsum(cnt)[:-1]]), cnt)
    cb = starts + np.arange(ca.size, dtype=np.int64)
    d = tbs[cb] - ta[ca]
    order = np.lexsort((cb, ca, np.abs(d)))
    used_a = np.zeros(ta.size, bool)
    used_b = np.zeros(tb.size, bool)
    keep = np.zeros(order.size, bool)
    for j, k in enumerate(order):
        a, b = ca[k], cb[k]
        if not used_a[a] and not used_b[b]:
            used_a[a] = used_b[b] = True
            keep[j] = True
    sel = order[keep]
    sel = sel[np.argsort(ca[sel], kind="stable")]
    return Matches(ca[sel], cb[sel], d[sel])


@dataclass(frozen=True)
class OffsetEstimate:
    offset_ns: float  # peak location (centroid of peak bin +/- 1 bin)
    peak_counts: int
    background_per_bin: float  # median histogram level away from the peak
    bin_ns: float
    counts: np.ndarray
    edges: np.ndarray


def offset_histogram(
    ta: np.ndarray, tb: np.ndarray, lo_ns: float, hi_ns: float, bin_ns: float, max_pairs: int = 50_000_000
) -> tuple[np.ndarray, np.ndarray]:
    """Histogram of all ``tb - ta`` differences in ``[lo_ns, hi_ns)`` (pair enumeration, capped)."""
    ta = np.asarray(ta, np.float64)
    tb = np.asarray(tb, np.float64)
    a_lo = np.searchsorted(tb, ta + lo_ns, side="left")
    a_hi = np.searchsorted(tb, ta + hi_ns, side="left")
    cnt = a_hi - a_lo
    total = int(cnt.sum())
    if total > max_pairs:
        raise ValueError(f"{total} candidate pairs > max_pairs; narrow the search or subsample ta")
    nb = int(np.ceil((hi_ns - lo_ns) / bin_ns))
    edges = lo_ns + bin_ns * np.arange(nb + 1)
    if total == 0:
        return np.zeros(nb, np.int64), edges
    ca = np.repeat(np.arange(ta.size), cnt)
    starts = np.repeat(a_lo - np.concatenate([[0], np.cumsum(cnt)[:-1]]), cnt)
    cb = starts + np.arange(total)
    counts, _ = np.histogram(tb[cb] - ta[ca], bins=edges)
    return counts, edges


def estimate_offset(
    ta: np.ndarray, tb: np.ndarray, lo_ns: float, hi_ns: float, bin_ns: float, **kw
) -> OffsetEstimate:
    counts, edges = offset_histogram(ta, tb, lo_ns, hi_ns, bin_ns, **kw)
    if counts.sum() == 0:
        raise ValueError("no candidate pairs in search range")
    k = int(np.argmax(counts))
    s = slice(max(k - 1, 0), min(k + 2, counts.size))
    centers = 0.5 * (edges[:-1] + edges[1:])
    w = counts[s].astype(float)
    off = float(np.sum(centers[s] * w) / w.sum())
    away = np.ones(counts.size, bool)
    away[max(k - 5, 0) : k + 6] = False
    bg = float(np.median(counts[away])) if away.any() else 0.0
    return OffsetEstimate(off, int(counts[k]), bg, bin_ns, counts, edges)


def coarse_offset_by_rate(ta: np.ndarray, tb: np.ndarray, bin_ns: float, max_lag_ns: float) -> float:
    """Coarse offset from cross-correlating singles-rate time series (FFT), resolution ``bin_ns``."""
    t0 = min(ta[0], tb[0])
    t1 = max(ta[-1], tb[-1])
    n = int(np.ceil((t1 - t0) / bin_ns)) + 1
    ra = np.bincount(((ta - t0) // bin_ns).astype(np.int64), minlength=n).astype(float)
    rb = np.bincount(((tb - t0) // bin_ns).astype(np.int64), minlength=n).astype(float)
    ra -= ra.mean()
    rb -= rb.mean()
    m = 1 << int(np.ceil(np.log2(2 * n)))
    xc = np.fft.irfft(np.conj(np.fft.rfft(ra, m)) * np.fft.rfft(rb, m), m)
    lags = np.concatenate([np.arange(0, m // 2), np.arange(-m // 2, 0)])
    ok = np.abs(lags) * bin_ns <= max_lag_ns
    best = lags[ok][np.argmax(xc[ok])]
    return float(best * bin_ns)


@dataclass(frozen=True)
class DriftEstimate:
    slope: float  # dimensionless (ns of offset change per ns of elapsed A time); x1e9 = ns/s
    slope_se: float
    intercept_ns: float
    block_t_ns: np.ndarray  # block centres (A time)
    block_offset_ns: np.ndarray  # per-block median residual dt
    block_n: np.ndarray

    @property
    def ns_per_s(self) -> float:
        return self.slope * 1e9


def estimate_drift(matches: Matches, ta: np.ndarray, block_ns: float, min_pairs: int = 20) -> DriftEstimate:
    """Linear drift of the residual offset from matched pairs, per contiguous time block.

    Uses the median ``dt`` in each block (robust to accidental coincidences) and an OLS fit
    of median-dt vs block centre. The slope SE is the OLS SE; blocks are treated as
    independent, which is only approximate (documented in the calibration record).
    """
    t = np.asarray(ta, np.float64)[matches.ia]
    if t.size == 0:
        raise ValueError("no matches")
    blk = ((t - t[0]) // block_ns).astype(np.int64)
    centers, meds, ns = [], [], []
    for b in np.unique(blk):
        m = blk == b
        if m.sum() >= min_pairs:
            centers.append(t[0] + (b + 0.5) * block_ns)
            meds.append(float(np.median(matches.dt[m])))
            ns.append(int(m.sum()))
    x, y = np.asarray(centers), np.asarray(meds)
    if x.size < 3:
        return DriftEstimate(float("nan"), float("nan"), float(np.median(matches.dt)), x, y, np.asarray(ns))
    A = np.vstack([x - x.mean(), np.ones_like(x)]).T
    coef, res, *_ = np.linalg.lstsq(A, y, rcond=None)
    resid = y - A @ coef
    s2 = float(resid @ resid) / (x.size - 2)
    se = float(np.sqrt(s2 / np.sum((x - x.mean()) ** 2)))
    intercept = float(coef[1] - coef[0] * x.mean())
    return DriftEstimate(float(coef[0]), se, intercept, x, y, np.asarray(ns))


@dataclass(frozen=True)
class Alignment:
    """Linear clock model ``tb ~= ta + offset_ns + slope * (ta - t_ref_ns)``."""

    offset_ns: float  # at t_ref_ns
    slope: float  # dimensionless; * 1e9 = ns/s
    t_ref_ns: float
    coarse_offset_ns: float
    block_t_ns: np.ndarray
    block_offset_ns: np.ndarray
    residual_std_ns: float
    n_blocks_used: int

    def to_a_frame(self, tb: np.ndarray) -> np.ndarray:
        """Map B times into A's clock frame (inverse of the linear model)."""
        return (np.asarray(tb, np.float64) - self.offset_ns + self.slope * self.t_ref_ns) / (1.0 + self.slope)


def align_streams(
    ta: np.ndarray,
    tb: np.ndarray,
    *,
    max_lag_ns: float = 30e9,
    coarse_bin_ns: float = 1e6,
    block_every_ns: float = 1e9,
    slice_ns: float = 2e7,
    search_ns: float = 2e4,
    min_peak_to_background: float = 10.0,
) -> Alignment:
    """Coarse (singles-rate cross-correlation) -> per-block coincidence peak -> linear drift fit.

    Independent of, but structurally similar to, the authors' 02_a_off_clean5hv_alt.py
    (coarse/fine offset search then linear drift). Blocks whose peak is not at least
    ``min_peak_to_background`` x the flat background (e.g. while a shutter opens) are
    dropped -- they would otherwise dominate the fit.
    """
    ta = np.asarray(ta, np.float64)
    tb = np.asarray(tb, np.float64)
    coarse = coarse_offset_by_rate(ta, tb, coarse_bin_ns, max_lag_ns)
    xs, ys = [], []
    start = np.ceil(ta[0] / block_every_ns) * block_every_ns
    for s0 in np.arange(start, ta[-1] - slice_ns, block_every_ns):
        m = (ta >= s0) & (ta < s0 + slice_ns)
        if m.sum() < 10:
            continue
        guess = ys[-1] if ys else None
        if guess is None:  # first lock: search +/- 1.5 coarse bins on a short (2 ms) slice
            m0 = (ta >= s0) & (ta < s0 + 2e6)
            if m0.sum() < 10:
                continue
            try:
                e00 = estimate_offset(ta[m0], tb, coarse - 1.5 * coarse_bin_ns, coarse + 1.5 * coarse_bin_ns, 10.0)
            except ValueError:
                continue
            if e00.peak_counts < min_peak_to_background * max(e00.background_per_bin, 1.0):
                continue
            guess = e00.offset_ns
        try:
            e0 = estimate_offset(ta[m], tb, guess - search_ns, guess + search_ns, 5.0)
        except ValueError:
            continue
        if e0.peak_counts < min_peak_to_background * max(e0.background_per_bin, 1.0):
            continue
        e = estimate_offset(ta[m], tb, e0.offset_ns - 20.0, e0.offset_ns + 20.0, 0.25)
        xs.append(s0 + slice_ns / 2)
        ys.append(e.offset_ns)
    if len(xs) < 3:
        raise ValueError("fewer than 3 blocks with a significant coincidence peak")
    x, y = np.asarray(xs), np.asarray(ys)
    t_ref = float(x[0])
    k, b = np.polyfit(x - t_ref, y, 1)
    resid = y - (k * (x - t_ref) + b)
    return Alignment(float(b), float(k), t_ref, coarse, x, y, float(np.std(resid)), int(x.size))
