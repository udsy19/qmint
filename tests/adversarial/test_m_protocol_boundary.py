"""Lane M red team: lane B token handles and challengers (CRYPTOGRAPHIC_REVIEW / DATA_LEAKAGE_REVIEW).

Strict-xfail tests assert the SAFE behaviour and currently fail; the owning lane removes the
marker when its fix lands (strict=True turns an unnoticed fix into a failure).
Passing tests are independent cross-checks that should keep passing.
"""

from __future__ import annotations

import copy
import pickle

import numpy as np
import pytest

from qmint.attacks.heuristic import a01_kraus
from qmint.protocols.kent_smoney_2022 import KentParams, KentScheme, KentSMoneySession
from qmint.protocols.wiesner import WiesnerChallenger, WiesnerMode
from qmint.quantum.cloner import cloner_kraus
from tests.adversarial._reach import reachable_types


def _note(n: int = 6, seed: int = 3):
    ch = WiesnerChallenger(mode=WiesnerMode.EXACT, seed=seed)
    return ch, ch.mint(n, seed + 100)


# --------------------------------------------------------------- cross-lane checks (pass)
@pytest.mark.parametrize("n", [1, 2, 3])
def test_mvw_optimal_cloner_against_lane_b_challenger_gives_3_4_pow_n(n):
    """Lane F's MVW channel run against lane B's challenger (never done by lanes B/C)."""
    ch, note = _note(n)
    c1, c2 = note.split(cloner_kraus("mvw"))
    assert ch.pair_acceptance_probability(c1, c2) == pytest.approx(0.75**n, abs=1e-12)


@pytest.mark.parametrize("n", [1, 2, 3])
def test_measure_resend_against_lane_b_challenger_gives_5_8_pow_n(n):
    """Independent check of the B/C correction: Z measure-resend wins W1 with (5/8)^n, not (3/4)^n."""
    ch, note = _note(n)
    c1, c2 = note.split(a01_kraus())
    assert ch.pair_acceptance_probability(c1, c2) == pytest.approx(0.625**n, abs=1e-12)


# --------------------------------------------------------------- M-B1: copy/pickle = cloning
@pytest.mark.xfail(strict=True, reason="M-B1: RegisterHandle can be deep-copied; the copy is a perfect counterfeit")
def test_handle_refuses_deepcopy():
    ch, note = _note(8)
    try:
        twin = copy.deepcopy(note)
    except Exception:
        return  # safe: copying a quantum token handle is refused
    pytest.fail(f"deepcopy succeeded; W1 pair acceptance = {ch.pair_acceptance_probability(note, twin):.6f}")


@pytest.mark.xfail(strict=True, reason="M-B1: RegisterHandle pickles with its density matrices; unpickled copy passes")
def test_handle_refuses_pickle():
    ch, note = _note(8)
    try:
        twin = pickle.loads(pickle.dumps(note))
    except Exception:
        return
    pytest.fail(f"pickle round trip succeeded; W1 pair acceptance = {ch.pair_acceptance_probability(note, twin):.6f}")


# --------------------------------------------------------------- M-B2: introspection
@pytest.mark.xfail(strict=True, reason="M-B2: the wallet handle reaches the simulator register (exact BB84 states)")
def test_wallet_handle_graph_holds_no_state_matrices():
    _, note = _note(4)
    assert "FactorizedRegister" not in reachable_types(note)


@pytest.mark.xfail(strict=True, reason="M-B2: the Alice-facing Kent session object holds Bob's IssuerSecret and t,u")
def test_kent_alice_facing_object_holds_no_bob_secret():
    s = KentSMoneySession(KentParams(KentScheme.IQT2, N=16), seed=5)
    s.bank_send_quantum(0.0)
    assert "IssuerSecret" not in reachable_types(s)


def test_kent_introspection_attack_wins_s1_with_certainty():
    """Documents M-B2 impact: reading private attributes wins the S1 double presentation (OUT_OF_MODEL)."""
    s = KentSMoneySession(KentParams(KentScheme.IQT2, N=16), seed=5)
    s.bank_send_quantum(0.0)
    s.bank_distribute(1.0)
    s.alice_send_c(0, 2.0)
    s.bank_forward_c(3.0)
    t = s._bob["B0"]["t"]  # in-process introspection, not a protocol capability
    assert s.present(0, t, 4.0) and s.present(1, t, 4.0)
    assert s.double_presentation_accepted()


def test_handle_introspection_recovers_secret_exactly():
    """Documents M-B2: exact reduced states identify every (basis, bit) without the IssuerSecret."""
    ch, note = _note(6)
    secret = ch.leak_secret_TEST_ONLY(note)
    reg, qs = note._register, note._qubits
    for q, b, x in zip(qs, secret["bases"], secret["bits"], strict=True):
        rho = reg.reduced_state([q]).real
        basis = "Z" if abs(rho[0, 1]) < 1e-9 else "X"
        bit = (0 if rho[0, 0] > 0.5 else 1) if basis == "Z" else (0 if rho[0, 1] > 0 else 1)
        assert (basis, bit) == (b, x)


# --------------------------------------------------------------- M-B3: serial binding
@pytest.mark.xfail(strict=True, reason="M-B3: redeem() verifies by record.token_id but spends record.public_metadata['serial']")
def test_redeem_binds_serial_to_token():
    ch = WiesnerChallenger(mode=WiesnerMode.EXACT, seed=2)
    mine, victim = ch.mint(4, 1), ch.mint(4, 2)
    mine.record.public_metadata = {"serial": victim.record.public_metadata["serial"]}
    res = ch.redeem(mine)
    assert not res.accepted, "a note presented under another note's serial must be rejected"
    assert ch.redeem(victim).accepted, "the victim's genuine note must still redeem"


def test_bb84_states_real_so_transpose_is_invisible():
    """Context for the SDP transpose tamper: every C7 BB84 projector is real symmetric (rho^T = rho)."""
    from qmint.protocols.register import bb84_projector

    for b in ("Z", "X"):
        for x in (0, 1):
            p = bb84_projector(b, x)
            assert np.allclose(p, p.T) and np.allclose(p.imag, 0)
