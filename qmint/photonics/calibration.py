"""QBER / basis-split calibration from the archived Schiansky et al. 2023 coincidence pairs.

Denominators (explicit, per basis B in {Z (folder linear), X (folder diagonal)}):
  * n_pairs      -- all archived coincidence pairs in folder B (TTP measured either basis);
  * n_sifted     -- pairs where the TTP's passive basis equals the Client's basis B;
  * n_errors     -- sifted pairs with client_bit == ttp_bit (|Psi^-> is anticorrelated);
  * QBER_B       = n_errors / n_sifted   (NOT / n_pairs);
  * ttp_Z_frac_B = (#pairs with TTP in Z) / n_pairs  -- passive-beamsplitter basis split,
    conditioned on a coincidence (includes TTP detector-efficiency differences).

Not observable from this archive (coincidence-filtered timetags only, no singles, no pump
or generation counts): detection efficiency, channel loss, multiphoton probability. Those
fields stay ``None`` -- never imputed. The paper's own estimates are kept separately as
PUBLISHED_AGGREGATE (see :data:`PUBLISHED_2023`).

Scope guard: records are tagged ``experiment_family="schiansky_2023"``. They describe the
2023 entangled-source 641 m link and must not be consumed by S-money (Kent et al. 2022)
proofs; :func:`check_consumer` enforces this.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from qmint.core.contracts import Basis, CalibrationRecord, EvidenceKind, Interval, Unit
from qmint.photonics.channels import SCHIANSKY_2023_V1, ChannelMapping, detect_channel_swap
from qmint.photonics.coincidences import Matches, estimate_drift, match_bins
from qmint.photonics.confidence import (
    block_bootstrap_ratio,
    clopper_pearson,
    contiguous_split,
    heterogeneity,
    two_proportion_z,
)
from qmint.photonics.parser import MemberKey, TagBlock, archive_members, open_archive, read_tsv_member

EXPERIMENT_FAMILY = "schiansky_2023"
COMPATIBLE_PROTOCOLS = frozenset({"schiansky_payment_2023"})
_Z95 = 1.959963984540054
ARCHIVE_BIN_NS = 3.0  # Zenodo record: "coincidence count events in a 3ns window"

# Paper numbers, transcribed from https://www.nature.com/articles/s41467-023-39519-w
# ("Experimental demonstration" text and Fig. 4a caption). Correction 10.1038/s41467-023-40866-x
# changes only Discussion para 4 sentence 6 (no numbers).
PUBLISHED_2023 = {
    "qber_Z_percent": {"value": 1.45, "pm": 0.01, "anchor": "Results, Experimental demonstration: "
                       "'average measured error rate is 1.45 +/- 0.01% for H/V'"},
    "qber_X_percent": {"value": 3.28, "pm": 0.01, "anchor": "same sentence: '3.28 +/- 0.01% for D/A'; "
                       "Fig. 4a caption e_m = 0.0328 +/- 0.0001"},
    "loss_percent": {"value": 22.40, "pm": 1.50, "anchor": "Results text 22.40 +/- 1.50%; Fig. 4a caption "
                     "l_m = 0.2239 +/- 0.0150 (text/caption differ in last digit)"},
    "multiphoton_percent": {"value": 6.76, "pm": 0.12, "anchor": "Results text, correlation measurement"},
    "g2_heralded_0": {"value": 0.03010, "pm": 0.00014, "anchor": "Methods, heralded g2, 2.96 ns window"},
    "fiber_m": {"value": 641, "pm": None, "anchor": "Abstract / Fig. 3"},
    "error_bar_method": "Poisson errors on coincidence counts (Fig. 4a caption)",
}


class InapplicableCalibration(ValueError):
    """Calibration consumed by a protocol whose proof model it does not describe."""


def check_consumer(record: CalibrationRecord, protocol_id: str) -> None:
    if record.experiment_family != EXPERIMENT_FAMILY or protocol_id not in COMPATIBLE_PROTOCOLS:
        raise InapplicableCalibration(
            f"calibration family {record.experiment_family!r} is not applicable to {protocol_id!r}; "
            f"allowed: {sorted(COMPATIBLE_PROTOCOLS)}"
        )


@dataclass
class RunResult:
    folder: str
    chunk: int
    basis: Basis
    n_pairs: int
    table: np.ndarray  # [ttp ch 2,3,4,5] x [client bit 0,1]
    n_sifted: int
    n_errors: int
    n_ttp_z: int
    pairing_violations: int  # archived row pairs not in the same 3-ns bin
    rematch_identical: bool  # independent match_bins on the two streams reproduces row pairing
    decode_status: dict[str, int]
    block_sifted: np.ndarray  # per 1-s contiguous block
    block_errors: np.ndarray
    block_dt_median: np.ndarray
    drift_ns_per_s: float  # residual offset slope after the authors' correction (median dt per block)
    drift_ns_per_s_se: float
    dt_quantiles: dict[str, float] = field(default_factory=dict)
    t_first_ns: float = 0.0
    t_last_ns: float = 0.0


def analyze_run(
    ttp: TagBlock,
    client: TagBlock,
    folder: str,
    chunk: int,
    mapping: ChannelMapping = SCHIANSKY_2023_V1,
    *,
    bin_ns: float = ARCHIVE_BIN_NS,
    block_ns: float = 1e9,
) -> RunResult:
    status = {k: ttp.status_counts()[k] + client.status_counts()[k] for k in ttp.status_counts()}
    if len(ttp) != len(client):
        raise ValueError(f"{folder}/{chunk}: ttp/client row counts differ ({len(ttp)} vs {len(client)})")
    good = (ttp.status == 0) & (client.status == 0)
    tc, tt = ttp.channel[good], ttp.t_ns[good]
    cc, ct = client.channel[good], client.t_ns[good]
    basis = mapping.client_basis_by_folder[folder]
    is_z, tbit = mapping.ttp_arrays(tc)
    cbit = mapping.client_bits(cc)
    ttp_basis_matches = is_z if basis == Basis.Z else ~is_z
    err = ttp_basis_matches & (cbit == tbit) if mapping.anticorrelated else ttp_basis_matches & (cbit != tbit)
    n_sifted, n_err = int(ttp_basis_matches.sum()), int(err.sum())
    detect_channel_swap(n_err, n_sifted)
    table = np.zeros((4, 2), np.int64)
    np.add.at(table, (tc.astype(np.int64) - 2, cbit.astype(np.int64)), 1)
    pairing_violations = int(np.sum(np.rint(tt / bin_ns) != np.rint(ct / bin_ns)))
    m = match_bins(tt, ct, bin_ns)
    rematch_identical = bool(len(m) == tt.size and np.array_equal(m.ia, m.ib))
    blk = ((tt - tt[0]) // block_ns).astype(np.int64)
    nblk = int(blk.max()) + 1
    b_s = np.bincount(blk, weights=ttp_basis_matches, minlength=nblk).astype(np.int64)
    b_e = np.bincount(blk, weights=err, minlength=nblk).astype(np.int64)
    dt = ct - tt
    idx = np.arange(tt.size)
    drift = estimate_drift(Matches(idx, idx, dt), tt, block_ns)
    b_med = np.full(nblk, np.nan)
    b_med[((drift.block_t_ns - tt[0]) // block_ns).astype(np.int64)] = drift.block_offset_ns
    q = np.quantile(dt, [0.0, 0.001, 0.5, 0.999, 1.0])
    return RunResult(
        folder=folder,
        chunk=chunk,
        basis=basis,
        n_pairs=int(tt.size),
        table=table,
        n_sifted=n_sifted,
        n_errors=n_err,
        n_ttp_z=int(is_z.sum()),
        pairing_violations=pairing_violations,
        rematch_identical=rematch_identical,
        decode_status=status,
        block_sifted=b_s,
        block_errors=b_e,
        block_dt_median=b_med,
        drift_ns_per_s=drift.ns_per_s,
        drift_ns_per_s_se=drift.slope_se * 1e9,
        dt_quantiles=dict(zip(["min", "q0.001", "median", "q0.999", "max"], map(float, q), strict=True)),
        t_first_ns=float(tt[0]),
        t_last_ns=float(tt[-1]),
    )


def analyze_archive(path: str | Path, mapping: ChannelMapping = SCHIANSKY_2023_V1) -> list[RunResult]:
    """Stream every (folder, chunk) pair of the archive; returns runs in (folder, chunk) order."""
    zf = open_archive(path)
    members = archive_members(zf)
    runs = []
    for key in sorted({(k.basis_folder, k.chunk) for k in members}):
        folder, chunk = key
        tm = members.get(MemberKey(folder, "ttp", chunk))
        cm = members.get(MemberKey(folder, "client", chunk))
        if tm is None or cm is None:
            raise ValueError(f"unpaired chunk {folder}/{chunk}")
        ttp = read_tsv_member(zf, tm, allowed_channels=mapping.ttp_channels)
        cli = read_tsv_member(zf, cm, allowed_channels=mapping.client_channels)
        runs.append(analyze_run(ttp, cli, folder, chunk, mapping))
    return runs


@dataclass
class BasisSummary:
    basis: Basis
    n_runs: int
    n_pairs: int
    n_sifted: int
    n_errors: int
    n_ttp_z: int
    qber: float
    qber_mean_of_runs: float
    qber_state_avg: float  # paper's estimator: mean over the 2 TTP states of P(error | state)
    qber_state_avg_se: float  # binomial SE of that mean
    error_given_state: dict[str, float]
    qber_cp: tuple[float, float]
    qber_boot_blocks: tuple[float, float]
    qber_boot_runs: tuple[float, float]
    ttp_z_frac: float
    ttp_z_frac_cp: tuple[float, float]
    ttp_z_frac_boot_runs: tuple[float, float]
    het_runs: dict[str, float]
    het_blocks: dict[str, float]
    split: dict[str, float]
    per_run_qber: list[float]


def summarize(runs: list[RunResult], basis: Basis, *, confidence: float = 0.95, seed: int = 0) -> BasisSummary:
    rs = [r for r in runs if r.basis == basis]
    k_runs = np.array([r.n_errors for r in rs])
    n_runs = np.array([r.n_sifted for r in rs])
    kb = np.concatenate([r.block_errors for r in rs])
    nb = np.concatenate([r.block_sifted for r in rs])
    k, n = int(k_runs.sum()), int(n_runs.sum())
    npairs = int(sum(r.n_pairs for r in rs))
    nz = int(sum(r.n_ttp_z for r in rs))
    _, blo, bhi = block_bootstrap_ratio(kb, nb, confidence=confidence, seed=seed)
    _, rlo, rhi = block_bootstrap_ratio(k_runs, n_runs, confidence=confidence, seed=seed)
    z_runs = np.array([r.n_ttp_z for r in rs])
    p_runs = np.array([r.n_pairs for r in rs])
    _, zlo, zhi = block_bootstrap_ratio(z_runs, p_runs, confidence=confidence, seed=seed)
    hr, hb = heterogeneity(k_runs, n_runs), heterogeneity(kb, nb)
    table = sum(r.table for r in rs)
    rows = (0, 1) if basis == Basis.Z else (2, 3)
    labels = ("H", "V") if basis == Basis.Z else ("+", "-")
    egs, var = {}, 0.0
    for lab, row, bit in zip(labels, rows, (0, 1), strict=True):
        tot = int(table[row].sum())
        p = table[row, bit] / tot  # anticorrelated: error iff client bit == TTP bit
        egs[lab] = float(p)
        var += p * (1 - p) / tot
    cal, hold = contiguous_split(len(rs), 0.5)
    k1, n1 = int(k_runs[cal].sum()), int(n_runs[cal].sum())
    k2, n2 = int(k_runs[hold].sum()), int(n_runs[hold].sum())
    z, pz = two_proportion_z(k1, n1, k2, n2)
    c_lo, c_hi = clopper_pearson(k1, n1, confidence)
    return BasisSummary(
        basis=basis,
        n_runs=len(rs),
        n_pairs=npairs,
        n_sifted=n,
        n_errors=k,
        n_ttp_z=nz,
        qber=k / n,
        qber_mean_of_runs=float(np.mean(k_runs / n_runs)),
        qber_state_avg=float(np.mean(list(egs.values()))),
        qber_state_avg_se=float(np.sqrt(var) / 2),
        error_given_state=egs,
        qber_cp=clopper_pearson(k, n, confidence),
        qber_boot_blocks=(blo, bhi),
        qber_boot_runs=(rlo, rhi),
        ttp_z_frac=nz / npairs,
        ttp_z_frac_cp=clopper_pearson(nz, npairs, confidence),
        ttp_z_frac_boot_runs=(zlo, zhi),
        het_runs={"chi2": hr.chi2, "dof": hr.dof, "p_value": hr.p_value, "dispersion": hr.dispersion},
        het_blocks={"chi2": hb.chi2, "dof": hb.dof, "p_value": hb.p_value, "dispersion": hb.dispersion},
        split={
            "calibration_runs": f"{rs[cal.start].chunk}-{rs[cal.stop - 1].chunk}",
            "holdout_runs": f"{rs[hold.start].chunk}-{rs[hold.stop - 1].chunk}",
            "qber_calibration": k1 / n1,
            "qber_calibration_cp_lo": c_lo,
            "qber_calibration_cp_hi": c_hi,
            "qber_holdout": k2 / n2,
            "holdout_inside_calibration_cp": float(c_lo <= k2 / n2 <= c_hi),
            "z": z,
            "p_value": pz,
        },
        per_run_qber=[float(x) for x in k_runs / n_runs],
    )


def _hull(point: float, *ivs: tuple[float, float]) -> Interval:
    lo = min(i[0] for i in ivs)
    hi = max(i[1] for i in ivs)
    return Interval(lo=lo, hi=hi, unit=Unit.FRACTION, point=point)


def calibration_record(
    s: BasisSummary,
    *,
    dataset_sha256: str,
    dataset_tag: str,
    runs: list[RunResult],
    confidence: float = 0.95,
) -> CalibrationRecord:
    rs = [r for r in runs if r.basis == s.basis]
    return CalibrationRecord(
        calibration_id=f"schiansky2023-{dataset_tag}-{s.basis.value}-v1",
        device_id="schiansky2023_ttp_client_641m_fiber",
        experiment_family=EXPERIMENT_FAMILY,
        data_origin=EvidenceKind.PHOTON_EXPERIMENT,
        dataset_sha256=dataset_sha256,
        time_start_ns=min(r.t_first_ns for r in rs),
        time_end_ns=max(r.t_last_ns for r in rs),
        n_events=s.n_pairs,
        qber_interval=_hull(
            s.qber,
            s.qber_cp,
            s.qber_boot_blocks,
            s.qber_boot_runs,
            (s.qber_state_avg - _Z95 * s.qber_state_avg_se, s.qber_state_avg + _Z95 * s.qber_state_avg_se),
        ),
        basis_bias_interval=_hull(s.ttp_z_frac, s.ttp_z_frac_cp, s.ttp_z_frac_boot_runs),
        detection_efficiency_interval=None,
        loss_interval=None,
        multiphoton_interval=None,
        clock_drift_interval=None,
        confidence_level=confidence,
        interval_method=(
            "hull(clopper_pearson pooled, time_block_bootstrap 1s blocks, run_bootstrap 11 runs "
            "[B=4000 seed=0 percentile], paper state-averaged estimator +/-1.96 SE); point = pooled "
            "errors/sifted; qber denominator = basis-matched (sifted) coincidences; "
            "basis_bias = fraction of coincidences with TTP passive basis Z"
        ),
        independence_assumptions=[
            f"client basis fixed per folder ({rs[0].folder}); TTP basis passive 50/50 beamsplitter",
            "coincidences = archived pairs (authors' 3-ns rounded-bin rule, after authors' offset/drift correction)",
            "runs (chunk files) assumed to be in acquisition order; absolute times not in archive",
            "clopper_pearson assumes iid trials; bootstrap assumes exchangeable 1-s blocks / runs",
            "times are relative per run (each run starts near zero); time_start/end span runs",
        ],
    )


def published_aggregate_record() -> CalibrationRecord:
    """The paper's own loss/multiphoton/QBER estimates, tagged PUBLISHED_AGGREGATE (not re-derived)."""
    P = PUBLISHED_2023

    def iv(key: str) -> Interval:
        v, pm = P[key]["value"] / 100, P[key]["pm"] / 100
        return Interval(lo=v - pm, hi=v + pm, unit=Unit.FRACTION, point=v)

    return CalibrationRecord(
        calibration_id="schiansky2023-published-aggregate-v1",
        device_id="schiansky2023_ttp_client_641m_fiber",
        experiment_family=EXPERIMENT_FAMILY,
        data_origin=EvidenceKind.PUBLISHED_AGGREGATE,
        n_events=0,
        qber_interval=iv("qber_X_percent"),
        loss_interval=iv("loss_percent"),
        multiphoton_interval=iv("multiphoton_percent"),
        confidence_level=0.6827,
        interval_method="paper-quoted +/- (Poisson, ~1 sigma); transcribed, not re-derived; qber = max basis (D/A)",
        independence_assumptions=["as stated by the authors; see PUBLISHED_2023 anchors"],
    )
