"""GET /health and /meta."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from qmint.core.contracts import SCHEMA_VERSION

from ..common import API_VERSION, LANE_PACKAGES, git_sha, lane_merged, provenance
from ..schemas import Envelope


class Health(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool


class LaneStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lane: str
    package: str
    description: str
    merged: bool
    detail: str


class MetaData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_version: str
    schema_version: str
    git_sha: str
    lanes: list[LaneStatus]
    disclaimer: str


class MetaResponse(Envelope):
    data: MetaData


DISCLAIMER = (
    "QMint is an open-source research platform. Results are simulations, published analytic values "
    "or committed datasets, each labelled with its evidence kind. It is not money, not a payment "
    "service and not a deployable quantum currency."
)

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=Health)
def health() -> Health:
    return Health(ok=True)


@router.get("/meta", response_model=MetaResponse)
def meta() -> MetaResponse:
    lanes = []
    for lane, (pkg, desc) in LANE_PACKAGES.items():
        merged, detail = lane_merged(lane)
        lanes.append(LaneStatus(lane=lane, package=pkg, description=desc, merged=merged, detail=detail))
    return MetaResponse(
        status="OK",
        evidence_kind=None,
        provenance=provenance("qmint.api.routes.meta"),
        data=MetaData(
            api_version=API_VERSION,
            schema_version=SCHEMA_VERSION,
            git_sha=git_sha(),
            lanes=lanes,
            disclaimer=DISCLAIMER,
        ),
    )
