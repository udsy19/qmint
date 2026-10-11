"""Run every H-scenario, emit C6 BenchmarkRecords, PQC timings and the X11 comparability matrix.

    python -m qmint.classical.run_baselines [--out reports/classical_baseline_notes] [--pqc-reps 3]
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from qmint.classical import comparability, h4_pqc
from qmint.classical import matched_topology as M
from qmint.classical import scenarios as S
from qmint.classical.common import lightcone_network
from qmint.core.contracts import BenchmarkRecord, EvidenceKind, SpacetimeNetwork, Targets
from qmint.core.serialization import canonical_hash, canonical_json, file_sha256

ROOT = Path(__file__).resolve().parents[2]

NETWORKS = {
    "2site_10km": lightcone_network("net-h-synthetic-2site-10km", {"A": (0.0, 0.0), "B": (10_000.0, 0.0)}),
    "3site_100km": lightcone_network("net-h-synthetic-3site-100km",
                                     {"A": (0.0, 0.0), "B": (100_000.0, 0.0), "H": (50_000.0, 0.0)}),
}


def _git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown-no-git"


def scenario_results(pqc_timings: dict | None = None) -> list[S.ScenarioResult]:
    out: list[S.ScenarioResult] = []
    for key, net in NETWORKS.items():
        hub = "H" if key == "3site_100km" else "A"
        out.append(S.run_h0(net))
        out.append(S.run_h1(net, hub, partition_site="B"))
        if key == "3site_100km":
            out.append(S.run_h2(net, f=1))
        for mode in ("preassigned", "late_commit_disclosed", "late_commit_ot_private"):
            out.append(S.run_h3(net, hub, mode))
        for combine in ("none", "h3_site_binding", "h1_ledger"):
            out.append(S.run_h4(net, combine, coord_site=hub, timings=pqc_timings))
        out.append(S.run_h5(net, True))
        out.append(S.run_h5(net, False))
        out.append(S.run_h6(net, hub))
    return out


# scenario variant -> matched-topology label whose STRONG adversary covers it (lane M finding M-H4). None: the
# weak replay adversary already double-spends (H4 alone, H5 with the assumption violated), nothing to strengthen.
STRONG_LABEL = {"negative_control": "H0", "coordinator": "H1", "sharded_quorum_f1": "H2",
                "preassigned": "H3_preassigned", "late_commit_disclosed": "H3_late_commit_disclosed",
                "late_commit_ot_private": "H3_late_commit_ot_private", "mldsa_none": None,
                "mldsa_h3_site_binding": "H4+H3", "mldsa_h1_ledger": "H4+H1", "assumption_holds": "H5",
                "assumption_violated_clone": None, "cfn88_sec1_k16": "H6"}
STRONG_CASE = "synthetic_10km"


def strong_double_spends(variant: str) -> dict | None:
    """Worst case over b of the matched-topology STRONG adversary (Jiang processing, seed 0)."""
    label = STRONG_LABEL[variant]
    if label is None:
        return None
    case = M.matched_cases()[STRONG_CASE]
    runs = [M.run_matched(case, label, b, "jiang_dTproc_1507ns", adversary="strong") for b in (0, 1)]
    return {"label": label, "case_id": STRONG_CASE, "attempts": list(runs[0].metrics["strong_attempts"]),
            "double_spends_successful": max(r.metrics["accepted_presentations"] - 1 for r in runs)}


def to_record(r: S.ScenarioResult, network: SpacetimeNetwork, git_sha: str, env_lock: str) -> BenchmarkRecord:
    strong = strong_double_spends(r.variant)
    worst = max(r.local_accept_ns.values()) if r.local_accept_ns else None  # worst accepting site
    cross = max(r.cross_check_ns.values()) if r.cross_check_ns else None
    config = {
        "variant": r.variant,
        "redemption_local_seconds_semantics": "max over presentation sites of honest presentation->local accept",
        "local_accept_ns_by_site": r.local_accept_ns,
        "double_spend_decisions": r.double_spend_decisions,
        "double_spends_by_adversary": {
            "replay_same_secret_at_other_site": r.double_spends_successful,
            "strong_matched_topology": strong if strong is not None else
            "not run: the replay adversary already double-spends",
            "reported_value": "max over the adversaries above"},
        "declared_processing_ns": {"site": S.SITE_PROC_NS, "coordinator": S.COORD_PROC_NS},
        "latency_basis": "lane-G engine, Lightcone runtime: every hop = link lower bound (exact light cone, "
                         "SYNTHETIC) + declared processing; lower bound, favourable to coordination-based designs",
        "extra": r.extra,
    }
    body = {"protocol_id": r.protocol_id, "network_id": r.network_id, "config": config}
    return BenchmarkRecord(
        record_id=f"H-{r.protocol_id}-{r.variant}-{r.network_id}-{canonical_hash(body)[:12]}",
        protocol_id=r.protocol_id,
        classical_or_quantum="classical",
        security_target=Targets(),  # no epsilon claimed for classical systems game C1
        trust_model=r.trust_model,
        pre_distribution=r.pre_distribution,
        spending_flexibility=r.spending_flexibility,
        privacy_game=r.privacy_game,
        network_id=network.network_id,
        site_count=r.site_count,
        redemption_local_seconds=None if worst is None else worst / 1e9,
        network_cross_check_seconds=None if cross is None else cross / 1e9,
        classical_bytes=r.classical_bytes,
        issuer_calls=r.issuer_calls,
        false_rejects=r.false_rejects,
        double_spends_successful=max(r.double_spends_successful,
                                     0 if strong is None else strong["double_spends_successful"]),
        method="lane-H deterministic state machines hosted on lane-G's discrete-event engine "
               "(qmint.classical.scenarios via qmint.classical.engine_adapter)",
        configuration=json.loads(canonical_json(config)),
        evidence_kind=EvidenceKind.MODELLED_LATENCY,
        git_sha=git_sha,
        environment_lock=env_lock,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(ROOT / "reports" / "classical_baseline_notes"))
    ap.add_argument("--pqc-reps", type=int, default=3)
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    timings = {ps: h4_pqc.measure_mldsa(ps, reps=args.pqc_reps) for ps in h4_pqc.PARAMETER_SETS}
    (out / "pqc_timings.json").write_text(json.dumps(timings, indent=2, sort_keys=True) + "\n")
    git_sha = _git_sha()
    env_lock = f"requirements.lock sha256:{file_sha256(ROOT / 'requirements.lock')}"
    nets = {n.network_id: n for n in NETWORKS.values()}
    records = [to_record(r, nets[r.network_id], git_sha, env_lock)
               for r in scenario_results(timings["ML_DSA_44"])]
    with open(out / "benchmark_records.jsonl", "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(canonical_json(rec) + "\n")
    comparability.write_csv(out / "comparability_matrix.csv")
    print(f"wrote {len(records)} BenchmarkRecords, pqc_timings.json, comparability_matrix.csv to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
