"""BB84 single-qubit states and exact analytic probabilities (C7 conventions).

Everything here is closed-form arithmetic: no Qiskit, no QuTiP, no matrices larger
than 2x2. It is the *analytic* leg of the three-way agreement checks
(analytic vs NumPy/QuTiP density matrices vs Qiskit) used by lane F.

Qubit order (C7): a note is a sequence ``q_0, q_1, ..., q_{n-1}``; outcome tuples
are indexed in that same order, ``outcome[i]`` belongs to ``q_i``. No decoder in
this package ever relies on an implicit Qiskit bit order (see
``qmint.quantum.circuits.decode_counts``).

State-vector simulation is capped at ``MAX_STATEVECTOR_QUBITS`` = 8 qubits. Larger
notes are handled only by the product formulas below (analytic mode).
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence

import numpy as np

from qmint.core.contracts import BB84_STATE_OF, Basis, BB84State, IssuerSecret

MAX_STATEVECTOR_QUBITS = 8

_SQRT_HALF = 1.0 / math.sqrt(2.0)

# C7: (Z,0)=|0>, (Z,1)=|1>, (X,0)=|+>, (X,1)=|->, written in the computational basis.
STATE_VECTORS: dict[BB84State, np.ndarray] = {
    BB84State.ZERO: np.array([1.0, 0.0], dtype=complex),
    BB84State.ONE: np.array([0.0, 1.0], dtype=complex),
    BB84State.PLUS: np.array([_SQRT_HALF, _SQRT_HALF], dtype=complex),
    BB84State.MINUS: np.array([_SQRT_HALF, -_SQRT_HALF], dtype=complex),
}

# Bloch vectors (x, y, z) of the four BB84 states.
BLOCH_VECTORS: dict[BB84State, tuple[float, float, float]] = {
    BB84State.ZERO: (0.0, 0.0, 1.0),
    BB84State.ONE: (0.0, 0.0, -1.0),
    BB84State.PLUS: (1.0, 0.0, 0.0),
    BB84State.MINUS: (-1.0, 0.0, 0.0),
}


def check_statevector_width(n_qubits: int) -> None:
    """Refuse dense 2^n simulation beyond the lane-F cap (master plan 7, F1/F2)."""
    if n_qubits < 1:
        raise ValueError("need at least one qubit")
    if n_qubits > MAX_STATEVECTOR_QUBITS:
        raise ValueError(
            f"{n_qubits} qubits exceeds MAX_STATEVECTOR_QUBITS={MAX_STATEVECTOR_QUBITS}; "
            "use the analytic product formulas for large n"
        )


def validate_note(bases: Sequence[Basis], bits: Sequence[int]) -> None:
    if len(bases) != len(bits):
        raise ValueError("bases and bits length mismatch")
    if not bases:
        raise ValueError("empty note")
    for b in bases:
        if not isinstance(b, Basis):
            raise TypeError(f"basis must be qmint.core.contracts.Basis, got {b!r}")
    for x in bits:
        if x not in (0, 1):
            raise ValueError("bits must be 0/1")


def state_label(basis: Basis | str, bit: int) -> BB84State:
    """C7 label of (basis, bit); ``basis`` may be a ``Basis`` or its string value."""
    return BB84_STATE_OF[(Basis(basis), int(bit))]


def state_vector(basis: Basis | str, bit: int) -> np.ndarray:
    """State vector (computational basis) for a (basis, bit) pair via the frozen C7 mapping.

    Canonical BB84 ket for every package (protocols, attacks, quantum); returns a copy."""
    return STATE_VECTORS[state_label(basis, bit)].copy()


def single_qubit_outcome_probability(prep_basis: Basis, prep_bit: int, meas_basis: Basis, outcome: int) -> float:
    """Exact Born probability of ``outcome`` when (prep_basis, prep_bit) is measured in ``meas_basis``.

    Matching basis: deterministic. Conjugate basis: 1/2 (|<0|+>|^2 = 1/2).
    """
    if outcome not in (0, 1):
        raise ValueError("outcome must be 0/1")
    if prep_basis == meas_basis:
        return 1.0 if outcome == prep_bit else 0.0
    return 0.5


def analytic_outcome_distribution(
    bases: Sequence[Basis], bits: Sequence[int], meas_bases: Sequence[Basis] | None = None
) -> dict[tuple[int, ...], float]:
    """Exact product-state outcome distribution, keyed by C7-ordered outcome tuples.

    Enumerates 2^n outcomes, so it is capped at MAX_STATEVECTOR_QUBITS like the dense paths.
    """
    validate_note(bases, bits)
    meas = list(bases) if meas_bases is None else list(meas_bases)
    if len(meas) != len(bases):
        raise ValueError("meas_bases length mismatch")
    check_statevector_width(len(bases))
    dist: dict[tuple[int, ...], float] = {}
    for outcome in itertools.product((0, 1), repeat=len(bases)):
        p = 1.0
        for pb, bit, mb, o in zip(bases, bits, meas, outcome, strict=True):
            p *= single_qubit_outcome_probability(pb, bit, mb, o)
        if p > 0.0:
            dist[outcome] = p
    return dist


def analytic_honest_accept_probability(n: int) -> float:
    """Ideal Wiesner verification in the secret basis accepts with probability exactly 1 (any n)."""
    if n < 1:
        raise ValueError("n >= 1")
    return 1.0


def analytic_wrong_basis_accept_probability(n_mismatched: int) -> float:
    """Exact-match acceptance when ``n_mismatched`` qubits are measured in the conjugate basis: 2^-k."""
    if n_mismatched < 0:
        raise ValueError("n_mismatched >= 0")
    return 0.5**n_mismatched


def overlap_squared(a: BB84State, b: BB84State) -> float:
    """|<a|b>|^2 via Bloch vectors: (1 + r_a . r_b) / 2 (independent of STATE_VECTORS)."""
    ra, rb = BLOCH_VECTORS[a], BLOCH_VECTORS[b]
    return 0.5 * (1.0 + sum(x * y for x, y in zip(ra, rb, strict=True)))


def random_note_secret(n: int, seed: int, token_id: str, protocol_id: str = "wiesner_ideal") -> IssuerSecret:
    """Uniformly random BB84 note (bases, bits) as an ``IssuerSecret`` (C1 private domain).

    Deterministic for a given seed (test vectors). The returned object refuses serialization.
    """
    if n < 1:
        raise ValueError("n >= 1")
    rng = np.random.default_rng(seed)
    bases = [Basis.Z if b == 0 else Basis.X for b in rng.integers(0, 2, size=n)]
    bits = [int(x) for x in rng.integers(0, 2, size=n)]
    return IssuerSecret(token_id=token_id, protocol_id=protocol_id, bases=bases, bits=bits)
