"""Shared response building blocks for the QMint research API (lane K).

Every endpoint returns an envelope with:

* ``status``: ``OK`` (real merged-lane code path), ``DEMO_ADAPTER`` (clearly labelled stand-in
  computed from published analytic formulas or merged code while the owning lane is not merged),
  or ``NOT_AVAILABLE`` (nothing honest to show; ``reason`` says why).
* ``evidence_kind``: the frozen-contract ``EvidenceKind`` of the payload's headline numbers
  (``None`` only for metadata / NOT_AVAILABLE payloads).
* ``provenance`` and ``reason`` (required whenever ``status != OK``).

Every number meant for display is a :class:`Quantity`: it carries its own evidence kind,
method, unit and source. ``value is None`` means "no applicable bound / not available" -- never 0.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from qmint.core.contracts import EvidenceKind, Unit

ApiStatus = Literal["OK", "DEMO_ADAPTER", "NOT_AVAILABLE"]

Method = Literal[
    "closed_form",  # transcribed / derived formula evaluated exactly
    "exact_enumeration",  # exact model value by enumerating outcomes / Kraus operators
    "aer_sampling",  # shot-sampled local Aer simulation (has a confidence interval)
    "monte_carlo",  # sampled attack/acceptance trials (lower bound on worst-case attack success; has a CI)
    "numerical_sdp",  # floating-point (or exactly re-certified) SDP solver output
    "event_simulation",  # lane-G discrete-event timing simulation
    "published_value",  # number quoted from a paper
    "measured_dataset",  # statistic of a committed real measurement dataset
    "not_available",
]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConfidenceInterval(_Model):
    """Interval around an estimate. For published aggregates this is the quoted +/- range."""

    lo: float
    hi: float
    confidence: float | None = Field(default=None, description="e.g. 0.99; None for quoted +/- ranges")
    method: str = Field(description="e.g. clopper_pearson_0.99, published_plus_minus, p05_p95")


class Quantity(_Model):
    """A displayable number with its evidence. ``value=None`` means not available (never 0)."""

    id: str
    label: str
    value: float | None
    log10_value: float | None = Field(default=None, description="log10(value), for values below float range")
    unit: Unit
    evidence_kind: EvidenceKind
    method: Method
    interval: ConfidenceInterval | None = None
    source: str = Field(min_length=1, description="module path or citation (URL + anchor)")
    formula: str | None = None
    note: str | None = None


class ApiProvenance(_Model):
    source: str
    git_sha: str
    generated_at_utc: str
    seed: int | None = None
    software: dict[str, str] = Field(default_factory=dict)
    notes: str | None = None


class Envelope(_Model):
    """Base of every endpoint response (never used directly as a response model)."""

    status: ApiStatus
    evidence_kind: EvidenceKind | None
    provenance: ApiProvenance
    reason: str | None = None

    @model_validator(mode="after")
    def _reason_required(self) -> Envelope:
        if self.status != "OK" and not (self.reason and self.reason.strip()):
            raise ValueError("reason is required when status != OK")
        return self


class ApiErrorBody(_Model):
    code: str
    message: str
    detail: Any | None = None


class ApiError(_Model):
    """Uniform error body for every 4xx/5xx response (incl. request validation)."""

    error: ApiErrorBody


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    422: {"model": ApiError, "description": "Request validation error"},
    500: {"model": ApiError, "description": "Internal error"},
}


class NoiseIn(_Model):
    """Declared (hypothetical) noise: one qubit channel on every note qubit plus readout error."""

    channel: Literal["none", "depolarizing", "dephasing", "amplitude_damping"] = "none"
    param: float = Field(default=0.0, ge=0.0, le=1.0)
    readout_p01: float = Field(default=0.0, ge=0.0, le=0.5)
    readout_p10: float = Field(default=0.0, ge=0.0, le=0.5)

    @model_validator(mode="after")
    def _none_has_no_param(self) -> NoiseIn:
        if self.channel == "none" and self.param != 0.0:
            raise ValueError("channel 'none' takes param 0")
        return self
