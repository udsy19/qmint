"""Coincidence matching / offset / drift tests on SYNTHETIC streams with known truth."""

from __future__ import annotations

import numpy as np
import pytest

from qmint.photonics.coincidences import (
    align_streams,
    coarse_offset_by_rate,
    estimate_drift,
    estimate_offset,
    match_bins,
    match_window,
)


def test_known_coincidences_bins():
    ta = np.array([0.0, 30.0, 60.0, 90.0])
    tb = np.array([0.4, 31.0, 75.0, 89.2])  # 3rd is 15 ns away -> not a coincidence
    m = match_bins(ta, tb, 3.0)
    assert m.ia.tolist() == [0, 1, 3] and m.ib.tolist() == [0, 1, 3]
    np.testing.assert_allclose(m.dt, [0.4, 1.0, -0.8])


def test_no_double_counting_window():
    # one B event equidistant-ish between two A events: must be used once
    ta = np.array([10.0, 12.0])
    tb = np.array([11.0])
    m = match_window(ta, tb, 1.5)
    assert len(m) == 1
    assert m.ia.tolist() == [0]  # |dt| tie (1.0 vs 1.0) -> smaller A index wins (deterministic)
    # two B events near one A: only the closer is used
    m2 = match_window(np.array([10.0]), np.array([9.0, 10.2]), 1.5)
    assert m2.ib.tolist() == [1]
    assert len(set(m2.ia.tolist())) == len(m2)


def test_no_double_counting_bins_multi_occupancy():
    ta = np.array([0.0, 0.5, 30.0])  # two A events in bin 0 -> bin excluded
    tb = np.array([0.2, 30.1])
    m = match_bins(ta, tb, 3.0)
    assert m.ia.tolist() == [2] and m.n_multi_a == 2 and m.n_multi_b == 0


def test_boundary_ties_bins_half_to_even():
    # t/3 = 0.5 rounds to 0 (even); t/3 = 1.5 rounds to 2 (even)
    ta = np.array([0.0, 6.0])
    tb = np.array([1.5, 4.5])
    m = match_bins(ta, tb, 3.0)
    assert m.ia.tolist() == [0, 1] and m.ib.tolist() == [0, 1]
    # the same 3.0-ns separation on the other side of an odd bin does NOT coincide
    m2 = match_bins(np.array([3.0]), np.array([4.5]), 3.0)  # rint(1.0)=1 vs rint(1.5)=2
    assert len(m2) == 0


def test_boundary_ties_window_closed_vs_open():
    ta, tb = np.array([0.0]), np.array([1.5])
    assert len(match_window(ta, tb, 1.5, closed="both")) == 1
    assert len(match_window(ta, tb, 1.5, closed="open")) == 0


def test_offset_applied_and_unsorted_rejected():
    ta = np.arange(0, 1e6, 1e3)
    tb = ta + 500.0
    assert len(match_bins(ta, tb, 3.0, offset_ns=500.0)) == ta.size
    assert len(match_bins(ta, tb, 3.0)) == 0
    with pytest.raises(ValueError):
        match_bins(ta[::-1], tb, 3.0)


def _streams(seed=0, n=40000, offset=12345.6, slope=3e-9, rate_a=2e5, eff=0.3, jitter=0.3, bg_rate=5e4):
    rng = np.random.default_rng(seed)
    ta = np.cumsum(rng.exponential(1e9 / rate_a, n))
    keep = rng.random(n) < eff
    tbt = ta[keep] + offset + slope * ta[keep] + rng.normal(0, jitter, keep.sum())
    bg = rng.uniform(ta[0], ta[-1] + offset, int(bg_rate * (ta[-1] - ta[0]) / 1e9))
    tb = np.sort(np.concatenate([tbt, bg]))
    return ta, tb, int(keep.sum())


def test_offset_estimation_recovers_injected_offset():
    ta, tb, _ = _streams(slope=0.0)
    e = estimate_offset(ta[:5000], tb, 12000, 12700, 0.5)
    assert abs(e.offset_ns - 12345.6) < 0.5
    assert e.peak_counts > 20 * max(e.background_per_bin, 1)


def test_coarse_offset_by_rate():
    rng = np.random.default_rng(3)
    # modulated rate so the cross-correlation has structure
    t = np.sort(rng.uniform(0, 2e9, 200000))
    t = t[(np.sin(t / 3e7) > -0.2) | (rng.random(t.size) < 0.2)]
    tb = np.sort(t[rng.random(t.size) < 0.5] + 4.0e8)
    c = coarse_offset_by_rate(t, tb, 1e6, 1e9)
    assert abs(c - 4.0e8) <= 1e6


def test_drift_estimation_recovers_slope():
    ta, tb, _ = _streams(slope=2e-9, n=60000)  # 2 ns/s
    m = match_window(ta, tb, 30.0, offset_ns=12345.6)
    d = estimate_drift(m, ta, block_ns=2e7)
    assert abs(d.ns_per_s - 2.0) < 0.3


def test_align_streams_end_to_end():
    rng = np.random.default_rng(5)
    n = 2_000_000
    ta = np.cumsum(rng.exponential(1e9 / 2e5, n))  # ~10 s at 200 kHz
    ta = ta[(ta < 2e9) & (rng.random(n) < 0.05) | (ta >= 2e9)]  # "shutter" closed for first 2 s
    keep = rng.random(ta.size) < 0.2
    offset, slope = -3.21e8, -3e-9
    tbt = ta[keep] + offset + slope * (ta[keep] - ta[0]) + rng.normal(0, 0.3, keep.sum())
    tb = np.sort(tbt)
    al = align_streams(ta, tb, max_lag_ns=1e9, coarse_bin_ns=1e6)
    assert abs(al.slope * 1e9 - (-3.0)) < 0.2
    m = match_bins(ta, al.to_a_frame(tb), 3.0)
    assert len(m) > 0.9 * keep.sum()
