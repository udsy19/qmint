"""Evidence and security badges, derived ONLY from ``EvidenceKind`` / ``CertificateStatus``.

Rules enforced here (master plan sections 6, 9; Agent K work order):
  * A badge is a pure function of the frozen enum -- never of a free-text field or a number.
  * Simulated/synthetic/modelled origins and measured/experimental origins never share a badge
    label or a CSS class (``origin`` differs, and the label sets are disjoint).
  * Only ``CertificateStatus.CERTIFIED`` produces the ``ok`` (green) tone. Everything else,
    including the default ``UNCERTIFIED``, is never green.
  * Every badge carries a text label, so color is never the only channel.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from qmint.core.contracts import CertificateStatus, EvidenceKind

Origin = Literal["theory", "numeric", "simulated", "measured", "none"]
Tone = Literal["ok", "info", "neutral", "warn", "danger"]


@dataclass(frozen=True)
class Badge:
    label: str  # visible text, e.g. "MONTE-CARLO (lower bound)"
    css: str  # CSS class suffix, unique per label
    origin: Origin
    tone: Tone
    title: str  # tooltip / accessible description


# One entry per EvidenceKind. Order of the dict is irrelevant; rendering sorts by label.
_EVIDENCE: dict[EvidenceKind, Badge] = {
    EvidenceKind.PUBLISHED_THEOREM: Badge(
        "THEOREM", "theorem", "theory", "info", "Bound transcribed from a peer-reviewed proof"
    ),
    EvidenceKind.NUMERICAL_SDP: Badge(
        "NUMERICAL", "numerical", "numeric", "neutral",
        "Floating-point SDP solver output; not a proof without residual accounting",
    ),
    EvidenceKind.CERTIFIED_NUMERIC: Badge(
        "CERTIFIED-NUMERIC", "certified-numeric", "numeric", "info",
        "Numeric bound with rigorous residual accounting",
    ),
    EvidenceKind.MONTE_CARLO: Badge(
        "MONTE-CARLO (lower bound)", "monte-carlo", "simulated", "neutral",
        "Sampled attack success: a LOWER bound on worst-case attack success, never an upper bound",
    ),
    EvidenceKind.PHOTON_EXPERIMENT: Badge(
        "PHOTON-EXPERIMENT", "photon-experiment", "measured", "info",
        "Real recorded photon events with dataset hash",
    ),
    EvidenceKind.PUBLISHED_AGGREGATE: Badge(
        "PUBLISHED-AGGREGATE", "published-aggregate", "theory", "neutral",
        "Number quoted from a paper table or text",
    ),
    EvidenceKind.DIGITIZED_FIGURE: Badge(
        "DIGITIZED-FIGURE", "digitized-figure", "theory", "neutral",
        "Read off a published figure; carries digitization error",
    ),
    EvidenceKind.SYNTHETIC: Badge(
        "SYNTHETIC", "synthetic", "simulated", "warn", "Generated fixture or hypothetical scenario"
    ),
    EvidenceKind.SIMULATOR_IDEAL: Badge(
        "SIMULATOR-IDEAL", "simulator-ideal", "simulated", "neutral", "Noiseless circuit/statevector simulation"
    ),
    EvidenceKind.SIMULATOR_NOISY: Badge(
        "SIMULATOR-NOISY", "simulator-noisy", "simulated", "neutral", "Simulation under a declared noise model"
    ),
    EvidenceKind.QPU: Badge("QPU", "qpu", "measured", "info", "Actual quantum hardware job with job id"),
    EvidenceKind.MODELLED_LATENCY: Badge(
        "MODELLED-LATENCY", "modelled-latency", "simulated", "neutral",
        "Latency from a model (light-cone, queue model); not a measurement",
    ),
    EvidenceKind.MEASURED_LATENCY: Badge(
        "MEASURED-LATENCY", "measured-latency", "measured", "info", "Latency from real measurements"
    ),
    EvidenceKind.UNCERTIFIED: Badge(
        "UNCERTIFIED", "uncertified", "none", "warn", "No applicable evidence"
    ),
}

_STATUS: dict[CertificateStatus, Badge] = {
    CertificateStatus.CERTIFIED: Badge(
        "CERTIFIED", "status-certified", "theory", "ok",
        "Every target met by an applicable, independently checked bound",
    ),
    CertificateStatus.UNCERTIFIED: Badge(
        "UNCERTIFIED", "status-uncertified", "none", "warn", "Missing bound, assumption or independent check"
    ),
    CertificateStatus.INFEASIBLE: Badge(
        "INFEASIBLE", "status-infeasible", "none", "warn", "Applicable bounds exist but targets cannot be met"
    ),
    CertificateStatus.UNSAFE: Badge(
        "UNSAFE", "status-unsafe", "none", "danger", "An attack exceeds the claimed bound or targets"
    ),
    CertificateStatus.OUT_OF_MODEL: Badge(
        "OUT-OF-MODEL", "status-out-of-model", "none", "danger",
        "Request violates the proof's trust/physical model",
    ),
}

# Fail at import time if a frozen enum gains a member the UI does not know how to label.
assert set(_EVIDENCE) == set(EvidenceKind), "every EvidenceKind needs a badge"
assert set(_STATUS) == set(CertificateStatus), "every CertificateStatus needs a badge"
assert all(b.tone != "ok" for b in _EVIDENCE.values()), "evidence badges are never green"
assert [s for s, b in _STATUS.items() if b.tone == "ok"] == [CertificateStatus.CERTIFIED]


def evidence_badge(kind: EvidenceKind | str) -> Badge:
    return _EVIDENCE[EvidenceKind(kind)]


def status_badge(status: CertificateStatus | str) -> Badge:
    return _STATUS[CertificateStatus(status)]


def all_badges() -> list[Badge]:
    return [*_EVIDENCE.values(), *_STATUS.values()]
