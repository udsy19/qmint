"""Independent state-physics references: NumPy density matrices and QuTiP (lane F, F1/F3).

Neither path imports Qiskit. Both index outcomes in C7 qubit order:
NumPy uses ``np.kron(q_0, q_1, ...)`` so q_0 is the *most* significant index, the
opposite of Qiskit's little-endian convention -- which is exactly why agreement with
the Qiskit path (``qmint.quantum.circuits``) tests the explicit bit-order decoder.

All dense paths are capped at ``MAX_STATEVECTOR_QUBITS``.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence

import numpy as np

from qmint.core.contracts import Basis
from qmint.quantum.bb84 import check_statevector_width, state_vector, validate_note
from qmint.quantum.channels import NoiseSpec, apply_kraus

_H = np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2.0)


def apply_readout(probs: np.ndarray, confusion: np.ndarray) -> np.ndarray:
    """Apply a per-bit column-stochastic confusion matrix to an (2,)*n probability tensor."""
    out = probs
    for axis in range(probs.ndim):
        out = np.moveaxis(np.tensordot(confusion, out, axes=([1], [axis])), 0, axis)
    return out


def tensor_to_distribution(t: np.ndarray, atol: float = 0.0) -> dict[tuple[int, ...], float]:
    return {
        tuple(int(i) for i in idx): float(t[idx])
        for idx in itertools.product((0, 1), repeat=t.ndim)
        if t[idx] > atol
    }


def numpy_note_density_matrix(
    bases: Sequence[Basis], bits: Sequence[int], noise: NoiseSpec | None = None
) -> np.ndarray:
    """rho = kron_i E(|s_i><s_i|), q_0 most significant."""
    validate_note(bases, bits)
    check_statevector_width(len(bases))
    kraus = (noise or NoiseSpec()).kraus()
    rho = np.array([[1.0 + 0j]])
    for b, x in zip(bases, bits, strict=True):
        v = state_vector(b, x)
        rho = np.kron(rho, apply_kraus(np.outer(v, v.conj()), kraus))
    return rho


def numpy_outcome_distribution(
    bases: Sequence[Basis],
    bits: Sequence[int],
    meas_bases: Sequence[Basis] | None = None,
    noise: NoiseSpec | None = None,
) -> dict[tuple[int, ...], float]:
    """Exact outcome distribution (C7-ordered tuples) from the full NumPy density matrix."""
    meas = list(bases) if meas_bases is None else list(meas_bases)
    if len(meas) != len(bases):
        raise ValueError("meas_bases length mismatch")
    noise = noise or NoiseSpec()
    rho = numpy_note_density_matrix(bases, bits, noise)
    u = np.array([[1.0 + 0j]])
    for m in meas:
        u = np.kron(u, _H if m == Basis.X else np.eye(2))
    p = np.real(np.diag(u @ rho @ u.conj().T)).clip(min=0.0)
    t = apply_readout(p.reshape((2,) * len(meas)), noise.confusion())
    return tensor_to_distribution(t)


def numpy_purity(rho: np.ndarray) -> float:
    return float(np.real(np.trace(rho @ rho)))


def bloch_vector(rho_1q: np.ndarray) -> tuple[float, float, float]:
    """(Tr rho X, Tr rho Y, Tr rho Z) of a single-qubit density matrix."""
    x = 2 * np.real(rho_1q[0, 1])
    y = -2 * np.imag(rho_1q[0, 1])
    z = np.real(rho_1q[0, 0] - rho_1q[1, 1])
    return float(x), float(y), float(z)


# --------------------------------------------------------------------------- #
# QuTiP reference (operators re-entered from QuTiP primitives, not from channels.py)
# --------------------------------------------------------------------------- #


def _qutip_ket(basis: Basis, bit: int):
    import qutip as qt

    if basis == Basis.Z:
        return qt.basis(2, bit)
    sign = 1 if bit == 0 else -1
    return (qt.basis(2, 0) + sign * qt.basis(2, 1)).unit()


def _qutip_kraus(noise: NoiseSpec):
    import qutip as qt

    p = noise.param
    i2 = qt.qeye(2)
    if noise.channel == "none":
        return [i2]
    if noise.channel == "depolarizing":
        return [math.sqrt(1 - 3 * p / 4) * i2] + [math.sqrt(p / 4) * s for s in (qt.sigmax(), qt.sigmay(), qt.sigmaz())]
    if noise.channel == "dephasing":
        return [math.sqrt(1 - p) * i2, math.sqrt(p) * qt.sigmaz()]
    if noise.channel == "amplitude_damping":
        # destroy(2) = |0><1| ; |1><1| = num(2)
        return [qt.basis(2, 0).proj() + math.sqrt(1 - p) * qt.num(2), math.sqrt(p) * qt.destroy(2)]
    raise ValueError(noise.channel)


def qutip_kraus_is_cptp(noise: NoiseSpec) -> bool:
    """QuTiP's own CPTP test on the superoperator built from the QuTiP Kraus list."""
    import qutip as qt

    return bool(qt.kraus_to_super(_qutip_kraus(noise)).iscptp)


def qutip_outcome_distribution(
    bases: Sequence[Basis],
    bits: Sequence[int],
    meas_bases: Sequence[Basis] | None = None,
    noise: NoiseSpec | None = None,
) -> dict[tuple[int, ...], float]:
    """Exact outcome distribution via QuTiP tensor products and measurement projectors."""
    import qutip as qt

    validate_note(bases, bits)
    n = len(bases)
    check_statevector_width(n)
    meas = list(bases) if meas_bases is None else list(meas_bases)
    if len(meas) != n:
        raise ValueError("meas_bases length mismatch")
    noise = noise or NoiseSpec()
    kraus = _qutip_kraus(noise)
    rhos = []
    for b, x in zip(bases, bits, strict=True):
        r = qt.ket2dm(_qutip_ket(b, x))
        rhos.append(sum(k * r * k.dag() for k in kraus))
    rho = qt.tensor(rhos)
    t = np.zeros((2,) * n)
    for outcome in itertools.product((0, 1), repeat=n):
        proj = qt.tensor([qt.ket2dm(_qutip_ket(m, o)) for m, o in zip(meas, outcome, strict=True)])
        t[outcome] = max(0.0, float(np.real(qt.expect(proj, rho))))
    return tensor_to_distribution(apply_readout(t, noise.confusion()))
