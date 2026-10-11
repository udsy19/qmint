"""T1/X15-local: CPTP checks, Aer-vs-own Kraus equality, high-shot binomial CI checks, records."""

import numpy as np
import pytest

from qmint.core.contracts import Basis, EvidenceKind, MeasurementEvent
from qmint.core.serialization import canonical_json
from qmint.quantum.bb84 import random_note_secret
from qmint.quantum.channels import (
    NoiseSpec,
    amplitude_damping_kraus,
    analytic_mean_accept_probability,
    analytic_note_accept_probability,
    apply_kraus,
    dephasing_kraus,
    depolarizing_kraus,
    is_cptp,
    readout_confusion,
)
from qmint.quantum.circuits import accepted_shots, build_verify_circuit, measurement_events, run_aer
from qmint.quantum.records import clopper_pearson, resource_counts
from qmint.quantum.references import qutip_kraus_is_cptp

PARAMS = [0.0, 0.01, 0.3, 0.999, 1.0]


def _random_rho(rng):
    a = rng.normal(size=(2, 2)) + 1j * rng.normal(size=(2, 2))
    r = a @ a.conj().T
    return r / np.trace(r)


@pytest.mark.parametrize("ctor", [depolarizing_kraus, dephasing_kraus, amplitude_damping_kraus])
@pytest.mark.parametrize("p", PARAMS)
def test_cptp_and_trace_preservation(ctor, p):
    k = ctor(p)
    assert is_cptp(k)
    rng = np.random.default_rng(0)
    for _ in range(20):
        rho = _random_rho(rng)
        out = apply_kraus(rho, k)
        assert abs(np.trace(out) - 1) < 1e-12
        assert np.allclose(out, out.conj().T)
        assert np.linalg.eigvalsh(out).min() > -1e-12


@pytest.mark.parametrize("kind", ["depolarizing", "dephasing", "amplitude_damping"])
@pytest.mark.parametrize("p", [0.0, 0.05, 0.5, 1.0])
def test_qutip_cptp_and_aer_channel_equals_own_kraus(kind, p):
    from qiskit.quantum_info import Kraus, SuperOp

    spec = NoiseSpec(kind, p)
    assert qutip_kraus_is_cptp(spec)
    assert SuperOp(Kraus(spec.aer_quantum_error())) == SuperOp(Kraus(spec.kraus()))


def test_not_cptp_detected():
    assert not is_cptp([np.eye(2) * 0.9])
    with pytest.raises(ValueError):
        depolarizing_kraus(1.2)
    with pytest.raises(ValueError):
        NoiseSpec("none", 0.1)


def test_readout_confusion_column_stochastic():
    m = readout_confusion(0.1, 0.3)
    assert np.allclose(m.sum(axis=0), 1) and m[1, 0] == 0.1 and m[0, 1] == 0.3


def test_analytic_mean_accept_large_n_needs_no_statevector():
    spec = NoiseSpec("depolarizing", 0.02)
    assert abs(analytic_mean_accept_probability(spec, 128) - 0.99**128) < 1e-12
    assert analytic_mean_accept_probability(NoiseSpec(), 128) == 1.0


# ------------------------------ shot tests --------------------------------- #

SHOTS = 40_000
CONF = 0.9999  # per-test false-alarm 1e-4, fixed seeds -> deterministic


def test_wrong_basis_binomial_ci():
    bases, bits = [Basis.Z, Basis.X, Basis.Z], [0, 1, 1]
    qc = build_verify_circuit(bases, bits, meas_bases=[Basis.X, Basis.X, Basis.X])  # 2 mismatched
    counts, _, _ = run_aer(qc, SHOTS, seed=3)
    ci = clopper_pearson(accepted_shots(counts, bits), SHOTS, CONF)
    assert ci.lo <= 0.25 <= ci.hi
    # qubit 1 is in matching basis: its outcome must always be 1
    assert all(k[1] == 1 for k in counts)


@pytest.mark.parametrize("kind", ["depolarizing", "dephasing", "amplitude_damping"])
def test_noisy_aer_acceptance_within_ci(kind):
    spec = NoiseSpec(kind, 0.1, 0.02, 0.03)
    sec = random_note_secret(5, seed=8, token_id="noisy")
    bases, bits = list(sec.bases), list(sec.bits)
    counts, prov, _ = run_aer(build_verify_circuit(bases, bits, noise=spec), SHOTS, seed=21, noise=spec)
    ci = clopper_pearson(accepted_shots(counts, bits), SHOTS, CONF)
    assert ci.lo <= analytic_note_accept_probability(spec, bases, bits) <= ci.hi
    assert prov.evidence_kind == EvidenceKind.SIMULATOR_NOISY and prov.noise_model


def test_measurement_events_and_provenance():
    sec = random_note_secret(3, seed=1, token_id="ev")
    bases, bits = list(sec.bases), list(sec.bits)
    spec = NoiseSpec("dephasing", 0.2)
    counts, prov, mem = run_aer(build_verify_circuit(bases, bits, noise=spec), 10, seed=2, noise=spec, memory=True)
    ev = measurement_events("tok", bases, mem, prov)
    assert len(ev) == 30 and all(isinstance(e, MeasurementEvent) for e in ev)
    assert all(e.source_kind == EvidenceKind.SIMULATOR_NOISY and e.noise_model for e in ev)
    assert [e.outcome for e in ev[:3]] == list(mem[0])
    assert prov.resources["width_qubits"] == 3 and prov.circuit_sha256
    canonical_json(prov)  # serialisable
    _, prov_i, mem_i = run_aer(build_verify_circuit(bases, bits), 5, seed=2, memory=True)
    assert all(e.source_kind == EvidenceKind.SIMULATOR_IDEAL for e in measurement_events("t", bases, mem_i, prov_i))


def test_resource_counts_and_fingerprint_deterministic():
    qc = build_verify_circuit([Basis.X, Basis.Z], [1, 1])
    r = resource_counts(qc)
    assert r["width_qubits"] == 2 and r["two_qubit_gates"] == 0
    assert r["gate_counts"]["measure"] == 2 and "NOT hardware-native" in r["generic_transpile"]["note"]
    from qmint.quantum.records import circuit_fingerprint

    assert circuit_fingerprint(qc) == circuit_fingerprint(build_verify_circuit([Basis.X, Basis.Z], [1, 1]))
    assert circuit_fingerprint(qc) != circuit_fingerprint(build_verify_circuit([Basis.X, Basis.Z], [1, 0]))
