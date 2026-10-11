"""X03: Qiskit vs NumPy density matrix vs QuTiP vs analytic -- exact agreement (ideal and noisy)."""

import itertools

import numpy as np
import pytest

from qmint.core.contracts import Basis
from qmint.quantum.bb84 import analytic_outcome_distribution, random_note_secret
from qmint.quantum.channels import NoiseSpec, analytic_note_accept_probability
from qmint.quantum.circuits import qiskit_exact_distribution
from qmint.quantum.references import (
    bloch_vector,
    numpy_note_density_matrix,
    numpy_outcome_distribution,
    numpy_purity,
    qutip_outcome_distribution,
)

ATOL = 1e-12
SPECS = [
    NoiseSpec(),
    NoiseSpec("depolarizing", 0.07, 0.01, 0.03),
    NoiseSpec("dephasing", 0.11),
    NoiseSpec("amplitude_damping", 0.2, 0.0, 0.04),
    NoiseSpec("none", 0.0, 0.05, 0.0),
]


def _close(a, b):
    return all(abs(a.get(k, 0.0) - b.get(k, 0.0)) < ATOL for k in set(a) | set(b))


@pytest.mark.parametrize("n", range(1, 9))
@pytest.mark.parametrize("spec", SPECS, ids=lambda s: f"{s.channel}-{s.param}-{s.readout_p01}")
def test_three_way_agreement(n, spec):
    sec = random_note_secret(n, seed=40 + n, token_id="x")
    bases, bits = list(sec.bases), list(sec.bits)
    rng = np.random.default_rng(n)
    meas_choices = [bases, [Basis.X if rng.random() < 0.5 else Basis.Z for _ in range(n)]]
    for meas in meas_choices:
        q = qiskit_exact_distribution(bases, bits, meas, spec)
        npy = numpy_outcome_distribution(bases, bits, meas, spec)
        qt = qutip_outcome_distribution(bases, bits, meas, spec)
        assert abs(sum(npy.values()) - 1) < ATOL
        assert _close(q, npy), "Qiskit vs NumPy"
        assert _close(qt, npy), "QuTiP vs NumPy"
        if spec.is_ideal:
            assert _close(analytic_outcome_distribution(bases, bits, meas), npy), "analytic vs NumPy"
    assert abs(numpy_outcome_distribution(bases, bits, None, spec).get(tuple(bits), 0.0)
               - analytic_note_accept_probability(spec, bases, bits)) < ATOL


def test_all_single_qubit_cases_exhaustively():
    for b, x, m in itertools.product((Basis.Z, Basis.X), (0, 1), (Basis.Z, Basis.X)):
        assert _close(qiskit_exact_distribution([b], [x], [m]), analytic_outcome_distribution([b], [x], [m]))


def test_density_matrix_trace_purity_bloch():
    rho = numpy_note_density_matrix([Basis.X], [1])
    assert abs(np.trace(rho) - 1) < ATOL and abs(numpy_purity(rho) - 1) < ATOL
    assert np.allclose(bloch_vector(rho), (-1, 0, 0))
    noisy = numpy_note_density_matrix([Basis.X], [1], NoiseSpec("depolarizing", 0.3))
    assert np.allclose(bloch_vector(noisy), (-0.7, 0, 0))  # isotropic shrink by 1-p
    assert numpy_purity(noisy) < 1
    damped = numpy_note_density_matrix([Basis.Z], [1], NoiseSpec("amplitude_damping", 0.25))
    assert np.allclose(bloch_vector(damped), (0, 0, -0.5))  # z = -1 + 2 gamma
