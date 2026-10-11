"""T7: brute-force agreement, null bound -> UNCERTIFIED, interval worst case (not mean), epsilon monotonicity,
independent re-validation of every emitted certificate."""

from __future__ import annotations

import pytest

from qmint.compiler.certify import certify, diagnose
from qmint.compiler.constraints import Problem, build_grid, ideal_device, make_targets, s2_device
from qmint.compiler.scoring import Scorer
from qmint.compiler.selectors import (
    Selection,
    compiler,
    exhaustive_oracle,
    naive_analytic,
    published_fixed,
)
from qmint.core.contracts import CertificateStatus, GameId, SecurityAxis, Targets
from qmint.proofs.checker import IndependentProofChecker
from qmint.proofs.ideal_bounds import min_length_for_target


@pytest.mark.parametrize("dev,interval", [("K22-F5a", False), ("K22-F5b-half", False), ("K22-F5b-half", True),
                                          ("K22-F5c-half", True), ("K22-F5a", True)])
@pytest.mark.parametrize("eps", [1e-6, 1e-9])
def test_s2_compiler_equals_exhaustive_oracle(s2_tiny, dev, interval, eps):
    p = s2_tiny(dev, interval, eps)
    o, c = exhaustive_oracle(p), compiler(p)
    assert (o.status, o.idx) == (c.status, c.idx)
    assert o.optimality == "global_optimum_on_grid" and c.optimality == "best_found"
    if c.status == "FEASIBLE":
        assert c.engine_calls < o.engine_calls / 5


@pytest.mark.parametrize("dev", ["D1-PUB-SI", "D1-PUB-INT"])
@pytest.mark.parametrize("eps,honest", [(1e-6, 1e-3), (1e-9, 1e-6), (1e-12, 1e-2)])
def test_d1_compiler_equals_exhaustive_oracle(d1_tiny, dev, eps, honest):
    p = d1_tiny(dev, eps, honest)
    o, c = exhaustive_oracle(p), compiler(p)
    assert (o.status, o.idx) == (c.status, c.idx)


@pytest.mark.parametrize("game", [GameId.W1, GameId.W1_CV, GameId.S1])
@pytest.mark.parametrize("eps", [1e-3, 1e-6, 1e-9, 1e-12])
def test_ideal_selectors_agree_with_closed_form_and_are_certified(game, eps):
    p = Problem("i", game, ideal_device(game), Targets(epsilon_unf=eps), build_grid("ideal"))
    n = min_length_for_target(game, eps)
    for fn in (naive_analytic, exhaustive_oracle, compiler):
        sel = fn(p)
        assert sel.N == n
        assert certify(p, sel).released
    assert published_fixed(p).status == "NOT_AVAILABLE"


def test_smaller_epsilon_never_needs_fewer_pulses(s2_tiny):
    ns = []
    for eps in (1e-3, 1e-6, 1e-9, 1e-12):
        sel = compiler(s2_tiny("K22-F5c-half", False, eps))
        ns.append(sel.N if sel.status == "FEASIBLE" else float("inf"))
    assert ns == sorted(ns)


def test_null_bound_gives_infeasibility_never_certificate():
    # Kent's experimental tuple is outside Theorem 1 (f <= 0) at every N: no value, never 0.
    from qmint.compiler.experiments import s2_problem

    p = s2_problem("K22-EXP", False, 1e-9, 1e-3)
    sel = compiler(p)
    assert sel.status == "INFEASIBLE" and sel.decisions is None
    inf = diagnose(p)
    unf = next(a for a in inf.axes if a.axis == "epsilon_unf")
    assert unf.best_log10_found is None and unf.points_with_bound == 0
    assert any("f(" in r or "Eq.(7)" in r for r in unf.reasons)
    # forcing a certificate on an out-of-domain tuple: the checker refuses (bound missing is never 0)
    forced = Selection("forced", p.scenario_id, "FEASIBLE", "none", decisions=p.decision_values((280, 25, 0, 29, 0)))
    out = certify(p, forced)
    assert not out.released and out.certificate.proof_check_status == CertificateStatus.UNCERTIFIED


def test_missing_assumption_surfaces_in_infeasibility_certificate(tiny_grid):
    dev = s2_device("K22-F5a", interval=False)
    dev["declared_assumptions"] = [d for d in dev["declared_assumptions"] if d != "table6_E_no_side_channels"]
    p = Problem("x", GameId.S2, dev, make_targets(GameId.S2, 1e-9, 1e-3), tiny_grid("S2"))
    assert compiler(p).status == "INFEASIBLE"
    inf = diagnose(p, stride=8)
    assert "ASSUMPTION_MISSING:table6_E_no_side_channels" in inf.missing_assumptions
    assert inf.status == CertificateStatus.OUT_OF_MODEL


def test_privacy_without_theorem_is_infeasible_not_zero():
    p = Problem("w", GameId.W1, ideal_device(GameId.W1), Targets(epsilon_unf=1e-9, epsilon_priv=1e-2), build_grid("ideal"))
    sel = compiler(p)
    assert sel.status == "INFEASIBLE" and "epsilon_priv" in sel.note
    s = Scorer().score(p, SecurityAxis.PRIVACY, {"n": 100})
    assert s.log10 is None  # never 0


def test_s2_privacy_target_respected():
    from qmint.compiler.experiments import s2_problem

    ok = compiler(s2_problem("K22-F5a", False, 1e-9, 1e-3, beta_E=1e-3, eps_priv=1e-2))
    bad = compiler(s2_problem("K22-F5a", False, 1e-9, 1e-3, beta_E=1e-3, eps_priv=1e-4))
    assert ok.status == "FEASIBLE" and ok.logs["epsilon_priv"] == pytest.approx(-3.0)
    assert bad.status == "INFEASIBLE" and "epsilon_priv" in bad.note


def test_interval_uses_worst_case_not_mean(s2_tiny):
    point, box = s2_tiny("K22-F5b-half", False), s2_tiny("K22-F5b-half", True)
    cp, ci = compiler(point), compiler(box)
    assert cp.status == ci.status == "FEASIBLE" and ci.N > cp.N
    # the mean-point selection is NOT valid on the box ...
    sc = Scorer().score_all(box, cp.decisions)
    assert not all(s.meets(box.target_log10(a)) for a, s in sc.items())
    assert not certify(box, Selection("mean", box.scenario_id, "FEASIBLE", "x", decisions=cp.decisions)).released
    # ... while the box selection is certified on the box (checker brute-forces every corner)
    assert certify(box, ci).released


def test_every_released_certificate_passes_the_independent_checker(s2_tiny):
    p = s2_tiny("K22-F5a", False)
    out = certify(p, compiler(p))
    assert out.released
    rechecked = IndependentProofChecker().check(out.certificate)
    assert rechecked.proof_check_status == CertificateStatus.CERTIFIED
    # tampering with a bound (optimistic) is caught on re-validation
    data = out.certificate.model_dump(mode="python")
    data["log10_upper_bounds"]["epsilon_unf"] -= 1.0
    data["upper_bounds"]["epsilon_unf"] = 10 ** data["log10_upper_bounds"]["epsilon_unf"]
    tampered = type(out.certificate).model_validate(data)
    assert IndependentProofChecker().check(tampered).proof_check_status == CertificateStatus.UNCERTIFIED


def test_d1_is_uncertified_by_construction(d1_tiny):
    p = d1_tiny()
    sel = compiler(p)
    assert sel.status == "FEASIBLE"
    out = certify(p, sel)
    assert not out.released and out.uncertified_by_construction and not out.checker_rejected
    assert "never certified" in out.certificate.reason


def test_published_and_naive_are_scored_through_engine(s2_tiny):
    p = s2_tiny("K22-F5a", False)
    pub, nv = published_fixed(p), naive_analytic(p)
    assert pub.N == 40_000_000 and pub.engine_calls == 3 and pub.idx is None
    assert nv.status in ("FEASIBLE", "INFEASIBLE") and nv.engine_calls > 0 and "monotone" in nv.note
