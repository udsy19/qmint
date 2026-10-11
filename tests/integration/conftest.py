"""Shared builders/fixtures for lane-L integration tests."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from qmint.core.contracts import AttackResult, EvidenceKind, Interval, Unit
from qmint.core.records import Provenance

ROOT = Path(__file__).resolve().parents[2]


def provenance(seed: int | None = 7) -> Provenance:
    return Provenance(git_sha="a" * 40, environment_lock="b" * 64, command="pytest", seed=seed)


def mc_attack(seed: int, trials: int = 200, deterministic: bool = True) -> AttackResult:
    """Toy measure-resend-style Monte Carlo record (SYNTHETIC test data, not a result)."""
    rng = random.Random(seed) if deterministic else random.SystemRandom()
    successes = sum(rng.random() < 0.75 for _ in range(trials))
    p = successes / trials
    return AttackResult(
        attack_id="A_test_toy", game_id="W1", attack_capability=["measure_resend"], token_n=1,
        attack_method="toy", quantum_channel_description="none (test fixture)", verifier_rule="exact",
        seed=seed, trials=trials, successes=successes,
        success_rate_ci=Interval(lo=max(0.0, p - 0.1), hi=min(1.0, p + 0.1), unit=Unit.PROBABILITY, point=p),
        ci_method="test-only", proof_applicability="NO_THEOREM", backend_kind="python_random",
        evidence_kind=EvidenceKind.MONTE_CARLO, source_code_sha="c" * 40,
    )


@pytest.fixture
def prov() -> Provenance:
    return provenance()


@pytest.fixture
def store(tmp_path):
    from qmint.core.records import RecordStore

    return RecordStore(tmp_path / "experiments")


@pytest.fixture(autouse=True)
def _no_ambient_secrets(monkeypatch):
    """Tests control credential env vars themselves."""
    monkeypatch.delenv("IONQ_API_KEY", raising=False)


@pytest.fixture
def make_attack():
    return mc_attack
