"""Photonic source / link / threshold-detector model (lane F, F4) -- SEPARATE from qubit gate noise.

This is a phenomenological photon-number model of a polarisation-encoded BB84 pulse:

  source      Poisson (weak coherent, mean mu) or heralded SPDC (thermal single mode,
              conditioned on a threshold herald click with efficiency eta_h, dark prob d_h)
  link        each photon independently survives with probability eta_link (eg 10^(-dB/10))
  detection   two threshold detectors (one per outcome of the measurement basis);
              per-photon efficiency eta_det, misalignment e_opt (photon routed to the wrong
              detector), independent dark-click probability p_dark per detector per gate;
              double clicks are assigned a uniformly random bit (squashing convention).

It does NOT import or reuse ``qmint.quantum.channels``: photon loss/vacuum/multiphoton
statistics and trapped-ion / gate-model noise are different physics and must never be
equated (master plan 7, F3/F4). Outputs are *simulated photonic events* labelled
``SYNTHETIC`` -- not ``PHOTON_EXPERIMENT`` data and not gate-model qubit outcomes. A
phenomenological model calibrated or not, this is not a physical security test.

All quantities are dimensionless probabilities/fractions in [0, 1] (C7) except mu
(mean photons per pulse, >= 0) and loss in dB.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from qmint.core.contracts import EvidenceKind

SourceKind = Literal["poisson", "heralded_spdc"]

PHOTONIC_EVIDENCE_KIND = EvidenceKind.SYNTHETIC


def transmission_from_loss_db(loss_db: float) -> float:
    if loss_db < 0 or not math.isfinite(loss_db):
        raise ValueError("loss_db must be finite and >= 0")
    return 10.0 ** (-loss_db / 10.0)


def _prob(x: float, name: str) -> None:
    if not (0.0 <= x <= 1.0) or not math.isfinite(x):
        raise ValueError(f"{name} must lie in [0,1], got {x}")


@dataclass(frozen=True)
class PhotonicLinkParams:
    source: SourceKind = "poisson"
    mu: float = 0.1
    herald_efficiency: float = 1.0
    herald_dark_prob: float = 0.0
    eta_link: float = 1.0
    eta_det: float = 1.0
    p_dark: float = 0.0
    e_opt: float = 0.0
    label: str = field(default="hypothetical")

    def __post_init__(self) -> None:
        if self.mu < 0 or not math.isfinite(self.mu):
            raise ValueError("mu must be finite and >= 0")
        for name in ("herald_efficiency", "herald_dark_prob", "eta_link", "eta_det", "p_dark", "e_opt"):
            _prob(getattr(self, name), name)
        if self.source == "heralded_spdc" and self.herald_efficiency == 0 and self.herald_dark_prob == 0:
            raise ValueError("heralded source can never herald")

    @property
    def eta_total(self) -> float:
        return self.eta_link * self.eta_det


# --------------------------------------------------------------------------- #
# Photon-number statistics
# --------------------------------------------------------------------------- #


def _kmax(p: PhotonicLinkParams) -> int:
    return max(10, int(p.mu * 20 + 40))


def emitted_photon_distribution(p: PhotonicLinkParams) -> np.ndarray:
    """P(k photons leave the source in one pulse), k = 0..kmax (heralded: conditioned on herald)."""
    from scipy.stats import poisson

    k = np.arange(_kmax(p) + 1)
    if p.source == "poisson":
        dist = poisson.pmf(k, p.mu)
    else:  # thermal single-mode SPDC: mu^k / (1+mu)^(k+1), then herald click 1-(1-d_h)(1-eta_h)^k
        dist = (p.mu**k) / (1.0 + p.mu) ** (k + 1)
        dist = dist * (1.0 - (1.0 - p.herald_dark_prob) * (1.0 - p.herald_efficiency) ** k)
    if 1.0 - dist.sum() > 1e-12 and p.source == "poisson":
        raise ValueError("photon-number truncation tail too large")
    if p.source == "heralded_spdc":
        tail = (p.mu / (1.0 + p.mu)) ** (len(k))  # unconditioned thermal tail P(k > kmax)
        if tail > 1e-12 * max(dist.sum(), 1e-300):
            raise ValueError("photon-number truncation tail too large")
        dist = dist / dist.sum()
    return dist


def multiphoton_fraction(p: PhotonicLinkParams) -> dict[str, float]:
    """P(k>=2) per (heralded) pulse and P(k>=2 | k>=1) among non-vacuum pulses."""
    d = emitted_photon_distribution(p)
    non_vac = 1.0 - d[0]
    multi = max(0.0, 1.0 - d[0] - d[1])
    return {
        "p_vacuum": float(d[0]),
        "p_single": float(d[1]),
        "p_multi": float(multi),
        "multi_given_nonvacuum": float(multi / non_vac) if non_vac > 0 else 0.0,
    }


def _gen(p: PhotonicLinkParams, x: float) -> float:
    """Probability generating function E[x^k] of the emitted photon number."""
    if p.source == "poisson":
        return math.exp(-p.mu * (1.0 - x))
    d = emitted_photon_distribution(p)
    return float(np.sum(d * x ** np.arange(len(d))))


def click_statistics(p: PhotonicLinkParams) -> dict[str, float]:
    """Exact per-pulse outcome probabilities in the matched basis.

    Each photon independently: reaches the correct detector w.p. t_c = eta(1-e), the wrong one
    w.p. t_w = eta e, is lost otherwise; detectors also dark-click independently w.p. d.
      P(correct silent) = (1-d) G(1 - t_c);  P(wrong silent) = (1-d) G(1 - t_w)
      P(both silent)    = (1-d)^2 G(1 - eta)
    """
    eta, e, d = p.eta_total, p.e_opt, p.p_dark
    t_c, t_w = eta * (1 - e), eta * e
    c_sil = (1 - d) * _gen(p, 1 - t_c)
    w_sil = (1 - d) * _gen(p, 1 - t_w)
    both_sil = (1 - d) ** 2 * _gen(p, 1 - eta)
    correct_only = w_sil - both_sil  # wrong silent, correct clicked
    wrong_only = c_sil - both_sil
    double = 1.0 - c_sil - w_sil + both_sil
    p_detect = 1.0 - both_sil
    p_ok = correct_only + 0.5 * double
    return {
        "p_no_click": both_sil,
        "p_correct_only": correct_only,
        "p_wrong_only": wrong_only,
        "p_double": double,
        "p_detect": p_detect,
        "p_pass": p_ok,
        "qber_given_detect": (wrong_only + 0.5 * double) / p_detect if p_detect > 0 else float("nan"),
    }


def note_accept_probability(p: PhotonicLinkParams, n: int) -> float:
    """Exact-match verifier with NO loss tolerance: every one of n pulses must click and decode correctly."""
    if n < 1:
        raise ValueError("n >= 1")
    return click_statistics(p)["p_pass"] ** n


# --------------------------------------------------------------------------- #
# Event-level Monte Carlo (seeded)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SimulatedPhotonEvents:
    """Per-pulse simulated photonic events (NOT PhotonEvent records: those are real-data only)."""

    emitted: np.ndarray  # photons leaving the source
    arrived_correct: np.ndarray  # photons detected at the correct detector (before darks)
    arrived_wrong: np.ndarray
    click_correct: np.ndarray  # bool
    click_wrong: np.ndarray  # bool
    decoded_ok: np.ndarray  # bool: single correct click, or double click with lucky random bit
    evidence_kind: EvidenceKind = PHOTONIC_EVIDENCE_KIND

    def summary(self) -> dict[str, float | int | str]:
        n = len(self.emitted)
        det = self.click_correct | self.click_wrong
        return {
            "pulses": n,
            "emitted_photons": int(self.emitted.sum()),
            "detected_pulses": int(det.sum()),
            "double_clicks": int((self.click_correct & self.click_wrong).sum()),
            "decoded_ok": int(self.decoded_ok.sum()),
            "evidence_kind": self.evidence_kind.value,
        }


def simulate_pulses(p: PhotonicLinkParams, pulses: int, seed: int) -> SimulatedPhotonEvents:
    rng = np.random.default_rng(seed)
    dist = emitted_photon_distribution(p)
    emitted = rng.choice(len(dist), size=pulses, p=dist / dist.sum())
    eta = p.eta_total
    routed = rng.multinomial  # per pulse: (correct, wrong, lost)
    probs = [eta * (1 - p.e_opt), eta * p.e_opt, 1 - eta]
    split = np.array([routed(k, probs) for k in emitted]) if pulses else np.zeros((0, 3), int)
    ac, aw = split[:, 0], split[:, 1]
    cc = (ac > 0) | (rng.random(pulses) < p.p_dark)
    cw = (aw > 0) | (rng.random(pulses) < p.p_dark)
    coin = rng.random(pulses) < 0.5
    ok = (cc & ~cw) | (cc & cw & coin)
    return SimulatedPhotonEvents(emitted, ac, aw, cc, cw, ok)
