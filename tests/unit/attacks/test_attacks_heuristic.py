"""T4: heuristic attacks -- exact analytics, Monte Carlo CI coverage, out-of-model attacks."""

import math

import pytest

from qmint.attacks import heuristic as h
from qmint.attacks.linalg import tp_residual
from qmint.attacks.stats import clopper_pearson_interval, wilson_interval

EXPECTED_PER_QUBIT = {
    "A01_basis_guess_resend": 5 / 8,
    "A01b_basis_guess_bayes_resend": (3 + math.sqrt(5)) / 8,
    "A02_breidbart_resend": 5 / 8,
    "A02b_breidbart_bayes_resend": (3 + math.sqrt(5)) / 8,
    "A03_universal_buzek_hillery": 2 / 3,
    "A03b_phase_covariant_xz": (3 + 2 * math.sqrt(2)) / 8,
    "A04_mvw_optimal_channel": 3 / 4,
}


@pytest.mark.parametrize("aid", sorted(h.W1_PRODUCT_ATTACKS))
def test_attack_is_cptp_and_exact_value(aid):
    kr = h.W1_PRODUCT_ATTACKS[aid][0]()
    assert tp_residual(kr) < 1e-12
    p = h.w1_product_exact(kr, 1)
    assert p == pytest.approx(EXPECTED_PER_QUBIT[aid], abs=1e-12)
    assert p <= 0.75 + 1e-12  # no heuristic exceeds the W1 optimum


@pytest.mark.parametrize("aid", ["A01_basis_guess_resend", "A03_universal_buzek_hillery", "A04_mvw_optimal_channel"])
def test_mc_ci_covers_exact(aid):
    kr = h.W1_PRODUCT_ATTACKS[aid][0]()
    n, trials = 2, 3000
    wins = h.mc_w1_product_attack(kr, n, trials, seed=11)
    lo, hi = clopper_pearson_interval(wins, trials, 0.999)
    assert lo <= h.w1_product_exact(kr, n) <= hi


def test_intervals_basic():
    lo, hi = wilson_interval(50, 100)
    assert lo < 0.5 < hi
    assert clopper_pearson_interval(0, 10)[0] == 0.0
    assert clopper_pearson_interval(10, 10)[1] == 1.0


def test_a06_split_loss_breaks_toy_w2():
    assert h.a06_exact(8, 4, 0.5, 0.0) == pytest.approx(1.0)
    assert h.mc_a06_split_loss(8, 0.5, 0.0, 200, seed=3) == 200
    p = h.a06_exact(8, 2, 0.25, 0.125)
    wins = h.mc_a06_split_loss(8, 0.25, 0.125, 2000, seed=4)
    lo, hi = clopper_pearson_interval(wins, 2000, 0.999)
    assert lo <= p <= hi
    assert p > 0.75**8  # the W1 number is not a W2 bound


def test_honest_w2_acceptance_bounds():
    assert h.honest_acceptance_w2(8, 0.0, 0.0, 0.25, 0.125) == pytest.approx(1.0)
    assert 0 < h.honest_acceptance_w2(8, 0.1, 0.02, 0.25, 0.125) < 1


def test_a08_oracle_attack_beats_w1_theorem_out_of_model():
    n, r, trials = 6, 10, 300
    st = h.mc_a08_oracle(n, r, trials, seed=5)
    lo, _ = clopper_pearson_interval(st.wins, trials)
    assert lo > 0.75**n
    assert h.a08_exact(n, r) == pytest.approx((1 - 2**-10) ** 6)
    assert st.mean_queries <= n * (r + 1)


def test_secret_leak_control_succeeds():
    assert h.mc_secret_leak_control(8, 100, seed=6) == 100
