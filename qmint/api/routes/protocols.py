"""GET /protocols and /games: the frozen protocol registry and the security games.

Bound formulas are transcribed from the frozen contract comments (``qmint/core/contracts.py``,
``GameId``) and ``project/CONTRACTS.md``; lane D (proofs) has not yet re-verified them.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from qmint.core.contracts import PROTOCOL_GAMES, QUANTUM_PROTOCOLS, EvidenceKind, GameId

from ..common import lane_merged, provenance
from ..schemas import Envelope

TRANSCRIPTION_NOTE = "transcribed from frozen contract comments; lane D verification pending"


@dataclass(frozen=True)
class GameEntry:
    title: str
    source: str
    formula: str | None  # per-game closed-form bound in the size parameter, or None
    size_parameter: str | None
    per_unit: float | None  # base b of the bound b**size, when a closed form exists
    assumptions: tuple[str, ...]


MVW2012 = "Molina, Vidick & Watrous 2012, arXiv:1202.4010 (abstract; Sec. 3.2)"
KENT2022 = "Kent et al. 2022, npj Quantum Information, https://www.nature.com/articles/s41534-022-00524-4"

GAMES: dict[GameId, GameEntry] = {
    GameId.W1: GameEntry(
        "Wiesner simple 1->2 counterfeiting, exact verifier",
        MVW2012,
        "(3/4)^n",
        "n",
        0.75,
        ("ideal noiseless qubits", "exact-match verifier in the secret bases", "single note, two verifications",
         "honest bank keeps bases/bits secret"),
    ),
    GameId.W1_CV: GameEntry(
        "Wiesner counterfeiting, MVW classical-verification variant",
        MVW2012,
        "(3/4 + sqrt(2)/8)^n",
        "n",
        0.75 + math.sqrt(2.0) / 8.0,
        ("ideal noiseless qubits", "MVW classical-verification variant (distinct from W1)"),
    ),
    GameId.W2: GameEntry(
        "Noisy / threshold Wiesner", "QMint master plan 3.1", None, None, None,
        ("no published closed form assumed",),
    ),
    GameId.S1: GameEntry(
        "Ideal two-site S-token",
        KENT2022,
        "(1/2 + 1/(2*sqrt(2)))^N",
        "N",
        0.5 + 1.0 / (2.0 * math.sqrt(2.0)),
        ("ideal two-site S-token", "no loss, no noise", "trusted same-party agents"),
    ),
    GameId.S2: GameEntry(
        "Realistic noisy/lossy S-token (finite size)", KENT2022, None, None, None,
        ("finite-size analysis; no closed form transcribed",),
    ),
    GameId.D1: GameEntry(
        "Quantum-digital payment cryptogram",
        "Schiansky et al. 2023, Nature Communications, https://www.nature.com/articles/s41467-023-39519-w",
        None, None, None, ("no closed form transcribed",),
    ),
    GameId.A1: GameEntry(
        "Anonymity / issuer tracking", "Gavinsky et al. 2025, arXiv:2510.06212", None, None, None,
        ("no closed form transcribed",),
    ),
    GameId.C1: GameEntry(
        "Classical double-spend systems game", "QMint master plan 3.1", None, None, None,
        ("classical baselines (lane H) not merged",),
    ),
}
assert set(GAMES) == set(GameId), "every GameId needs a catalogue entry"


def bound_fn(game: GameId) -> Callable[[int], float] | None:
    per = GAMES[game].per_unit
    return None if per is None else (lambda size: per**size)


class GameInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    game_id: GameId
    title: str
    source: str
    closed_form: bool
    formula: str | None
    size_parameter: str | None
    per_unit_value: float | None
    bound_evidence_kind: EvidenceKind
    assumptions: list[str]
    protocols: list[str]
    note: str


class ProtocolInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    protocol_id: str
    family: str
    quantum: bool
    games: list[GameId]
    implemented_by_merged_lane: bool
    note: str


class GamesResponse(Envelope):
    data: list[GameInfo]


class ProtocolsResponse(Envelope):
    data: list[ProtocolInfo]


def game_info(g: GameId) -> GameInfo:
    e = GAMES[g]
    return GameInfo(
        game_id=g,
        title=e.title,
        source=e.source,
        closed_form=e.formula is not None,
        formula=e.formula,
        size_parameter=e.size_parameter,
        per_unit_value=e.per_unit,
        bound_evidence_kind=EvidenceKind.PUBLISHED_THEOREM if e.formula else EvidenceKind.UNCERTIFIED,
        assumptions=list(e.assumptions),
        protocols=sorted(p for p, gs in PROTOCOL_GAMES.items() if g in gs),
        note=TRANSCRIPTION_NOTE if e.formula else "no closed-form bound assumed; null, never 0",
    )


def _family(pid: str) -> str:
    if pid.startswith("wiesner"):
        return "wiesner"
    if pid.startswith("s_money"):
        return "s_money"
    if pid.startswith("classical_"):
        return "classical"
    return pid.split("_")[0]


router = APIRouter(tags=["protocols"])


@router.get("/games", response_model=GamesResponse)
def games() -> GamesResponse:
    return GamesResponse(
        status="OK",
        evidence_kind=EvidenceKind.PUBLISHED_THEOREM,
        provenance=provenance("qmint.core.contracts.GameId", notes=TRANSCRIPTION_NOTE),
        data=[game_info(g) for g in GameId],
    )


@router.get("/protocols", response_model=ProtocolsResponse)
def protocols() -> ProtocolsResponse:
    b_merged, _ = lane_merged("B")
    h_merged, _ = lane_merged("H")
    out = []
    for pid in sorted(PROTOCOL_GAMES):
        quantum = pid in QUANTUM_PROTOCOLS
        if pid == "wiesner_ideal":
            impl, note = True, "BB84 note circuits and W1 cloners available via lane F (qmint.quantum)"
        elif quantum:
            impl, note = b_merged, "protocol simulation owned by lane B"
        else:
            impl, note = h_merged, "classical baseline owned by lane H"
        out.append(
            ProtocolInfo(
                protocol_id=pid,
                family=_family(pid),
                quantum=quantum,
                games=sorted(PROTOCOL_GAMES[pid], key=lambda g: g.value),
                implemented_by_merged_lane=impl,
                note=note,
            )
        )
    return ProtocolsResponse(
        status="OK", evidence_kind=None, provenance=provenance("qmint.core.contracts.PROTOCOL_GAMES"), data=out
    )
