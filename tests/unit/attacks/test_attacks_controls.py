"""T3/T4: negative controls must fail to reproduce W1 or be flagged; undetectable ones are documented."""

import pytest

from qmint.attacks import coherent_sdp
from qmint.attacks.heuristic import bit_order_swap_honest_acceptance


@pytest.fixture(scope="module")
def controls():
    return {c.name: c for c in coherent_sdp.run_negative_controls("SCS")}


def test_every_control_is_accounted_for(controls):
    undetectable = {"transpose_omitted_bb84", "subsystem_order_mvw_YZX_fed_as_XYZ_n1"}
    for name, c in controls.items():
        if name in undetectable:
            assert not c.flagged and "UNDETECTABLE" in c.note
        else:
            assert c.flagged, name


def test_transpose_omission_detected_on_complex_ensemble(controls):
    c = controls["transpose_omitted_six_state"]
    assert abs(c.primal_value - 0.5) < 1e-5 and c.reference_value == pytest.approx(2 / 3)


def test_missing_permutation_detected(controls):
    assert abs(controls["subsystem_order_missing_W_pi_n2"].primal_value - 0.375) < 1e-5


def test_bit_order_swap_flagged_by_honest_oracle(controls):
    c = controls["bit_order_swap_verifier_n2"]
    assert not c.deviates  # attacker absorbs the relabeling: SDP value unchanged
    assert c.flagged
    assert bit_order_swap_honest_acceptance(2) == pytest.approx(0.375)
    assert bit_order_swap_honest_acceptance(1) == pytest.approx(1.0)


def test_threshold_variant_does_not_reproduce_w1(controls):
    assert abs(controls["threshold_per_note_n2_t1"].primal_value - 1.0) < 1e-5
    assert abs(controls["threshold_mvw_R_n2_t1"].primal_value - 15 / 16) < 1e-5


def test_secret_basis_gives_perfect_cloning(controls):
    assert abs(controls["secret_basis_given_to_attacker"].primal_value - 1.0) < 1e-5
