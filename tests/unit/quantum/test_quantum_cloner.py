"""F2: 1->2 cloning circuits for W1. Never 'optimal' unless the exact value is 3/4."""

import math
from fractions import Fraction

import numpy as np
import pytest

from qmint.core.contracts import AttackResult, Basis, GameId
from qmint.quantum import cloner

STATES = [(Basis.Z, 0), (Basis.Z, 1), (Basis.X, 0), (Basis.X, 1)]


@pytest.mark.parametrize("name", ["bruss2000", "mvw2012"])
def test_isometry_and_kraus_completeness(name):
    v = cloner.cloner_isometry(name)
    assert np.allclose(v.T @ v, np.eye(2))
    k = cloner.cloner_kraus(name)
    assert np.allclose(sum(a.conj().T @ a for a in k), np.eye(2))
    u = cloner._unitary_completion(v)
    assert np.allclose(u.conj().T @ u, np.eye(8))


@pytest.mark.parametrize("name", ["bruss2000", "mvw2012"])
@pytest.mark.parametrize("basis,bit", STATES)
def test_circuit_matches_numpy_and_analytic(name, basis, bit):
    c = cloner.circuit_both_pass_probability([basis], [bit], name)
    assert abs(c - cloner.numpy_both_pass_probability(basis, bit, name)) < 1e-12
    assert abs(c - cloner.analytic_both_pass(name)) < 1e-12
    assert c <= 0.75 + 1e-12  # never exceeds the MVW W1 optimum


def test_bruss_values_from_paper():
    a, b = 0.5 + math.sqrt(1 / 8), math.sqrt(1 / 8)
    assert abs(a * a + b * b - (0.5 + math.sqrt(1 / 8))) < 1e-15  # single-copy fidelity, eq. (34)
    assert abs(cloner.BRUSS_BOTH_PASS_ANALYTIC - a * a) < 1e-15
    assert cloner.BRUSS_BOTH_PASS_ANALYTIC < 0.75
    assert not cloner.is_optimal_for_w1("bruss2000")
    assert cloner.attack_label("bruss2000") == "heuristic_circuit_attack"


def test_bruss_single_copy_fidelity():
    v = cloner.cloner_isometry("bruss2000")
    for basis, bit in STATES:
        from qmint.quantum.bb84 import state_vector

        psi = state_vector(basis, bit)
        out = (v @ psi).reshape(2, 2, 2)
        rho1 = np.einsum("abc,dbc->ad", out, out.conj())
        assert abs(np.real(psi.conj() @ rho1 @ psi) - (0.5 + math.sqrt(1 / 8))) < 1e-12


def test_mvw_exact_three_quarters():
    assert cloner.mvw_both_pass_exact() == Fraction(3, 4)
    assert cloner.is_optimal_for_w1("mvw2012")
    assert cloner.attack_label("mvw2012") == "mvw2012_optimal_channel_circuit"


@pytest.mark.parametrize("name", ["bruss2000", "mvw2012"])
def test_two_qubit_note_product(name):
    p = cloner.circuit_both_pass_probability([Basis.X, Basis.Z], [1, 0], name)
    assert abs(p - cloner.analytic_both_pass(name, 2)) < 1e-12


def test_width_cap():
    with pytest.raises(ValueError):
        cloner.build_cloning_attack_circuit([Basis.Z] * 3, [0] * 3, "mvw2012")


@pytest.mark.parametrize("name", ["bruss2000", "mvw2012"])
def test_simulated_attack_result(name):
    r = cloner.simulate_attack(name, n=1, n_notes=4, shots_per_note=10_000, seed=5, source_code_sha="test")
    assert isinstance(r, AttackResult) and r.game_id == GameId.W1
    assert r.theorem_upper_bound == 0.75 and r.evidence_kind.value == "SIMULATOR_IDEAL"
    assert r.success_rate_ci.lo <= cloner.analytic_both_pass(name) <= r.success_rate_ci.hi
    assert ("optimal" in r.attack_method) == (name == "mvw2012")
