"""Lane D entrypoints for ``qmint proofs ...`` and run_core (see ``qmint.core.lanes``).

    qmint proofs verify --game W1 --n 1 --method sdp --primal-dual
    qmint proofs verify --game W1_CV --n 1 --method sdp
    qmint proofs verify --game W1 --n 73 --method theorem
    qmint proofs reproduce [--out proofs/certificates]

``--method sdp`` solves lane C's Choi SDP (primal and dual, NUMERICAL_SDP), certifies lane C's
dual in exact rationals (CERTIFIED_NUMERIC), and re-verifies the bound through lane D's
independent exact code path (``qmint.proofs.sdp_exact``, which imports nothing from
``qmint.attacks``). It passes only if all agree with the published theorem value.
``--method theorem`` evaluates the registered closed form (ideal games W1, W1_CV, S1 only).
"""

from __future__ import annotations

import argparse
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

from qmint.core.contracts import PROTOCOL_GAMES, BoundRequest, GameId, SecurityAxis
from qmint.core.lanes import StageSkipped, write_stage_json
from qmint.proofs import reproduce, sdp_exact
from qmint.proofs.engine import ProofEngine
from qmint.proofs.ideal_bounds import IDEAL_BASES
from qmint.proofs.registry import default_registry

SDP_GAMES = {GameId.W1: (1, 2), GameId.W1_CV: (1,)}
TOL = 1e-6


def theorem_bound(game: GameId, n: int) -> dict[str, Any]:
    """Registered closed form via the ProofEngine (value-less UNSUPPORTED when no theorem applies)."""
    protocol = next(p for p, games in PROTOCOL_GAMES.items() if game in games)
    claim = next((c for c in default_registry().claims if c.game == game.value), None)
    params = {"n": n, "N": n, "declared_assumptions": list(claim.required_declarations) if claim else []}
    res = ProofEngine().evaluate(BoundRequest(protocol_id=protocol, game_id=game, axis=SecurityAxis.UNFORGEABILITY,
                                              parameters=params))
    return res.model_dump(mode="json")


def verify_sdp(game: GameId, n: int) -> dict[str, Any]:
    """Primal/dual SDP (lane C) + exact certificate (lane C) + independent exact recheck (lane D)."""
    from qmint.attacks import report

    if n not in SDP_GAMES.get(game, ()):
        raise ValueError(f"SDP verification supports {[(g.value, ns) for g, ns in SDP_GAMES.items()]}; "
                         f"got {game.value} n={n} (larger n: cite MVW Sec. 3.4, use --method theorem)")
    theorem = IDEAL_BASES[game][0] ** n
    if game == GameId.W1:
        sec = report.sdp_section(n, "SCS", timings=False)
        primal, dual = sec["numerical"]["primal_value"], sec["numerical"]["dual_value"]
        certified = sec["certified"]["upper_bound_float_up"]
        independent: Fraction = sdp_exact.w1_independent_upper_bound(n)
        records = sec["attack_results"]
    else:
        sec = report.w1cv_section()
        primal, dual = sec["numerical"]["primal_value"], sec["numerical"]["dual_value"]
        certified = sec["certified_upper_bound_float_up"]
        independent = sdp_exact.w1cv_independent_upper_bound()
        records = [sec["attack_result"]]
    checks = {
        "primal_matches_theorem": abs(primal - theorem) < TOL,
        "dual_matches_theorem": abs(dual - theorem) < TOL,
        "laneC_certified_upper_ge_theorem": certified >= theorem - 1e-12,
        "laneD_independent_exact_upper_ge_theorem": float(independent) >= theorem - 1e-12,
        "laneD_independent_exact_upper_tight": float(independent) - theorem < TOL,
        "laneC_certified_ge_laneD_exact": certified >= float(independent) - 1e-12,
    }
    return {
        "game": game.value, "n": n, "theorem_value": theorem,
        "sdp_primal": primal, "sdp_dual": dual, "duality_gap": dual - primal,
        "laneC_certified_upper_bound": certified,
        "laneD_independent_exact_upper_bound": str(independent),
        "evidence_kinds": {"sdp_primal/dual": "NUMERICAL_SDP", "certified": "CERTIFIED_NUMERIC",
                           "theorem": "PUBLISHED_THEOREM"},
        "checks": checks, "pass": all(checks.values()), "attack_results": records,
    }


def cli_main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="qmint proofs", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="action", required=True)
    v = sub.add_parser("verify", help="verify a bound (SDP primal-dual or registered theorem)")
    v.add_argument("--game", required=True)
    v.add_argument("--n", type=int, required=True)
    v.add_argument("--method", choices=["sdp", "theorem"], default="sdp")
    v.add_argument("--primal-dual", action="store_true", help="print primal and dual values (sdp)")
    v.add_argument("--out", type=Path, help="write the JSON result to this file")
    r = sub.add_parser("reproduce", help="reproduce every registered numerical example")
    r.add_argument("--out", default="proofs/certificates")
    a = ap.parse_args(argv[1:])
    if a.action == "reproduce":
        return reproduce.main(["--out", a.out])
    game = GameId(a.game)
    if a.method == "theorem":
        res = theorem_bound(game, a.n)
        ok = res["value"] is not None or res["log10_value"] is not None
        print(f"{game.value} n={a.n}: log10 bound={res['log10_value']} value={res['value']} "
              f"[{res['evidence_kind']}] status={res['status']} {res['notes']}")
    else:
        try:
            res = verify_sdp(game, a.n)
        except ValueError as e:
            print(f"UNSUPPORTED: {e}", file=sys.stderr)
            return 2
        ok = res["pass"]
        if a.primal_dual:
            print(f"{game.value} n={a.n}: primal={res['sdp_primal']!r} dual={res['sdp_dual']!r} "
                  f"gap={res['duality_gap']:.3e} [NUMERICAL_SDP]")
        print(f"{game.value} n={a.n}: lane C certified upper={res['laneC_certified_upper_bound']!r} "
              f"[CERTIFIED_NUMERIC]; lane D independent exact upper={res['laneD_independent_exact_upper_bound']} "
              f"[CERTIFIED_NUMERIC]; theorem={res['theorem_value']!r} [PUBLISHED_THEOREM]")
        for k, val in res["checks"].items():
            print(f"  [{'ok' if val else 'FAIL'}] {k}")
    if a.out is not None:
        write_stage_json(a.out.parent, a.out.name, res)
    return 0 if ok else 1


def run_core_stage(*, seed: int, out_dir: Path) -> dict[str, Any]:
    """reproduce.py (every registered example + checked certificates) and W1/W1_CV SDP verification."""
    del seed  # deterministic, unseeded computations
    try:
        import cvxpy  # noqa: F401
    except ImportError as e:  # optional [sdp] extra
        raise StageSkipped(f"cvxpy not installed: {e}") from e
    cert_dir = out_dir / "certificates"
    if reproduce.main(["--out", str(cert_dir)]) != 0:
        raise RuntimeError("proofs reproduce: some reproduced value disagrees with its source")
    sdp = [verify_sdp(GameId.W1, 1), verify_sdp(GameId.W1, 2), verify_sdp(GameId.W1_CV, 1)]
    if not all(r["pass"] for r in sdp):
        raise RuntimeError(f"SDP verification failed: {[(r['game'], r['n']) for r in sdp if not r['pass']]}")
    outputs = sorted(cert_dir.glob("*.json")) + [write_stage_json(out_dir, "sdp_verify.json", sdp)]
    return {"outputs": outputs}
