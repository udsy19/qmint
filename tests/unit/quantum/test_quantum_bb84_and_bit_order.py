"""T1: BB84 C7 states, overlaps, analytic distributions, and explicit Qiskit bit-order decoding."""

import itertools
import math

import numpy as np
import pytest

from qmint.core.contracts import Basis, BB84State, SecretBoundaryError
from qmint.core.serialization import canonical_json
from qmint.quantum.bb84 import (
    MAX_STATEVECTOR_QUBITS,
    analytic_outcome_distribution,
    analytic_wrong_basis_accept_probability,
    overlap_squared,
    random_note_secret,
    single_qubit_outcome_probability,
    state_label,
    state_vector,
)
from qmint.quantum.circuits import (
    build_prepare_circuit,
    build_verify_circuit,
    decode_bitstring,
    decode_counts,
    encode_tuple,
    run_aer,
)

Z, X = Basis.Z, Basis.X


def test_c7_state_mapping():
    assert state_label(Z, 0) == BB84State.ZERO
    assert state_label(Z, 1) == BB84State.ONE
    assert state_label(X, 0) == BB84State.PLUS
    assert state_label(X, 1) == BB84State.MINUS
    s = 1 / math.sqrt(2)
    assert np.allclose(state_vector(X, 0), [s, s])
    assert np.allclose(state_vector(X, 1), [s, -s])


@pytest.mark.parametrize("a,b", list(itertools.product([(Z, 0), (Z, 1), (X, 0), (X, 1)], repeat=2)))
def test_overlap_vectors_match_bloch(a, b):
    va, vb = state_vector(*a), state_vector(*b)
    assert abs(np.vdot(va, va) - 1) < 1e-15
    assert abs(abs(np.vdot(va, vb)) ** 2 - overlap_squared(state_label(*a), state_label(*b))) < 1e-15


def test_single_qubit_probabilities():
    for basis, bit in itertools.product((Z, X), (0, 1)):
        assert single_qubit_outcome_probability(basis, bit, basis, bit) == 1.0
        assert single_qubit_outcome_probability(basis, bit, basis, 1 - bit) == 0.0
        other = X if basis == Z else Z
        assert single_qubit_outcome_probability(basis, bit, other, 0) == 0.5


def test_analytic_distribution_wrong_basis():
    d = analytic_outcome_distribution([Z, X, X], [1, 0, 1], [X, X, Z])
    assert len(d) == 4 and all(abs(p - 0.25) < 1e-15 for p in d.values())
    assert all(k[1] == 0 for k in d)
    assert analytic_wrong_basis_accept_probability(2) == 0.25


def test_width_cap_refuses_large_statevector():
    with pytest.raises(ValueError, match="MAX_STATEVECTOR_QUBITS"):
        build_prepare_circuit([Z] * (MAX_STATEVECTOR_QUBITS + 1), [0] * (MAX_STATEVECTOR_QUBITS + 1))
    with pytest.raises(ValueError):
        analytic_outcome_distribution([Z] * 9, [0] * 9)


def test_random_note_secret_deterministic_and_private():
    a = random_note_secret(8, seed=3, token_id="t")
    b = random_note_secret(8, seed=3, token_id="t")
    assert a.bases == b.bases and a.bits == b.bits
    with pytest.raises(SecretBoundaryError):
        canonical_json(a)
    assert "REDACTED" in repr(a)


# ------------------------------- bit order -------------------------------- #


def test_decode_bitstring_little_endian():
    # Qiskit key '001' means clbit0 = 1 -> C7 tuple (1, 0, 0)
    assert decode_bitstring("001", 3) == (1, 0, 0)
    assert decode_bitstring("110", 3) == (0, 1, 1)
    assert decode_bitstring("0x1", 3) == (1, 0, 0)
    assert decode_bitstring("0x6", 3) == (0, 1, 1)
    for t in itertools.product((0, 1), repeat=4):
        assert decode_bitstring(encode_tuple(t), 4) == t


@pytest.mark.parametrize("bad", ["01", "0011", "0 1 0", "012", "0x8"])
def test_decode_rejects_malformed(bad):
    with pytest.raises(ValueError):
        decode_bitstring(bad, 3)


def test_decode_counts_merges():
    assert decode_counts({"01": 3, "0x1": 2}, 2) == {(1, 0): 5}


def test_asymmetric_circuit_qubit_indexing():
    """Only q_0 is flipped: the C7 tuple must have the 1 in position 0 (physical qubit indexing)."""
    qc = build_verify_circuit([Z, Z, Z], [1, 0, 0])
    counts, _, _ = run_aer(qc, shots=64, seed=1)
    assert counts == {(1, 0, 0): 64}


@pytest.mark.parametrize("n", range(1, MAX_STATEVECTOR_QUBITS + 1))
def test_ideal_verification_in_secret_basis_always_accepts(n):
    sec = random_note_secret(n, seed=100 + n, token_id=f"n{n}")
    counts, prov, _ = run_aer(build_verify_circuit(list(sec.bases), list(sec.bits)), shots=200, seed=n)
    assert counts == {tuple(sec.bits): 200}
    assert prov.evidence_kind.value == "SIMULATOR_IDEAL" and not prov.is_hardware


def test_x_basis_uses_h_before_measure():
    qc = build_verify_circuit([X], [1])
    names = [i.operation.name for i in qc.data]
    # prep X, H ; barrier ; H then measure
    assert names == ["x", "h", "barrier", "h", "measure"]
