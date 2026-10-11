"""Gate/storage noise channels for qubit circuits (lane F, F3).

This module models *qubit* noise only: depolarizing, dephasing, amplitude damping
(CPTP maps given by Kraus operators) and classical readout error (a column-stochastic
confusion matrix applied to measured bits). It deliberately knows nothing about
photons; photonic loss/detection lives in ``qmint.quantum.photonic_model`` and the
two must never be equated (master plan 7, F3).

Noise location (declared, used identically by every simulation path): the channel
acts once on every note qubit *between preparation and verification* (a storage /
transmission channel); readout error acts on every measured bit.

Parameters supplied by callers are hypothetical unless a calibration says otherwise;
curves computed from them are labelled ``SYNTHETIC`` (analytic) or ``SIMULATOR_NOISY``
(sampled from Aer), never as physical evidence.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np

from qmint.core.contracts import Basis

ChannelKind = Literal["none", "depolarizing", "dephasing", "amplitude_damping"]

_I = np.eye(2, dtype=complex)
_X = np.array([[0, 1], [1, 0]], dtype=complex)
_Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
_Z = np.array([[1, 0], [0, -1]], dtype=complex)


def _check_prob(p: float, name: str) -> float:
    if not (0.0 <= p <= 1.0) or not math.isfinite(p):
        raise ValueError(f"{name} must be a probability in [0,1], got {p}")
    return float(p)


def depolarizing_kraus(p: float) -> list[np.ndarray]:
    """E(rho) = (1-p) rho + p I/2  (same parametrisation as qiskit_aer depolarizing_error(p, 1))."""
    _check_prob(p, "p")
    return [
        math.sqrt(1 - 3 * p / 4) * _I,
        math.sqrt(p / 4) * _X,
        math.sqrt(p / 4) * _Y,
        math.sqrt(p / 4) * _Z,
    ]


def dephasing_kraus(p: float) -> list[np.ndarray]:
    """Phase flip: E(rho) = (1-p) rho + p Z rho Z."""
    _check_prob(p, "p")
    return [math.sqrt(1 - p) * _I, math.sqrt(p) * _Z]


def amplitude_damping_kraus(gamma: float) -> list[np.ndarray]:
    """|1> -> |0> with probability gamma (Nielsen & Chuang eq. 8.108)."""
    _check_prob(gamma, "gamma")
    return [
        np.array([[1, 0], [0, math.sqrt(1 - gamma)]], dtype=complex),
        np.array([[0, math.sqrt(gamma)], [0, 0]], dtype=complex),
    ]


def is_cptp(kraus: list[np.ndarray], atol: float = 1e-12) -> bool:
    """Kraus completeness sum_k K^dagger K = I (trace preservation; CP is automatic for Kraus form)."""
    if not kraus:
        return False
    d_in = kraus[0].shape[1]
    s = sum(k.conj().T @ k for k in kraus)
    return bool(np.allclose(s, np.eye(d_in), atol=atol))


def apply_kraus(rho: np.ndarray, kraus: list[np.ndarray]) -> np.ndarray:
    return sum(k @ rho @ k.conj().T for k in kraus)


def readout_confusion(p01: float, p10: float) -> np.ndarray:
    """Column-stochastic M[reported, true]: p01 = P(report 1 | true 0), p10 = P(report 0 | true 1)."""
    _check_prob(p01, "p01")
    _check_prob(p10, "p10")
    return np.array([[1 - p01, p10], [p01, 1 - p10]], dtype=float)


@dataclass(frozen=True)
class NoiseSpec:
    """One qubit channel (applied to every note qubit) plus symmetric-or-not readout error."""

    channel: ChannelKind = "none"
    param: float = 0.0
    readout_p01: float = 0.0
    readout_p10: float = 0.0

    def __post_init__(self) -> None:
        _check_prob(self.param, "param")
        _check_prob(self.readout_p01, "readout_p01")
        _check_prob(self.readout_p10, "readout_p10")
        if self.channel == "none" and self.param != 0.0:
            raise ValueError("channel 'none' takes param 0")

    @property
    def is_ideal(self) -> bool:
        return self.channel == "none" and self.readout_p01 == 0.0 and self.readout_p10 == 0.0

    def kraus(self) -> list[np.ndarray]:
        if self.channel == "none":
            return [_I.copy()]
        if self.channel == "depolarizing":
            return depolarizing_kraus(self.param)
        if self.channel == "dephasing":
            return dephasing_kraus(self.param)
        if self.channel == "amplitude_damping":
            return amplitude_damping_kraus(self.param)
        raise ValueError(f"unknown channel {self.channel!r}")

    def confusion(self) -> np.ndarray:
        return readout_confusion(self.readout_p01, self.readout_p10)

    def describe(self) -> str:
        return (
            f"qubit_channel={self.channel}(param={self.param}) on every note qubit between prep and "
            f"verify; readout p01={self.readout_p01} p10={self.readout_p10}; hypothetical parameters"
        )

    def aer_quantum_error(self):  # -> qiskit_aer.noise.QuantumError | None
        """Same channel built with qiskit_aer's own constructors (independent parametrisation)."""
        from qiskit_aer.noise import amplitude_damping_error, depolarizing_error, pauli_error

        if self.channel == "none":
            return None
        if self.channel == "depolarizing":
            return depolarizing_error(self.param, 1)
        if self.channel == "dephasing":
            return pauli_error([("Z", self.param), ("I", 1 - self.param)])
        return amplitude_damping_error(self.param)

    def aer_noise_model(self):  # -> qiskit_aer.noise.NoiseModel
        """Readout-error part of the model; the qubit channel is inserted explicitly in the circuit."""
        from qiskit_aer.noise import NoiseModel, ReadoutError

        nm = NoiseModel()
        if self.readout_p01 or self.readout_p10:
            m = self.confusion()
            # Aer: probabilities[true][reported]
            nm.add_all_qubit_readout_error(ReadoutError([[m[0, 0], m[1, 0]], [m[0, 1], m[1, 1]]]))
        return nm


def analytic_correct_probability(spec: NoiseSpec, basis: Basis, bit: int) -> float:
    """Closed-form P(true outcome == bit) after the channel, measured in the preparation basis.

    Derived by hand (not from the Kraus code):
      depolarizing p:     1 - p/2 for every BB84 state
      dephasing p:        Z basis 1;  X basis 1 - p
      amplitude damping g: |0> 1;  |1> 1-g;  |+>,|-> (1 + sqrt(1-g))/2
    """
    p = spec.param
    if spec.channel == "none":
        return 1.0
    if spec.channel == "depolarizing":
        return 1.0 - p / 2.0
    if spec.channel == "dephasing":
        return 1.0 if basis == Basis.Z else 1.0 - p
    if spec.channel == "amplitude_damping":
        if basis == Basis.Z:
            return 1.0 if bit == 0 else 1.0 - p
        return 0.5 * (1.0 + math.sqrt(1.0 - p))
    raise ValueError(spec.channel)


def analytic_qubit_pass_probability(spec: NoiseSpec, basis: Basis, bit: int) -> float:
    """P(reported bit == secret bit) for one qubit: channel then readout error."""
    pc = analytic_correct_probability(spec, basis, bit)
    flip_from_correct = spec.readout_p01 if bit == 0 else spec.readout_p10
    flip_from_wrong = spec.readout_p10 if bit == 0 else spec.readout_p01
    return pc * (1.0 - flip_from_correct) + (1.0 - pc) * flip_from_wrong


def analytic_note_accept_probability(spec: NoiseSpec, bases: list[Basis], bits: list[int]) -> float:
    """Exact-match Wiesner verification of a specific note: product of per-qubit pass probabilities."""
    return math.prod(analytic_qubit_pass_probability(spec, b, x) for b, x in zip(bases, bits, strict=True))


def analytic_mean_accept_probability(spec: NoiseSpec, n: int) -> float:
    """Expected acceptance for a *uniformly random* n-qubit note (any n; analytic mode, no 2^n)."""
    per_qubit = 0.25 * sum(
        analytic_qubit_pass_probability(spec, b, x) for b in (Basis.Z, Basis.X) for x in (0, 1)
    )
    return per_qubit**n
