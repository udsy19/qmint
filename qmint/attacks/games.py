"""Lane C's own minimal, independent W1 challenger and toy verifier variants.

Lane C deliberately does NOT import lane B's Wiesner implementation, so attack results are
an independent check. At integration the attack functions (which take per-qubit Kraus
operators) can be run against lane B via the ``Challenger``/``TokenHandle`` protocols in
``qmint.core.interfaces``.

Capability boundary
-------------------
The adversary receives a :class:`NoteRegister` (a ``TokenHandle``). It can apply channels
given as Kraus operators, detach/attach qubits and hand candidates to a verifier. It never
receives preparation bases/bits: those live in an ``IssuerSecret`` held by the challenger.
The register keeps density matrices internally -- that is a simulator artefact, not a
capability (reading ``_positions`` from attack code is a test failure, see tests).

Games implemented here
----------------------
* ``W1``  -- :class:`W1Challenger`: exact projective verifier, all n positions must pass,
  no oracle access. MVW 2012 Theorem 1 applies: optimal 1->2 success = (3/4)^n.
* ``W2`` (toy) -- :class:`ThresholdLossChallenger`: holder reports per-position loss flags
  BEFORE verification (flags are fixed at submission and cannot be revised after any
  outcome is revealed); verifier ignores lost positions, accepts iff
  #lost <= floor(max_loss_fraction * n) and #errors <= floor(max_error_fraction * #reported).
  No published closed form is assumed for this game.
* ``W1`` + oracle (toy, OUT_OF_MODEL) -- :class:`LeakyOracleChallenger`: additionally offers
  ``query_oracle`` which verifies a note, reveals only accept/reject, and RETURNS the
  post-measurement note to the holder; repeated submissions allowed. This violates the
  W1 game definition ("no additional adaptive access to the secret verifier").
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np

from qmint.attacks.linalg import apply_kraus, kron_all, proj
from qmint.core.contracts import (
    Basis,
    GameId,
    IssuerSecret,
    StateKind,
    TokenRecord,
    check_protocol_game,
)
from qmint.proofs.ideal_bounds import IDEAL_BASES, UnsupportedGameError
from qmint.proofs.registry import default_registry
from qmint.quantum.bb84 import state_vector

# --------------------------------------------------------------------------- #
# Game-ID guard for theorem values (published bounds are game-specific)
# --------------------------------------------------------------------------- #

#: Citation of the MVW 2012 source, from lane D's theorem registry (proofs/OBLIGATIONS.yaml).
MVW_SOURCE = default_registry().sources["MVW2012"].citation
_MVW_GAMES = (GameId.W1, GameId.W1_CV)


def theorem_upper_bound(game_id: GameId | str, n: int) -> float:
    """Published optimal success for exactly W1 or W1_CV (MVW 2012 Thms 1-2); anything else raises.

    Per-qubit bases come from ``qmint.proofs.ideal_bounds.IDEAL_BASES`` (lane D). W2/S1/S2/D1/A1/C1
    have no MVW bound here: we never transfer the W1 theorem across games.
    """
    g = GameId(game_id)
    if n < 1:
        raise ValueError("n must be >= 1")
    if g not in _MVW_GAMES:
        raise UnsupportedGameError(f"no MVW theorem applies to game {g.value}; bound is UNKNOWN (None), not 0")
    return IDEAL_BASES[g][0] ** n


# --------------------------------------------------------------------------- #
# Register / token handle
# --------------------------------------------------------------------------- #


class _HeldQubit:
    """Opaque qubit detached from a note. Only physical operations are exposed."""

    __slots__ = ("_rho",)

    def __init__(self, rho: np.ndarray) -> None:
        self._rho = rho

    def __repr__(self) -> str:
        return "_HeldQubit(<opaque>)"


class NoteRegister:
    """A (possibly multi-copy) simulated note register. Implements ``TokenHandle``.

    Each of the ``n`` positions holds a joint density matrix over ``n_copies`` qubits
    ("lanes"): lane c is position i of candidate c. Positions are mutually unentangled,
    which suffices for all attacks in this module (they act position-wise; joint coherent
    attacks are handled exactly by the SDP module, not by simulation).
    """

    def __init__(self, record: TokenRecord, positions: list[np.ndarray], n_copies: int = 1) -> None:
        self.record = record
        self._positions = positions
        self._n_copies = n_copies

    def n_qubits(self) -> int:
        return len(self._positions)

    @property
    def n_copies(self) -> int:
        return self._n_copies

    def apply_channel(self, kraus: Sequence[np.ndarray]) -> None:
        """Apply the same channel (Kraus operators) independently at every position."""
        self.apply_position_channels([kraus] * self.n_qubits())

    def apply_position_channels(self, channels: Sequence[Sequence[np.ndarray]]) -> None:
        """Apply channel ``channels[i]`` at position i.

        Kraus operators map C^(2^n_copies) -> C^(2^m) with the same m for every position;
        afterwards the register holds m copies (m=2 for a 1->2 counterfeiting map).
        """
        if len(channels) != self.n_qubits():
            raise ValueError("need one channel per position")
        douts = {k[0].shape[0] for k in channels}
        if len(douts) != 1 or any(k[0].shape[1] != 2**self._n_copies for k in channels):
            raise ValueError("channel dimensions inconsistent with register")
        dout = douts.pop()
        m = int(round(math.log2(dout)))
        if 2**m != dout:
            raise ValueError("output dimension must be a power of two")
        for i, kraus in enumerate(channels):
            self._positions[i] = apply_kraus(kraus, self._positions[i])
        self._n_copies = m

    def detach(self, i: int) -> _HeldQubit:
        if self._n_copies != 1:
            raise ValueError("detach only supported on single-copy notes")
        held = _HeldQubit(self._positions[i])
        self._positions[i] = np.zeros((2, 2), dtype=complex)  # empty slot until attach
        return held

    def attach(self, i: int, qubit: _HeldQubit | np.ndarray) -> None:
        """Attach a held qubit, or an attacker-PREPARED state (attacker knows its matrix)."""
        if self._n_copies != 1:
            raise ValueError("attach only supported on single-copy notes")
        rho = qubit._rho if isinstance(qubit, _HeldQubit) else np.asarray(qubit, dtype=complex)
        if rho.shape != (2, 2) or abs(np.trace(rho) - 1) > 1e-9:
            raise ValueError("attach requires a single-qubit density matrix")
        self._positions[i] = rho

    def candidate(self, copy_index: int, loss_flags: Sequence[int] = ()) -> Candidate:
        if not 0 <= copy_index < self._n_copies:
            raise IndexError("copy index out of range")
        return Candidate(self, copy_index, frozenset(int(i) for i in loss_flags))


@dataclass(frozen=True)
class Candidate:
    """One candidate note for verification: lane ``copy_index`` of a register.

    ``loss_flags`` are the holder's per-position loss reports, fixed at submission time.
    """

    register: NoteRegister
    copy_index: int
    loss_flags: frozenset[int] = field(default_factory=frozenset)

    @property
    def record(self) -> TokenRecord:
        return self.register.record

    def n_qubits(self) -> int:
        return self.register.n_qubits()


def fresh_note(states: Sequence[np.ndarray], record: TokenRecord) -> NoteRegister:
    """A single-copy register prepared from attacker-KNOWN states (e.g. a counterfeit)."""
    return NoteRegister(record, [np.asarray(s, dtype=complex) for s in states], 1)


# --------------------------------------------------------------------------- #
# Challengers
# --------------------------------------------------------------------------- #


class W1Challenger:
    """Independent lane-C W1 challenger (Wiesner, exact projective verifier).

    ``mint`` samples bases/bits uniformly and independently per position from the
    challenger's own RNG; the ``IssuerSecret`` never leaves this object (except via the
    explicit OUT_OF_MODEL ``leak_secret_out_of_model`` used by negative controls).
    """

    protocol_id = "wiesner_ideal"
    game_id = GameId.W1

    def __init__(self) -> None:
        check_protocol_game(self.protocol_id, self.game_id)
        self._secrets: dict[str, IssuerSecret] = {}
        self._rng: np.random.Generator = np.random.default_rng(0)
        self._counter = 0

    def mint(self, n: int, rng_seed: int) -> NoteRegister:
        if n < 1:
            raise ValueError("n must be >= 1")
        rng = np.random.default_rng(rng_seed)
        bases = [Basis.Z if b == 0 else Basis.X for b in rng.integers(0, 2, n)]
        bits = [int(b) for b in rng.integers(0, 2, n)]
        # verifier randomness is independent of the minting randomness
        self._rng = np.random.default_rng([rng_seed, 0x5EC12E7])
        self._counter += 1
        token_id = f"C-{self.protocol_id}-{rng_seed}-{self._counter}"
        self._secrets[token_id] = IssuerSecret(token_id=token_id, protocol_id=self.protocol_id, bases=bases, bits=bits)
        record = TokenRecord(
            token_id=token_id,
            protocol_id=self.protocol_id,
            n_prepared=n,
            source_state_family="BB84",
            public_metadata={"serial": token_id},
            issue_event_id=f"ev-{token_id}",
            state_kind=StateKind.IDEAL_SIMULATED,
            ownership_context="lane_C_attack_lab",
            backend_provenance="SIMULATOR_IDEAL:qmint.attacks.games",
        )
        positions = [proj(state_vector(b, x)) for b, x in zip(bases, bits, strict=True)]
        return NoteRegister(record, positions, 1)

    # -- verification ------------------------------------------------------ #

    def _secret_projector(self, token_id: str, i: int) -> np.ndarray:
        s = self._secrets[token_id]
        return proj(state_vector(s.bases[i], s.bits[i]))

    def _measure_position(self, cand: Candidate, i: int) -> bool:
        reg = cand.register
        k = reg.n_copies
        pi = self._secret_projector(cand.record.token_id, i)
        ops = [np.eye(2)] * k
        ops[cand.copy_index] = pi
        p_op = kron_all(ops)
        rho = reg._positions[i]
        p = float(np.real(np.trace(p_op @ rho)))
        p = min(1.0, max(0.0, p))
        passed = bool(self._rng.random() < p)
        q = p_op if passed else np.eye(2**k) - p_op
        pr = p if passed else 1.0 - p
        if pr > 0:
            reg._positions[i] = q @ rho @ q / pr  # Lueders collapse (affects the other copy)
        return passed

    def verify(self, candidate: Candidate | NoteRegister) -> bool:
        """Exact W1 verifier: measure EVERY position; accept iff all pass. Loss flags not allowed."""
        cand = candidate.candidate(0) if isinstance(candidate, NoteRegister) else candidate
        if cand.loss_flags:
            return False  # W1 has no loss tolerance
        results = [self._measure_position(cand, i) for i in range(cand.n_qubits())]
        return all(results)

    def leak_secret_out_of_model(self, token_id: str) -> dict[str, object]:
        """NEGATIVE CONTROL ONLY: reveal the secret. Any attack using this is OUT_OF_MODEL."""
        return self._secrets[token_id].reveal_for_testing_only()


class ThresholdLossChallenger(W1Challenger):
    """Toy W2 challenger: loss-flag reporting + error threshold (see module docstring)."""

    protocol_id = "wiesner_noisy"
    game_id = GameId.W2

    def __init__(self, max_loss_fraction: float, max_error_fraction: float) -> None:
        if not (0 <= max_loss_fraction <= 1 and 0 <= max_error_fraction <= 1):
            raise ValueError("fractions must be in [0,1]")
        super().__init__()
        self.max_loss_fraction = max_loss_fraction
        self.max_error_fraction = max_error_fraction

    def allowed(self, n: int, n_lost: int) -> tuple[int, int]:
        """(max lost positions, max errors given n_lost)."""
        return math.floor(self.max_loss_fraction * n + 1e-12), math.floor(
            self.max_error_fraction * (n - n_lost) + 1e-12
        )

    def verify(self, candidate: Candidate | NoteRegister) -> bool:
        cand = candidate.candidate(0) if isinstance(candidate, NoteRegister) else candidate
        n = cand.n_qubits()
        lost = cand.loss_flags
        max_lost, max_err = self.allowed(n, len(lost))
        if len(lost) > max_lost:
            return False
        errors = sum(not self._measure_position(cand, i) for i in range(n) if i not in lost)
        return errors <= max_err


class LeakyOracleChallenger(W1Challenger):
    """Toy W1 challenger with an accept/reject oracle that returns the note (OUT_OF_MODEL)."""

    def __init__(self) -> None:
        super().__init__()
        self.oracle_queries = 0

    def query_oracle(self, note: NoteRegister) -> bool:
        """Verify ``note`` (single copy); reveal one bit; the holder keeps the measured note."""
        self.oracle_queries += 1
        cand = note.candidate(0)
        results = [self._measure_position(cand, i) for i in range(note.n_qubits())]
        return all(results)
