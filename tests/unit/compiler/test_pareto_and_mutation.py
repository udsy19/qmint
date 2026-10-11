"""Pareto dominance / duplicate removal, cache keys, and mutation tests (reversed inequalities must be killed)."""

from __future__ import annotations

import pytest

from qmint.compiler import scoring, selectors
from qmint.compiler.certify import certify
from qmint.compiler.pareto import Point, dominates, pareto_front
from qmint.compiler.scoring import Score, Scorer
from qmint.compiler.selectors import compiler, exhaustive_oracle


def test_dominance():
    assert dominates((1, 2, 3), (1, 2, 4))
    assert not dominates((1, 2, 3), (1, 2, 3))
    assert not dominates((1, 5), (2, 4))
    assert dominates((1, None), (2, 7))  # compared on jointly defined objectives only
    assert not dominates((None,), (None,))


def test_front_removes_duplicates_and_dominated():
    pts = [Point("a", (10, -3.0)), Point("b", (10, -3.0)), Point("c", (12, -4.0)), Point("d", (12, -2.0)),
           Point("e", (9, -1.0))]
    front = pareto_front(pts)
    keys = sorted(p.key for p in front)
    assert keys == ["a", "c", "e"]  # b duplicate of a (smaller key kept), d dominated by a
    for p in front:
        assert not any(dominates(q.costs, p.costs) for q in front)


def test_cache_key_covers_calibration_and_proof_version(s2_tiny, monkeypatch):
    p = s2_tiny()
    s1 = Scorer()
    k1 = s1.cache_key(p, scoring.SecurityAxis.UNFORGEABILITY, {"N": 1})
    monkeypatch.setattr(scoring, "proof_version", lambda: {"engine": "other"})
    assert Scorer().cache_key(p, scoring.SecurityAxis.UNFORGEABILITY, {"N": 1}) != k1
    p2 = s2_tiny(interval=True)
    assert s1.cache_key(p2, scoring.SecurityAxis.UNFORGEABILITY, {"N": 1}) != k1


def test_cache_hits_do_not_change_results(s2_tiny):
    p = s2_tiny("K22-F5a", False)
    sc = Scorer()
    a, b = compiler(p, sc), compiler(p, sc)
    assert (a.idx, a.logs) == (b.idx, b.logs) and b.cache_hits > 0 and b.engine_calls == 0


# ---------------------------------------------------------------- mutation tests


def test_mutant_reversed_target_inequality_is_killed_by_checker(s2_tiny, monkeypatch):
    """Mutant: 'bound <= target' -> 'bound >= target'. Oracle and compiler share the mutant, so only the
    independent checker can kill it: nothing the mutant selects may be released."""
    monkeypatch.setattr(Score, "meets", lambda self, t: self.log10 is not None and self.log10 >= t)
    p = s2_tiny("K22-F5a", False)
    sel = exhaustive_oracle(p)
    assert sel.status == "FEASIBLE"  # the mutant happily 'finds' something ...
    assert not certify(p, sel).released  # ... which the independent checker refuses
    c = compiler(p)
    assert c.status == "INFEASIBLE" or not certify(p, c).released


def test_mutant_reversed_monotone_direction_is_killed_by_oracle_agreement(s2_tiny, monkeypatch):
    """Mutant: the rob-feasible gamma_det set treated as a suffix instead of a prefix (reversed M2)."""
    p = s2_tiny("K22-F5b-half", False)
    good = exhaustive_oracle(p)
    monkeypatch.setattr(selectors, "_last_true", lambda lo, hi, pred: selectors._first_true(lo, hi, pred))
    mutant = compiler(p)
    assert (mutant.status, mutant.idx) != (good.status, good.idx)


def test_mutant_reversed_tie_break_is_killed_by_oracle_agreement(s2_tiny, monkeypatch):
    """Mutant: maximise instead of minimise the honest-failure bound in the tie-break."""
    p = s2_tiny("K22-F5a", False)
    good = exhaustive_oracle(p)
    real = selectors.honest_log10
    monkeypatch.setattr(selectors, "honest_log10", lambda prob, logs: (lambda h: None if h is None else -h)(real(prob, logs)))
    mutant = compiler(p)
    assert mutant.idx != good.idx


@pytest.mark.parametrize("sign", [-1.0])
def test_mutant_reversed_epsilon_direction_is_killed_by_checker(s2_tiny, sign):
    """Mutant certificate reporting 1 - eps style values (wrong direction) is refused by the checker."""
    p = s2_tiny("K22-F5a", False)
    out = certify(p, compiler(p))
    data = out.certificate.model_dump(mode="python")
    data["log10_upper_bounds"]["epsilon_unf"] = sign * 1e-12  # ~1 - tiny: wrong direction
    data["upper_bounds"]["epsilon_unf"] = None
    data["proof_check_status"] = "UNCERTIFIED"
    from qmint.proofs.checker import IndependentProofChecker

    checked = IndependentProofChecker().check(type(out.certificate).model_validate(data))
    assert checked.proof_check_status.value == "UNCERTIFIED"
