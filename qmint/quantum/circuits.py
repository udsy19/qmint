"""Qiskit BB84 note circuits (1-8 qubits), explicit bit-order decoding, Aer execution (lane F, F1).

Layout (C7, fixed): note qubit ``q_i`` is Qiskit qubit ``i`` and is measured into
classical bit ``i``. Qiskit prints count keys little-endian (clbit 0 is the
*rightmost* character); ``decode_bitstring`` converts a key into a C7-ordered tuple
``(b_0, ..., b_{n-1})``. No other code path may index count strings directly.

Verification in the secret basis: Z -> measure; X -> H then Z-measure.

Caveat (do not remove): a simulator's statevector is classical data that the host can
copy freely. Nothing here demonstrates software-level no-cloning; only the physics of
the *modelled* quantum register is simulated.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from qmint.core.contracts import Basis, EvidenceKind, MeasurementEvent
from qmint.quantum.bb84 import check_statevector_width, validate_note
from qmint.quantum.channels import NoiseSpec
from qmint.quantum.records import BackendProvenance, circuit_fingerprint, resource_counts, software_versions
from qmint.quantum.references import apply_readout, tensor_to_distribution


def decode_bitstring(key: str, n: int) -> tuple[int, ...]:
    """Qiskit little-endian key -> C7 tuple: result[i] = classical bit i = note qubit i.

    Accepts plain binary keys of length n or hex keys ('0x..'). Keys containing spaces
    (multiple classical registers) are rejected: lane F circuits use a single register.
    """
    if " " in key:
        raise ValueError(f"multi-register count key {key!r} not supported")
    if key.startswith("0x"):
        v = int(key, 16)
        if v >= 1 << n:
            raise ValueError(f"hex key {key!r} exceeds {n} bits")
        return tuple((v >> i) & 1 for i in range(n))
    if len(key) != n or set(key) - {"0", "1"}:
        raise ValueError(f"count key {key!r} is not an {n}-bit binary string")
    return tuple(int(key[n - 1 - i]) for i in range(n))


def decode_counts(counts: Mapping[str, int | float], n: int) -> dict[tuple[int, ...], int | float]:
    out: dict[tuple[int, ...], Any] = {}
    for k, v in counts.items():
        t = decode_bitstring(k, n)
        out[t] = out.get(t, 0) + v
    return out


def encode_tuple(outcome: Sequence[int]) -> str:
    """Inverse of decode_bitstring (C7 tuple -> Qiskit key); used only in tests/fixtures."""
    return "".join(str(int(b)) for b in reversed(outcome))


# --------------------------------------------------------------------------- #
# Circuit construction
# --------------------------------------------------------------------------- #


def build_prepare_circuit(bases: Sequence[Basis], bits: Sequence[int]):
    """|0> -> X^bit -> H if X basis:  (Z,0)|0>, (Z,1)|1>, (X,0)|+>, (X,1)|->."""
    from qiskit import QuantumCircuit

    validate_note(bases, bits)
    check_statevector_width(len(bases))
    qc = QuantumCircuit(len(bases), name="bb84_prepare")
    for i, (b, x) in enumerate(zip(bases, bits, strict=True)):
        if x == 1:
            qc.x(i)
        if b == Basis.X:
            qc.h(i)
    return qc


def append_channel(qc, noise: NoiseSpec, qubits: Sequence[int] | None = None) -> None:
    """Insert the declared qubit channel (Aer instruction) on each listed qubit."""
    err = noise.aer_quantum_error()
    if err is None:
        return
    for q in range(qc.num_qubits) if qubits is None else qubits:
        qc.append(err.to_instruction(), [q])


def append_basis_measurement(qc, meas_bases: Sequence[Basis], qubits: Sequence[int] | None = None) -> None:
    """Measure qubit qubits[j] in meas_bases[j] into clbit j (H before Z-measure for X)."""
    qs = list(range(len(meas_bases))) if qubits is None else list(qubits)
    if len(qs) != len(meas_bases) or qc.num_clbits < len(qs):
        raise ValueError("qubit/basis/clbit size mismatch")
    for q, m in zip(qs, meas_bases, strict=True):
        if m == Basis.X:
            qc.h(q)
    for j, q in enumerate(qs):
        qc.measure(q, j)


def build_verify_circuit(
    bases: Sequence[Basis],
    bits: Sequence[int],
    meas_bases: Sequence[Basis] | None = None,
    noise: NoiseSpec | None = None,
):
    """Prepare the note, apply the declared channel, measure in ``meas_bases`` (default: secret bases)."""
    from qiskit import QuantumCircuit

    meas = list(bases) if meas_bases is None else list(meas_bases)
    if len(meas) != len(bases):
        raise ValueError("meas_bases length mismatch")
    prep = build_prepare_circuit(bases, bits)
    n = len(bases)
    qc = QuantumCircuit(n, n, name="bb84_verify")
    qc.compose(prep, inplace=True)
    qc.barrier()
    if noise is not None:
        append_channel(qc, noise)
        qc.barrier()
    append_basis_measurement(qc, meas)
    return qc


# --------------------------------------------------------------------------- #
# Exact Qiskit path (quantum_info) and sampled Aer path
# --------------------------------------------------------------------------- #


def qiskit_exact_distribution(
    bases: Sequence[Basis],
    bits: Sequence[int],
    meas_bases: Sequence[Basis] | None = None,
    noise: NoiseSpec | None = None,
) -> dict[tuple[int, ...], float]:
    """Exact distribution via qiskit.quantum_info; channel taken from Aer's constructors."""
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import DensityMatrix, Kraus, Statevector

    meas = list(bases) if meas_bases is None else list(meas_bases)
    if len(meas) != len(bases):
        raise ValueError("meas_bases length mismatch")
    noise = noise or NoiseSpec()
    n = len(bases)
    prep = build_prepare_circuit(bases, bits)
    rot = QuantumCircuit(n)
    for i, m in enumerate(meas):
        if m == Basis.X:
            rot.h(i)
    err = noise.aer_quantum_error()
    if err is None:
        state = Statevector.from_instruction(prep).evolve(rot)
    else:
        state = DensityMatrix.from_instruction(prep)
        k = Kraus(err)
        for i in range(n):
            state = state.evolve(k, qargs=[i])
        state = state.evolve(rot)
    t = np.zeros((2,) * n)
    for key, p in state.probabilities_dict().items():
        t[decode_bitstring(key, n)] = max(0.0, float(p))
    return tensor_to_distribution(apply_readout(t, noise.confusion()))


def run_aer(
    qc,
    shots: int,
    seed: int,
    noise: NoiseSpec | None = None,
    memory: bool = False,
) -> tuple[dict[tuple[int, ...], int], BackendProvenance, list[tuple[int, ...]] | None]:
    """Sample ``qc`` on a local AerSimulator. Returns decoded counts, provenance, optional per-shot memory."""
    from qiskit_aer import AerSimulator

    noisy = noise is not None and not noise.is_ideal
    sim = AerSimulator(noise_model=noise.aer_noise_model() if noisy else None, seed_simulator=seed)
    result = sim.run(qc, shots=shots, memory=memory).result()
    n = qc.num_clbits
    counts = decode_counts(result.get_counts(), n)
    mem = [decode_bitstring(k, n) for k in result.get_memory()] if memory else None
    prov = BackendProvenance(
        backend_name=result.backend_name,
        backend_kind="aer_simulator",
        evidence_kind=EvidenceKind.SIMULATOR_NOISY if noisy else EvidenceKind.SIMULATOR_IDEAL,
        simulator_method=str(result.results[0].metadata.get("method", "automatic")),
        shots=shots,
        seed_simulator=seed,
        job_id=result.job_id,
        noise_model=noise.describe() if noisy else None,
        circuit_sha256=circuit_fingerprint(qc),
        resources=resource_counts(qc),
        software=software_versions(),
        is_hardware=False,
        notes="local simulator; job_id is a random Aer UUID, not a hardware job",
    )
    return counts, prov, mem


def accepted_shots(counts: Mapping[tuple[int, ...], int], expected: Sequence[int]) -> int:
    """Exact-match verifier: shots whose full outcome tuple equals the secret bits."""
    return int(counts.get(tuple(int(b) for b in expected), 0))


def measurement_events(
    token_id: str,
    meas_bases: Sequence[Basis],
    memory: Sequence[tuple[int, ...]],
    provenance: BackendProvenance,
    site_id: str = "local_sim",
    start_time_ns: int = 0,
) -> list[MeasurementEvent]:
    """One C2 MeasurementEvent per (shot, qubit). Times are a logical simulator clock, not UTC.

    Each shot is a freshly prepared note (destructive measurement); events of one shot share
    a logical timestamp and are never presented as re-verification of the same physical note.
    """
    if provenance.evidence_kind not in (EvidenceKind.SIMULATOR_IDEAL, EvidenceKind.SIMULATOR_NOISY):
        raise ValueError("lane F events are simulator events only")
    events: list[MeasurementEvent] = []
    for s, outcome in enumerate(memory):
        if len(outcome) != len(meas_bases):
            raise ValueError("memory width mismatch")
        for q, (m, o) in enumerate(zip(meas_bases, outcome, strict=True)):
            events.append(
                MeasurementEvent(
                    event_id=f"{token_id}:shot{s}:q{q}",
                    token_id=f"{token_id}:shot{s}",
                    site_id=site_id,
                    clock_id="simulator_logical_clock",
                    event_time_utc_ns=start_time_ns + s,
                    timestamp_accuracy_ns=0.0,
                    basis=m,
                    outcome=int(o),
                    valid=True,
                    shots=1,
                    backend=provenance.backend_name,
                    job_id=provenance.job_id,
                    source_kind=provenance.evidence_kind,
                    noise_model=provenance.noise_model,
                )
            )
    return events
