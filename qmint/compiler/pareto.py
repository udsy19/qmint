"""Multiobjective Pareto filtering over CERTIFIED configurations (master plan 4.2-4.3, Fig. 8).

Objectives are all minimised: prepared pulses N, issuance seconds (N / source rate, MODELLED),
honest-failure bound, classical bits (MODELLED proxy), and log10 eps_unf achieved. Issuance time and
classical bits are monotone transforms of N in the frozen resource model, so they never change which
points are non-dominated; they are carried for reporting. Points with a missing objective (e.g. the
ideal model's unmodelled honest failure) are compared only on objectives both points define.
"""

from __future__ import annotations

from collections.abc import Hashable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any

OBJECTIVES = ("N", "issuance_seconds", "honest_failure_log10", "classical_bits", "log10_eps_unf")


@dataclass(frozen=True)
class Point:
    key: Hashable
    costs: tuple[float | None, ...]
    payload: Any = None


def dominates(a: Sequence[float | None], b: Sequence[float | None]) -> bool:
    """a dominates b iff a <= b on every jointly defined objective and a < b on at least one."""
    pairs = [(x, y) for x, y in zip(a, b, strict=True) if x is not None and y is not None]
    if not pairs:
        return False
    return all(x <= y for x, y in pairs) and any(x < y for x, y in pairs)


def pareto_front(points: Iterable[Point]) -> list[Point]:
    """Non-dominated points; exact duplicate cost vectors are collapsed to the smallest key (deterministic)."""
    uniq: dict[tuple, Point] = {}
    for p in sorted(points, key=lambda p: (tuple(_sortable(c) for c in p.costs), repr(p.key))):
        uniq.setdefault(p.costs, p)
    cand = list(uniq.values())
    return [p for p in cand if not any(dominates(q.costs, p.costs) for q in cand if q is not p)]


def _sortable(c: float | None) -> float:
    return float("inf") if c is None else c
