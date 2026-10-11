"""Uncertainty for count ratios: exact binomial, time-block bootstrap, contiguous splits.

Clopper-Pearson assumes i.i.d. Bernoulli trials. Photon-counting runs are not guaranteed
i.i.d. (alignment drift, run-to-run differences), so we always report a time-block
bootstrap alongside it, and a heterogeneity test across contiguous blocks. The *reported*
interval in a CalibrationRecord is the wider of the two (conservative), never the narrower.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats


def clopper_pearson(k: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Exact two-sided binomial CI for k successes in n trials."""
    if n <= 0 or not (0 <= k <= n):
        raise ValueError("need 0 <= k <= n and n > 0")
    a = 1.0 - confidence
    lo = 0.0 if k == 0 else float(stats.beta.ppf(a / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(stats.beta.ppf(1 - a / 2, k + 1, n - k))
    return lo, hi


def block_bootstrap_ratio(
    k_blocks: np.ndarray,
    n_blocks: np.ndarray,
    *,
    confidence: float = 0.95,
    n_boot: int = 4000,
    seed: int = 0,
) -> tuple[float, float, float]:
    """Percentile CI for sum(k)/sum(n), resampling whole time blocks with replacement.

    Returns (point, lo, hi). Deterministic for a given seed.
    """
    k = np.asarray(k_blocks, np.float64)
    n = np.asarray(n_blocks, np.float64)
    if k.shape != n.shape or k.ndim != 1 or k.size < 2:
        raise ValueError("need >= 2 blocks of matching shape")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, k.size, size=(n_boot, k.size))
    ks, ns = k[idx].sum(axis=1), n[idx].sum(axis=1)
    r = ks / np.where(ns > 0, ns, np.nan)
    a = 1.0 - confidence
    lo, hi = np.nanquantile(r, [a / 2, 1 - a / 2])
    return float(k.sum() / n.sum()), float(lo), float(hi)


@dataclass(frozen=True)
class Heterogeneity:
    chi2: float
    dof: int
    p_value: float
    dispersion: float  # chi2/dof; ~1 for homogeneous binomial blocks


def heterogeneity(k_blocks: np.ndarray, n_blocks: np.ndarray) -> Heterogeneity:
    """Pearson chi-square test that all blocks share one error probability."""
    k = np.asarray(k_blocks, np.float64)
    n = np.asarray(n_blocks, np.float64)
    m = n > 0
    k, n = k[m], n[m]
    p = k.sum() / n.sum()
    var = n * p * (1 - p)
    chi2 = float(np.sum((k - n * p) ** 2 / np.where(var > 0, var, np.nan)))
    dof = int(k.size - 1)
    return Heterogeneity(chi2, dof, float(stats.chi2.sf(chi2, dof)), chi2 / dof if dof else float("nan"))


def contiguous_split(n_items: int, calibration_fraction: float = 0.5) -> tuple[slice, slice]:
    """Time-contiguous calibration/holdout split over ordered blocks (no shuffling)."""
    if not 0 < calibration_fraction < 1 or n_items < 2:
        raise ValueError("need 0<fraction<1 and >= 2 blocks")
    cut = min(max(int(round(n_items * calibration_fraction)), 1), n_items - 1)
    return slice(0, cut), slice(cut, n_items)


def two_proportion_z(k1: int, n1: int, k2: int, n2: int) -> tuple[float, float]:
    """Two-sided pooled z-test for p1 == p2. Returns (z, p_value)."""
    p = (k1 + k2) / (n1 + n2)
    se = np.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    z = (k1 / n1 - k2 / n2) / se if se > 0 else 0.0
    return float(z), float(2 * stats.norm.sf(abs(z)))


def welch_t(a: np.ndarray, b: np.ndarray) -> tuple[float | None, float | None]:
    """Two-sided Welch t-test on per-run rates (the run is the unit when runs are overdispersed).

    Returns (t, p_value), or (None, None) when either group has fewer than 2 runs or no variance
    (undefined -- never reported as 'no difference').
    """
    a, b = np.asarray(a, np.float64), np.asarray(b, np.float64)
    if a.size < 2 or b.size < 2 or (np.var(a) == 0 and np.var(b) == 0):
        return None, None
    res = stats.ttest_ind(a, b, equal_var=False)
    return float(res.statistic), float(res.pvalue)
