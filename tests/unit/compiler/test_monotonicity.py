"""The monotonicity conditions M1-M3 that justify the compiler's pruning, tested THROUGH lane D's engine
on seeded random in-domain tuples (frozen_experiments.yaml: monotonicity_conditions)."""

from __future__ import annotations

import random

from qmint.compiler.constraints import Problem, build_grid, d1_device, make_targets, s2_device
from qmint.compiler.scoring import Scorer
from qmint.core.contracts import GameId, SecurityAxis

ROB, COR, UNF = SecurityAxis.ROBUSTNESS, SecurityAxis.CORRECTNESS, SecurityAxis.UNFORGEABILITY
RNG = random.Random(0)


def _s2(dev: str, interval: bool) -> Problem:
    return Problem("m", GameId.S2, s2_device(dev, interval=interval), make_targets(GameId.S2, 1e-9, 1e-3), build_grid("S2"))


def _le(a, b):  # None (no bound) is the worst value
    return b is None or (a is not None and a <= b + 1e-12)


def test_m1_bounds_nonincreasing_in_n_and_domain_independent_of_n():
    sc = Scorer()
    for dev, interval in (("K22-F5a", False), ("K22-F5b-half", True), ("K22-F5c-half", False)):
        p = _s2(dev, interval)
        shape = p.shape
        for _ in range(40):
            rest = tuple(RNG.randrange(k) for k in shape[1:])
            n1, n2 = sorted(RNG.sample(range(shape[0]), 2))
            for ax in (ROB, COR, UNF):
                a = sc.score(p, ax, p.decision_values((n1, *rest)))
                b = sc.score(p, ax, p.decision_values((n2, *rest)))
                assert a.out_of_domain == b.out_of_domain
                if a.log10 is not None:
                    assert b.log10 is not None and b.log10 <= a.log10 + 1e-12
    p = Problem("m", GameId.D1, d1_device("D1-PUB-INT"), make_targets(GameId.D1, 1e-9, 1e-3), build_grid("D1"))
    for _ in range(40):
        i, j = RNG.randrange(121), RNG.randrange(121)
        n1, n2 = sorted(RNG.sample(range(p.shape[0]), 2))
        for ax in (UNF, COR):
            a, b = sc.score(p, ax, p.decision_values((n1, i, j))), sc.score(p, ax, p.decision_values((n2, i, j)))
            assert a.out_of_domain == b.out_of_domain and _le(b.log10, a.log10)


def test_m2_s2_threshold_directions():
    sc = Scorer()
    for dev, interval in (("K22-F5a", False), ("K22-F5b-half", True)):
        p = _s2(dev, interval)
        nN, nD, nE, nC, nU = p.shape
        for _ in range(60):
            n, d, e, c, u = (RNG.randrange(k) for k in p.shape)
            if d + 1 < nD:  # rob nondecreasing in gamma_det; unf nonincreasing (domain upward closed)
                lo, hi = p.decision_values((n, d, e, c, u)), p.decision_values((n, d + 1, e, c, u))
                assert _le(sc.score(p, ROB, lo).log10, sc.score(p, ROB, hi).log10)
                assert _le(sc.score(p, UNF, hi).log10, sc.score(p, UNF, lo).log10)
            if e + 1 < nE:  # min_nu cor nonincreasing in gamma_err; unf nondecreasing (domain downward closed)
                lo, hi = p.decision_values((n, d, e, c, u)), p.decision_values((n, d, e + 1, c, u))
                cmin = [min((s for s in (sc.score(p, COR, p.decision_values((n, d, ee, cc, u))).log10 for cc in range(nC))
                             if s is not None), default=None) for ee in (e, e + 1)]
                assert _le(cmin[1], cmin[0])
                assert _le(sc.score(p, UNF, lo).log10, sc.score(p, UNF, hi).log10)


def test_m3_d1_directions_and_downward_closed_admissibility():
    sc = Scorer()
    p = Problem("m", GameId.D1, d1_device("D1-PUB-INT"), make_targets(GameId.D1, 1e-9, 1e-3), build_grid("D1"))
    for _ in range(80):
        n, i, j = RNG.randrange(p.shape[0]), RNG.randrange(120), RNG.randrange(120)
        base = sc.score(p, UNF, p.decision_values((n, i, j)))
        up_i = sc.score(p, UNF, p.decision_values((n, i + 1, j)))
        up_j = sc.score(p, COR, p.decision_values((n, i, j + 1)))
        if base.out_of_domain:  # admissible set downward closed: growing a delta never re-enters it
            assert up_i.out_of_domain and up_j.out_of_domain
        elif not up_i.out_of_domain:
            assert up_i.log10 <= base.log10 + 1e-12
            assert up_j.out_of_domain or up_j.log10 <= sc.score(p, COR, p.decision_values((n, i, j))).log10 + 1e-12
