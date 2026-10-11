"""Lane C entrypoints for ``qmint attacks ...`` and run_core (see ``qmint.core.lanes``).

    qmint attacks run --suite optimal-small --game W1 [--trials 200] [--seed 42] [--out experiments/results]
    qmint attacks run --suite optimal-small --game W1_CV
    qmint attacks run --suite crossrun --game W1
    qmint attacks g1-evidence --out handoffs/Q-G1_evidence.json

Suites (game W1 unless stated):
  optimal-small  W1: Choi SDP n=1 (NUMERICAL_SDP + CERTIFIED_NUMERIC), Monte Carlo of every per-qubit
                 attack at n=1,2 on lane C's own challenger, and the same channels on lane B's bank.
                 W1_CV: POVM SDP n=1 with certified dual.
  crossrun       W1: lane C channels on lane B's Wiesner bank vs C's exact values and lane F circuits.
Other games have no attack suite here (no W1 theorem transfer): exit 2.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from qmint.attacks import crossrun, report
from qmint.core.contracts import GameId
from qmint.core.lanes import write_stage_json

SUITES: dict[str, tuple[GameId, ...]] = {"optimal-small": (GameId.W1, GameId.W1_CV), "crossrun": (GameId.W1,)}


def run_suite(suite: str, game: GameId, *, trials: int, seed: int) -> dict[str, Any]:
    """Deterministic for fixed (suite, game, trials, seed); every number carries its evidence kind."""
    if game not in SUITES[suite]:
        raise ValueError(f"suite {suite!r} has no attacks for game {game.value}; supported: "
                         f"{[g.value for g in SUITES[suite]]}")
    out: dict[str, Any] = {"suite": suite, "game": game.value, "trials": trials, "seed": seed,
                           "monte_carlo_semantics": "lower bound on the worst-case adversary only"}
    if suite == "optimal-small" and game == GameId.W1_CV:
        out["w1_cv_sdp_n1"] = report.w1cv_section()
        return out
    cr = crossrun.crossrun(ns=(1, 2), seeds=(0, 1), trials=trials, seed=seed)
    out["crossrun_laneB"] = {"rows": cr["rows"], "attack_results": cr["records"]}
    if suite == "optimal-small":
        out["w1_sdp_n1"] = report.sdp_section(1, "SCS", timings=False)
        out["w1_monte_carlo_laneC"] = report.w1_mc_section(trials, seed, ns=(1, 2))
    return out


def summary_lines(res: dict[str, Any]) -> list[str]:
    lines = []
    if "w1_sdp_n1" in res:
        s = res["w1_sdp_n1"]
        lines.append(f"W1 n=1 SDP primal={s['numerical']['primal_value']:.12f} dual={s['numerical']['dual_value']:.12f}"
                     f" [NUMERICAL_SDP]; certified upper={s['certified']['upper_bound_float_up']!r} [CERTIFIED_NUMERIC]")
    if "w1_cv_sdp_n1" in res:
        s = res["w1_cv_sdp_n1"]
        lines.append(f"W1_CV n=1 SDP primal={s['numerical']['primal_value']:.12f}; certified upper="
                     f"{s['certified_upper_bound_float_up']!r} [CERTIFIED_NUMERIC]; theorem={s['theorem_value']!r}")
    for r in res.get("crossrun_laneB", {}).get("rows", []):
        lines.append(f"{r['attack_id']:<32} n={r['n']} exact(B)={r['B_exact_min_over_secrets']:.12f} "
                     f"closed={r['closed_form_value']:.12f} agrees={r['agrees']} [SIMULATOR_IDEAL]")
    return lines


def cli_main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="qmint attacks", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="action", required=True)
    r = sub.add_parser("run", help="run an attack suite")
    r.add_argument("--suite", choices=sorted(SUITES), required=True)
    r.add_argument("--game", required=True, help="game id, e.g. W1 or W1_CV")
    r.add_argument("--trials", type=int, default=200)
    r.add_argument("--seed", type=int, default=42)
    r.add_argument("--out", type=Path, help="directory for the JSON result")
    g = sub.add_parser("g1-evidence", help="write the G1 cross-implementation evidence JSON")
    g.add_argument("--out", type=Path, default=Path("handoffs/Q-G1_evidence.json"))
    g.add_argument("--trials", type=int, default=400)
    g.add_argument("--seed", type=int, default=42)
    a = ap.parse_args(argv[1:])
    if a.action == "g1-evidence":
        return crossrun.main(["--out", str(a.out), "--trials", str(a.trials), "--seed", str(a.seed)])
    try:
        res = run_suite(a.suite, GameId(a.game), trials=a.trials, seed=a.seed)
    except ValueError as e:
        print(f"UNSUPPORTED: {e}", file=sys.stderr)
        return 2
    print("\n".join(summary_lines(res)))
    if a.out is not None:
        path = write_stage_json(a.out, f"attacks_{a.suite}_{a.game}_seed{a.seed}.json", res)
        print(f"wrote {path}")
    agree = all(r["agrees"] for r in res.get("crossrun_laneB", {}).get("rows", []))
    return 0 if agree else 1


def run_core_stage(*, seed: int, out_dir: Path) -> dict[str, Any]:
    """SDP n=1 (W1, W1_CV) + small Monte Carlo suite + lane-B cross-run; FAIL on any disagreement."""
    w1 = run_suite("optimal-small", GameId.W1, trials=200, seed=seed)
    cv = run_suite("optimal-small", GameId.W1_CV, trials=0, seed=seed)
    bad = [r["attack_id"] for r in w1["crossrun_laneB"]["rows"] if not r["agrees"]]
    if abs(w1["w1_sdp_n1"]["numerical"]["primal_value"] - 0.75) > 1e-6:
        bad.append("w1_sdp_n1")
    if bad:
        raise RuntimeError(f"attack results disagree with independent values: {bad}")
    return {"outputs": [write_stage_json(out_dir, "attacks_optimal_small_W1.json", w1),
                        write_stage_json(out_dir, "attacks_optimal_small_W1_CV.json", cv)]}
