"""Published ideal-model bounds (games W1, W1_CV, S1), computed in log space.

  W1    MVW2012 Theorem 1             (3/4)^n
  W1_CV MVW2012 Theorem 2             (3/4 + sqrt(2)/8)^n
  S1    Kent et al. 2022 Lemma 1/Eq.1 (1/2 + 1/(2 sqrt 2))^N

Each formula is guarded by its game ID: it is refused for every other game (W2, S2, D1, ...)
and for any request carrying a parameter outside the per-game allowlist (W1/W1_CV: ``n``;
S1: ``N`` and ``M = 1``; plus declarations and an exact, oracle-free verifier), so noise, loss,
thresholds or error tolerance under any spelling are OUT_OF_MODEL. These are
THEORETICAL IDEAL-MODEL bounds, not experimental security certificates.

Supersedes ``bootstrap/ideal_bounds.py`` (same numbers: n_min(1e-9) = 73 / 273 / 131).
"""

from __future__ import annotations

import math

from qmint.core.contracts import (
    BoundRequest,
    BoundResult,
    EvidenceKind,
    GameId,
    SecurityAxis,
)
from qmint.proofs import assumption_check as ac
from qmint.proofs.registry import Registry, default_registry
from qmint.proofs.results import bounded, unsupported

# game -> (per-qubit base, registry bound_id, length parameter name)
IDEAL_BASES: dict[GameId, tuple[float, str, str]] = {
    GameId.W1: (0.75, "P-W1/unf", "n"),
    GameId.W1_CV: (0.75 + math.sqrt(2) / 8, "P-W1CV/unf", "n"),
    GameId.S1: (0.5 + 1 / (2 * math.sqrt(2)), "P-S1/unf", "N"),
}


class UnsupportedGameError(ValueError):
    """An ideal formula was requested for a game it was not proven for."""


def _base(game: GameId | str) -> float:
    try:
        g = GameId(game)
    except ValueError as e:
        raise UnsupportedGameError(f"unknown game {game!r}") from e
    if g not in IDEAL_BASES:
        raise UnsupportedGameError(f"no published ideal closed-form bound for game {g.value}")
    return IDEAL_BASES[g][0]


def _length(n: object) -> int:
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError("length must be a positive integer")
    return n


def log10_bound(game: GameId | str, n: int) -> float:
    """log10 of the ideal-game success bound for length ``n`` (no underflow for any n)."""
    return _length(n) * math.log10(_base(game))


def min_length_for_target(game: GameId | str, epsilon: float) -> int:
    """Smallest n with bound(n) <= epsilon (exact integer rounding, checked both sides)."""
    b = _base(game)
    if not isinstance(epsilon, (int, float)) or not math.isfinite(epsilon) or not (0 < epsilon < 1):
        raise ValueError("target epsilon must be strictly between 0 and 1")
    target, step = math.log10(epsilon), math.log10(b)
    n = max(1, math.ceil(target / step))
    while n * step > target:  # guard float rounding of the ceil
        n += 1
    while n > 1 and (n - 1) * step <= target:
        n -= 1
    return n


class IdealBoundEvaluator:
    """``ProofEvaluator`` for the three ideal published games."""

    evaluator_id = "qmint.proofs.ideal_bounds/v1"

    def __init__(self, registry: Registry | None = None) -> None:
        self._registry = registry or default_registry()

    def evaluate(self, request: BoundRequest) -> BoundResult:
        game = request.game_id
        if game not in IDEAL_BASES:
            return unsupported(request, f"no ideal closed-form theorem for game {game.value}; refused", out_of_domain=True)
        base, bound_id, length_key = IDEAL_BASES[game]
        claim, spec = self._registry.bound(bound_id)
        if request.axis != spec.axis:
            return unsupported(
                request,
                f"{claim.claim_id} bounds {spec.axis.value} only; no theorem for {request.axis.value}"
                + (" (privacy is never reported as 0)" if request.axis == SecurityAxis.PRIVACY else ""),
            )
        params = request.parameters
        report = ac.check_declarations(claim, params).merged(ac.check_noise_free(claim, params, request.calibration))
        if game == GameId.S1 and params.get("M", 1) != 1:
            report = report.merged(ac.AssumptionReport(failed=("OUT_OF_MODEL:S1_is_two_site_only(M=1)",)))
        if not report.ok:
            return unsupported(request, f"{claim.claim_id} hypotheses not met", report=report, theorem_id=None)
        n = params.get(length_key)
        try:
            n = _length(n)
        except ValueError:
            return unsupported(
                request, f"{length_key} must be a positive integer, got {n!r}", out_of_domain=True
            )
        return bounded(
            request,
            bound_id,
            n * math.log10(base),
            status=claim.status,
            evidence_kind=EvidenceKind.PUBLISHED_THEOREM,
            report=report,
            notes=f"{spec.anchor}: {spec.formula} with {length_key}={n}; ideal model only",
        )


__all__ = [
    "IDEAL_BASES",
    "IdealBoundEvaluator",
    "UnsupportedGameError",
    "log10_bound",
    "min_length_for_target",
]
