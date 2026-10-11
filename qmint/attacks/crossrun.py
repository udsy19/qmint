"""G1 cross-implementation run: lane C attack channels against lane B's Wiesner bank.

    python -m qmint.attacks.crossrun --out handoffs/Q-G1_evidence.json [--trials 400]

Lane C built its own minimal W1 challenger (``qmint.attacks.games``) on purpose. This module
runs the SAME per-qubit Kraus channels against lane B's independent implementation
(``qmint.protocols.wiesner.WiesnerChallenger`` / ``RegisterHandle``), driven only through the
``PairChallenger`` / ``ChannelTokenHandle`` interfaces. Agreement of

  * lane B's exact pair acceptance (``pair_acceptance_probability``, factorized density matrices),
  * lane C's own exact per-position analytics (``heuristic.joint_outcome_probs``),
  * the published / derived closed forms, and
  * lane F's Qiskit cloner circuits (A03b <-> ``bruss2000``, A04 <-> ``mvw2012``)

is the cross-implementation leg of gate G1. Every per-qubit value below is state-independent
for the four BB84 states, so B's exact value for ANY minted note equals the closed form to the
n-th power. Monte Carlo rates are lower bounds on the worst-case adversary only.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import pickle
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from qmint.attacks.games import theorem_upper_bound
from qmint.attacks.heuristic import W1_PRODUCT_ATTACKS, joint_outcome_probs, mc_secret_leak_control
from qmint.attacks.records import attacks_source_sha, monte_carlo_result
from qmint.core.contracts import AttackResult, EvidenceKind, GameId, Interval, SecretBoundaryError, Unit
from qmint.core.interfaces import ChannelTokenHandle, PairChallenger
from qmint.protocols.wiesner import (
    WiesnerChallenger,
    WiesnerMode,
    forge_from_leaked_secret,
    unsafe_secret_leak_control,
)

#: Closed-form per-qubit W1 both-pass probabilities (uniform BB84 secret).
CLOSED_FORM_PER_QUBIT: dict[str, tuple[float, str]] = {
    "A01_basis_guess_resend": (5 / 8, "5/8"),
    "A01b_basis_guess_bayes_resend": ((3 + math.sqrt(5)) / 8, "(3+sqrt5)/8"),
    "A02_breidbart_resend": (5 / 8, "5/8"),
    "A02b_breidbart_bayes_resend": ((3 + math.sqrt(5)) / 8, "(3+sqrt5)/8"),
    "A03_universal_buzek_hillery": (2 / 3, "2/3"),
    "A03b_phase_covariant_xz": ((3 + 2 * math.sqrt(2)) / 8, "(3+2sqrt2)/8"),
    "A04_mvw_optimal_channel": (3 / 4, "3/4"),
}
#: Lane F cloner circuit implementing the same channel (qmint.quantum.cloner).
F_CIRCUIT_OF: dict[str, str] = {"A03b_phase_covariant_xz": "bruss2000", "A04_mvw_optimal_channel": "mvw2012"}

B_BACKEND = "qmint.protocols.register.FactorizedRegister (lane B)"
W1_RULE_B = "lane B WiesnerChallenger EXACT: projective verifier in secret basis, both candidates must pass"
AGREE_TOL = 1e-12


def _bank(seed: int) -> WiesnerChallenger:
    ch = WiesnerChallenger(mode=WiesnerMode.EXACT, seed=seed)
    if not isinstance(ch, PairChallenger):  # interface boundary, not an implementation detail
        raise TypeError("lane B challenger does not satisfy PairChallenger")
    return ch


def _split(ch: WiesnerChallenger, kraus: Sequence[np.ndarray], n: int, seed: int) -> tuple[Any, Any]:
    note = ch.mint(n, seed)
    if not isinstance(note, ChannelTokenHandle):
        raise TypeError("lane B handle does not satisfy ChannelTokenHandle")
    c1, c2 = note.split(kraus)
    return c1, c2


def b_exact_pair(kraus: Sequence[np.ndarray], n: int, seed: int) -> float:
    """Lane B's exact Pr[both candidates accepted] for one minted note under a per-qubit channel."""
    ch = _bank(seed)
    return ch.pair_acceptance_probability(*_split(ch, kraus, n, seed))


def b_monte_carlo_wins(kraus: Sequence[np.ndarray], n: int, trials: int, seed: int) -> int:
    """W1 wins over ``trials`` FRESH notes, each verified destructively by lane B's ``verify_pair``."""
    ch = _bank(seed)
    seeds = np.random.default_rng(seed).integers(0, 2**62, trials)
    return sum(all(ch.verify_pair(*_split(ch, kraus, n, int(s)))) for s in seeds)


def f_circuit_per_qubit(name: str) -> float:
    """Lane F statevector both-pass probability, averaged over the four BB84 states (n=1)."""
    from qmint.core.contracts import Basis
    from qmint.quantum.cloner import circuit_both_pass_probability

    vals = [circuit_both_pass_probability([b], [x], name) for b in (Basis.Z, Basis.X) for x in (0, 1)]  # type: ignore[arg-type]
    return float(np.mean(vals))


def f_kraus_on_b(name: str, n: int, seed: int) -> float:
    """Lane F's cloner Kraus operators executed on lane B's register (third implementation pair)."""
    from qmint.quantum.cloner import cloner_kraus

    return b_exact_pair(cloner_kraus(name), n, seed)  # type: ignore[arg-type]


def exact_record(attack_id: str, n: int, value: float, method: str, channel: str) -> AttackResult:
    """Exact (non-sampled) density-matrix success of ONE attack: SIMULATOR_IDEAL, trials=0."""
    return AttackResult(
        attack_id=f"{attack_id}@laneB_exact",
        game_id=GameId.W1,
        attack_capability=["one_note", "per_qubit_channel", "no_verifier_oracle"],
        token_n=n,
        attack_method=method,
        quantum_channel_description=channel,
        verifier_rule=W1_RULE_B,
        seed=None,
        trials=0,
        successes=0,
        success_rate_ci=Interval(lo=value, hi=value, unit=Unit.PROBABILITY, point=value),
        ci_method="exact: lane B pair_acceptance_probability (no sampling)",
        proof_applicability="IN_MODEL",
        theorem_upper_bound=theorem_upper_bound(GameId.W1, n),
        backend_kind=B_BACKEND,
        evidence_kind=EvidenceKind.SIMULATOR_IDEAL,
        source_code_sha=attacks_source_sha(),
    )


def crossrun(ns: Sequence[int] = (1, 2, 3), seeds: Sequence[int] = (0, 1, 2), trials: int = 400, seed: int = 42,
             attacks: Sequence[str] | None = None) -> dict[str, Any]:
    """Rows comparing B-exact / C-exact / closed form / F circuits, plus C3 AttackResult records."""
    rows: list[dict[str, Any]] = []
    records: list[AttackResult] = []
    for attack_id in attacks or list(CLOSED_FORM_PER_QUBIT):
        make_kraus, desc = W1_PRODUCT_ATTACKS[attack_id]
        kraus = make_kraus()
        closed, closed_txt = CLOSED_FORM_PER_QUBIT[attack_id]
        c_pp = joint_outcome_probs(kraus)["pp"]
        f_name = F_CIRCUIT_OF.get(attack_id)
        f_pp = f_circuit_per_qubit(f_name) if f_name else None
        for n in ns:
            b_vals = [b_exact_pair(kraus, n, s) for s in seeds]
            target = closed**n
            row: dict[str, Any] = {
                "attack_id": attack_id,
                "n": n,
                "closed_form": f"({closed_txt})^{n}",
                "closed_form_value": target,
                "C_exact_independent_challenger": c_pp**n,
                "B_exact_min_over_secrets": min(b_vals),
                "B_exact_max_over_secrets": max(b_vals),
                "secrets_tested": len(seeds),
                "F_circuit": None if f_pp is None else f_pp**n,
                "F_kraus_on_B_register": f_kraus_on_b(f_name, n, seeds[0]) if f_name else None,
                "evidence_kind": EvidenceKind.SIMULATOR_IDEAL.value,
            }
            cmp = [v for v in (row["C_exact_independent_challenger"], *b_vals, row["F_circuit"],
                               row["F_kraus_on_B_register"]) if v is not None]
            row["max_abs_diff_vs_closed_form"] = max(abs(v - target) for v in cmp)
            row["agrees"] = row["max_abs_diff_vs_closed_form"] <= AGREE_TOL
            channel = f"per-qubit Kraus channel C^2 -> C^2 (x) C^2 from qmint.attacks.heuristic: {desc}"
            records.append(exact_record(attack_id, n, b_vals[0], "lane C channel via RegisterHandle.split", channel))
            if trials:
                wins = b_monte_carlo_wins(kraus, n, trials, seed + n)
                rec, ci = monte_carlo_result(
                    attack_id=f"{attack_id}@laneB_mc", game_id=GameId.W1,
                    capability=["one_note", "per_qubit_channel", "no_verifier_oracle"], n=n,
                    method="lane C channel via ChannelTokenHandle.split; PairChallenger.verify_pair",
                    channel=channel, verifier_rule=W1_RULE_B, seed=seed + n, trials=trials, successes=wins,
                    applicability="IN_MODEL", theorem_bound=theorem_upper_bound(GameId.W1, n), backend_kind=B_BACKEND)
                records.append(rec)
                row["B_monte_carlo"] = {"successes": wins, "trials": trials, **ci,
                                        "ci_covers_exact": ci["clopper_pearson_lo"] <= target <= ci["clopper_pearson_hi"],
                                        "evidence_kind": EvidenceKind.MONTE_CARLO.value}
            rows.append(row)
    return {"rows": rows, "records": records}


def secret_leak_control(n: int = 4, trials: int = 50, seed: int = 42) -> dict[str, Any]:
    """TEST_ONLY negative control on both implementations: leaked secret -> success 1, OUT_OF_MODEL."""
    ch = _bank(seed)
    note = ch.mint(n, seed)
    f1, f2 = forge_from_leaked_secret(ch.leak_secret_TEST_ONLY(note), note.record)
    b_exact = ch.pair_acceptance_probability(f1, f2)
    b_mc = unsafe_secret_leak_control(n, trials, seed, source_code_sha=attacks_source_sha())
    c_wins = mc_secret_leak_control(n, trials, seed)
    return {
        "n": n,
        "B_exact_pair_acceptance": b_exact,
        "B_mc": {"successes": b_mc.successes, "trials": b_mc.trials},
        "C_mc": {"successes": c_wins, "trials": trials},
        "proof_applicability": b_mc.proof_applicability,
        "agrees": abs(b_exact - 1.0) <= AGREE_TOL and b_mc.successes == trials and c_wins == trials
        and b_mc.proof_applicability == "OUT_OF_MODEL",
        "record": b_mc,
    }


def secret_boundary_checks() -> dict[str, bool]:
    """Lane B secret boundary, re-checked live through the public surface only."""
    ch = _bank(7)
    note = ch.mint(4, 7)

    def refuses(fn: Callable[[], object]) -> bool:
        try:
            fn()
        except SecretBoundaryError:
            return True
        return False

    public = {a for a in dir(note) if not a.startswith("_")}
    return {
        "challenger_refuses_deepcopy": refuses(lambda: copy.deepcopy(ch)),
        "challenger_refuses_copy": refuses(lambda: copy.copy(ch)),
        "challenger_refuses_pickle": refuses(lambda: pickle.dumps(ch)),
        "handle_has_no_secret_attributes": not public & {"bases", "bits", "secret", "issuer_secret"},
        "record_has_no_bases_or_bits": not {"bases", "bits"} & set(note.record.model_dump()),
    }


def g1_evidence(trials: int = 400, seed: int = 42) -> dict[str, Any]:
    """All G1 legs, recomputed live (each with its evidence kind)."""
    from qmint.attacks import certify, coherent_sdp
    from qmint.proofs import sdp_exact
    from qmint.quantum.evidence import three_way_agreement

    rep = coherent_sdp.solve_w1(1, "SCS")
    cert = certify.certify_w1_dual(rep.Y, 1, rep.dual_value)
    d_ub = sdp_exact.w1_independent_upper_bound(1)
    tw = three_way_agreement()
    tw_max = max(max(r["max_abs_diff_qiskit_numpy"], r["max_abs_diff_qutip_numpy"],
                     r.get("max_abs_diff_analytic_numpy", 0.0)) for r in tw)
    cr = crossrun(trials=trials, seed=seed)
    leak = secret_leak_control(seed=seed)
    boundary = secret_boundary_checks()
    checks = {
        "C_sdp_n1": {
            "lane": "C", "primal": rep.primal_value, "dual": rep.dual_value,
            "certified_upper_bound_float_up": cert.bound_float_up, "theorem": 0.75,
            "evidence_kind": "NUMERICAL_SDP + CERTIFIED_NUMERIC",
            "pass": abs(rep.primal_value - 0.75) < 1e-6 and abs(rep.dual_value - 0.75) < 1e-6
            and 0.75 <= cert.bound_float_up < 0.75 + 1e-8,
        },
        "D_independent_exact_recheck": {
            "lane": "D", "exact_upper_bound_n1": str(d_ub), "evidence_kind": "CERTIFIED_NUMERIC (exact rational)",
            "pass": str(d_ub) == "3/4" and cert.bound_float_up >= float(d_ub),
        },
        "F_bb84_three_way_agreement": {
            "lane": "F", "cases": len(tw), "max_abs_diff": tw_max,
            "evidence_kind": "SIMULATOR_IDEAL / SIMULATOR_NOISY", "pass": tw_max < 1e-12,
        },
        "B_secret_boundary": {"lane": "B", **boundary, "pass": all(boundary.values())},
        "Q_cross_implementation": {
            "lane": "Q", "rows": len(cr["rows"]), "max_abs_diff": max(r["max_abs_diff_vs_closed_form"] for r in cr["rows"]),
            "mc_ci_cover_exact": sum(r["B_monte_carlo"]["ci_covers_exact"] for r in cr["rows"] if "B_monte_carlo" in r),
            "evidence_kind": "SIMULATOR_IDEAL (exact) + MONTE_CARLO",
            "pass": all(r["agrees"] for r in cr["rows"]),
        },
        "Q_secret_leak_control": {k: v for k, v in leak.items() if k != "record"} | {"pass": leak["agrees"]},
    }
    return {
        "gate": "G1",
        "lane": "Q",
        "claim_scope": "W1 (MVW 2012 simple counterfeiting) only; no transfer to W1_CV/W2/S*/D1",
        "source_code_sha": attacks_source_sha(),
        "checks": checks,
        "all_pass": all(c["pass"] for c in checks.values()),
        "crossrun_rows": cr["rows"],
        "attack_results": [json.loads(r.model_dump_json()) for r in [*cr["records"], leak["record"]]],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=Path("handoffs/Q-G1_evidence.json"))
    ap.add_argument("--trials", type=int, default=400)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args(argv)
    ev = g1_evidence(a.trials, a.seed)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(ev, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for name, c in ev["checks"].items():
        print(f"[{'PASS' if c['pass'] else 'FAIL'}] {name}")
    return 0 if ev["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
