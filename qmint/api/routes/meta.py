"""GET /health, /meta and /meta/tracker (gate + task status read from project/TRACKER.yaml)."""

from __future__ import annotations

from typing import Any

import yaml
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from qmint.core.config import REPO_ROOT
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
    """Liveness probe."""
    return Health(ok=True)


@router.get("/meta", response_model=MetaResponse)
def meta() -> MetaResponse:
    """API and schema versions, git sha, lane package probe and the research-platform disclaimer."""
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


TRACKER = "project/TRACKER.yaml"


class GateStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gate_id: str
    description: str
    status: str
    evidence: list[str]
    notes: str | None


class TaskStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str
    lane: str
    description: str
    status: str
    commit: str | None
    evidence: list[str]
    blockers: list[str]
    notes: str | None


class TrackerData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_file: str
    project_phase: str | None
    updated_at_utc: str | None
    status_values: list[str]
    gates: list[GateStatus]
    tasks: list[TaskStatus]


class TrackerResponse(Envelope):
    data: TrackerData


def _strs(v: Any) -> list[str]:
    return [str(x) for x in v] if isinstance(v, list) else []


def read_tracker() -> TrackerData | None:
    path = REPO_ROOT / TRACKER
    if not path.is_file():
        return None
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    gates = [
        GateStatus(gate_id=gid, description=str(g.get("description", "")), status=str(g.get("status", "UNKNOWN")),
                   evidence=_strs(g.get("evidence")), notes=g.get("notes"))
        for gid, g in (doc.get("gates") or {}).items()
    ]
    tasks = [
        TaskStatus(task_id=tid, lane=str(t.get("lane", "")), description=str(t.get("description", "")),
                   status=str(t.get("status", "UNKNOWN")), commit=None if t.get("commit") is None else str(t["commit"]),
                   evidence=_strs(t.get("evidence")), blockers=_strs(t.get("blockers")), notes=t.get("notes"))
        for tid, t in (doc.get("tasks") or {}).items()
    ]
    return TrackerData(
        source_file=TRACKER,
        project_phase=doc.get("project_phase"),
        updated_at_utc=None if doc.get("updated_at_utc") is None else str(doc["updated_at_utc"]),
        status_values=_strs(doc.get("status_values")),
        gates=gates,
        tasks=tasks,
    )


@router.get("/meta/tracker", response_model=TrackerResponse)
def tracker() -> TrackerResponse:
    """Gate and task status read verbatim from project/TRACKER.yaml (lead-maintained)."""
    data = read_tracker()
    if data is None:
        return TrackerResponse(
            status="NOT_AVAILABLE", evidence_kind=None, reason=f"{TRACKER} not found in this checkout",
            provenance=provenance(TRACKER),
            data=TrackerData(source_file=TRACKER, project_phase=None, updated_at_utc=None, status_values=[], gates=[],
                             tasks=[]),
        )
    return TrackerResponse(
        status="OK", evidence_kind=None, data=data,
        provenance=provenance(TRACKER, notes="lead-maintained tracker; statuses verbatim, not re-derived"),
    )
