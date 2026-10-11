"""T3: W1 Choi SDP quality, independent constructions, certification (lane C)."""

from fractions import Fraction

import numpy as np
import pytest

from qmint.attacks import certify, coherent_sdp
from qmint.attacks.linalg import choi_from_kraus, choi_tp_residual, min_eig, partial_trace, tp_residual

TOL = 1e-6  # declared solver tolerance for n=1 and n=2 (SCS eps 1e-9; Clarabel defaults)


@pytest.mark.parametrize("n", [1, 2])
def test_objective_numpy_equals_qutip(n):
    a = coherent_sdp.w1_objective_numpy(n)
    b = coherent_sdp.w1_objective_qutip(n)
    assert a.shape == (8**n, 8**n)
    np.testing.assert_allclose(a, b, atol=1e-14)


@pytest.mark.parametrize("n", [1, 2])
def test_objective_float_equals_exact_rational(n):
    exact = np.array(certify.exact_w1_objective(n), dtype=float)
    np.testing.assert_allclose(coherent_sdp.w1_objective_numpy(n).real, exact, atol=1e-15)


def test_objective_properties():
    g = coherent_sdp.w1_objective_numpy(1)
    assert np.allclose(g, g.conj().T)
    assert min_eig(g) > -1e-12
    # MVW Sec. 3.2: ||Q|| = 3/8, so Y = (3/8) I is dual feasible with value 3/4
    assert np.isclose(np.linalg.eigvalsh(g).max(), 3 / 8)


def test_partial_trace_matches_manual():
    rng = np.random.default_rng(1)
    a = rng.normal(size=(2, 2)) + 1j * rng.normal(size=(2, 2))
    b = rng.normal(size=(4, 4))
    m = np.kron(a, b)
    np.testing.assert_allclose(partial_trace(m, [2, 4], keep=[0]), a * np.trace(b))
    np.testing.assert_allclose(partial_trace(m, [2, 4], keep=[1]), b * np.trace(a))


def test_mvw_channel_is_cptp_and_achieves_three_quarters():
    k = coherent_sdp.mvw_optimal_kraus()
    assert tp_residual(k) < 1e-12
    j = choi_from_kraus(k)
    assert min_eig(j) > -1e-12
    assert choi_tp_residual(j, 2, 4) < 1e-12
    val = float(np.real(np.trace(coherent_sdp.w1_objective_numpy(1) @ j)))
    assert abs(val - 0.75) < 1e-12
    assert certify.exact_choi_value_of_mvw_channel(1) == Fraction(3, 4)
    assert certify.exact_choi_value_of_mvw_channel(2) == Fraction(9, 16)


@pytest.mark.parametrize("solver", coherent_sdp.SOLVERS)
def test_w1_n1_sdp_reproduces_theorem(solver):
    r = coherent_sdp.solve_w1(1, solver)
    assert r.primal_status == "optimal" and r.dual_status == "optimal"
    assert abs(r.primal_value - 0.75) < TOL
    assert abs(r.dual_value - 0.75) < TOL
    assert abs(r.duality_gap) < TOL
    assert r.j_min_eig > -TOL
    assert r.tp_residual < TOL
    assert r.dual_slack_min_eig > -TOL


def test_w1_n2_sdp_scs():
    r = coherent_sdp.solve_w1(2, "SCS")
    assert abs(r.primal_value - 0.5625) < TOL
    assert abs(r.dual_value - 0.5625) < TOL
    assert r.tp_residual < TOL and r.j_min_eig > -TOL and r.dual_slack_min_eig > -TOL


@pytest.mark.slow
def test_w1_n2_sdp_clarabel():
    r = coherent_sdp.solve_w1(2, "CLARABEL")
    assert abs(r.primal_value - 0.5625) < TOL and abs(r.dual_value - 0.5625) < TOL


def test_large_n_refused_not_oom():
    with pytest.raises(coherent_sdp.SDPSizeUnsupported):
        coherent_sdp.solve_w1(3)
    with pytest.raises(coherent_sdp.SDPSizeUnsupported):
        coherent_sdp.solve_counterfeit_sdp(np.zeros((128, 128)), 2, 64)


@pytest.mark.parametrize("n", [1, 2])
def test_certified_dual_bound(n):
    r = coherent_sdp.solve_w1(n, "SCS")
    c = certify.certify_w1_dual(r.Y, n, r.dual_value)
    assert c.evidence_kind == "CERTIFIED_NUMERIC"
    assert c.bound >= Fraction(3, 4) ** n  # weak duality vs exact achieving channel
    assert c.bound_float_up - 0.75**n < 1e-8
    assert Fraction(c.bound_float_up) >= c.bound


def test_certifier_repairs_infeasible_dual_and_never_undercuts_optimum():
    # Y = 0.3 I is infeasible (needs 3/8); the certifier must shift it up to feasibility
    c = certify.certify_w1_dual(0.3 * np.eye(2), 1, 0.6)
    assert c.bound >= Fraction(3, 4)
    assert c.delta > 0


def test_exact_pd_check():
    m = [[Fraction(2), Fraction(1)], [Fraction(1), Fraction(2)]]
    assert certify.is_positive_definite_exact(m)[0]
    s = [[Fraction(1), Fraction(1)], [Fraction(1), Fraction(1)]]  # PSD, singular -> not PD
    assert not certify.is_positive_definite_exact(s)[0]
    neg = [[Fraction(1), Fraction(2)], [Fraction(2), Fraction(1)]]
    assert not certify.is_positive_definite_exact(neg)[0]


def test_w1cv_n1_matches_theorem_2():
    r = coherent_sdp.solve_w1cv_n1("SCS")
    target = 0.75 + np.sqrt(2) / 8
    assert abs(r.primal_value - target) < TOL and abs(r.dual_value - target) < TOL
    assert r.povm_min_eig > -TOL and r.povm_completeness_residual < TOL
    c = certify.certify_w1cv_dual(r.Y, r.dual_value)
    assert target - 1e-12 <= c.bound_float_up < target + 1e-8


def test_threshold_mvw_eq4_cross_check():
    r = coherent_sdp.solve_counterfeit_sdp(coherent_sdp.threshold_objective_mvw_eq4(2, 1), 4, 16)
    assert abs(r.primal_value - coherent_sdp.mvw_eq4_value(2, 1)) < TOL
    assert abs(coherent_sdp.mvw_eq4_value(2, 1) - 15 / 16) < 1e-15
    # t = n recovers W1
    r2 = coherent_sdp.solve_counterfeit_sdp(coherent_sdp.threshold_objective_mvw_eq4(2, 2), 4, 16)
    assert abs(r2.primal_value - 0.5625) < TOL
