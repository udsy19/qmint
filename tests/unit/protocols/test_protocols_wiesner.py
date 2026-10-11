"""Lane B / B1: Wiesner reference implementation tests (deterministic seeds)."""

import copy
import math
import pickle

import numpy as np
import pytest
from scipy.stats import binom, binomtest

from qmint.core.contracts import (
    Basis,
    EvidenceKind,
    IssuerSecret,
    ProtocolSpec,
    SecretBoundaryError,
    StateKind,
)
from qmint.core.interfaces import Challenger, TokenHandle
from qmint.core.serialization import canonical_json
from qmint.protocols import wiesner as W
from qmint.protocols.register import (
    ConsumedTokenError,
    FactorizedRegister,
    RegisterError,
    bb84_projector,
)
from qmint.quantum.bb84 import state_vector

SQ2 = 1 / math.sqrt(2)


def _dm(v):
    return np.outer(v, np.conj(v))


# --- reusable 1 -> 2 qubit attack channels (Kraus, shape 4x2) -------------------------
def kraus_measure_resend_z():
    """Measure in Z, prepare |oo>: K_o = |o o><o|."""
    ks = []
    for o in (0, 1):
        k = np.zeros((4, 2), dtype=complex)
        k[3 * o, o] = 1.0  # |00> index 0, |11> index 3
        ks.append(k)
    return ks


def kraus_keep_and_blank():
    """Isometry |psi> -> |psi>|0>: keep the original, output |0> as the second note."""
    v = np.zeros((4, 2), dtype=complex)
    v[0, 0] = 1.0  # |0>|0>
    v[2, 1] = 1.0  # |1>|0>
    return [v]


# --------------------------------------------------------------------------- C7 ordering
def test_state_ordering_c7():
    assert np.allclose(state_vector(Basis.Z, 0), [1, 0])
    assert np.allclose(state_vector(Basis.Z, 1), [0, 1])
    assert np.allclose(state_vector(Basis.X, 0), [SQ2, SQ2])
    assert np.allclose(state_vector(Basis.X, 1), [SQ2, -SQ2])


@pytest.mark.parametrize("basis", [Basis.Z, Basis.X])
def test_same_basis_outcomes_orthogonal_and_deterministic(basis):
    for bit in (0, 1):
        rho = _dm(state_vector(basis, bit))
        assert np.isclose(np.trace(bb84_projector(basis, bit) @ rho).real, 1.0)
        assert np.isclose(np.trace(bb84_projector(basis, 1 - bit) @ rho).real, 0.0)


def test_wrong_basis_is_fifty_fifty_exact_and_sampled():
    for prep, meas in ((Basis.Z, Basis.X), (Basis.X, Basis.Z)):
        for bit in (0, 1):
            p = np.trace(bb84_projector(meas, 0) @ _dm(state_vector(prep, bit))).real
            assert np.isclose(p, 0.5)
    rng = np.random.default_rng(7)
    reg = FactorizedRegister()
    qs = reg.add_product_state([_dm(state_vector(Basis.Z, 0))] * 4000)
    ones = sum(reg.measure(q, bb84_projector(Basis.X, 0), rng) for q in qs)
    ci = binomtest(ones, 4000).proportion_ci(confidence_level=0.999, method="exact")
    assert ci.low <= 0.5 <= ci.high


# ----------------------------------------------------------------- honest acceptance
@pytest.mark.parametrize("n", [1, 2, 8, 16, 32, 64, 128])
def test_honest_accept_is_one_exact_and_scales(n):
    ch = W.WiesnerChallenger(mode=W.WiesnerMode.EXACT, seed=1)
    note = ch.mint(n, rng_seed=100 + n)
    assert note.n_qubits() == n
    assert ch.acceptance_probability(note) == pytest.approx(1.0, abs=1e-12)
    assert ch.verify(note) is True
    assert note.consumed


@pytest.mark.parametrize("mode", [W.WiesnerMode.SHOTS, W.WiesnerMode.SYMBOLIC])
def test_honest_accept_other_modes(mode):
    ch = W.WiesnerChallenger(mode=mode, seed=2)
    assert all(ch.verify(ch.mint(24, s)) for s in range(20))


def test_symbolic_record_kind_and_no_attack_surface():
    ch = W.WiesnerChallenger(mode=W.WiesnerMode.SYMBOLIC)
    note = ch.mint(8, 3)
    assert note.record.state_kind == StateKind.SYMBOLIC_RECORD
    with pytest.raises(RegisterError):
        note.split(kraus_keep_and_blank())


def test_mint_is_iid_uniform_bb84():
    ch = W.WiesnerChallenger()
    note = ch.mint(4000, 11)
    sec = ch.leak_secret_TEST_ONLY(note)
    for arr in ([b == "Z" for b in sec["bases"]], sec["bits"]):
        k = int(sum(arr))
        ci = binomtest(k, 4000).proportion_ci(confidence_level=0.999, method="exact")
        assert ci.low <= 0.5 <= ci.high


def test_consumed_note_cannot_be_reverified():
    ch = W.WiesnerChallenger()
    note = ch.mint(4, 5)
    ch.verify(note)
    with pytest.raises(ConsumedTokenError):
        ch.verify(note)


# ---------------------------------------------------------- attacker API (lane C hook)
def _n_x(ch, note):
    return sum(b == "X" for b in ch.leak_secret_TEST_ONLY(note)["bases"])


def _blank_pass(ch, note):
    """Pr[|0> passes verification] for the note's secret: Z0 -> 1, Z1 -> 0, X -> 1/2."""
    sec = ch.leak_secret_TEST_ONLY(note)
    table = {("Z", 0): 1.0, ("Z", 1): 0.0, ("X", 0): 0.5, ("X", 1): 0.5}
    return float(np.prod([table[(b, x)] for b, x in zip(sec["bases"], sec["bits"], strict=True)]))


@pytest.mark.parametrize("n", [1, 2, 8, 16, 32, 64, 128])
def test_qubitwise_attacks_exact_pair_probabilities(n):
    """Exact, conditional on the (TEST_ONLY-revealed) secret; averages checked below."""
    ch = W.WiesnerChallenger(seed=3)
    note = ch.mint(n, 7 + n)
    expected = _blank_pass(ch, note)
    a, b = note.split(kraus_keep_and_blank())
    # keep-original + |0>: original passes surely; |0> passes Z0 always, Z1 never, X w.p. 1/2
    assert ch.acceptance_probability(a) == pytest.approx(1.0, abs=1e-12)
    assert ch.pair_acceptance_probability(a, b) == pytest.approx(expected, rel=1e-9, abs=1e-300)
    note = ch.mint(n, 9 + n)
    nx = _n_x(ch, note)
    a, b = note.split(kraus_measure_resend_z())
    # measure-resend in Z: per X-qubit one copy passes w.p. 1/2, both copies w.p. 1/4
    assert ch.acceptance_probability(a) == pytest.approx(0.5**nx, rel=1e-9)
    assert ch.pair_acceptance_probability(a, b) == pytest.approx(0.25**nx, rel=1e-9)


def test_secret_averaged_attack_values():
    """Averaged over the uniform secret: keep+blank -> (1/2)^n; Z measure-resend -> single
    copy (3/4)^n, both copies (5/8)^n (all below the W1 optimum (3/4)^n, as they must be).
    Averages of exact conditional values over many mints (Monte Carlo over the secret)."""
    ch = W.WiesnerChallenger(seed=3)
    n, m = 3, 3000
    kb, mr, mr1 = [], [], []
    for i in range(m):
        a, b = ch.mint(n, 50_000 + i).split(kraus_keep_and_blank())
        kb.append(ch.pair_acceptance_probability(a, b))
        a, b = ch.mint(n, 90_000 + i).split(kraus_measure_resend_z())
        mr.append(ch.pair_acceptance_probability(a, b))
        mr1.append(ch.acceptance_probability(a))
    for vals, target in ((kb, 0.5**n), (mr, 0.625**n), (mr1, 0.75**n)):
        se = np.std(vals) / np.sqrt(m)
        assert abs(np.mean(vals) - target) < 5 * se


def test_joint_channel_matches_qubitwise_for_product_attack():
    n = 2
    ks = []
    for o1 in (0, 1):
        for o2 in (0, 1):
            k = np.zeros((16, 4), dtype=complex)
            out = (o1 << 3) | (o2 << 2) | (o1 << 1) | o2  # |o1 o2>_cand0 |o1 o2>_cand1
            k[out, (o1 << 1) | o2] = 1.0
            ks.append(k)
    ch = W.WiesnerChallenger(seed=4)
    note = ch.mint(n, 21)
    nx = _n_x(ch, note)
    a, b = note.split(ks, joint=True)
    assert ch.pair_acceptance_probability(a, b) == pytest.approx(0.25**nx, rel=1e-9)


def test_sampled_pair_verification_matches_exact():
    ch = W.WiesnerChallenger(seed=5)
    n, trials, wins = 3, 3000, 0
    for i in range(trials):
        a, b = ch.mint(n, 1000 + i).split(kraus_measure_resend_z())
        x, y = ch.verify_pair(a, b)
        wins += x and y
    ci = binomtest(wins, trials).proportion_ci(confidence_level=0.999, method="exact")
    assert ci.low <= 0.625**n <= ci.high


def test_shots_mode_pair_frequency_matches_exact():
    ch = W.WiesnerChallenger(mode=W.WiesnerMode.SHOTS, seed=6)
    trials, wins = 3000, 0
    for i in range(trials):
        a, b = ch.mint(2, 5000 + i).split(kraus_measure_resend_z())
        x, y = ch.verify_pair(a, b)
        wins += x and y
    ci = binomtest(wins, trials).proportion_ci(confidence_level=0.999, method="exact")
    assert ci.low <= 0.625**2 <= ci.high


def test_non_cptp_attack_rejected():
    ch = W.WiesnerChallenger()
    bad = [np.zeros((4, 2), dtype=complex)]
    with pytest.raises(RegisterError):
        ch.mint(2, 1).split(bad)


# ---------------------------------------------------------------- secret boundary (C1)
def _walk(obj, seen=None):
    seen = seen if seen is not None else set()
    if id(obj) in seen:
        return
    seen.add(id(obj))
    yield obj
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _walk(v, seen)
    elif isinstance(obj, (list, tuple, set)):
        for v in obj:
            yield from _walk(v, seen)
    elif hasattr(obj, "__dict__"):
        for v in vars(obj).values():
            yield from _walk(v, seen)


def test_wallet_handle_carries_no_secret():
    ch = W.WiesnerChallenger()
    note = ch.mint(16, 42)
    assert isinstance(note, TokenHandle) and isinstance(ch, Challenger)
    js = canonical_json(note.record)
    leaked = ch.leak_secret_TEST_ONLY(note)
    assert "bases" not in js and "bits" not in js
    assert "".join(leaked["bases"]) not in js
    assert not any(isinstance(o, IssuerSecret) for o in _walk(note))
    assert set(note.record.public_metadata) == {"serial"}


def test_challenger_cannot_be_copied_or_serialized():
    ch = W.WiesnerChallenger()
    ch.mint(4, 1)
    with pytest.raises(SecretBoundaryError):
        copy.deepcopy(ch)
    with pytest.raises(SecretBoundaryError):
        pickle.dumps(ch)
    with pytest.raises(SecretBoundaryError):
        canonical_json(list(ch._secrets.values()))


def test_specs_match_frozen_fixture():
    import json
    from pathlib import Path

    fx = json.loads(
        (Path(__file__).resolve().parents[2] / "fixtures/contracts/protocol_wiesner.json").read_text()
    )
    assert W.WIESNER_IDEAL_SPEC == ProtocolSpec(**fx)
    assert W.WIESNER_NOISY_SPEC.adversary_game_id.value == "W2"
    assert W.WIESNER_NOISY_SPEC.theorem_id is None


# ----------------------------------------------------- TEST_ONLY unsafe control
def test_leaked_secret_trivial_forger_wins_out_of_model():
    res = W.unsafe_secret_leak_control(n=16, trials=50, seed=9, source_code_sha="test")
    assert res.successes == res.trials == 50
    assert res.proof_applicability == "OUT_OF_MODEL"
    assert res.theorem_upper_bound is None
    assert res.evidence_kind == EvidenceKind.MONTE_CARLO


def test_forger_refuses_non_test_only_input():
    ch = W.WiesnerChallenger()
    note = ch.mint(2, 1)
    with pytest.raises(ValueError):
        W.forge_from_leaked_secret({"bases": ["Z", "Z"], "bits": [0, 0]}, note.record)


# ------------------------------------------------------- serials, spend-once, replay
def test_serial_collision_detected():
    ch = W.WiesnerChallenger(serial_factory=lambda rng: "SN-dup")
    ch.mint(2, 1)
    with pytest.raises(W.SerialCollisionError):
        ch.mint(2, 2)


def test_serials_unique_by_default():
    ch = W.WiesnerChallenger()
    serials = {ch.mint(1, s).record.public_metadata["serial"] for s in range(500)}
    assert len(serials) == 500


def test_spend_once_replay_and_remint():
    ch = W.WiesnerChallenger(seed=8)
    note = ch.mint(8, 77)
    serial = note.record.public_metadata["serial"]
    r1 = ch.redeem(note)
    assert r1.accepted and r1.reason == "accepted"
    assert note.record.freshness == "spent" and ch.serial_status(serial) == "spent"
    assert r1.reminted is not None and r1.reminted.record.freshness == "verified_reminted"
    assert r1.reminted.record.public_metadata["serial"] != serial
    # replay: a copy of the classical record with any quantum state is refused outright
    replay = ch.mint(8, 78)
    replay.record = replay.record.model_copy(update={"public_metadata": {"serial": serial}})
    r2 = ch.redeem(replay)
    assert (r2.accepted, r2.reason) == (False, "replay") and not replay.consumed
    assert ch.redeem(r1.reminted).accepted


def test_rejected_presentation_also_spends_serial():
    ch = W.WiesnerChallenger(seed=1, remint=False)
    a, b = ch.mint(12, 3).split(kraus_measure_resend_z())
    first = ch.redeem(a)
    second = ch.redeem(b)
    assert second.reason == "replay" and not second.accepted
    assert first.reason in ("accepted", "rejected")


def test_unknown_serial_rejected():
    ch1, ch2 = W.WiesnerChallenger(), W.WiesnerChallenger()
    assert ch2.redeem(ch1.mint(2, 1)).reason == "unknown_serial"


# --------------------------------------------------------- noisy / threshold (W2)
def test_noisy_requires_threshold_and_registers_w2():
    with pytest.raises(ValueError):
        W.WiesnerChallenger(noise=W.NoiseModel("depolarizing", 0.1))
    ch = W.WiesnerChallenger(noise=W.NoiseModel("depolarizing", 0.1), threshold=2)
    assert ch.protocol_id == "wiesner_noisy" and ch.spec.adversary_game_id.value == "W2"
    assert ch.mint(4, 1).record.protocol_id == "wiesner_noisy"


@pytest.mark.parametrize("n,p,t", [(20, 0.1, 0), (20, 0.1, 2), (64, 0.05, 3)])
def test_depolarizing_honest_acceptance_is_binomial_survival(n, p, t):
    ch = W.WiesnerChallenger(noise=W.NoiseModel("depolarizing", p), threshold=t)
    exact = ch.acceptance_probability(ch.mint(n, 31))
    assert exact == pytest.approx(binom.cdf(t, n, p / 2), rel=1e-9)
    assert exact == pytest.approx(W.honest_acceptance_probability(n, p / 2, t), rel=1e-12)


def test_bit_flip_honest_acceptance_depends_on_z_count():
    p, t = 0.2, 1
    ch = W.WiesnerChallenger(noise=W.NoiseModel("bit_flip", p), threshold=t)
    note = ch.mint(30, 12)
    n_z = sum(b == "Z" for b in ch.leak_secret_TEST_ONLY(note)["bases"])
    assert 0 < n_z < 30
    assert ch.acceptance_probability(note) == pytest.approx(binom.cdf(t, n_z, p), rel=1e-9)


@pytest.mark.parametrize("mode", [W.WiesnerMode.SHOTS, W.WiesnerMode.SYMBOLIC, W.WiesnerMode.EXACT])
def test_noisy_sampled_acceptance_matches_formula(mode):
    n, p, t, trials = 16, 0.2, 1, 2000
    ch = W.WiesnerChallenger(mode=mode, noise=W.NoiseModel("depolarizing", p), threshold=t, seed=13)
    acc = sum(ch.verify(ch.mint(n, 4000 + i)) for i in range(trials))
    ci = binomtest(acc, trials).proportion_ci(confidence_level=0.999, method="exact")
    assert ci.low <= binom.cdf(t, n, p / 2) <= ci.high


def test_noise_model_validation():
    with pytest.raises(ValueError):
        W.NoiseModel("bit_flip", 1.5)
    for nm in (W.NoiseModel("bit_flip", 0.3), W.NoiseModel("depolarizing", 0.3)):
        assert np.allclose(sum(k.conj().T @ k for k in nm.kraus()), np.eye(2))


# ------------------------------------------------------------------- mutation test
def _honest_checks_pass(ch_factory) -> bool:
    ch = ch_factory()
    return all(np.isclose(ch.acceptance_probability(ch.mint(8, s)), 1.0) for s in range(10))


def _pair_check_passes(ch_factory) -> bool:
    ch = ch_factory()
    a, _ = ch.mint(6, 3).split(kraus_keep_and_blank())
    return bool(np.isclose(ch.acceptance_probability(a), 1.0))  # kept original must pass


def test_mutation_wrong_verifier_mapping_is_caught(monkeypatch):
    factory = lambda: W.WiesnerChallenger(seed=0)  # noqa: E731
    assert _honest_checks_pass(factory) and _pair_check_passes(factory)

    def swapped(basis, bit):  # mutant: verifier uses (X,0)=|-> and (X,1)=|+>
        return bb84_projector(basis, bit if Basis(basis) == Basis.Z else 1 - bit)

    monkeypatch.setattr(W, "bb84_projector", swapped)
    assert not _honest_checks_pass(factory)
    assert not _pair_check_passes(factory)

    def wrong_basis(basis, bit):  # mutant: verifier measures every qubit in Z
        return bb84_projector(Basis.Z, bit)

    monkeypatch.setattr(W, "bb84_projector", wrong_basis)
    assert not _honest_checks_pass(factory)
