"""Builders for frozen C3 ``AttackResult`` records emitted by lane C."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from qmint.attacks.stats import clopper_pearson_interval, wilson_interval
from qmint.core.contracts import AttackResult, EvidenceKind, GameId, Interval, Unit
from qmint.core.serialization import sha256_hex

CI_METHOD = "Clopper-Pearson exact two-sided 95% (Wilson 95% also reported in evidence JSON)"


@lru_cache(maxsize=1)
def attacks_source_sha() -> str:
    """SHA-256 over the sorted (path, contents) of every qmint/attacks/*.py source file."""
    root = Path(__file__).resolve().parent
    blob = "".join(f"{p.name}\n{p.read_text(encoding='utf-8')}\n" for p in sorted(root.glob("*.py")))
    return sha256_hex(blob)


def monte_carlo_result(
    *,
    attack_id: str,
    game_id: GameId,
    capability: list[str],
    n: int,
    method: str,
    channel: str,
    verifier_rule: str,
    seed: int,
    trials: int,
    successes: int,
    applicability: str,
    theorem_bound: float | None,
) -> tuple[AttackResult, dict[str, float]]:
    """MONTE_CARLO record (a LOWER bound on worst-case attack success, never an upper bound)."""
    lo, hi = clopper_pearson_interval(successes, trials)
    wlo, whi = wilson_interval(successes, trials)
    p = successes / trials
    rec = AttackResult(
        attack_id=attack_id,
        game_id=game_id,
        attack_capability=capability,
        token_n=n,
        attack_method=method,
        quantum_channel_description=channel,
        verifier_rule=verifier_rule,
        seed=seed,
        trials=trials,
        successes=successes,
        success_rate_ci=Interval(lo=lo, hi=hi, unit=Unit.PROBABILITY, point=p),
        ci_method=CI_METHOD,
        proof_applicability=applicability,  # type: ignore[arg-type]
        theorem_upper_bound=theorem_bound,
        backend_kind="numpy_density_matrix_position_product",
        evidence_kind=EvidenceKind.MONTE_CARLO,
        source_code_sha=attacks_source_sha(),
    )
    return rec, {"wilson_lo": wlo, "wilson_hi": whi, "clopper_pearson_lo": lo, "clopper_pearson_hi": hi}


def sdp_result(
    *,
    attack_id: str,
    game_id: GameId,
    n: int,
    verifier_rule: str,
    primal: float,
    dual: float,
    dual_residual: float,
    primal_residual: float,
    solver: str,
    applicability: str,
    theorem_bound: float | None,
    evidence: EvidenceKind,
    channel: str = "arbitrary CPTP map input -> (out1, out2), Choi matrix optimised",
) -> AttackResult:
    if evidence not in (EvidenceKind.NUMERICAL_SDP, EvidenceKind.CERTIFIED_NUMERIC):
        raise ValueError("sdp_result only emits NUMERICAL_SDP or CERTIFIED_NUMERIC")
    return AttackResult(
        attack_id=attack_id,
        game_id=game_id,
        attack_capability=["one_note", "arbitrary_cptp_1to2", "no_verifier_oracle"],
        token_n=n,
        attack_method="Choi-matrix SDP (MVW 2012 Sec. 3.1)",
        quantum_channel_description=channel,
        verifier_rule=verifier_rule,
        seed=None,
        trials=0,
        successes=0,
        sdp_primal=primal,
        sdp_dual=dual,
        dual_feasibility_residual=dual_residual,
        primal_feasibility_residual=primal_residual,
        solver=solver,
        proof_applicability=applicability,  # type: ignore[arg-type]
        theorem_upper_bound=theorem_bound,
        backend_kind="cvxpy_complex_hermitian" if evidence == EvidenceKind.NUMERICAL_SDP else "exact_rational_ldlt",
        evidence_kind=evidence,
        source_code_sha=attacks_source_sha(),
    )
