"""GET /benchmarks -- quantum vs classical benchmark explorer backend.

Sources (all merged lanes, read from their committed evidence files; nothing is invented here):

* lane H -- ``reports/classical_baseline_notes/benchmark_records.jsonl`` (C6 ``BenchmarkRecord``,
  MODELLED_LATENCY on SYNTHETIC light-cone networks) and ``comparability_matrix.csv`` (X11:
  QUALIFIED / INCOMPARABLE per classical-vs-S1 pair with the concessions per column);
* lane G -- latency case studies: Jiang et al. 2024 modelled S-money timing vs the paper's
  published aggregate, and RIPE Atlas measured one-way delays (RTT/2 assumption flagged);
* lane E -- per-run QBER of the Schiansky 2023 Zenodo photon archive with Clopper-Pearson
  intervals, pooled calibration hulls and the paper's published values.

There is deliberately no single "better" score: every classical row carries the X11 pair status.
Matched-topology quantum runs (lane GH) are an explicit NOT_AVAILABLE slot until that lane merges.
"""

from __future__ import annotations

import csv
import json
import statistics
from functools import lru_cache
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from qmint.core.config import REPO_ROOT
from qmint.core.contracts import BenchmarkRecord, CalibrationRecord, EvidenceKind, Unit
from qmint.networks import ripe
from qmint.networks.s_money_sites import run_s_money
from qmint.networks.topology import JIANG2024_URL, TopologyCase, jiang2024_intercity, jiang2024_intracity
from qmint.photonics.calibration import PUBLISHED_2023, published_aggregate_record
from qmint.photonics.confidence import clopper_pearson

from ..common import provenance
from ..schemas import ConfidenceInterval, Envelope, Quantity

H_DIR = REPO_ROOT / "reports" / "classical_baseline_notes"
H_RECORDS = H_DIR / "benchmark_records.jsonl"
H_MATRIX = H_DIR / "comparability_matrix.csv"
E_DIR = REPO_ROOT / "reports" / "data_working" / "schiansky2023"
RIPE_SEEDS = range(20)
S1_PROTOCOL = "s_money_kent_2022_ideal_2site"
KENT2022_URL = "https://arxiv.org/abs/2104.11717"
SCHIANSKY_URL = "https://www.nature.com/articles/s41467-023-39519-w"

DoubleSpend = Literal["PREVENTED", "SUCCEEDS", "DETECTED_NOT_PREVENTED", "OUT_OF_MODEL", "BOUNDED_BY_THEOREM"]


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DoubleSpendOutcome(_M):
    outcome: DoubleSpend
    successful: int | None
    detail: str


class Concession(_M):
    column: str
    left: str
    right: str


class ComparabilityPair(_M):
    pair_id: str
    left_protocol: str
    right_protocol: str
    status: Literal["COMPARABLE", "QUALIFIED", "INCOMPARABLE"]
    columns: list[Concession]


class ProtocolRow(_M):
    id: str
    code: str
    label: str
    family: Literal["quantum", "classical"]
    protocol_id: str
    variant: str | None
    network_id: str | None
    site_count: int
    double_spend: DoubleSpendOutcome
    local_validation: Quantity | None
    cross_check: Quantity | None
    pre_presentation_commit: Quantity | None
    latency_unavailable_reason: str | None
    trust_model: str
    trusted_hardware: str
    adversary: str
    pre_distribution: str
    flexibility: str
    privacy: str
    issuer_calls: int | None
    classical_bytes: int | None
    comparability_pair: str | None
    comparability_status: Literal["COMPARABLE", "QUALIFIED", "INCOMPARABLE", "REFERENCE", "NO_PAIR"]
    evidence_kind: EvidenceKind
    method: str
    latency_basis: str | None
    record_git_sha: str | None
    environment_lock: str | None
    reproduce: str
    sources: list[str]


class LatencyCase(_M):
    id: str
    title: str
    kind: Literal["paper_topology", "measured_network"]
    protocol_id: str
    quantities: list[Quantity]
    assumptions: list[str]
    reproduce: str
    sources: list[str]


class PhotonRun(_M):
    folder: str
    chunk: int
    basis: Literal["Z", "X"]
    n_pairs: int
    n_sifted: int
    n_errors: int
    qber: float
    ci_lo: float
    ci_hi: float


class PhotonBasis(_M):
    basis: Literal["Z", "X"]
    label: str
    pooled: Quantity
    state_averaged: Quantity
    published: Quantity
    run_dispersion_chi2_per_dof: float
    holdout_p_value: float
    calibration_id: str


class PhotonData(_M):
    runs: list[PhotonRun]
    bases: list[PhotonBasis]
    published_aggregate_calibration_id: str
    not_observable: list[str]
    dataset: dict[str, str | int]
    ci_method: str
    reproduce: str
    sources: list[str]


class Slot(_M):
    status: Literal["OK", "NOT_AVAILABLE"]
    reason: str
    expected_source: str


class Reproducibility(_M):
    commands: list[str]
    lane_h_git_shas: list[str]
    environment_locks: list[str]
    evidence_files: list[str]


class BenchmarksData(_M):
    protocols: list[ProtocolRow]
    comparability: list[ComparabilityPair]
    latency_cases: list[LatencyCase]
    photon: PhotonData
    matched_topology: Slot
    reproducibility: Reproducibility
    comparability_note: str


class BenchmarksResponse(Envelope):
    data: BenchmarksData


COMPARABILITY = (
    "No single 'better' score exists. Lane H's X11 matrix marks each classical construction QUALIFIED "
    "(comparable only after pricing the listed concessions) or INCOMPARABLE (fails the double-spend goal, "
    "or uses a different trust model) against the ideal S1 model; no pair is COMPARABLE. Classical latencies "
    "are MODELLED lower bounds on SYNTHETIC light-cone networks; S1 is information-theoretic in an ideal model."
)
GH_REASON = (
    "Matched-topology quantum runs (S-money on lane H's synthetic networks) belong to lane GH, which is in "
    "flight and not merged. Until then quantum and classical latencies are never placed on one axis."
)
SMONEY_ASSUMPTIONS = [
    "timing/causality model only; says nothing about security",
    "dT_tran = dT_proc + L_fibre / c_fibre (Jiang et al. 2024, Methods eq. (10)-(11))",
    "secret validation record pre-distributed to the remote bank agent",
]
H_REPRODUCE = "$PY -m qmint.classical.run_baselines --pqc-reps 5"
E_REPRODUCE = "$PY -m qmint.photonics.schiansky2023"


# --------------------------------------------------------------------------- #
# lane H
# --------------------------------------------------------------------------- #


def _split(cell: str) -> tuple[str, str]:
    left, _, right = cell.partition(" || ")
    return left.removeprefix("H: ").strip(), right.removeprefix("S1: ").strip()


@lru_cache(maxsize=1)
def _matrix() -> tuple[ComparabilityPair, ...]:
    with open(H_MATRIX, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    skip = {"pair_id", "left_protocol", "right_protocol", "comparability_status"}
    out = []
    for r in rows:
        cols = []
        for k, v in r.items():
            if k in skip:
                continue
            left, right = _split(v)
            cols.append(Concession(column=k, left=left, right=right))
        out.append(ComparabilityPair(pair_id=r["pair_id"], left_protocol=r["left_protocol"],
                                     right_protocol=r["right_protocol"], status=r["comparability_status"],
                                     columns=cols))
    return tuple(out)


def _col(pair: ComparabilityPair | None, name: str, side: Literal["left", "right"] = "left") -> str:
    if pair is None:
        return "not in X11 matrix"
    return next((getattr(c, side) for c in pair.columns if c.column == name), "not stated")


def _code(protocol_id: str) -> str:
    return protocol_id.removeprefix("classical_").split("_")[0].upper()


def _ns(id_: str, label: str, seconds: float | None, rec: BenchmarkRecord, note: str) -> Quantity | None:
    if seconds is None:
        return None
    return Quantity(id=id_, label=label, value=seconds * 1e9, unit=Unit.NANOSECOND, evidence_kind=rec.evidence_kind,
                    method="event_simulation", source=f"lane H BenchmarkRecord {rec.record_id}", note=note)


def _double_spend(rec: BenchmarkRecord) -> DoubleSpendOutcome:
    cfg = rec.configuration
    variant = cfg.get("variant", "")
    decisions = ", ".join(f"{k}: {v}" for k, v in cfg.get("double_spend_decisions", {}).items())
    n = rec.double_spends_successful
    if not n:
        return DoubleSpendOutcome(outcome="PREVENTED", successful=n, detail=decisions)
    if cfg.get("extra", {}).get("detection_is_not_prevention"):
        return DoubleSpendOutcome(outcome="DETECTED_NOT_PREVENTED", successful=n,
                                  detail=f"{decisions}; double spender identified at deposit (ex post)")
    if "violated" in variant:
        return DoubleSpendOutcome(outcome="OUT_OF_MODEL", successful=n,
                                  detail=f"{decisions}; tamper-resistance assumption H5-TR broken")
    return DoubleSpendOutcome(outcome="SUCCEEDS", successful=n, detail=decisions)


def _classical_row(rec: BenchmarkRecord, pairs: dict[str, ComparabilityPair]) -> ProtocolRow:
    cfg = rec.configuration
    variant = cfg.get("variant")
    pair = pairs.get(f"{rec.protocol_id}[{variant}]")
    commit_ns = cfg.get("extra", {}).get("stage_ii_commit_to_activation_ns")
    sem = cfg.get("redemption_local_seconds_semantics", "")
    return ProtocolRow(
        id=rec.record_id, code=_code(rec.protocol_id),
        label=f"{_code(rec.protocol_id)} {rec.protocol_id.removeprefix('classical_').split('_', 1)[1].replace('_', ' ')}",
        family="classical", protocol_id=rec.protocol_id, variant=variant, network_id=rec.network_id,
        site_count=rec.site_count, double_spend=_double_spend(rec),
        local_validation=_ns("local_validation", "Local validation (presentation to accept)",
                             rec.redemption_local_seconds, rec, sem),
        cross_check=_ns("cross_check", "Network cross-check during presentation", rec.network_cross_check_seconds, rec,
                        "coordinator / quorum round trip, included in local validation"),
        pre_presentation_commit=None if not commit_ns else Quantity(
            id="pre_presentation_commit", label="Stage-II commit to site activation", value=float(commit_ns),
            unit=Unit.NANOSECOND, evidence_kind=rec.evidence_kind, method="event_simulation",
            source=f"lane H BenchmarkRecord {rec.record_id}",
            note="must complete before presentation (same causal requirement as S1's Stage-II bit c)"),
        latency_unavailable_reason=None,
        trust_model=rec.trust_model, trusted_hardware=_col(pair, "trusted_hardware"),
        adversary=_col(pair, "adversary_power"), pre_distribution=rec.pre_distribution,
        flexibility=rec.spending_flexibility, privacy=rec.privacy_game, issuer_calls=rec.issuer_calls,
        classical_bytes=rec.classical_bytes, comparability_pair=pair.pair_id if pair else None,
        comparability_status=pair.status if pair else "NO_PAIR", evidence_kind=rec.evidence_kind, method=rec.method,
        latency_basis=cfg.get("latency_basis"), record_git_sha=rec.git_sha, environment_lock=rec.environment_lock,
        reproduce=H_REPRODUCE, sources=["reports/classical_baseline_notes/README.md"],
    )


def _s1_row(any_pair: ComparabilityPair) -> ProtocolRow:
    return ProtocolRow(
        id="S1-kent2022-ideal-2site", code="S1", label="S1 ideal two-site S-money (Kent et al. 2022)",
        family="quantum", protocol_id=S1_PROTOCOL, variant="ideal", network_id=None, site_count=2,
        double_spend=DoubleSpendOutcome(
            outcome="BOUNDED_BY_THEOREM", successful=None,
            detail=f"both sites accept with probability <= {_col(any_pair, 'security_target', 'right')} "
                   "(KLPR2022 Lemma 1, Eq. (1); ideal lossless model only)"),
        local_validation=None, cross_check=None, pre_presentation_commit=None,
        latency_unavailable_reason=GH_REASON,
        trust_model=_col(any_pair, "issuer_trust", "right"), trusted_hardware=_col(any_pair, "trusted_hardware", "right"),
        adversary=_col(any_pair, "adversary_power", "right"), pre_distribution=_col(any_pair, "issuance_included", "right"),
        flexibility="late_choice_any_site", privacy=_col(any_pair, "spender_privacy", "right"),
        issuer_calls=None, classical_bytes=None, comparability_pair=None, comparability_status="REFERENCE",
        evidence_kind=EvidenceKind.PUBLISHED_THEOREM, method="published theorem (ideal model); no latency model on matched topology",
        latency_basis=None, record_git_sha=None, environment_lock=None,
        reproduce="$PY -m qmint.proofs.reproduce", sources=[f"{KENT2022_URL} (Table I, Lemma 1 Eq. (1))"],
    )


@lru_cache(maxsize=1)
def _records() -> tuple[BenchmarkRecord, ...]:
    with open(H_RECORDS, encoding="utf-8") as f:
        return tuple(BenchmarkRecord.model_validate_json(line) for line in f if line.strip())


# --------------------------------------------------------------------------- #
# lane G
# --------------------------------------------------------------------------- #


def _paper_case(case_id: str, title: str, case: TopologyCase, classical_key: str, classical_label: str) -> LatencyCase:
    prov = case.provenance
    run = run_s_money(case, b=1)
    pub = float(prov["published_mean_transaction_time_ns"])
    cite = f"Jiang et al. 2024, {JIANG2024_URL} ({prov['anchors']})"
    q = [
        Quantity(id="smoney_modelled", label="S-money transaction time (modelled)", value=run.transaction_time_ns,
                 unit=Unit.NANOSECOND, evidence_kind=EvidenceKind.MODELLED_LATENCY, method="event_simulation",
                 source="qmint.networks.s_money_sites.run_s_money", formula="dT_proc + L_fibre / c_fibre"),
        Quantity(id="smoney_published", label="Published mean transaction time", value=pub, unit=Unit.NANOSECOND,
                 evidence_kind=EvidenceKind.PUBLISHED_AGGREGATE, method="published_value",
                 interval=ConfidenceInterval(lo=pub - 10.0, hi=pub + 10.0, confidence=None, method="published_plus_minus"),
                 source=cite),
        Quantity(id=classical_key, label=classical_label, value=float(prov[f"published_{classical_key}_ns"]),
                 unit=Unit.NANOSECOND, evidence_kind=EvidenceKind.PUBLISHED_AGGREGATE, method="published_value",
                 source=cite, note="reference quoted by the paper, not a QMint classical baseline"),
        Quantity(id="lightcone_bound", label="Light-cone lower bound (straight line / c)",
                 value=case.network.links[0].propagation_lower_bound_ns, unit=Unit.NANOSECOND,
                 evidence_kind=EvidenceKind.MODELLED_LATENCY, method="closed_form",
                 source="qmint.networks.causality.lightcone_delay_ns", formula="D / c"),
    ]
    return LatencyCase(
        id=case_id, title=title, kind="paper_topology", protocol_id=run.trace.protocol_id, quantities=q,
        assumptions=[*SMONEY_ASSUMPTIONS, f"fibre {prov['fiber_length_m']:.0f} m at {prov['fiber_velocity_m_per_s']:.3g} m/s"],
        reproduce="$PY -m pytest tests/unit/networks/test_networks_s_money.py -q", sources=[cite],
    )


def _ripe_case(probe_a: int, probe_b: int, title: str) -> LatencyCase:
    case = ripe.ripe_two_site_case(ripe.load_fixture(), probe_a, probe_b)
    prov = case.provenance
    d = next(iter(prov["directions"].values()))
    pct = d["one_way_ns_percentiles"]
    src = f"RIPE Atlas msm {d['msm_id']} ({prov['source']}), retrieved {prov['retrieved_utc']}"
    times = [run_s_money(case, b=1, t_choice_ns=1e8, seed=s).transaction_time_ns for s in RIPE_SEEDS]
    q = [
        Quantity(id="one_way_p50", label="One-way delay p50 (RTT/2)", value=pct["p50"], unit=Unit.NANOSECOND,
                 evidence_kind=EvidenceKind.MEASURED_LATENCY, method="measured_dataset",
                 interval=ConfidenceInterval(lo=pct["p05"], hi=pct["p95"], confidence=None, method="p05_p95"),
                 source=src, note=ripe.ONE_WAY_ASSUMPTION),
        Quantity(id="lightcone_bound", label="Light-cone lower bound (chord / c)", value=prov["lightcone_ns"],
                 unit=Unit.NANOSECOND, evidence_kind=EvidenceKind.MODELLED_LATENCY, method="closed_form",
                 source="qmint.networks.causality.lightcone_delay_ns", formula="chord(D) / c"),
    ]
    done = [t for t in times if t is not None]
    if len(done) == len(times):
        q.insert(1, Quantity(
            id="smoney_modelled_median", label=f"S-money transaction time, median of {len(done)} seeds",
            value=statistics.median(done), unit=Unit.NANOSECOND, evidence_kind=EvidenceKind.MODELLED_LATENCY,
            method="event_simulation", source="qmint.networks.s_money_sites.run_s_money with ripe.Empirical latency",
            interval=ConfidenceInterval(lo=min(done), hi=max(done), confidence=None, method="min_max_over_seeds"),
            note="modelled on measured RTT/2 samples; not a measured transaction"))
    return LatencyCase(
        id=f"ripe-prb{probe_a}-prb{probe_b}", title=title, kind="measured_network", protocol_id=S1_PROTOCOL,
        quantities=q,
        assumptions=[*SMONEY_ASSUMPTIONS, ripe.ONE_WAY_ASSUMPTION,
                     f"clock error bound {prov['clock_error_bound_ns_assumed']:.0f} ns assumed (NTP-class)"],
        reproduce="$PY -m pytest tests/unit/networks/test_networks_ripe.py -q", sources=[src],
    )


# --------------------------------------------------------------------------- #
# lane E
# --------------------------------------------------------------------------- #


def _photon() -> PhotonData:
    with open(E_DIR / "per_run.csv", encoding="utf-8", newline="") as f:
        raw = list(csv.DictReader(f))
    runs = []
    for r in raw:
        k, n = int(r["n_errors"]), int(r["n_sifted"])
        lo, hi = clopper_pearson(k, n, 0.95)
        runs.append(PhotonRun(folder=r["folder"], chunk=int(r["chunk"]), basis=r["client_basis"], n_pairs=int(r["n_pairs"]),
                              n_sifted=n, n_errors=k, qber=k / n, ci_lo=lo, ci_hi=hi))
    summary = json.loads((E_DIR / "summary.json").read_text(encoding="utf-8"))
    cals = {c.calibration_id: c for c in
            (CalibrationRecord.model_validate(x) for x in json.loads((E_DIR / "calibration_records.json").read_text("utf-8")))}
    ds = summary["dataset"]
    zen = f"Zenodo record {ds['zenodo_record']} (sha256 {ds['sha256'][:12]}…)"
    bases = []
    for b, label, key in (("Z", "H/V (Z basis)", "qber_Z_percent"), ("X", "D/A (X basis)", "qber_X_percent")):
        s = summary["basis_summaries"][b]
        cal = next(c for c in cals.values() if c.calibration_id.endswith(f"-{b}-v1"))
        iv = cal.qber_interval
        assert iv is not None
        pub = PUBLISHED_2023[key]
        se = s["qber_state_avg_se"]
        bases.append(PhotonBasis(
            basis=b, label=label,
            pooled=Quantity(id=f"qber_{b}_pooled", label="Pooled QBER (errors / sifted)", value=iv.point, unit=Unit.FRACTION,
                            evidence_kind=EvidenceKind.PHOTON_EXPERIMENT, method="measured_dataset",
                            interval=ConfidenceInterval(lo=iv.lo, hi=iv.hi, confidence=cal.confidence_level,
                                                        method="hull(clopper_pearson, block bootstrap, run bootstrap, state-avg ±1.96 SE)"),
                            source=f"lane E CalibrationRecord {cal.calibration_id}; {zen}"),
            state_averaged=Quantity(id=f"qber_{b}_state_avg", label="State-averaged QBER (paper's estimator)",
                                    value=s["qber_state_avg"], unit=Unit.FRACTION, evidence_kind=EvidenceKind.PHOTON_EXPERIMENT,
                                    method="measured_dataset",
                                    interval=ConfidenceInterval(lo=s["qber_state_avg"] - 1.959964 * se,
                                                                hi=s["qber_state_avg"] + 1.959964 * se, confidence=0.95,
                                                                method="normal ±1.96 SE"),
                                    source=f"reports/data_working/schiansky2023/summary.json; {zen}"),
            published=Quantity(id=f"qber_{b}_published", label="Published", value=pub["value"] / 100, unit=Unit.FRACTION,
                               evidence_kind=EvidenceKind.PUBLISHED_AGGREGATE, method="published_value",
                               interval=ConfidenceInterval(lo=(pub["value"] - pub["pm"]) / 100, hi=(pub["value"] + pub["pm"]) / 100,
                                                           confidence=None, method="published_plus_minus"),
                               source=f"Schiansky et al. 2023, {SCHIANSKY_URL} ({pub['anchor']})"),
            run_dispersion_chi2_per_dof=s["het_runs"]["dispersion"], holdout_p_value=s["split"]["p_value"],
            calibration_id=cal.calibration_id,
        ))
    return PhotonData(
        runs=runs, bases=bases, published_aggregate_calibration_id=published_aggregate_record().calibration_id,
        not_observable=list(summary["not_observable_from_archive"]),
        dataset={"zenodo_record": ds["zenodo_record"], "sha256": ds["sha256"], "license": ds["license"], "file": ds["file"]},
        ci_method="per run: Clopper-Pearson 95% (assumes iid trials; runs are overdispersed, so the pooled hull is wider)",
        reproduce=E_REPRODUCE, sources=[SCHIANSKY_URL, "https://zenodo.org/records/7979319"],
    )


# --------------------------------------------------------------------------- #


@lru_cache(maxsize=1)
def _data() -> BenchmarksData:
    pairs = {p.left_protocol: p for p in _matrix()}
    recs = _records()
    protocols = [_s1_row(_matrix()[0])] + [_classical_row(r, pairs) for r in recs]
    cases = [
        _paper_case("jiang2024-intracity", "Jinan intra-city, 2.766 km fibre", jiang2024_intracity(),
                    "classical_crosscheck", "Published classical cross-check (2 L / c_fibre)"),
        _paper_case("jiang2024-intercity", "Yiyuan–Mazhan inter-city, 60.54 km fibre", jiang2024_intercity(),
                    "classical_free_space", "Published classical free-space reference (2 D / c)"),
        _ripe_case(6330, 6251, "RIPE Atlas Helsinki → Tampere"),
        _ripe_case(6979, 6251, "RIPE Atlas Frankfurt → Tampere"),
    ]
    return BenchmarksData(
        protocols=protocols, comparability=list(_matrix()), latency_cases=cases, photon=_photon(),
        matched_topology=Slot(status="NOT_AVAILABLE", reason=GH_REASON,
                              expected_source="lane GH: S-money runs on net-h-synthetic-2site-10km / 3site-100km"),
        reproducibility=Reproducibility(
            commands=[H_REPRODUCE, E_REPRODUCE, "$PY -m pytest tests/unit/networks -q", "$PY -m qmint.proofs.reproduce"],
            lane_h_git_shas=sorted({r.git_sha for r in recs}), environment_locks=sorted({r.environment_lock for r in recs}),
            evidence_files=[str(p.relative_to(REPO_ROOT)) for p in (H_RECORDS, H_MATRIX, E_DIR / "per_run.csv",
                                                                     E_DIR / "summary.json", E_DIR / "calibration_records.json")],
        ),
        comparability_note=COMPARABILITY,
    )


router = APIRouter(tags=["benchmarks"])


@router.get("/benchmarks", response_model=BenchmarksResponse)
def benchmarks() -> BenchmarksResponse:
    return BenchmarksResponse(
        status="OK",
        evidence_kind=EvidenceKind.MODELLED_LATENCY,
        provenance=provenance("lanes H (classical), G (networks), E (photonics)", seed=0,
                              notes="RIPE S-money medians: seeds 0..19; matched topology (lane GH) NOT_AVAILABLE"),
        data=_data(),
    )
