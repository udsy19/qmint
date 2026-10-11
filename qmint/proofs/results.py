"""Construction of frozen ``BoundResult`` records shared by the lane-D evaluators.

A bound is always carried in log10 form; the linear ``value`` is filled only when it is
representable (never an underflowed 0.0, which would read as "perfectly secure").
"""

from __future__ import annotations

import math

from qmint.core.contracts import BoundRequest, BoundResult, EvidenceKind, ProofStatus
from qmint.proofs.assumption_check import AssumptionReport

MIN_LINEAR_VALUE = 1e-300


def unsupported(
    request: BoundRequest,
    notes: str,
    *,
    out_of_domain: bool = False,
    report: AssumptionReport | None = None,
    theorem_id: str | None = None,
) -> BoundResult:
    report = report or AssumptionReport()
    return BoundResult(
        protocol_id=request.protocol_id,
        game_id=request.game_id,
        axis=request.axis,
        status=ProofStatus.UNSUPPORTED,
        theorem_id=theorem_id,
        evidence_kind=EvidenceKind.UNCERTIFIED,
        assumptions_checked=list(report.checked),
        failed_assumptions=list(report.failed),
        out_of_domain=out_of_domain,
        notes=notes,
    )


def bounded(
    request: BoundRequest,
    theorem_id: str,
    log10_value: float,
    *,
    status: ProofStatus,
    evidence_kind: EvidenceKind,
    report: AssumptionReport,
    notes: str,
) -> BoundResult:
    if not math.isfinite(log10_value):
        raise ValueError("non-finite log10 bound")
    if log10_value >= 0.0:
        log10_value, notes = 0.0, notes + " | bound is trivial (>= 1), clamped to 1"
    value = 10.0**log10_value if log10_value >= math.log10(MIN_LINEAR_VALUE) else None
    return BoundResult(
        protocol_id=request.protocol_id,
        game_id=request.game_id,
        axis=request.axis,
        value=value,
        log10_value=log10_value,
        status=status,
        theorem_id=theorem_id,
        evidence_kind=evidence_kind,
        assumptions_checked=list(report.checked),
        failed_assumptions=[],
        out_of_domain=False,
        notes=notes,
    )
