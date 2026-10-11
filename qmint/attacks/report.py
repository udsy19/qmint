"""Generate lane C evidence: ``python -m qmint.attacks.report --out handoffs/C-C1-evidence.json``.

Every number in the output carries its evidence kind. Monte Carlo rates are LOWER bounds on
the worst-case adversary; NUMERICAL_SDP values are solver output; CERTIFIED_NUMERIC values
are exactly verified dual-feasible upper bounds for the stated finite-dimensional game.
"""

from __future__ import annotations

import argparse
import json
import platform
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import cvxpy
import numpy as np

from qmint.attacks import certify, coherent_sdp, heuristic
from qmint.attacks.games import MVW_SOURCE, theorem_upper_bound
from qmint.attacks.records import attacks_source_sha, monte_carlo_result, sdp_result
from qmint.core.contracts import EvidenceKind, GameId
from qmint.core.serialization import canonical_json

W1_RULE = "exact projective BB84 verifier on every position; both candidates must pass"


#: SDPReport fields that vary run to run (wall time / memory); dropped when ``timings=False``.
TIMING_KEYS = ("primal_time_s", "dual_time_s", "peak_rss_mb")


def sdp_section(n: int, solver: str, *, timings: bool = True) -> dict[str, Any]:
    """W1 Choi SDP for n: numerical (NUMERICAL_SDP) + exact-certified dual (CERTIFIED_NUMERIC) records.

    ``timings=False`` gives byte-deterministic output for a fixed solver (run_core)."""
    rep = coherent_sdp.solve_w1(n, solver)
    cert = certify.certify_w1_dual(rep.Y, n, rep.dual_value)
    lower = certify.exact_choi_value_of_mvw_channel(n)
    num = sdp_result(
        attack_id=f"A04_choi_sdp_n{n}",
        game_id=GameId.W1,
        n=n,
        verifier_rule=W1_RULE,
        primal=rep.primal_value,
        dual=rep.dual_value,
        dual_residual=max(0.0, -rep.dual_slack_min_eig),
        primal_residual=max(rep.tp_residual, max(0.0, -rep.j_min_eig)),
        solver=f"cvxpy {cvxpy.__version__} / {solver}",
        applicability="IN_MODEL",
        theorem_bound=theorem_upper_bound(GameId.W1, n),
        evidence=EvidenceKind.NUMERICAL_SDP,
    )
    cer = sdp_result(
        attack_id=f"A04_choi_sdp_n{n}_certified_dual",
        game_id=GameId.W1,
        n=n,
        verifier_rule=W1_RULE,
        primal=float(lower),
        dual=cert.bound_float_up,
        dual_residual=0.0,
        primal_residual=0.0,
        solver=f"exact Fraction LDL^T on rounded {solver} dual + delta*I",
        applicability="IN_MODEL",
        theorem_bound=theorem_upper_bound(GameId.W1, n),
        evidence=EvidenceKind.CERTIFIED_NUMERIC,
    )
    drop = ("J", "Y") if timings else ("J", "Y", *TIMING_KEYS)
    d = {k: v for k, v in asdict(rep).items() if k not in drop}
    return {
        "numerical": d,
        "certified": {
            "upper_bound_exact": f"{cert.bound.numerator}/{cert.bound.denominator}",
            "upper_bound_float_up": cert.bound_float_up,
            "delta_shift": float(cert.delta),
            "min_exact_pivot": float(cert.min_pivot),
            "attempts": cert.attempts,
            "imag_part_dropped_norm": cert.imag_part_dropped_norm,
            "exact_lower_bound_from_mvw_channel": str(lower),
            "evidence_kind": "CERTIFIED_NUMERIC (upper) / exact achieving channel (lower)",
        },
        "attack_results": [json.loads(canonical_json(num)), json.loads(canonical_json(cer))],
    }


def w1cv_section(solver: str = "SCS") -> dict[str, Any]:
    """W1_CV n=1 POVM SDP with exact-certified dual (CERTIFIED_NUMERIC record)."""
    cv = coherent_sdp.solve_w1cv_n1(solver)
    cvc = certify.certify_w1cv_dual(cv.Y, cv.dual_value)
    return {
        "numerical": {k: v for k, v in asdict(cv).items() if k != "Y"},
        "certified_upper_bound_float_up": cvc.bound_float_up,
        "theorem_value": theorem_upper_bound(GameId.W1_CV, 1),
        "attack_result": json.loads(
            canonical_json(
                sdp_result(
                    attack_id="W1CV_povm_sdp_n1",
                    game_id=GameId.W1_CV,
                    n=1,
                    verifier_rule="classical challenge c in {Z,X}^2 per round; answer valid iff basis mismatch or correct bit",
                    primal=cv.primal_value,
                    dual=cvc.bound_float_up,
                    dual_residual=0.0,
                    primal_residual=max(cv.povm_completeness_residual, max(0.0, -cv.povm_min_eig)),
                    solver="cvxpy/SCS + exact Fraction LDL^T",
                    applicability="IN_MODEL",
                    theorem_bound=theorem_upper_bound(GameId.W1_CV, 1),
                    evidence=EvidenceKind.CERTIFIED_NUMERIC,
                    channel="per challenge pair POVM {X_a1a2} (MVW Sec. 4.1 block-diagonal reduction)",
                )
            )
        ),
    }


def w1_mc_section(trials: int, seed: int, ns: tuple[int, ...] = (1, 2, 4, 8)) -> list[dict[str, Any]]:
    """Monte Carlo of every per-qubit W1 attack on lane C's own challenger (lower bounds), with exact values."""
    mc: list[dict[str, Any]] = []
    for idx, (aid, (fk, desc)) in enumerate(heuristic.W1_PRODUCT_ATTACKS.items()):
        kr = fk()
        for n in ns:
            s = seed + 1000 * idx + n
            wins = heuristic.mc_w1_product_attack(kr, n, trials, s)
            rec, ci = monte_carlo_result(
                attack_id=aid,
                game_id=GameId.W1,
                capability=["one_note", "per_qubit_channel", "no_verifier_oracle"],
                n=n,
                method=desc,
                channel=f"i.i.d. per-qubit Kraus channel C^2 -> C^2 (x) C^2 ({len(kr)} Kraus ops)",
                verifier_rule=W1_RULE,
                seed=s,
                trials=trials,
                successes=wins,
                applicability="IN_MODEL",
                theorem_bound=theorem_upper_bound(GameId.W1, n),
            )
            exact = heuristic.w1_product_exact(kr, n)
            mc.append(
                {
                    "record": json.loads(canonical_json(rec)),
                    "exact_analytic": exact,
                    "ci_covers_exact": ci["clopper_pearson_lo"] <= exact <= ci["clopper_pearson_hi"],
                    **ci,
                }
            )
    return mc


def build(trials: int, seed: int, clarabel_n2: bool) -> dict[str, Any]:
    t0 = time.time()
    out: dict[str, Any] = {
        "lane": "C",
        "source": MVW_SOURCE,
        "source_code_sha": attacks_source_sha(),
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "cvxpy": cvxpy.__version__},
        "g_constructions_max_abs_diff": {
            str(n): float(np.abs(coherent_sdp.w1_objective_numpy(n) - coherent_sdp.w1_objective_qutip(n)).max())
            for n in (1, 2)
        },
    }
    sdp: dict[str, Any] = {}
    for n in (1, 2):
        for solver in coherent_sdp.SOLVERS:
            if n == 2 and solver == "CLARABEL" and not clarabel_n2:
                sdp[f"n{n}_{solver}"] = {"status": "NOT_RUN (pass --clarabel-n2; ~6 GB peak RSS observed)"}
                continue
            sdp[f"n{n}_{solver}"] = sdp_section(n, solver)
    try:
        coherent_sdp.solve_w1(3)
    except coherent_sdp.SDPSizeUnsupported as e:
        sdp["n3"] = {"status": "UNSUPPORTED", "reason": str(e), "general_n": "MVW Sec. 3.4 (cited theorem, not computed)"}
    out["w1_sdp"] = sdp

    out["w1_cv_n1"] = w1cv_section()

    out["negative_controls"] = [asdict(c) for c in coherent_sdp.run_negative_controls("SCS")]

    out["w1_monte_carlo"] = w1_mc_section(trials, seed)

    # ---- A06 toy W2 ----
    a06 = []
    for n, lf, ef in ((8, 0.5, 0.0), (8, 0.25, 0.125), (16, 0.25, 0.125), (8, 0.0, 0.125)):
        k = heuristic.a06_plan(n, lf)
        s = seed + 50000 + n
        wins = heuristic.mc_a06_split_loss(n, lf, ef, trials, s)
        rec, ci = monte_carlo_result(
            attack_id="A06_split_and_report_loss",
            game_id=GameId.W2,
            capability=["one_note", "per_qubit_channel", "selective_loss_reporting", "no_verifier_oracle"],
            n=n,
            method=f"{k} positions original->copy1 (copy2 reports lost), {k} original->copy2, rest MVW clone",
            channel="position-dependent Kraus channels; loss flags fixed before verification",
            verifier_rule=f"toy W2: accept iff lost<=floor({lf}n) and errors<=floor({ef}*reported)",
            seed=s,
            trials=trials,
            successes=wins,
            applicability="NO_THEOREM",
            theorem_bound=None,
        )
        exact = heuristic.a06_exact(n, k, lf, ef)
        a06.append(
            {
                "record": json.loads(canonical_json(rec)),
                "exact_analytic": exact,
                "w1_value_for_contrast_only": 0.75**n,
                "honest_acceptance_eta0.1_q0.02": heuristic.honest_acceptance_w2(n, 0.1, 0.02, lf, ef),
                "ci_covers_exact": ci["clopper_pearson_lo"] <= exact <= ci["clopper_pearson_hi"],
                **ci,
            }
        )
    out["a06_toy_w2"] = a06

    # ---- A08 leaky oracle, OUT_OF_MODEL ----
    a08 = []
    for n, r in ((4, 10), (8, 10)):
        s = seed + 60000 + n
        a8_trials = max(200, trials // 10)
        st = heuristic.mc_a08_oracle(n, r, a8_trials, s)
        rec, ci = monte_carlo_result(
            attack_id="A08_adaptive_oracle_probe",
            game_id=GameId.W1,
            capability=["one_note", "accept_reject_oracle", "note_returned_after_query", "repeated_queries"],
            n=n,
            method=f"swap one position for a Z/X probe, read accept bit, {r} Z-probes + 1 X-probe max per position",
            channel="detach/attach per position; attacker-prepared probes",
            verifier_rule="toy leaky verifier: reveals accept/reject and returns post-measurement note",
            seed=s,
            trials=a8_trials,
            successes=st.wins,
            applicability="OUT_OF_MODEL",
            theorem_bound=None,
        )
        exact = heuristic.a08_exact(n, r)
        a08.append(
            {
                "record": json.loads(canonical_json(rec)),
                "exact_analytic": exact,
                "mean_oracle_queries": st.mean_queries,
                "w1_value_for_contrast_only": 0.75**n,
                "ci_covers_exact": ci["clopper_pearson_lo"] <= exact <= ci["clopper_pearson_hi"],
                **ci,
            }
        )
    out["a08_oracle_out_of_model"] = a08

    # ---- secret leak control and honest acceptance ----
    n = 8
    wins = heuristic.mc_secret_leak_control(n, 1000, seed + 70000)
    rec, ci = monte_carlo_result(
        attack_id="CTRL_secret_basis_leak",
        game_id=GameId.W1,
        capability=["one_note", "issuer_secret_revealed"],
        n=n,
        method="prepare two perfect copies from leaked bases/bits",
        channel="none (classical preparation)",
        verifier_rule=W1_RULE,
        seed=seed + 70000,
        trials=1000,
        successes=wins,
        applicability="OUT_OF_MODEL",
        theorem_bound=None,
    )
    out["ctrl_secret_leak"] = {"record": json.loads(canonical_json(rec)), **ci}
    hon = heuristic.honest_acceptance_mc(8, 1000, seed + 80000)
    out["honest_acceptance_w1_n8"] = {"accepted": hon, "trials": 1000, "evidence_kind": "SIMULATOR_IDEAL"}
    out["wall_time_s"] = time.time() - t0
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--trials", type=int, default=10000)
    p.add_argument("--seed", type=int, default=20261011)
    p.add_argument("--clarabel-n2", action="store_true")
    a = p.parse_args()
    data = build(a.trials, a.seed, a.clarabel_n2)
    a.out.write_text(json.dumps(data, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(f"wrote {a.out} in {data['wall_time_s']:.1f}s")


if __name__ == "__main__":
    main()
