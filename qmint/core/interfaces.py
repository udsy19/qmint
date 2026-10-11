"""Frozen cross-lane interfaces (structural Protocols).

These are the only coupling points between lanes. Implementations live in the
owning lane's package; consumers depend on these Protocols, not on each other.

  ProofEvaluator      -- lane D implements; lane I (compiler) and K/N consume.
  IndependentChecker  -- lane D implements a SEPARATE code path; lane I post-validates.
  AttackSimulator     -- lane C implements; never consumed by the compiler as a bound.
  Challenger          -- lane B implements per protocol; owns IssuerSecret; adversary
                         receives only `TokenHandle` capabilities, never secrets.
  CalibrationProvider -- lane E implements; returns CalibrationRecord with intervals.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

from qmint.core.contracts import (
    AttackResult,
    BoundRequest,
    BoundResult,
    CalibrationRecord,
    SecurityCertificate,
    TokenRecord,
)


@runtime_checkable
class ProofEvaluator(Protocol):
    evaluator_id: str

    def evaluate(self, request: BoundRequest) -> BoundResult:
        """Return an applicable upper bound or a value-less UNSUPPORTED/out-of-domain result."""
        ...


@runtime_checkable
class IndependentChecker(Protocol):
    checker_id: str

    def check(self, certificate: SecurityCertificate) -> SecurityCertificate:
        """Re-derive every bound independently. Return a copy whose status is CERTIFIED only
        if all bounds re-derive within declared tolerance; otherwise UNCERTIFIED with reason."""
        ...


@runtime_checkable
class TokenHandle(Protocol):
    """Opaque capability to a (simulated or physical) quantum register.

    Exposes only what a physical holder could do: apply a channel / measure. It must
    not expose preparation bases/bits; deep-copying the Python object is a simulator
    artefact and is NOT cloning (see docs/THREAT_MODEL.md)."""

    record: TokenRecord

    def n_qubits(self) -> int: ...


@runtime_checkable
class Challenger(Protocol):
    protocol_id: str

    def mint(self, n: int, rng_seed: int) -> TokenHandle: ...

    def verify(self, candidate: Any) -> bool:
        """Verify a candidate against the hidden IssuerSecret held only by the challenger."""
        ...


@runtime_checkable
class AttackSimulator(Protocol):
    attack_id: str

    def run(self, challenger_factory: Any, n: int, trials: int, seed: int) -> AttackResult: ...


@runtime_checkable
class CalibrationProvider(Protocol):
    def calibrations(self) -> Sequence[CalibrationRecord]: ...
