"""Lane B / B3: Schiansky et al. 2023 quantum-digital payments (game D1)."""

import copy
import itertools
import math

import numpy as np
import pytest
from scipy.stats import binomtest

from qmint.core.contracts import Basis, SecretBoundaryError, TransactionTrace
from qmint.core.serialization import canonical_json
from qmint.protocols import schiansky_payment_2023 as S
from qmint.protocols.register import bb84_projector, projector_from_angle

TIMES = {"issue": 0.0, "pay": 10.0, "to_merchant": 20.0, "forward": 30.0, "verify": 40.0}


def system(ell=4, N=8, rule=None, seed=1, merchants=(3, 5, 9)):
    return S.SchianskyPaymentSystem(ell=ell, N=N, merchants=merchants, rule=rule or S.IdealRule(), seed=seed)


# ----------------------------------------------------------------- paper vectors
def test_step2_example_vector_from_paper():
    """(b, B) = (0101, 0011) -> |+>|->|0>|1> (P04 main text, step 2)."""
    from qmint.protocols.register import bb84_ket

    b, B = (0, 1, 0, 1), (0, 0, 1, 1)
    sq = 1 / math.sqrt(2)
    expect = [[sq, sq], [sq, -sq], [1, 0], [0, 1]]
    for bj, Bj, v in zip(b, B, expect, strict=True):
        assert np.allclose(bb84_ket(S.BASIS_OF_BIT[Bj], bj), v)


def test_published_aggregates_reproduced():
    """SI Table 2 (PUBLISHED_AGGREGATE): M(e_m^{+/-}, l_m) = 0.448, allowed mishaps 0.4849."""
    assert S.mishaps(0.03278, 0.224) == pytest.approx(0.448, abs=5e-4)
    assert S.allowed_mishaps(0.0602) == pytest.approx(0.4849, abs=1e-4)
    # with the paper's delta_h = 0.031, delta_d = 0.01, eq. (23) holds at the measured point
    assert S.parameters_admissible(0.03278, 0.224, 0.031, 0.01, 0.0602)
    assert not S.parameters_admissible(0.03278, 0.30, 0.031, 0.01, 0.0602)


# --------------------------------------------------------------------- the MAC
def test_polymac_is_strongly_universal_ell2():
    mac = S.PolyMac(2)
    keys = list(itertools.product(range(4), range(4)))  # |C| = 16 = |M|^2
    for m1, m2 in itertools.permutations(range(4), 2):
        pairs = [(mac.tag(k, m1), mac.tag(k, m2)) for k in keys]
        assert len(set(pairs)) == 16  # each tag pair hit by exactly one key: forge prob 1/|m|


@pytest.mark.parametrize("ell", [1, 2, 4, 8, 16, 32, 64])
def test_gf2_field_inverse_exists(ell):
    rng = np.random.default_rng(ell)
    a = int(rng.integers(1, 2 ** min(ell, 62)))
    # a^(2^ell - 1) = 1 in GF(2^ell)*
    r, base, e = 1, a, 2**ell - 1
    while e:
        if e & 1:
            r = S.gf2_mul(r, base, ell)
        base = S.gf2_mul(base, base, ell)
        e >>= 1
    assert r == 1


def test_basis_bits_expand_sub_tokens():
    assert S.basis_bits(0b10, 2, 3) == (1, 1, 1, 0, 0, 0)


# -------------------------------------------------------------- honest payments
@pytest.mark.parametrize("seed", range(8))
def test_honest_payment_accepted_and_trace_valid(seed):
    sysm = system(seed=seed)
    sysm.open_account("cid-1", -100.0)
    rep = sysm.honest_payment("cid-1", 5, TIMES, rng_seed=seed)
    assert rep.accepted
    tr = sysm.trace("tr", "net", token_id=sysm._token_of["cid-1"])
    assert isinstance(tr, TransactionTrace) and not tr.double_spend_accepted
    kinds = [e.kind for e in tr.events]
    for a, b in [
        ("issue", "quantum_exchange"),
        ("branch_choice", "measurement"),
        ("measurement", "local_validation_start"),
    ]:
        assert kinds.index(a) < kinds.index(b)
    assert kinds[-3:] == [
        "verification_result_available_local",
        "issuer_aware_of_spend",
        "bank_settlement_final",
    ]
    canonical_json(tr)


def test_replay_of_cryptogram_rejected():
    sysm = system()
    sysm.open_account("c", 0.0)
    h = sysm.issue_token("c", 1.0)
    kappa = sysm.client_pay("c", h, 3, 2.0)
    assert sysm.ttp_verify("c", 3, kappa, 3.0).accepted
    again = sysm.ttp_verify("c", 3, kappa, 4.0)
    assert not again.accepted and again.reason == "token already spent"


def test_merchant_substitution_rejected():
    sysm = system(ell=8, N=16, merchants=tuple(range(256)))
    sysm.open_account("c", 0.0)
    key = sysm.client_key_TEST_ONLY("c")
    other = next(m for m in range(256) if sysm.mac.tag(key, m) != sysm.mac.tag(key, 7))
    h = sysm.issue_token("c", 1.0)
    kappa = sysm.client_pay("c", h, 7, 2.0)
    assert not sysm.check("c", other, kappa).accepted  # CH3 tampering: wrong M_i
    assert sysm.check("c", 7, kappa).accepted


def test_unknown_merchant_refused_by_client():
    sysm = system()
    sysm.open_account("c", 0.0)
    with pytest.raises(ValueError):
        sysm.client_pay("c", sysm.issue_token("c", 1.0), 4, 2.0)


def test_quantum_channel_substitution_detected():
    """CH1 attacker swaps |P> for fresh random BB84 states: the TTP rejects."""
    from qmint.protocols.register import FactorizedRegister, RegisterHandle, bb84_ket

    sysm = system(ell=4, N=16)
    sysm.open_account("c", 0.0)
    h = sysm.issue_token("c", 1.0)
    rng = np.random.default_rng(0)
    reg = FactorizedRegister()
    kets = [
        bb84_ket(Basis.Z if rng.integers(2) else Basis.X, int(rng.integers(2))) for _ in range(h.n_qubits())
    ]
    fake = RegisterHandle(reg, reg.add_product_state([np.outer(v, v.conj()) for v in kets]), h.record)
    kappa = sysm.client_pay("c", fake, 5, 2.0)
    assert not sysm.ttp_verify("c", 5, kappa, 3.0).accepted


# --------------------------------------------------------------- threshold rule
def _kappa_with(sysm, cid, merchant, n_err, n_loss):
    """Craft a cryptogram on a single-block token with exact error / loss counts (TEST_ONLY)."""
    key = sysm.client_key_TEST_ONLY(cid)
    m = S.basis_bits(sysm.mac.tag(key, merchant), sysm.ell, sysm.N)
    sec = sysm._tokens[sysm._token_of[cid]].reveal_for_testing_only()
    b, B = sec["bits"], sec["extra"]["B"]
    kappa = list(b)
    sift = [j for j in range(len(b)) if m[j] == B[j]]
    for j in sift[:n_err]:
        kappa[j] ^= 1
    for j in [j for j in range(len(b)) if j not in sift][:n_loss]:
        kappa[j] = None
    return tuple(kappa), len(sift)


def test_threshold_rule_boundary():
    N = 200
    sysm = system(ell=1, N=N, merchants=(0, 1), rule=S.ThresholdRule(max_mishaps=0.30))
    sysm.open_account("c", 0.0)
    sysm.issue_token("c", 1.0)
    kappa, n_sift = _kappa_with(sysm, "c", 1, n_err=2, n_loss=40)
    e, l_ = 2 / n_sift, 40 / N
    rep = sysm.check("c", 1, kappa)
    assert rep.units[0]["e_hat"] == pytest.approx(e) and rep.units[0]["l_hat"] == pytest.approx(l_)
    assert rep.accepted == (S.mishaps(e, l_) < 0.30)
    kappa2, _ = _kappa_with(sysm, "c", 1, n_err=12, n_loss=40)
    assert not sysm.check("c", 1, kappa2).accepted


def test_ideal_rule_rejects_any_declared_loss():
    sysm = system(ell=1, N=50, merchants=(0, 1))
    sysm.open_account("c", 0.0)
    sysm.issue_token("c", 1.0)
    kappa, _ = _kappa_with(sysm, "c", 0, n_err=0, n_loss=1)
    assert not sysm.check("c", 0, kappa).accepted


def _reference_pass_rate(N, loss, err, thr, draws=400_000, seed=0):
    """Count-level reference for one sub-token: lost ~ Bin(N, loss); sifted ~ Bin(N-lost, 1/2);
    errors ~ Bin(sifted, err); pass iff M(e_hat, l_hat) < thr. Independent code path."""
    rng = np.random.default_rng(seed)
    lost = rng.binomial(N, loss, draws)
    sift = rng.binomial(N - lost, 0.5)
    errs = rng.binomial(sift, err)
    e_hat = np.where(sift > 0, errs / np.maximum(sift, 1), 0.0)
    return float(np.mean(S.mishaps(e_hat, lost / N) < thr))


@pytest.mark.parametrize("granularity", ["per_block", "whole"])
def test_honest_lossy_noisy_pass_rate_matches_count_level_reference(granularity):
    """Honest device at the paper's operating point (l=0.224, e=0.0328) with tolerance
    (1+0.031) M(e_h, l_h) (SI Table 2 delta_h). ell=1 so per-block == whole token."""
    N, trials, loss, err = 2000, 150, 0.224, 0.0328
    thr = S.threshold_from_honest(err, loss, 0.031)
    acc = 0
    for seed in range(trials):
        sysm = system(ell=1, N=N, merchants=(0, 1), rule=S.ThresholdRule(thr, granularity), seed=seed)
        sysm.open_account("c", 0.0)
        dev = S.ClientDevice(loss=loss, error=err)
        acc += sysm.honest_payment("c", 1, TIMES, device=dev, rng_seed=seed).accepted
    ref = _reference_pass_rate(N, loss, err, thr)
    ci = binomtest(acc, trials).proportion_ci(confidence_level=0.999, method="exact")
    assert ci.low <= ref <= ci.high
    # finding: at N = 2000 the paper's small delta_h leaves a large honest-abort probability;
    # the paper's own sub-token length is N ~ 4.48e6 (SI Table 2)
    assert ref < 0.95


# ------------------------------------------------- D1 dual cryptograms (simple MC)
def _d1_trial(seed, strategy, N=3):
    """Malicious client (knows its own C) tries to obtain valid cryptograms for TWO merchants."""
    sysm = system(ell=1, N=N, merchants=(0, 1), seed=seed)
    sysm.open_account("c", 0.0)
    key = sysm.client_key_TEST_ONLY("c")
    m0, m1 = (S.basis_bits(sysm.mac.tag(key, m), 1, N) for m in (0, 1))
    if m0 == m1:  # MAC collision (prob 1/|m| = 1/2 for ell = 1): trivial double use, excluded here
        return None
    h = sysm.issue_token("c", 1.0)
    rng = np.random.default_rng(seed + 7)
    if strategy == "measure_m0_guess_m1":
        k0 = tuple(h.measure(j, bb84_projector(S.BASIS_OF_BIT[m0[j]], 0), rng) for j in range(N))
        k1 = tuple(int(v) for v in rng.integers(0, 2, size=N))
    else:  # Breidbart: one outcome serves as the guess in both bases (P04 Methods, 85.4%)
        k0 = k1 = tuple(h.measure(j, projector_from_angle(math.pi / 8), rng) for j in range(N))
    return sysm.check("c", 0, k0).accepted and sysm.check("c", 1, k1).accepted


@pytest.mark.parametrize(
    "strategy,per_state",
    [("measure_m0_guess_m1", 0.75), ("breidbart", 0.5 + 1 / (2 * math.sqrt(2)))],
)
def test_d1_double_cryptogram_monte_carlo(strategy, per_state):
    """MONTE_CARLO lower-bound evidence for two simple strategies (no bound claimed)."""
    res = [r for r in (_d1_trial(s, strategy) for s in range(8000)) if r is not None]
    wins = sum(res)
    ci = binomtest(wins, len(res)).proportion_ci(confidence_level=0.999, method="exact")
    assert len(res) > 3000
    assert ci.low <= per_state**3 <= ci.high


# ---------------------------------------------------------- boundary & privacy
def test_secrets_not_exposed_to_merchant_or_trace():
    sysm = system()
    sysm.open_account("c", 0.0)
    sysm.honest_payment("c", 3, TIMES)
    with pytest.raises(SecretBoundaryError):
        copy.deepcopy(sysm)
    assert {k for k, _ in sysm.views["Merchant"]} == {"kappa", "cid"}
    tr = sysm.trace("t", "n", token_id=sysm._token_of["c"])
    assert all(not isinstance(v, (list, tuple)) for e in tr.events for v in e.detail.values())
    h = sysm.issue_token("c", 50.0)
    assert set(h.record.public_metadata) == {"cid", "ell", "N"}


def test_cryptogram_law_independent_of_merchant():
    """Bases are never revealed: kappa is uniform whichever merchant was chosen (exact, N=1)."""
    for m_bit in (0, 1):
        p0 = 0.0
        for b, B in itertools.product((0, 1), repeat=2):
            from qmint.protocols.register import bb84_ket

            v = bb84_ket(S.BASIS_OF_BIT[B], b)
            p0 += 0.25 * np.real(v.conj() @ bb84_projector(S.BASIS_OF_BIT[m_bit], 0) @ v)
        assert p0 == pytest.approx(0.5)


# ------------------------------------------------------------------- mutation
def test_mutation_wrong_basis_mapping_caught(monkeypatch):
    def ok_rate():
        n = 0
        for seed in range(10):
            sysm = system(seed=seed)
            sysm.open_account("c", 0.0)
            n += sysm.honest_payment("c", 5, TIMES, rng_seed=seed).accepted
        return n

    assert ok_rate() == 10

    def swapped(basis, bit):  # mutant client device: (X,0) read as |->
        return bb84_projector(basis, bit if Basis(basis) == Basis.Z else 1 - bit)

    monkeypatch.setattr(S, "bb84_projector", swapped)
    assert ok_rate() == 0
