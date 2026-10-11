"""T0/T2/T4: lane C challenger boundary, game-ID guard and records."""

import math

import numpy as np
import pytest

from qmint.attacks.games import (
    ThresholdLossChallenger,
    W1Challenger,
    theorem_upper_bound,
)
from qmint.attacks.records import monte_carlo_result, sdp_result
from qmint.core.contracts import EvidenceKind, GameId, SecretBoundaryError
from qmint.core.interfaces import Challenger, TokenHandle
from qmint.core.serialization import canonical_json
from qmint.proofs.ideal_bounds import UnsupportedGameError


def test_theorem_guard_w1_and_w1cv_only():
    assert theorem_upper_bound(GameId.W1, 3) == pytest.approx(0.75**3)
    assert theorem_upper_bound("W1_CV", 1) == pytest.approx(0.75 + math.sqrt(2) / 8)
    for g in (GameId.W2, GameId.S1, GameId.S2, GameId.D1, GameId.A1, GameId.C1):
        with pytest.raises(UnsupportedGameError):
            theorem_upper_bound(g, 4)


def test_challenger_satisfies_interfaces():
    ch = W1Challenger()
    note = ch.mint(4, 7)
    assert isinstance(ch, Challenger)
    assert isinstance(note, TokenHandle)
    assert note.n_qubits() == 4


def test_public_record_has_no_secret_and_secret_does_not_serialize():
    ch = W1Challenger()
    note = ch.mint(8, 1)
    js = canonical_json(note.record)
    assert "bases" not in js and "bits" not in js
    with pytest.raises(SecretBoundaryError):
        canonical_json(ch._secrets[note.record.token_id])
    assert not any(hasattr(note, a) for a in ("bases", "bits", "secret"))


def test_honest_note_always_accepted():
    for s in range(50):
        ch = W1Challenger()
        assert ch.verify(ch.mint(6, s))


def test_mint_is_deterministic_per_seed():
    a, b = W1Challenger(), W1Challenger()
    na, nb = a.mint(8, 42), b.mint(8, 42)
    assert all(np.allclose(x, y) for x, y in zip(na._positions, nb._positions, strict=True))


def test_w1_rejects_loss_flags():
    ch = W1Challenger()
    note = ch.mint(4, 3)
    assert not ch.verify(note.candidate(0, loss_flags=[0]))


def test_w2_threshold_accounting():
    ch = ThresholdLossChallenger(0.25, 0.125)
    assert ch.allowed(8, 2) == (2, 0)
    assert ch.allowed(16, 4) == (4, 1)
    note = ch.mint(8, 5)
    assert not ch.verify(note.candidate(0, loss_flags=[0, 1, 2]))  # too many losses
    note = ch.mint(8, 6)
    assert ch.verify(note.candidate(0, loss_flags=[0, 1]))


def test_records_validate_and_never_present_mc_as_bound():
    rec, ci = monte_carlo_result(
        attack_id="X", game_id=GameId.W1, capability=["one_note"], n=2, method="m", channel="c",
        verifier_rule="v", seed=1, trials=100, successes=56, applicability="IN_MODEL", theorem_bound=0.5625,
    )
    assert rec.evidence_kind == EvidenceKind.MONTE_CARLO
    assert rec.sdp_dual is None  # an MC record carries no upper-bound field
    assert rec.success_rate_ci.lo <= 0.56 <= rec.success_rate_ci.hi
    assert ci["wilson_lo"] <= 0.56 <= ci["wilson_hi"]
    with pytest.raises(ValueError):
        sdp_result(
            attack_id="X", game_id=GameId.W1, n=1, verifier_rule="v", primal=0.75, dual=0.75, dual_residual=0,
            primal_residual=0, solver="s", applicability="IN_MODEL", theorem_bound=0.75,
            evidence=EvidenceKind.MONTE_CARLO,
        )
    with pytest.raises(ValueError):
        monte_carlo_result(
            attack_id="X", game_id=GameId.W1, capability=["a"], n=1, method="m", channel="c", verifier_rule="v",
            seed=1, trials=10, successes=11, applicability="IN_MODEL", theorem_bound=None,
        )
