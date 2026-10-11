"""POST /certificates -- honest certificate studio backend.

Until lanes D (proofs) and I (compiler) merge, the returned C5 ``SecurityCertificate`` is always
``UNCERTIFIED`` with null bounds. For the ideal games W1 and S1 only, the response also carries
``demo_bounds``: the published closed-form bound at the requested size and the minimal size meeting
the target. Those are DEMO_ADAPTER values and explicitly not a certificate.
"""

from __future__ import annotations

import math

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from qmint.core.contracts import (
    PROTOCOL_GAMES,
    EvidenceKind,
    GameId,
    SecurityCertificate,
    Targets,
    Unit,
    check_protocol_game,
)

from ..common import git_sha, lane_merged, provenance
from ..schemas import ERROR_RESPONSES, Envelope, NoiseIn, Quantity
from .protocols import GAMES, GameInfo, game_info

DEMO_GAMES = (GameId.W1, GameId.S1)
NOT_A_CERTIFICATE = "not a certificate; ideal noiseless game only; honest-error tolerance not accounted"


class CertificateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    game: GameId = GameId.W1
    protocol_id: str | None = Field(default=None, description="defaults to the first protocol registered for game")
    epsilon_unf_target: float = Field(default=1e-9, gt=0.0, lt=1.0)
    n: int = Field(default=64, ge=1, le=2000, description="qubits (W1) or N (S1)")
    honest_error_tolerance: float = Field(default=0.0, ge=0.0, le=0.5)
    channel: NoiseIn | None = None
    adversary_assumptions: list[str] = Field(default_factory=list)


class AssumptionCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assumption: str
    satisfied: bool | None = Field(description="None = cannot be checked by this adapter")
    detail: str


class CertificateData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    certificate: SecurityCertificate
    theorem: GameInfo
    reasons: list[str]
    assumption_checks: list[AssumptionCheck]
    demo_bounds: list[Quantity]
    demo_bounds_status: str


class CertificateResponse(Envelope):
    data: CertificateData


router = APIRouter(tags=["certificates"], responses=ERROR_RESPONSES)


def _protocol_for(game: GameId, requested: str | None) -> str:
    if requested is not None:
        try:
            check_protocol_game(requested, game)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        return requested
    return sorted(p for p, gs in PROTOCOL_GAMES.items() if game in gs)[0]


@router.post("/certificates", response_model=CertificateResponse)
def certificates(req: CertificateRequest) -> CertificateResponse:
    game = req.game
    entry = GAMES[game]
    protocol_id = _protocol_for(game, req.protocol_id)

    reasons: list[str] = []
    for lane, what in (("D", "proofs"), ("I", "certificate compiler")):
        merged, detail = lane_merged(lane)
        if not merged:
            reasons.append(f"lane {lane} ({what}) not merged: {detail}")
        else:
            reasons.append(f"lane {lane} ({what}) present but not wired into this API yet")

    checks = [
        AssumptionCheck(assumption=a, satisfied=None, detail="not machine-checked by this adapter")
        for a in entry.assumptions
    ]
    failed: list[str] = []
    noisy = req.channel is not None and not (
        req.channel.channel == "none" and req.channel.readout_p01 == 0.0 and req.channel.readout_p10 == 0.0
    )
    if game in DEMO_GAMES:
        ok = req.honest_error_tolerance == 0.0 and not noisy
        checks.append(
            AssumptionCheck(
                assumption="noiseless channel and zero honest-error tolerance (ideal game)",
                satisfied=ok,
                detail="requested parameters fit the ideal game" if ok else
                "requested noise / honest-error tolerance is outside the ideal game; see W2 / S2 (no closed form)",
            )
        )
        if not ok:
            failed.append("ideal_noiseless_game")
    for a in req.adversary_assumptions:
        checks.append(AssumptionCheck(assumption=f"user-declared adversary assumption: {a}", satisfied=None,
                                      detail="recorded, not checked"))

    demo: list[Quantity] = []
    per = entry.per_unit
    if game in DEMO_GAMES and per is not None:
        log10 = req.n * math.log10(per)
        value = 10.0**log10 if log10 > -300 else None
        demo.append(
            Quantity(
                id="published_bound_at_size", label=f"Published ideal bound at {entry.size_parameter}={req.n}",
                value=value, log10_value=log10, unit=Unit.PROBABILITY, evidence_kind=EvidenceKind.PUBLISHED_THEOREM,
                method="closed_form", source=entry.source, formula=entry.formula,
                note=NOT_A_CERTIFICATE if value is not None else NOT_A_CERTIFICATE + "; value below float range, see log10",
            )
        )
        n_min = math.ceil(math.log(req.epsilon_unf_target) / math.log(per))
        demo.append(
            Quantity(
                id="min_size_for_target", label=f"Minimal {entry.size_parameter} with bound <= target",
                value=float(n_min), unit=Unit.COUNT, evidence_kind=EvidenceKind.PUBLISHED_THEOREM,
                method="closed_form", source=entry.source,
                formula=f"ceil(ln(target) / ln({per:.6g}))", note=NOT_A_CERTIFICATE,
            )
        )
        reasons.append("demo_bounds are published ideal-game values (DEMO_ADAPTER), " + NOT_A_CERTIFICATE)
        status, demo_status, reason = "DEMO_ADAPTER", "DEMO_ADAPTER", "; ".join(reasons[:2])
    else:
        demo_status = "NOT_AVAILABLE"
        reasons.append(f"no closed-form bound transcribed for game {game.value}; bound is null, never 0")
        status, reason = "NOT_AVAILABLE", "; ".join(reasons)

    cert = SecurityCertificate(
        protocol_id=protocol_id,
        game_id=game,
        security_model_id=f"{game.value}-api-demo",
        parameters={
            "n": req.n,
            "honest_error_tolerance": req.honest_error_tolerance,
            "channel": req.channel.model_dump() if req.channel else None,
            "adversary_assumptions": req.adversary_assumptions,
        },
        targets=Targets(epsilon_unf=req.epsilon_unf_target),
        assumptions_met=False,
        failed_assumptions=failed,
        reason="UNCERTIFIED: " + "; ".join(reasons),
        software_revision=git_sha(),
    )
    return CertificateResponse(
        status=status,
        evidence_kind=EvidenceKind.UNCERTIFIED,
        reason=reason,
        provenance=provenance("qmint.api.routes.certificates", notes=NOT_A_CERTIFICATE),
        data=CertificateData(
            certificate=cert,
            theorem=game_info(game),
            reasons=reasons,
            assumption_checks=checks,
            demo_bounds=demo,
            demo_bounds_status=demo_status,
        ),
    )
