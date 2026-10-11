"""Small 1->2 cloning-attack circuits on BB84 note qubits, game W1 (lane F, F2).

Two per-qubit cloners, each a 3-qubit circuit (input/copy-1, blank/copy-2, ancilla):

* ``bruss2000``: the optimal *phase-covariant* cloner for xz-equatorial qubits,
  Bruss, Cinchetti, D'Ariano, Macchiavello, PRA 62, 012302 (2000), arXiv:quant-ph/9909046,
  Sec. IV eq. (35) with coefficients a = 1/2 + sqrt(1/8), b = sqrt(1/8), c = 1/2 - sqrt(1/8)
  (eq. (33); normalisation a^2 + 2b^2 + c^2 = 1, eq. (26)). It maximises the
  *single-copy* fidelity (1/2 + sqrt(1/8) ~ 0.854, eq. (34)); that is NOT the W1 figure
  of merit. Its W1 both-pass probability is a^2 = (3 + 2 sqrt 2)/8 ~ 0.7286 < 3/4,
  so it is labelled ``heuristic_circuit_attack``.

* ``mvw2012``: the channel Phi(rho) = A0 rho A0* + A1 rho A1* printed in Molina, Vidick,
  Watrous, arXiv:1202.4010, Sec. 3.2 (primal solution of value 3/4), realised here through
  its Stinespring isometry W = A0 (x) |0>_E + A1 (x) |1>_E on one ancilla qubit. It is called
  ``optimal`` only because ``mvw_both_pass_exact()`` re-derives exactly 3/4 in rational
  arithmetic, matching the MVW optimum (3/4)^n for the W1 game; the simulated circuit
  value is floating point and carries SIMULATOR_IDEAL evidence, not a proof.

Width: 3 qubits per note qubit, so circuits are limited to n <= 2 note qubits (8-qubit cap).
Larger n uses the product formula p^n (each cloner acts independently per qubit).

Simulator caveat: the host can copy a statevector; this module never claims software-level
no-cloning. It only evaluates the modelled physical cloning map.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Literal

import numpy as np

from qmint.core.contracts import AttackResult, Basis, EvidenceKind, GameId
from qmint.quantum.bb84 import MAX_STATEVECTOR_QUBITS, random_note_secret, validate_note
from qmint.quantum.circuits import (
    accepted_shots,
    append_basis_measurement,
    build_prepare_circuit,
    decode_bitstring,
    run_aer,
)
from qmint.quantum.records import clopper_pearson

ClonerName = Literal["bruss2000", "mvw2012"]

W1_OPTIMAL_PER_QUBIT = Fraction(3, 4)  # MVW 2012 abstract / Sec. 3.2
BRUSS_BOTH_PASS_ANALYTIC = (3.0 + 2.0 * math.sqrt(2.0)) / 8.0


# MVW 2012 Sec. 3.2 Kraus operators, integer numerators over sqrt(12); rows index (copy1, copy2).
_MVW_A_INT = (
    np.array([[3, 0], [0, 1], [0, 1], [1, 0]]),
    np.array([[0, 1], [1, 0], [1, 0], [0, 3]]),
)


def _bruss_isometry() -> np.ndarray:
    """8x2 isometry; row index = 4*copy1 + 2*copy2 + ancilla (C7 / kron order)."""
    a, b, c = 0.5 + math.sqrt(1 / 8), math.sqrt(1 / 8), 0.5 - math.sqrt(1 / 8)
    v = np.zeros((8, 2))
    # U|0>|0>|X> = a|00>|0> + b(|01>+|10>)|1> + c|11>|0>
    v[0b000, 0], v[0b011, 0], v[0b101, 0], v[0b110, 0] = a, b, b, c
    # U|1>|0>|X> = a|11>|1> + b(|10>+|01>)|0> + c|00>|1>
    v[0b111, 1], v[0b100, 1], v[0b010, 1], v[0b001, 1] = a, b, b, c
    return v


def _mvw_isometry() -> np.ndarray:
    e = np.eye(2)
    return sum(np.kron(ak / math.sqrt(12.0), e[:, [k]]) for k, ak in enumerate(_MVW_A_INT))


def cloner_isometry(name: ClonerName) -> np.ndarray:
    v = _bruss_isometry() if name == "bruss2000" else _mvw_isometry()
    if not np.allclose(v.T.conj() @ v, np.eye(2), atol=1e-12):
        raise AssertionError(f"{name} map is not an isometry")
    return v


def cloner_kraus(name: ClonerName) -> list[np.ndarray]:
    """Kraus operators (4x2, rows = (copy1, copy2)) obtained by tracing out the ancilla."""
    v = cloner_isometry(name).reshape(4, 2, 2)  # (copy1copy2, ancilla, input)
    return [v[:, k, :] for k in range(2)]


def _unitary_completion(v: np.ndarray) -> np.ndarray:
    """8x8 unitary U with U[:,0] = v[:,0] (input |0>) and U[:,4] = v[:,1] (input |1>)."""
    from scipy.linalg import null_space

    u = np.zeros((8, 8), dtype=complex)
    u[:, 0], u[:, 4] = v[:, 0], v[:, 1]
    comp = null_space(v.conj().T)  # 8x6 orthonormal complement
    for j, col in zip([1, 2, 3, 5, 6, 7], comp.T, strict=True):
        u[:, j] = col
    return u


def cloner_gate(name: ClonerName):
    from qiskit.circuit.library import UnitaryGate

    return UnitaryGate(_unitary_completion(cloner_isometry(name)), label=f"clone_{name}")


def build_cloning_attack_circuit(bases: list[Basis], bits: list[int], name: ClonerName, measure: bool = True):
    """Prepare note -> per-qubit cloner -> (optionally) bank verifies BOTH copies in the secret bases.

    Qubits: copy-1 of q_i = i, copy-2 = n+i, ancilla = 2n+i. Clbits: copy-1 -> 0..n-1, copy-2 -> n..2n-1.
    """
    from qiskit import QuantumCircuit

    validate_note(bases, bits)
    n = len(bases)
    if 3 * n > MAX_STATEVECTOR_QUBITS:
        raise ValueError(f"cloning circuit needs 3n={3 * n} qubits > {MAX_STATEVECTOR_QUBITS}; use p**n")
    qc = QuantumCircuit(3 * n, 2 * n if measure else 0, name=f"w1_{name}")
    qc.compose(build_prepare_circuit(bases, bits), qubits=list(range(n)), inplace=True)
    qc.barrier()
    gate = cloner_gate(name)
    for i in range(n):
        # Qiskit matrix index bit k <-> qargs[k]; row index 4*c1 + 2*c2 + anc needs qargs (anc, c2, c1).
        qc.append(gate, [2 * n + i, n + i, i])
    if measure:
        qc.barrier()
        append_basis_measurement(qc, list(bases) + list(bases), qubits=list(range(2 * n)))
    return qc


def circuit_both_pass_probability(bases: list[Basis], bits: list[int], name: ClonerName) -> float:
    """Exact (statevector) probability that both copies pass, from the Qiskit circuit."""
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Statevector

    n = len(bases)
    qc = build_cloning_attack_circuit(bases, bits, name, measure=False)
    rot = QuantumCircuit(3 * n)
    for i, b in enumerate(list(bases) + list(bases)):
        if b == Basis.X:
            rot.h(i)
    probs = Statevector.from_instruction(qc).evolve(rot).probabilities_dict(qargs=list(range(2 * n)))
    target = tuple(bits) + tuple(bits)
    return float(sum(p for k, p in probs.items() if decode_bitstring(k, 2 * n) == target))


def numpy_both_pass_probability(basis: Basis, bit: int, name: ClonerName) -> float:
    """Independent reference: <psi psi| Phi(|psi><psi|) |psi psi> from the Kraus operators."""
    from qmint.quantum.bb84 import state_vector

    psi = state_vector(basis, bit)
    pp = np.kron(psi, psi)
    return float(sum(abs(pp.conj() @ k @ psi) ** 2 for k in cloner_kraus(name)))


def mvw_both_pass_exact() -> Fraction:
    """Average W1 both-pass probability of the MVW channel over the 4 BB84 states, in exact rationals."""
    vecs = {(Basis.Z, 0): (1, 0), (Basis.Z, 1): (0, 1), (Basis.X, 0): (1, 1), (Basis.X, 1): (1, -1)}
    total = Fraction(0)
    for v in vecs.values():
        v_arr = np.array(v, dtype=object)
        vv = np.array([v[0] * v[0], v[0] * v[1], v[1] * v[0], v[1] * v[1]], dtype=object)
        norm_v = sum(x * x for x in v)  # |v|^2, and |vv|^2 = norm_v^2
        for a in _MVW_A_INT:
            amp = int(vv @ (a.astype(object) @ v_arr))
            total += Fraction(amp * amp, 12 * norm_v**3)
    return total / 4


def is_optimal_for_w1(name: ClonerName) -> bool:
    """True only when the exact rational both-pass value equals 3/4 (never inferred from floats)."""
    return name == "mvw2012" and mvw_both_pass_exact() == W1_OPTIMAL_PER_QUBIT


def attack_label(name: ClonerName) -> str:
    """'optimal' wording only when the exact rational W1 value equals 3/4; otherwise heuristic."""
    return "mvw2012_optimal_channel_circuit" if is_optimal_for_w1(name) else "heuristic_circuit_attack"


def analytic_both_pass(name: ClonerName, n: int = 1) -> float:
    per = BRUSS_BOTH_PASS_ANALYTIC if name == "bruss2000" else float(mvw_both_pass_exact())
    return per**n


def simulate_attack(
    name: ClonerName,
    n: int,
    n_notes: int,
    shots_per_note: int,
    seed: int,
    source_code_sha: str,
    confidence: float = 0.99,
) -> AttackResult:
    """Aer shot estimate over ``n_notes`` uniformly random notes -> C3 AttackResult (SIMULATOR_IDEAL)."""
    successes = trials = 0
    for j in range(n_notes):
        secret = random_note_secret(n, seed=seed + j, token_id=f"w1_{name}_{j}")
        qc = build_cloning_attack_circuit(list(secret.bases), list(secret.bits), name)
        counts, prov, _ = run_aer(qc, shots=shots_per_note, seed=seed + 10_000 + j)
        successes += accepted_shots(counts, list(secret.bits) * 2)
        trials += shots_per_note
    label = attack_label(name)
    return AttackResult(
        attack_id=f"F2_{name}_cloner",
        game_id=GameId.W1,
        attack_capability=["single_note_copy", "local_quantum_channel", "one_ancilla_qubit_per_note_qubit"],
        token_n=n,
        attack_method=f"{label}: per-qubit 1->2 cloner {name} as 3-qubit unitary; {n_notes} random notes",
        quantum_channel_description="ideal (noiseless) local Aer simulation; no channel noise",
        verifier_rule="bank measures both copies in the secret bases; success iff both exact-match",
        seed=seed,
        trials=trials,
        successes=successes,
        success_rate_ci=clopper_pearson(successes, trials, confidence),
        ci_method=f"clopper_pearson_{confidence}",
        proof_applicability="IN_MODEL",
        theorem_upper_bound=float(W1_OPTIMAL_PER_QUBIT) ** n,
        backend_kind=prov.backend_kind,
        evidence_kind=EvidenceKind.SIMULATOR_IDEAL,
        source_code_sha=source_code_sha,
    )
