"""Lane B entrypoints for ``qmint simulate ...`` and run_core (see ``qmint.core.lanes``).

    qmint simulate wiesner --n 16 --honest-runs 10000 --attack measure-resend --seed 41
    qmint simulate smoney --protocol kent_2022 --scheme IQT1 --N 64 --runs 20 --sites 2
    qmint simulate schiansky --ell 4 --N 8 --runs 8

Honest acceptance counts come from the simulated register (SIMULATOR_IDEAL / SIMULATOR_NOISY).
Attack rates are MONTE_CARLO (a LOWER bound on the worst-case adversary) plus the exact
density-matrix value of that one attack; the W1 theorem value is printed only for game W1.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import binom

from qmint.attacks.stats import clopper_pearson_interval
from qmint.core.contracts import EvidenceKind, GameId
from qmint.core.lanes import write_stage_json
from qmint.protocols import kent_smoney_2022 as kent
from qmint.protocols import schiansky_payment_2023 as sch
from qmint.protocols.wiesner import NoiseModel, WiesnerChallenger, WiesnerMode

#: CLI attack names -> lane C per-qubit W1 attack ids (qmint.attacks.heuristic.W1_PRODUCT_ATTACKS).
WIESNER_ATTACKS = {
    "measure-resend": "A01_basis_guess_resend",
    "measure-resend-bayes": "A01b_basis_guess_bayes_resend",
    "breidbart": "A02_breidbart_resend",
    "breidbart-bayes": "A02b_breidbart_bayes_resend",
    "universal-cloner": "A03_universal_buzek_hillery",
    "phase-covariant-cloner": "A03b_phase_covariant_xz",
    "mvw-optimal": "A04_mvw_optimal_channel",
}
SCHIANSKY_TIMES = {"issue": 0.0, "pay": 10.0, "to_merchant": 20.0, "forward": 30.0, "verify": 40.0}


def _rate(successes: int, trials: int, kind: EvidenceKind) -> dict[str, Any]:
    lo, hi = clopper_pearson_interval(successes, trials)
    return {"successes": successes, "trials": trials, "rate": successes / trials,
            "clopper_pearson_95": [lo, hi], "evidence_kind": kind.value}


def honest_wiesner(n: int, runs: int, seed: int, *, mode: str = "exact", noise: str | None = None,
                   threshold: int | None = None) -> dict[str, Any]:
    """Mint ``runs`` fresh notes and verify each honestly at lane B's bank."""
    nm = None
    if noise:
        kind, p = noise.split(":")
        nm = NoiseModel(kind, float(p))  # type: ignore[arg-type]
    ch = WiesnerChallenger(mode=WiesnerMode(mode), noise=nm, threshold=threshold, seed=seed)
    seeds = np.random.default_rng(seed).integers(0, 2**62, runs)
    ok = sum(ch.verify(ch.mint(n, int(s))) for s in seeds)
    expected = 1.0 if nm is None else (
        float(binom.cdf(ch.threshold, n, nm.p / 2)) if nm.kind == "depolarizing" else None)
    kind = EvidenceKind.SIMULATOR_NOISY if nm else EvidenceKind.SIMULATOR_IDEAL
    return {"protocol_id": ch.protocol_id, "game": ch.spec.adversary_game_id.value, "n": n, "mode": mode,
            "noise": noise, "threshold": ch.threshold, "honest": _rate(ok, runs, kind),
            "honest_expected_exact": expected}


def attack_wiesner(n: int, attack: str, runs: int, seed: int) -> dict[str, Any]:
    """Lane C per-qubit attack against lane B's bank: exact value + Monte Carlo + C3 record."""
    from qmint.attacks import crossrun
    from qmint.attacks.games import theorem_upper_bound
    from qmint.attacks.heuristic import W1_PRODUCT_ATTACKS
    from qmint.attacks.records import monte_carlo_result

    attack_id = WIESNER_ATTACKS[attack]
    make_kraus, desc = W1_PRODUCT_ATTACKS[attack_id]
    kraus = make_kraus()
    wins = crossrun.b_monte_carlo_wins(kraus, n, runs, seed)
    rec, _ = monte_carlo_result(
        attack_id=f"{attack_id}@laneB_mc", game_id=GameId.W1,
        capability=["one_note", "per_qubit_channel", "no_verifier_oracle"], n=n,
        method="per-qubit channel via ChannelTokenHandle.split; PairChallenger.verify_pair", channel=desc,
        verifier_rule=crossrun.W1_RULE_B, seed=seed, trials=runs, successes=wins, applicability="IN_MODEL",
        theorem_bound=theorem_upper_bound(GameId.W1, n), backend_kind=crossrun.B_BACKEND)
    return {"attack": attack, "attack_id": attack_id, "n": n,
            "exact_success_this_attack": crossrun.b_exact_pair(kraus, n, seed),
            "monte_carlo": _rate(wins, runs, EvidenceKind.MONTE_CARLO),
            "w1_theorem_upper_bound": theorem_upper_bound(GameId.W1, n),
            "note": "MC is a lower bound on the worst-case adversary for W1 only", "record": rec}


def honest_kent(scheme: str, N: int, runs: int, seed: int, *, gamma_det: float = 0.3, gamma_err: float = 0.1,
                p_det: float = 1.0, error: float = 0.0) -> dict[str, Any]:
    """Kent et al. 2022 two-site S-money, honest Alice presenting at a random site b."""
    s_ = kent.KentScheme(scheme)
    params = kent.KentParams(s_, N) if s_.ideal else kent.KentParams(s_, N, gamma_det=gamma_det, gamma_err=gamma_err)
    rng = np.random.default_rng(seed)
    ok = double = 0
    for i in range(runs):
        sess = kent.KentSMoneySession(params, seed=seed + 2 * i)
        alice = kent.HonestAlice(sess, seed=seed + 2 * i + 1,
                                 channel=kent.HonestChannel(p_det, error) if not s_.ideal else kent.HonestChannel())
        ok += bool(alice.run(int(rng.integers(0, 2)), kent.monotone_times()))
        double += bool(sess.double_presentation_accepted())
    kind = EvidenceKind.SIMULATOR_IDEAL if (p_det == 1.0 and error == 0.0) else EvidenceKind.SIMULATOR_NOISY
    return {"protocol_id": params.protocol_id, "scheme": s_.value, "N": N, "sites": 2,
            "honest": _rate(ok, runs, kind), "double_presentation_accepted": double}


def honest_schiansky(ell: int, N: int, runs: int, seed: int) -> dict[str, Any]:
    """Schiansky et al. 2023 quantum-digital payment, honest client and ideal verification rule."""
    ok = 0
    for i in range(runs):
        system = sch.SchianskyPaymentSystem(ell=ell, N=N, merchants=(3, 5, 9), rule=sch.IdealRule(), seed=seed + i)
        system.open_account("cid-1", -100.0)
        ok += bool(system.honest_payment("cid-1", 5, SCHIANSKY_TIMES, rng_seed=seed + i).accepted)
    return {"protocol_id": sch.SCHIANSKY_SPEC.protocol_id, "ell": ell, "N": N,
            "honest": _rate(ok, runs, EvidenceKind.SIMULATOR_IDEAL)}


# ----------------------------------------------------------------------------- CLI / stages


def _emit(obj: dict[str, Any], out: Path | None) -> None:
    if out is not None:
        write_stage_json(out.parent, out.name, obj)
    print(json.dumps(json.loads(json.dumps(obj, default=lambda o: o.model_dump(mode="json"))), indent=2,
                     sort_keys=True))


def cli_main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="qmint simulate", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("wiesner", help="Wiesner money (W1 ideal; W2 with --noise/--threshold)")
    w.add_argument("--n", type=int, default=16)
    w.add_argument("--honest-runs", type=int, default=1000)
    w.add_argument("--attack", choices=["none", *WIESNER_ATTACKS], default="none")
    w.add_argument("--attack-runs", type=int, default=1000)
    w.add_argument("--mode", choices=[m.value for m in WiesnerMode], default="exact")
    w.add_argument("--noise", help="KIND:P with KIND in depolarizing|bit_flip (game W2)")
    w.add_argument("--threshold", type=int, help="W2 error threshold (required with --noise)")
    s = sub.add_parser("smoney", help="Kent et al. 2022 two-site S-money")
    s.add_argument("--protocol", choices=["kent_2022"], default="kent_2022")
    s.add_argument("--scheme", choices=[k.value for k in kent.KentScheme], default="IQT1")
    s.add_argument("--sites", type=int, default=2, choices=[2], help="only the published two-site scheme")
    s.add_argument("--N", type=int, default=64)
    s.add_argument("--runs", type=int, default=20)
    s.add_argument("--gamma-det", type=float, default=0.3)
    s.add_argument("--gamma-err", type=float, default=0.1)
    s.add_argument("--p-det", type=float, default=1.0)
    s.add_argument("--error", type=float, default=0.0)
    p = sub.add_parser("schiansky", help="Schiansky et al. 2023 quantum-digital payments")
    p.add_argument("--ell", type=int, default=4)
    p.add_argument("--N", type=int, default=8)
    p.add_argument("--runs", type=int, default=8)
    for sp in (w, s, p):
        sp.add_argument("--seed", type=int, default=42)
        sp.add_argument("--out", type=Path, help="also write the JSON result to this file")
    a = ap.parse_args(argv[1:])
    try:
        if a.cmd == "wiesner":
            if (a.noise is None) != (a.threshold is None):
                ap.error("--noise and --threshold go together (game W2)")
            res: dict[str, Any] = {"wiesner": honest_wiesner(a.n, a.honest_runs, a.seed, mode=a.mode, noise=a.noise,
                                                             threshold=a.threshold)}
            if a.attack != "none":
                if a.noise is not None:
                    ap.error("--attack is the W1 (noiseless) game only; no W2 attack theorem is assumed")
                res["attack"] = attack_wiesner(a.n, a.attack, a.attack_runs, a.seed + 1)
        elif a.cmd == "smoney":
            res = {"smoney": honest_kent(a.scheme, a.N, a.runs, a.seed, gamma_det=a.gamma_det,
                                         gamma_err=a.gamma_err, p_det=a.p_det, error=a.error)}
        else:
            res = {"schiansky": honest_schiansky(a.ell, a.N, a.runs, a.seed)}
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    _emit(res, a.out)
    return 0


def run_core_stage(*, seed: int, out_dir: Path) -> dict[str, Any]:
    """Small honest runs of every lane-B protocol plus one W1 attack (offline, seeded)."""
    res = {
        "wiesner_W1_honest": honest_wiesner(16, 200, seed),
        "wiesner_W2_depolarizing_honest": honest_wiesner(16, 200, seed, noise="depolarizing:0.05", threshold=1),
        "wiesner_W1_measure_resend": attack_wiesner(4, "measure-resend", 200, seed + 1),
        "kent_2022": [honest_kent(k.value, 32, 5, seed) for k in kent.KentScheme],
        "schiansky_2023": honest_schiansky(4, 8, 4, seed),
    }
    bad = [k for k in ("wiesner_W1_honest",) if res[k]["honest"]["successes"] != res[k]["honest"]["trials"]]
    bad += [r["scheme"] for r in res["kent_2022"] if r["honest"]["successes"] != r["honest"]["trials"]]
    if res["schiansky_2023"]["honest"]["rate"] != 1.0:
        bad.append("schiansky")
    if bad:
        raise RuntimeError(f"ideal honest runs rejected: {bad}")
    return {"outputs": [write_stage_json(out_dir, "protocols_core.json", res)]}
