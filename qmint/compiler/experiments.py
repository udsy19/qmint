"""Runner for the pre-registered experiments X12 (selectors / oracle agreement / Pareto) and X13 (ablations).

Everything is read from ``benchmarks/frozen_experiments.yaml``; outputs go to
``reports/optimizer_working/`` (results.json, results.md, CSVs, figures). Deterministic: no sampling.
"""

from __future__ import annotations

import csv
import json
import math
import sys
import time
import tracemalloc
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from qmint.compiler import calibration as cal
from qmint.compiler.certify import CertOutcome, certify, diagnose
from qmint.compiler.constraints import (
    FROZEN_PATH,
    ROOT,
    Problem,
    UnsupportedCombination,
    build_grid,
    d1_device,
    declarations,
    frozen,
    ideal_device,
    make_targets,
    s2_device,
)
from qmint.compiler.pareto import OBJECTIVES, Point, pareto_front
from qmint.compiler.scoring import Scorer, proof_version
from qmint.compiler.selectors import (
    Selection,
    compiler,
    exhaustive_oracle,
    naive_analytic,
    published_fixed,
    s2_best_unf_at_n,
)
from qmint.core.contracts import CalibrationRecord, GameId, Targets
from qmint.core.manifest import git_state
from qmint.core.serialization import canonical_json, file_sha256
from qmint.proofs.checker import IndependentProofChecker
from qmint.proofs.engine import ProofEngine
from qmint.proofs.ideal_bounds import min_length_for_target

OUT_DIR = ROOT / "reports" / "optimizer_working"
PREREG_COMMIT = "0268feed3b37bc0c6f6b544ccfc6eb882f134e91"
GRID_STEP = 10 ** (1 / 40)
MATCH_SLACK_DEX = 1e-6  # matched targets = published achieved bound + 1e-6 dex, so the recipe meets its own
#                         bounds after the float round-trip (2.3e-6 relative; recorded in results)


def _matched(log10_value: float) -> float:
    return 10 ** (log10_value + MATCH_SLACK_DEX)


# --------------------------------------------------------------------------- #
# Problem builders
# --------------------------------------------------------------------------- #


def s2_problem(dev: str, interval: bool, eps: float, honest: float, *, M: int = 1, small: bool = False,
               beta_E: float | None = None, eps_priv: float | None = None) -> Problem:
    sid = f"S2/{dev}/{'interval' if interval else 'point'}/M{M}/unf{eps:g}/h{honest:g}" + (f"/priv{eps_priv:g}" if eps_priv else "")
    return Problem(sid, GameId.S2, s2_device(dev, interval=interval, M=M, beta_E=beta_E),
                   make_targets(GameId.S2, eps, honest, eps_priv), build_grid("S2", small=small),
                   meta={"device": dev, "uncertainty": "interval" if interval else "point", "M": M})


def d1_calibration(dev: str) -> CalibrationRecord | None:
    method = {"D1-ZEN-IID": "iid", "D1-ZEN-DRIFT": "drift"}.get(dev)
    return cal.calibration_record(method) if method else None


def d1_problem(dev: str, eps: float, honest: float, *, small: bool = False) -> Problem:
    calib = d1_calibration(dev)
    return Problem(f"D1/{dev}/unf{eps:g}/h{honest:g}", GameId.D1, d1_device(dev), make_targets(GameId.D1, eps, honest),
                   build_grid("D1", small=small), calibration=calib,
                   meta={"device": dev, "uncertainty": "interval" if dev != "D1-PUB-SI" else "point", "M": 1})


def ideal_problem(game: GameId, eps: float, eps_priv: float | None = None) -> Problem:
    return Problem(f"{game.value}/unf{eps:g}" + (f"/priv{eps_priv:g}" if eps_priv else ""), game, ideal_device(game),
                   make_targets(game, eps, None, eps_priv), build_grid("ideal"),
                   meta={"device": "ideal", "uncertainty": "none", "M": 1})


# --------------------------------------------------------------------------- #
# Run context and row records
# --------------------------------------------------------------------------- #


@dataclass
class Ctx:
    engine: ProofEngine = field(default_factory=ProofEngine)
    checker: IndependentProofChecker = field(default_factory=IndependentProofChecker)
    revision: str = ""
    rows: list[dict[str, Any]] = field(default_factory=list)
    infeasibility: list[dict[str, Any]] = field(default_factory=list)
    checker_rejections: int = 0
    released: int = 0
    uncertified_by_construction: int = 0
    certificates: dict[str, Any] = field(default_factory=dict)

    def scorer(self) -> Scorer:
        return Scorer(self.engine, cache=True)


def resources(problem: Problem, N: int | None) -> dict[str, Any]:
    if N is None:
        return {"issuance_seconds": None, "classical_bits": None, "expected_photons": None}
    rate = float(frozen()["resource_model"]["source_rate_hz"]["value"])  # YAML 1.1 reads "1.0e8" as a string
    out: dict[str, Any] = {"issuance_seconds": N / rate, "expected_photons": None}
    if problem.family == "S2":
        p_det = frozen()["devices"]["S2"]["common"]["P_det"]["value"]
        out["classical_bits"] = N + 2 * math.ceil(p_det * N)
        out["expected_photons"] = frozen()["devices"]["S2"]["common"]["mu"]["value"] * N
    elif problem.family == "D1":
        out["classical_bits"] = N
    else:
        out["classical_bits"] = 2 * N
    return out


def device_evidence(problem: Problem) -> str:
    dev = problem.meta.get("device")
    if problem.family == "S2":
        spec = frozen()["devices"]["S2"][dev]
        ev = spec["evidence"]
        return ev + ("+HYPOTHETICAL_INTERVAL" if problem.meta.get("uncertainty") == "interval" else "")
    if problem.family == "D1":
        return "PHOTON_EXPERIMENT(e_h)+PUBLISHED_AGGREGATE(l_h,p_m)" if problem.calibration else "PUBLISHED_AGGREGATE"
    return "IDEAL_MODEL"


def record(ctx: Ctx, experiment: str, problem: Problem, sel: Selection, *, do_certify: bool = True,
           extra: dict[str, Any] | None = None) -> dict[str, Any]:
    outcome: CertOutcome | None = None
    if do_certify and sel.status == "FEASIBLE":
        outcome = certify(problem, sel, engine=ctx.engine, checker=ctx.checker, software_revision=ctx.revision)
        if outcome.released:
            ctx.released += 1
        elif outcome.uncertified_by_construction:
            ctx.uncertified_by_construction += 1
        else:
            ctx.checker_rejections += 1
    t = problem.targets
    row = {
        "experiment": experiment, "scenario_id": problem.scenario_id, "family": problem.family,
        "game": problem.game.value, "device": problem.meta.get("device"), "uncertainty": problem.meta.get("uncertainty"),
        "M": problem.meta.get("M", 1), "eps_unf_target": t.epsilon_unf,
        "honest_target": (None if t.epsilon_cor is None else (t.epsilon_cor + (t.epsilon_rob or 0.0))),
        "eps_priv_target": t.epsilon_priv,
        "selector": sel.selector, "status": sel.status, "optimality": sel.optimality, "N": sel.N,
        "decisions": json.dumps(sel.decisions, sort_keys=True) if sel.decisions else None,
        "log10_eps_unf": sel.logs.get("epsilon_unf"), "log10_eps_cor": sel.logs.get("epsilon_cor"),
        "log10_eps_rob": sel.logs.get("epsilon_rob"), "log10_eps_priv": sel.logs.get("epsilon_priv"),
        "honest_failure_log10": sel.honest_log10,
        "certificate_status": outcome.certificate.proof_check_status.value if outcome else None,
        "released": outcome.released if outcome else False,
        "checker_reason": (outcome.certificate.reason[:300] if outcome and not outcome.released else None),
        "bound_evidence_kind": outcome.certificate.evidence_kind.value if outcome else None,
        "device_evidence": device_evidence(problem),
        "resource_evidence": "MODELLED (HYPOTHETICAL source rate / proxy bit model)",
        "engine_calls": sel.engine_calls, "cache_hits": sel.cache_hits, "wall_seconds": round(sel.wall_seconds, 6),
        "note": sel.note,
        **resources(problem, sel.N if sel.status == "FEASIBLE" else None),
        **(extra or {}),
    }
    if outcome and outcome.released and sel.selector == "compiler":
        ctx.certificates[problem.scenario_id] = json.loads(canonical_json(outcome.certificate))
    ctx.rows.append(row)
    return row


def infeasibility(ctx: Ctx, problem: Problem, note: str) -> dict[str, Any]:
    cert = diagnose(problem, Scorer(ctx.engine), note=note)
    d = json.loads(canonical_json(cert))
    ctx.infeasibility.append(d)
    return d


# --------------------------------------------------------------------------- #
# X12
# --------------------------------------------------------------------------- #


def x12_ideal(ctx: Ctx) -> list[dict[str, Any]]:
    out = []
    for game in (GameId.W1, GameId.S1):
        for eps in frozen()["targets"]["epsilon_unf"]:
            p = ideal_problem(game, eps)
            golden = min_length_for_target(game, eps)
            for fn in (published_fixed, naive_analytic, exhaustive_oracle, compiler):
                sel = fn(p, ctx.scorer() if fn is not exhaustive_oracle else None)
                sel.feasible_points = None
                out.append(record(ctx, "X12-ideal", p, sel, extra={"closed_form_n_min": golden,
                                                                    "agrees_with_closed_form": sel.N == golden if sel.N else None}))
    return out


def x12_s2(ctx: Ctx) -> None:
    eps_l, hon_l = frozen()["targets"]["epsilon_unf"], frozen()["targets"]["honest_failure"]
    for dev in frozen()["scenario_matrix"]["S2"]["devices"]:
        for interval in (False, True):
            for eps in eps_l:
                for h in hon_l:
                    p = s2_problem(dev, interval, eps, h)
                    scorer = ctx.scorer()
                    for fn in (published_fixed, naive_analytic, compiler):
                        record(ctx, "X12-S2", p, fn(p, scorer))
                    comp = ctx.rows[-1]
                    if comp["status"] == "INFEASIBLE" and (eps, h) == (1e-9, 1e-3):
                        infeasibility(ctx, p, f"compiler: {comp['note']}")


def x12_oracle_agreement(ctx: Ctx) -> list[dict[str, Any]]:
    sm = frozen()["scenario_matrix"]
    out = []
    jobs: list[Problem] = []
    for dev in sm["S2_oracle_agreement"]["devices"]:
        for interval in (False, True):
            for eps in sm["S2_oracle_agreement"]["epsilon_unf"]:
                for h in sm["S2_oracle_agreement"]["honest_failure"]:
                    jobs.append(s2_problem(dev, interval, eps, h, small=True))
    for dev in sm["D1_oracle_agreement"]["devices"]:
        for eps in sm["D1_oracle_agreement"]["epsilon_unf"]:
            for h in sm["D1_oracle_agreement"]["honest_failure"]:
                jobs.append(d1_problem(dev, eps, h, small=True))
    measured: set[str] = set()
    for p in jobs:
        res = {}
        for name, fn, cache in (("exhaustive_oracle", exhaustive_oracle, False), ("compiler", compiler, True)):
            sel = fn(p, Scorer(ctx.engine, cache=cache))
            peak = None
            if p.family not in measured:  # tracemalloc is slow: peak memory on the first job of each family only
                tracemalloc.start()
                fn(p, Scorer(ctx.engine, cache=cache))  # identical rerun, for peak memory only
                _, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
            n_feasible = len(sel.feasible_points or [])
            sel.feasible_points = None
            record(ctx, "X12-oracle-agreement", p, sel,
                   extra={"peak_memory_bytes": peak, "grid_points": math.prod(p.shape), "oracle_feasible_points": n_feasible or None})
            res[name] = sel
        measured.add(p.family)
        o, c = res["exhaustive_oracle"], res["compiler"]
        out.append({
            "scenario_id": p.scenario_id, "grid_points": math.prod(p.shape),
            "oracle_status": o.status, "compiler_status": c.status, "oracle_idx": o.idx, "compiler_idx": c.idx,
            "oracle_N": o.N, "compiler_N": c.N, "identical": (o.status, o.idx) == (c.status, c.idx),
            "oracle_engine_calls": o.engine_calls, "compiler_engine_calls": c.engine_calls,
            "oracle_seconds": round(o.wall_seconds, 4), "compiler_seconds": round(c.wall_seconds, 4),
            "oracle_peak_bytes": ctx.rows[-2]["peak_memory_bytes"], "compiler_peak_bytes": ctx.rows[-1]["peak_memory_bytes"],
        })
    return out


def x12_rejections(ctx: Ctx) -> list[dict[str, Any]]:
    """Unsupported requests must be refused (or produce an infeasibility certificate), never approximated."""
    out: list[dict[str, Any]] = []

    def attempt(case: str, build: Callable[[], Problem]) -> None:
        try:
            p = build()
        except UnsupportedCombination as e:
            out.append({"case": case, "outcome": "REJECTED", "reason": str(e)})
            return
        sel = compiler(p, ctx.scorer())
        if sel.status == "FEASIBLE":
            o = certify(p, sel, engine=ctx.engine, checker=ctx.checker)
            out.append({"case": case, "outcome": "FEASIBLE", "certificate_status": o.certificate.proof_check_status.value,
                        "N": sel.N, "reason": o.certificate.reason[:200]})
        else:
            d = infeasibility(ctx, p, sel.note)
            out.append({"case": case, "outcome": d["status"], "reason": d["reason"],
                        "missing_assumptions": d["missing_assumptions"],
                        "axes": {a["axis"]: list(a["reasons"])[:2] for a in d["axes"]}})

    s2dev = s2_device("K22-F5a", interval=False)
    for g in (GameId.W2, GameId.A1, GameId.C1):
        attempt(f"game {g.value}", lambda g=g: Problem(f"{g.value}", g, {"declared_assumptions": ["x"]},
                                                         make_targets(GameId.W1, 1e-9, None), build_grid("ideal")))
    attempt("S2 reporting strategy 'report_with_basis'", lambda: Problem(
        "S2/bad-report", GameId.S2, {**s2dev, "reporting_strategy": "report_with_basis"},
        make_targets(GameId.S2, 1e-9, 1e-3), build_grid("S2")))
    attempt("W1 with noise parameter E", lambda: Problem(
        "W1/noisy", GameId.W1, {**ideal_device(GameId.W1), "E": 0.01}, make_targets(GameId.W1, 1e-9, None), build_grid("ideal")))
    attempt("S2 with Schiansky 2023 calibration", lambda: Problem(
        "S2/sch-cal", GameId.S2, s2dev, make_targets(GameId.S2, 1e-9, 1e-3), build_grid("S2"),
        calibration=cal.calibration_record("iid")))
    attempt("D1 with three merchants", lambda: Problem(
        "D1/3m", GameId.D1, {**d1_device("D1-PUB-SI"), "merchants": 3}, make_targets(GameId.D1, 1e-9, 1e-3), build_grid("D1")))
    out.append({"case": "Jiang 2024 published tuple (S2_JIANG24)", "outcome": "REJECTED",
                "reason": frozen()["selectors"]["published_fixed"]["S2_JIANG24"]["expected"]})
    attempt("W1 with privacy target 1e-2", lambda: ideal_problem(GameId.W1, 1e-9, eps_priv=1e-2))
    attempt("D1 with privacy target 1e-2", lambda: Problem(
        "D1/priv", GameId.D1, d1_device("D1-PUB-SI"), make_targets(GameId.D1, 1e-9, 1e-3, 1e-2), build_grid("D1")))
    pc = frozen()["devices"]["S2"]["privacy_check"]
    for tp in pc["epsilon_priv_targets"]:
        attempt(f"S2 {pc['device']} privacy target {tp:g} (beta_E={pc['beta_E']['value']:g}, HYPOTHETICAL)",
                lambda tp=tp: s2_problem(pc["device"], False, 1e-9, 1e-3, beta_E=pc["beta_E"]["value"], eps_priv=tp))
    attempt("S2 missing declaration table6_E_no_side_channels", lambda: Problem(
        "S2/missing-decl", GameId.S2,
        {**s2dev, "declared_assumptions": [d for d in declarations(GameId.S2) if d != "table6_E_no_side_channels"]},
        make_targets(GameId.S2, 1e-9, 1e-3), build_grid("S2")))
    attempt("S2 K22-EXP (paper's experimental tuple)", lambda: s2_problem("K22-EXP", False, 1e-9, 1e-3))
    return out


def x12_published_matched(ctx: Ctx) -> list[dict[str, Any]]:
    """Strict matching: the compiler must meet, on every axis, the published recipe's own achieved bound."""
    out = []
    for dev in frozen()["scenario_matrix"]["S2"]["devices"]:
        for interval in (False, True):
            base = s2_problem(dev, interval, 1e-9, 1e-3)
            pub = published_fixed(base)
            if not all(k in pub.logs for k in ("epsilon_unf", "epsilon_cor", "epsilon_rob")):
                out.append({"scenario": base.scenario_id, "mode": "strict", "published": "NO_APPLICABLE_BOUND_AT_DEVICE",
                            "published_logs": pub.logs})
                continue
            capped = pub.logs["epsilon_rob"] < -300
            tg = {"epsilon_unf": _matched(pub.logs["epsilon_unf"]), "epsilon_cor": _matched(pub.logs["epsilon_cor"]),
                  "epsilon_rob": _matched(max(pub.logs["epsilon_rob"], -300))}
            p = Problem(base.scenario_id.replace("/unf1e-09/h0.001", "/strict-matched"), GameId.S2, base.device,
                        Targets(**tg), base.grid, meta=dict(base.meta))
            c = compiler(p, ctx.scorer())
            record(ctx, "X12-published-matched", p, c)
            pub_m = record(ctx, "X12-published-matched", p, published_fixed(p))
            out.append({"scenario": p.scenario_id, "mode": "strict", "published_N": pub.N, "compiler_N": c.N,
                        "published_released": pub_m["released"], "compiler_released": ctx.rows[-2]["released"],
                        "compiler_status": c.status, "ratio_published_over_compiler": (pub.N / c.N) if c.N else None,
                        "rob_target_capped_at_1e-300": capped,
                        "caveat": "published eps_rob is below float range; matched only to 1e-300 (weaker than published on eps_rob)" if capped else ""})
    # D1 (UNCERTIFIED by construction): strict = published achieved bounds; design = published p_d, honest 1e-3
    for dev in ("D1-PUB-SI",):
        base = d1_problem(dev, 1e-9, 1e-3)
        pub = published_fixed(base)
        design = math.log10(frozen()["selectors"]["published_fixed"]["D1"]["design_target"])
        for mode, tg in (("strict", {"epsilon_unf": _matched(pub.logs["epsilon_unf"]), "epsilon_cor": _matched(pub.logs["epsilon_cor"])}),
                         ("design", {"epsilon_unf": _matched(design), "epsilon_cor": 1e-3})):
            p = Problem(f"D1/{dev}/{mode}-matched", GameId.D1, base.device, Targets(**tg), base.grid,
                        calibration=base.calibration, meta=dict(base.meta))
            c = compiler(p, ctx.scorer())
            pub_m = published_fixed(p)
            record(ctx, "X12-published-matched", p, c)
            record(ctx, "X12-published-matched", p, pub_m)
            out.append({"scenario": p.scenario_id, "mode": mode, "published_N": pub_m.N, "published_status": pub_m.status,
                        "compiler_N": c.N, "compiler_status": c.status,
                        "ratio_published_over_compiler": (pub_m.N / c.N) if c.N and pub_m.status == "FEASIBLE" else None,
                        "certification": "UNCERTIFIED by construction (D1)"})
    return out


def d1_matrix(ctx: Ctx) -> None:
    for dev in frozen()["scenario_matrix"]["D1"]["devices"]:
        for eps in frozen()["targets"]["epsilon_unf"]:
            for h in frozen()["targets"]["honest_failure"]:
                p = d1_problem(dev, eps, h)
                scorer = ctx.scorer()
                for fn in (published_fixed, naive_analytic, compiler):
                    record(ctx, "X12-D1", p, fn(p, scorer))
                if ctx.rows[-1]["status"] == "INFEASIBLE" and (eps, h) == (1e-9, 1e-3):
                    infeasibility(ctx, p, f"compiler: {ctx.rows[-1]['note']}")


# --------------------------------------------------------------------------- #
# X13 ablations
# --------------------------------------------------------------------------- #


def _rows(ctx: Ctx, **kw: Any) -> list[dict[str, Any]]:
    return [r for r in ctx.rows if all(r.get(k) == v for k, v in kw.items())]


def x13_uncertainty(ctx: Ctx) -> list[dict[str, Any]]:
    out = []
    for dev in frozen()["scenario_matrix"]["S2"]["devices"]:
        for eps in frozen()["targets"]["epsilon_unf"]:
            for h in frozen()["targets"]["honest_failure"]:
                pt = s2_problem(dev, False, eps, h)
                iv = s2_problem(dev, True, eps, h)
                for selector in ("compiler", "naive_analytic", "published_fixed"):
                    rp = _rows(ctx, experiment="X12-S2", scenario_id=pt.scenario_id, selector=selector)[0]
                    ri = _rows(ctx, experiment="X12-S2", scenario_id=iv.scenario_id, selector=selector)[0]
                    safety = None
                    if rp["status"] == "FEASIBLE":  # re-score the POINT-selected decisions on the interval box
                        sel = Selection(selector, iv.scenario_id, "FEASIBLE", "rescored", decisions=json.loads(rp["decisions"]))
                        sc = Scorer(ctx.engine).score_all(iv, sel.decisions)
                        ok = all(s.meets(iv.target_log10(a)) for a, s in sc.items())
                        safety = "still certified under interval" if ok and certify(iv, sel, engine=ctx.engine, checker=ctx.checker).released \
                            else "NOT certified under interval (point selection unsafe under uncertainty)"
                    out.append({"device": dev, "eps_unf": eps, "honest": h, "selector": selector,
                                "N_point": rp["N"] if rp["status"] == "FEASIBLE" else None, "point_status": rp["status"],
                                "N_interval": ri["N"] if ri["status"] == "FEASIBLE" else None, "interval_status": ri["status"],
                                "point_selection_under_interval": safety})
    return out


def x13_drift_holdout(ctx: Ctx, out_dir: Path) -> dict[str, Any]:
    """A2 (D1 only): select on calibration runs, FREEZE, then evaluate on holdout runs 6-10."""
    sel_cells: dict[str, Any] = {}
    for dev in ("D1-ZEN-IID", "D1-ZEN-DRIFT"):
        for eps in frozen()["targets"]["epsilon_unf"]:
            for h in frozen()["targets"]["honest_failure"]:
                r = _rows(ctx, experiment="X12-D1", scenario_id=d1_problem(dev, eps, h).scenario_id, selector="compiler")[0]
                sel_cells[f"{dev}|{eps:g}|{h:g}"] = {"status": r["status"], "N": r["N"],
                                                     "decisions": json.loads(r["decisions"]) if r["decisions"] else None}
    calib = {m: cal.calibration_record(m).qber_interval.model_dump(mode="json") for m in ("iid", "drift")}
    frozen_path = out_dir / "d1_frozen_selection.json"
    sha = cal.freeze_selection({"selections": sel_cells, "calibration_intervals": calib,
                                "frozen_experiments_sha256": file_sha256(FROZEN_PATH)}, frozen_path)
    # ---- holdout access only after the freeze ----
    rows = cal.holdout_rows(frozen_path)
    per_run = []
    for r in rows:
        lo, hi = cal.clopper_pearson(r["n_errors"], r["n_sifted"])
        rec = cal.calibration_record("iid", rows=[r], tag=f"holdout-run-{r['run']}")
        entry = {"run": r["run"], "qber": r["qber"], "cp95": [lo, hi],
                 "inside_iid": calib["iid"]["lo"] <= r["qber"] <= calib["iid"]["hi"],
                 "inside_drift": calib["drift"]["lo"] <= r["qber"] <= calib["drift"]["hi"]}
        for dev in ("D1-ZEN-IID", "D1-ZEN-DRIFT"):
            cell = sel_cells[f"{dev}|1e-09|0.001"]
            if cell["status"] != "FEASIBLE":
                entry[f"{dev}_frozen_config_on_holdout"] = "NO_FROZEN_CONFIG (selection infeasible)"
                continue
            p = Problem(f"D1/holdout-run-{r['run']}/{dev}", GameId.D1, d1_device(dev), make_targets(GameId.D1, 1e-9, 1e-3),
                        build_grid("D1"), calibration=rec)
            sc = Scorer(ctx.engine).score_all(p, cell["decisions"])
            if any(s.out_of_domain for s in sc.values()):
                verdict = "INADMISSIBLE (SI Eq. 23 fails on holdout interval)"
            else:
                verdict = "targets met" if all(s.meets(p.target_log10(a)) for a, s in sc.items()) else "targets NOT met"
            entry[f"{dev}_frozen_config_on_holdout"] = verdict
        per_run.append(entry)
    return {"frozen_selection_sha256": sha, "calibration_intervals": calib, "holdout_runs": per_run,
            "coverage_iid": sum(e["inside_iid"] for e in per_run) / len(per_run),
            "coverage_drift": sum(e["inside_drift"] for e in per_run) / len(per_run),
            "selections_primary_cell": {k: v for k, v in sel_cells.items() if k.endswith("|1e-09|0.001")}}


def x13_fixed_n(ctx: Ctx) -> list[dict[str, Any]]:
    out = []
    n_pub = frozen()["selectors"]["published_fixed"]["S2"]["tuple"]["N"]
    for dev in frozen()["scenario_matrix"]["S2"]["devices"]:
        for interval in (False, True):
            p = s2_problem(dev, interval, 1e-9, 1e-3)
            pub = published_fixed(p)
            fx = s2_best_unf_at_n(p, n_pub, ctx.scorer())
            nv = _rows(ctx, experiment="X12-S2", scenario_id=p.scenario_id, selector="naive_analytic")[0]
            cp = _rows(ctx, experiment="X12-S2", scenario_id=p.scenario_id, selector="compiler")[0]
            out.append({"device": dev, "uncertainty": "interval" if interval else "point",
                        "published_log10_eps_unf_at_4e7": pub.logs.get("epsilon_unf"),
                        "thresholds_optimised_log10_eps_unf_at_4e7": fx.logs.get("epsilon_unf"),
                        "N_thresholds_fixed_by_rule (naive)": nv["N"] if nv["status"] == "FEASIBLE" else None,
                        "N_joint (compiler)": cp["N"] if cp["status"] == "FEASIBLE" else None})
    return out


def x13_sites(ctx: Ctx) -> list[dict[str, Any]]:
    out = []
    for dev in frozen()["scenario_matrix"]["S2"]["devices"]:
        for interval in (False, True):
            for M in frozen()["scenario_matrix"]["S2"]["sites_sweep"]["M"]:
                p = s2_problem(dev, interval, 1e-9, 1e-3, M=M)
                r = record(ctx, "X13-sites", p, compiler(p, ctx.scorer()))
                out.append({"device": dev, "uncertainty": "interval" if interval else "point", "M": M,
                            "presentation_points": 2**M, "C": p.device.get("C", 1), "N": r["N"], "status": r["status"],
                            "released": r["released"]})
    return out


# --------------------------------------------------------------------------- #
# Pareto, verdict, reporting
# --------------------------------------------------------------------------- #


def pareto_rows(ctx: Ctx) -> list[dict[str, Any]]:
    """Fig. 8 data: CERTIFIED S2 points per (device, uncertainty) over the target sweep, with front flags."""
    out = []
    groups: dict[tuple, list[dict[str, Any]]] = {}
    for r in ctx.rows:
        if r["experiment"] == "X12-S2" and r["released"]:
            groups.setdefault((r["device"], r["uncertainty"]), []).append(r)
    for (dev, unc), rows in sorted(groups.items()):
        pts = [Point((r["selector"], r["scenario_id"]), tuple(r[o] if o != "log10_eps_unf" else r["log10_eps_unf"] for o in OBJECTIVES), r)
               for r in rows]
        front_all = {id(p.payload) for p in pareto_front(pts)}
        per_sel: dict[str, set[int]] = {}
        for s in {r["selector"] for r in rows}:
            per_sel[s] = {id(p.payload) for p in pareto_front([p for p in pts if p.payload["selector"] == s])}
        for p in pts:
            r = p.payload
            out.append({"device": dev, "uncertainty": unc, "selector": r["selector"], "eps_unf_target": r["eps_unf_target"],
                        "honest_target": r["honest_target"], "N": r["N"], "issuance_seconds": r["issuance_seconds"],
                        "honest_failure_log10": r["honest_failure_log10"], "classical_bits": r["classical_bits"],
                        "log10_eps_unf": r["log10_eps_unf"], "on_combined_front": id(r) in front_all,
                        "on_selector_front": id(r) in per_sel[r["selector"]], "status": "CERTIFIED"})
    return out


def g5_verdict(ctx: Ctx) -> dict[str, Any]:
    cell = frozen()["targets"]["primary_cell"]
    per_dev = []
    for dev in frozen()["scenario_matrix"]["S2"]["devices"]:
        res: dict[str, Any] = {"device": dev}
        ok_both = True
        for unc, interval in (("point", False), ("interval", True)):
            sid = s2_problem(dev, interval, cell["epsilon_unf"], cell["honest_failure"]).scenario_id
            c = _rows(ctx, experiment="X12-S2", scenario_id=sid, selector="compiler")[0]
            n = _rows(ctx, experiment="X12-S2", scenario_id=sid, selector="naive_analytic")[0]
            pb = _rows(ctx, experiment="X12-S2", scenario_id=sid, selector="published_fixed")[0]
            ratio = (n["N"] / c["N"]) if (c["released"] and n["released"]) else None
            res[unc] = {"compiler_N": c["N"] if c["released"] else None, "naive_N": n["N"] if n["released"] else None,
                        "published_N": pb["N"] if pb["released"] else None, "compiler_status": c["status"],
                        "naive_status": n["status"], "published_status": pb["status"],
                        "ratio_naive_over_compiler": ratio,
                        "ratio_published_over_compiler": (pb["N"] / c["N"]) if (c["released"] and pb["released"]) else None}
            ok_both &= ratio is not None and ratio >= GRID_STEP
        res["improvement_rule_holds"] = ok_both
        per_dev.append(res)
    positive = any(d["improvement_rule_holds"] for d in per_dev)
    return {"rule": frozen()["primary_metric"]["g5_rule"], "primary_cell": cell, "per_device": per_dev,
            "checker_rejections_total": ctx.checker_rejections, "released_certificates": ctx.released,
            "verdict": "POSITIVE (pre-registered improvement rule met)" if positive else "NEGATIVE (rule not met on any device)"}


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    rows = list(rows)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: list[str] = []
    for r in rows:
        keys += [k for k in r if k not in keys]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: (json.dumps(v) if isinstance(v, (list, dict, tuple)) else v) for k, v in r.items()})


def run_all(out_dir: Path = OUT_DIR, *, figures: bool = True) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    sha, dirty = git_state(ROOT)
    ctx = Ctx(revision=f"{sha}{'-dirty' if dirty else ''}")
    t0 = time.perf_counter()
    timings: dict[str, float] = {}

    def timed(name: str, fn: Callable[[], Any]) -> Any:
        s = time.perf_counter()
        r = fn()
        timings[name] = round(time.perf_counter() - s, 2)
        print(f"[lane I] {name}: {timings[name]} s", file=sys.stderr, flush=True)
        return r

    ideal = timed("x12_ideal", lambda: x12_ideal(ctx))
    timed("x12_s2", lambda: x12_s2(ctx))
    agreement = timed("x12_oracle_agreement", lambda: x12_oracle_agreement(ctx))
    rejections = timed("x12_rejections", lambda: x12_rejections(ctx))
    matched = timed("x12_published_matched", lambda: x12_published_matched(ctx))
    timed("d1_matrix", lambda: d1_matrix(ctx))
    unc = timed("x13_uncertainty", lambda: x13_uncertainty(ctx))
    drift = timed("x13_drift_holdout", lambda: x13_drift_holdout(ctx, out_dir))
    fixed_n = timed("x13_fixed_n", lambda: x13_fixed_n(ctx))
    sites = timed("x13_sites", lambda: x13_sites(ctx))
    pareto = pareto_rows(ctx)
    verdict = g5_verdict(ctx)
    results = {
        "meta": {
            "lane": "I", "experiments": ["X12", "X13"], "preregistration_commit": PREREG_COMMIT,
            "frozen_experiments_sha256": file_sha256(FROZEN_PATH),
            "holdouts_sha256": file_sha256(cal.HOLDOUTS_PATH), "software_revision": ctx.revision,
            "matched_target_slack_dex": MATCH_SLACK_DEX,
            "proof_version": proof_version(), "runtime_seconds": round(time.perf_counter() - t0, 2),
            "section_seconds": timings,
            "evidence_legend": {
                "bounds": "PUBLISHED_THEOREM (W1/S1/S2, re-derived by lane D checker) | PUBLISHED_AGGREGATE (D1: never certified)",
                "devices": "DIGITIZED_FIGURE (Kent Fig.5 points) | HYPOTHETICAL (half-beta devices, interval boxes) | PHOTON_EXPERIMENT (Zenodo QBER) | PUBLISHED_AGGREGATE",
                "resources": "MODELLED: issuance = N / 1e8 Hz (HYPOTHETICAL rate); classical bits = proxy",
                "runtime_memory": "measured on this machine (wall clock, tracemalloc peak)",
            },
        },
        "x12": {"ideal": [r for r in ideal if r["selector"] != "published_fixed"],
                "oracle_agreement": agreement, "rejections_and_infeasibility": rejections,
                "published_matched": matched},
        "x13": {"uncertainty": unc, "drift_holdout": drift, "fixed_n_vs_joint": fixed_n, "sites": sites,
                "checker": {"released": ctx.released, "checker_rejections": ctx.checker_rejections,
                            "uncertified_by_construction_D1": ctx.uncertified_by_construction}},
        "g5": verdict,
        "infeasibility_certificates": ctx.infeasibility,
    }
    (out_dir / "results.json").write_text(json.dumps(results, indent=1, sort_keys=True, default=str), encoding="utf-8")
    _write_csv(out_dir / "selections.csv", ctx.rows)
    _write_csv(out_dir / "pareto_s2_certified.csv", pareto)
    _write_csv(out_dir / "d1_uncertified.csv", [r for r in ctx.rows if r["family"] == "D1"])
    _write_csv(out_dir / "oracle_agreement.csv", agreement)
    _write_csv(out_dir / "ablation_uncertainty.csv", unc)
    _write_csv(out_dir / "ablation_sites.csv", sites)
    _write_csv(out_dir / "ablation_fixed_n.csv", fixed_n)
    _write_csv(out_dir / "d1_holdout.csv", drift["holdout_runs"])
    (out_dir / "released_compiler_certificates.json").write_text(
        json.dumps(ctx.certificates, indent=1, sort_keys=True), encoding="utf-8")
    from qmint.compiler.report import write_markdown

    write_markdown(results, ctx.rows, out_dir / "results.md")
    if figures:
        from qmint.compiler.report import write_figures

        write_figures(pareto, unc, out_dir)
    return results
