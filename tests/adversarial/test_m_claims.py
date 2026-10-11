"""Lane M claims audit: independent re-derivations (CLAIMS_AUDIT.md). No lane code is imported here
except where a lane's number is compared, so these are independent checks."""

from __future__ import annotations

import io
import math
import os
import zipfile
from pathlib import Path

import numpy as np
import pytest
from scipy import stats

# --------------------------------------------------------------- Schiansky 2023 SI Eq. (22)
W = 4 + 2 * math.sqrt(2)  # SI Eq. (18) error weight
PM, N, DELTA_D = 0.0602, 4.2e6, 0.01  # SI Table 2 / Fig. 4b
ALLOWED = 0.5 * (1 - PM / 2)  # 0.48495


def test_published_pd_formula_recomputes():
    assert math.exp(-(DELTA_D**2 / 2) * ALLOWED * N) == pytest.approx(5.911e-45, rel=1e-3)


def test_chernoff_on_weighted_mishaps_is_violated_by_an_iid_cheater():
    """M-S1: per-state mishap X = W * 1[error] (zero declared loss, mean = allowed mishaps) is iid and
    on the fitted boundary M(e, 0) = 1/2 (1 - p_m/2). Its exact lower tail exceeds the published
    Eq. (22) value by ~36 orders of magnitude, but respects the rescaled [0,1] Chernoff bound."""
    q = ALLOWED / W
    k_max = math.floor((1 - DELTA_D) * ALLOWED * N / W)
    exact = stats.binom.cdf(k_max, int(N), q)
    published = math.exp(-(DELTA_D**2 / 2) * ALLOWED * N)
    rescaled = math.exp(-(DELTA_D**2 / 2) * ALLOWED * N / W)
    assert exact > published * 1e30
    assert exact <= rescaled
    assert 1e-9 < exact < 1e-8  # 6.96e-9


def test_published_pd_uses_fig4b_n_not_si_table_n():
    p_table_n = math.exp(-(DELTA_D**2 / 2) * ALLOWED * 4_482_440)
    assert p_table_n == pytest.approx(6.27e-48, rel=1e-2)  # SI Table 2 N gives a SMALLER (stronger) value


# --------------------------------------------------------------- B/C correction of the work order
def test_measure_resend_both_copies_is_5_8_single_copy_is_3_4():
    kets = {("Z", 0): np.array([1, 0]), ("Z", 1): np.array([0, 1]),
            ("X", 0): np.array([1, 1]) / math.sqrt(2), ("X", 1): np.array([1, -1]) / math.sqrt(2)}
    both = single = 0.0
    for (b, x), psi in kets.items():
        for m in (0, 1):  # measure in Z, resend |m>|m>
            pm = abs(psi[m]) ** 2
            ok = abs(kets[(b, x)] @ kets[("Z", m)]) ** 2
            both += 0.25 * pm * ok**2
            single += 0.25 * pm * ok
    assert both == pytest.approx(5 / 8) and single == pytest.approx(3 / 4)


# --------------------------------------------------------------- Schiansky 2023 raw data (Zenodo 7979319)
CACHE = Path(os.environ.get("QMINT_DATA_CACHE", "/Users/udsy/PycharmProjects/qmint-data-cache"))
ARCHIVE = CACHE / "zenodo_7979319" / "Archive.zip"
# TTP channel -> client channel of the CORRECT outcome, inferred from the raw contingency table
# (the alternative assignment gives ~98.6 % errors).
MAP = {"linear": {2: 4, 3: 2}, "diagonal": {4: 4, 5: 2}}


@pytest.fixture(scope="module")
def runs():
    if not ARCHIVE.exists():
        pytest.skip(f"real dataset not in cache: {ARCHIVE}")
    import pandas as pd

    out: dict[str, list[dict[int, tuple[int, int]]]] = {}
    with zipfile.ZipFile(ARCHIVE) as z:
        for folder, m in MAP.items():
            out[folder] = []
            for i in range(11):
                t = pd.read_csv(io.BytesIO(z.read(f"{folder}/ttp_chunk{i:02d}.tsv")), sep="\t")
                c = pd.read_csv(io.BytesIO(z.read(f"{folder}/client_chunk{i:02d}.tsv")), sep="\t")
                assert len(t) == len(c)
                assert float(np.abs(t["tag"].to_numpy() - c["tag"].to_numpy()).max()) < 3.0  # 3-ns pairing
                tc, cc = t["channel"].to_numpy(), c["channel"].to_numpy()
                out[folder].append({ch: (int(np.sum(cc[tc == ch] != good)), int(np.sum(tc == ch))) for ch, good in m.items()})
    return out


@pytest.mark.realdata
@pytest.mark.parametrize(("folder", "published", "pooled_counts"), [
    ("linear", 0.014491, (31231, 2183822)), ("diagonal", 0.032787, (75417, 2294692))])
def test_qber_reproduced_independently(runs, folder, published, pooled_counts):
    per_state = {ch: tuple(sum(r[ch][j] for r in runs[folder]) for j in (0, 1)) for ch in MAP[folder]}
    state_avg = float(np.mean([e / n for e, n in per_state.values()]))
    assert round(state_avg, 6) == published
    assert (sum(e for e, _ in per_state.values()), sum(n for _, n in per_state.values())) == pooled_counts


@pytest.mark.realdata
@pytest.mark.parametrize("folder", ["linear", "diagonal"])
def test_lane_e_nonstationarity_is_overdispersion_not_drift(runs, folder):
    """M-E1: runs are overdispersed (chi2/dof ~10); the E1 split-half p=0.003 (diagonal, runs 0-5 vs 6-10)
    comes from a pooled binomial test. A run-level test does not reject stationarity."""
    k = np.array([sum(e for e, _ in r.values()) for r in runs[folder]])
    n = np.array([sum(m for _, m in r.values()) for r in runs[folder]])
    p = k.sum() / n.sum()
    assert np.sum((k - n * p) ** 2 / (n * p * (1 - p))) / (len(k) - 1) > 5
    for a, b in ((slice(0, 6), slice(6, 11)), (slice(0, 5), slice(6, 11))):
        assert stats.ttest_ind(k[a] / n[a], k[b] / n[b], equal_var=False).pvalue > 0.05
