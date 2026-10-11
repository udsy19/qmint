"""The ONLY path by which lane I scores a candidate: lane D's ``ProofEngine.evaluate``.

``Scorer`` wraps the engine with an optional evaluation cache keyed by the canonical hash of
(game, axis, parameters, calibration, proof version). The proof version covers the engine id and the
SHA-256 of the theorem registry and of every lane-D evaluator source file, so a change in any proof
code or registry entry invalidates the cache instead of silently reusing stale bounds.
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path
from typing import Any, NamedTuple

from qmint.compiler.constraints import Problem
from qmint.core.contracts import BoundRequest, SecurityAxis
from qmint.core.serialization import canonical_hash, file_sha256
from qmint.proofs.engine import ProofEngine
from qmint.proofs.registry import OBLIGATIONS_PATH

_PROOF_SOURCES = ("engine.py", "finite_size.py", "ideal_bounds.py", "assumption_check.py", "results.py", "registry.py")


@lru_cache(maxsize=1)
def proof_version() -> dict[str, str]:
    src = Path(OBLIGATIONS_PATH).resolve().parents[1] / "qmint" / "proofs"
    return {
        "engine": ProofEngine.evaluator_id,
        "obligations_sha256": file_sha256(OBLIGATIONS_PATH),
        **{f"{name}_sha256": file_sha256(src / name) for name in _PROOF_SOURCES},
    }


class Score(NamedTuple):
    """A lane-D verdict: ``log10`` is None when no applicable bound exists (never 0)."""

    log10: float | None
    out_of_domain: bool
    notes: str
    failed: tuple[str, ...]

    def meets(self, target_log10: float) -> bool:
        return self.log10 is not None and self.log10 <= target_log10


def lse10(a: float, b: float) -> float:
    """log10(10^a + 10^b) without under/overflow."""
    hi, lo = max(a, b), min(a, b)
    return hi + math.log10(1.0 + 10.0 ** (lo - hi))


class Scorer:
    def __init__(self, engine: ProofEngine | None = None, *, cache: bool = True) -> None:
        self.engine = engine or ProofEngine()
        self.use_cache = cache
        self._cache: dict[str, Score] = {}
        self.engine_calls = 0
        self.cache_hits = 0
        self._pv = canonical_hash(proof_version())

    def cache_key(self, problem: Problem, axis: SecurityAxis, params: dict[str, Any]) -> str:
        return canonical_hash({
            "game": problem.game.value,
            "axis": axis.value,
            "device": problem.device_hash,
            "params": params,
            "calibration": problem.calibration,
            "proof_version": self._pv,
        })

    def score(self, problem: Problem, axis: SecurityAxis, decisions: dict[str, Any]) -> Score:
        params = problem.engine_params(decisions, axis)
        key = self.cache_key(problem, axis, params) if self.use_cache else None
        if key is not None and key in self._cache:
            self.cache_hits += 1
            return self._cache[key]
        self.engine_calls += 1
        res = self.engine.evaluate(
            BoundRequest(protocol_id=problem.protocol_id, game_id=problem.game, axis=axis, parameters=params,
                         calibration=problem.calibration)
        )
        out = Score(res.log10_value, res.out_of_domain, res.notes, tuple(res.failed_assumptions))
        if key is not None:
            self._cache[key] = out
        return out

    def score_all(self, problem: Problem, decisions: dict[str, Any]) -> dict[SecurityAxis, Score]:
        return {a: self.score(problem, a, decisions) for a in problem.target_axes}


def honest_log10(problem: Problem, logs: dict[SecurityAxis, float]) -> float | None:
    """Honest-failure bound: S2 eps_rob + eps_cor (union bound), D1 eps_cor, ideal: not modelled (None)."""
    if problem.family == "S2":
        r, c = logs.get(SecurityAxis.ROBUSTNESS), logs.get(SecurityAxis.CORRECTNESS)
        if r is None or c is None:
            return None
        return lse10(r, c)
    if problem.family == "D1":
        return logs.get(SecurityAxis.CORRECTNESS)
    return None
