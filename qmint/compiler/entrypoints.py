"""Lane I entrypoints (``qmint.core.lanes`` convention): ``qmint compiler optimize|verify|experiments``.

  qmint compiler optimize --game S2 --device K22-F5a [--interval] --eps-unf 1e-9 --honest 1e-3 [--M 1]
                          [--eps-priv X] [--selector compiler] [--out cert.json]
  qmint compiler verify cert.json          re-run lane D's IndependentProofChecker on a certificate
  qmint compiler experiments [--out DIR]   full pre-registered X12/X13 run (minutes)

Exit codes: 0 = CERTIFIED (optimize/verify) or run completed (experiments); 1 = UNCERTIFIED / infeasible;
2 = usage error or unsupported combination.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from qmint.compiler.certify import certify, diagnose
from qmint.compiler.constraints import (
    Problem,
    UnsupportedCombination,
    build_grid,
    d1_device,
    ideal_device,
    make_targets,
    s2_device,
)
from qmint.compiler.experiments import d1_calibration, run_all
from qmint.compiler.scoring import Scorer
from qmint.compiler.selectors import SELECTORS
from qmint.core.contracts import CertificateStatus, GameId, SecurityCertificate
from qmint.core.serialization import canonical_json
from qmint.proofs.checker import IndependentProofChecker

EXIT_OK, EXIT_FAIL, EXIT_USAGE = 0, 1, 2


def build_problem(game: str, device: str | None, interval: bool, eps_unf: float, honest: float | None,
                  eps_priv: float | None = None, M: int = 1, small: bool = False) -> Problem:
    g = GameId(game)
    if g == GameId.S2:
        if not device:
            raise UnsupportedCombination("S2 needs --device (a frozen KLPR2022 device id)")
        return Problem(f"cli/S2/{device}", g, s2_device(device, interval=interval, M=M, beta_E=1e-3 if eps_priv else None),
                       make_targets(g, eps_unf, honest, eps_priv), build_grid("S2", small=small),
                       meta={"device": device, "uncertainty": "interval" if interval else "point", "M": M})
    if g == GameId.D1:
        if not device:
            raise UnsupportedCombination("D1 needs --device (a frozen Schiansky 2023 device id)")
        return Problem(f"cli/D1/{device}", g, d1_device(device), make_targets(g, eps_unf, honest, eps_priv),
                       build_grid("D1", small=small), calibration=d1_calibration(device), meta={"device": device})
    return Problem(f"cli/{g.value}", g, ideal_device(g), make_targets(g, eps_unf, honest, eps_priv), build_grid("ideal"),
                   meta={"device": "ideal"})


def optimize(problem: Problem, selector: str = "compiler") -> dict[str, Any]:
    sel = SELECTORS[selector](problem, Scorer())
    out: dict[str, Any] = {"scenario_id": problem.scenario_id, "selector": selector, "status": sel.status,
                           "optimality": sel.optimality, "N": sel.N, "decisions": sel.decisions, "log10_bounds": sel.logs,
                           "engine_calls": sel.engine_calls, "wall_seconds": round(sel.wall_seconds, 4), "note": sel.note}
    if sel.status == "FEASIBLE":
        o = certify(problem, sel)
        out["certificate"] = json.loads(canonical_json(o.certificate))
        out["released"] = o.released
    else:
        out["infeasibility_certificate"] = json.loads(canonical_json(diagnose(problem, note=sel.note)))
        out["released"] = False
    return out


def verify(path: Path) -> SecurityCertificate:
    data = json.loads(path.read_text(encoding="utf-8"))
    cert = SecurityCertificate.model_validate(data.get("certificate", data))
    return IndependentProofChecker().check(cert)


def cli_main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="qmint compiler", description="lane I certificate compiler")
    sub = p.add_subparsers(dest="action", required=True)
    o = sub.add_parser("optimize")
    o.add_argument("--game", required=True, choices=[g.value for g in GameId])
    o.add_argument("--device")
    o.add_argument("--interval", action="store_true", help="use the frozen HYPOTHETICAL uncertainty box (S2)")
    o.add_argument("--eps-unf", type=float, required=True)
    o.add_argument("--honest", type=float)
    o.add_argument("--eps-priv", type=float)
    o.add_argument("--M", type=int, default=1)
    o.add_argument("--selector", default="compiler", choices=sorted(SELECTORS))
    o.add_argument("--small", action="store_true", help="use the small (oracle-agreement) grid")
    o.add_argument("--out", type=Path)
    v = sub.add_parser("verify")
    v.add_argument("certificate", type=Path)
    e = sub.add_parser("experiments")
    e.add_argument("--out", type=Path)
    e.add_argument("--no-figures", action="store_true")
    args = p.parse_args(argv[1:] if argv and argv[0] == "compiler" else argv)

    if args.action == "verify":
        checked = verify(args.certificate)
        print(json.dumps({"proof_check_status": checked.proof_check_status.value, "reason": checked.reason}, indent=1))
        return EXIT_OK if checked.proof_check_status == CertificateStatus.CERTIFIED else EXIT_FAIL
    if args.action == "experiments":
        kw: dict[str, Any] = {"figures": not args.no_figures}
        res = run_all(args.out, **kw) if args.out else run_all(**kw)
        print(json.dumps(res["g5"]["verdict"]))
        return EXIT_OK
    try:
        problem = build_problem(args.game, args.device, args.interval, args.eps_unf, args.honest, args.eps_priv, args.M, args.small)
    except (UnsupportedCombination, ValueError, KeyError) as exc:
        print(f"UNSUPPORTED: {exc}", file=sys.stderr)
        return EXIT_USAGE
    out = optimize(problem, args.selector)
    text = json.dumps(out, indent=1, sort_keys=True, default=str)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text if not args.out else json.dumps({k: out[k] for k in ("status", "N", "released")}))
    return EXIT_OK if out["released"] else EXIT_FAIL


def run_core_stage(*, seed: int, out_dir: Path) -> dict[str, Any]:
    """Offline, deterministic smoke of the compiler: ideal W1/S1 and one S2 primary cell, oracle-checked."""
    out_dir.mkdir(parents=True, exist_ok=True)
    runs = {}
    for game in ("W1", "S1"):
        runs[game] = optimize(build_problem(game, None, False, 1e-9, None))
    s2 = build_problem("S2", "K22-F5a", False, 1e-9, 1e-3)
    runs["S2/K22-F5a"] = optimize(s2)
    small = build_problem("S2", "K22-F5a", False, 1e-9, 1e-3, small=True)
    c, o = SELECTORS["compiler"](small, Scorer()), SELECTORS["exhaustive_oracle"](small, Scorer(cache=False))
    summary = {"seed": seed, "released": {k: v["released"] for k, v in runs.items()},
               "N": {k: v["N"] for k, v in runs.items()},
               "small_grid_oracle_agreement": (c.status, c.idx) == (o.status, o.idx)}
    path = out_dir / "compiler_core.json"
    path.write_text(json.dumps({"summary": summary, "runs": runs}, indent=1, sort_keys=True, default=str), encoding="utf-8")
    if not all(summary["released"].values()) or not summary["small_grid_oracle_agreement"]:
        raise RuntimeError(f"compiler core stage failed: {summary}")
    return {"outputs": [str(path)], "summary": summary}
