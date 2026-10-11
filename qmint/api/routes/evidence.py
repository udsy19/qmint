"""GET /evidence (record store index) and /evidence/labels (display labels).

Labels are derived from ``qmint.ui.evidence_badges`` (the single source of the enum -> label
mapping) plus the two API-only statuses DEMO_ADAPTER and NOT_AVAILABLE.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from qmint.core.config import load_config
from qmint.core.contracts import CertificateStatus, EvidenceKind
from qmint.core.records import RecordStore
from qmint.ui.evidence_badges import Origin, Tone, evidence_badge, status_badge

from ..common import provenance
from ..schemas import Envelope


class EvidenceLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    group: Literal["evidence_kind", "certificate_status", "api_status"]
    label: str
    css: str
    origin: Origin | Literal["api"]
    tone: Tone
    title: str


class EvidenceLabelsResponse(Envelope):
    data: list[EvidenceLabel]


class RecordSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_id: str
    contract: str
    evidence_kind: EvidenceKind
    payload_sha256: str
    reproducibility: str
    flags: list[str]
    created_utc: str


class EvidenceData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    experiments_dir: str
    records: list[RecordSummary]


class EvidenceResponse(Envelope):
    data: EvidenceData


API_STATUS_LABELS = [
    EvidenceLabel(key="DEMO_ADAPTER", group="api_status", label="DEMO ADAPTER", css="demo-adapter", origin="api",
                  tone="warn", title="Demonstration computed from analytic / published formulas or merged lane-F/G "
                  "code while the owning lane is not merged; not that lane's output"),
    EvidenceLabel(key="NOT_AVAILABLE", group="api_status", label="NOT AVAILABLE", css="not-available",
                  origin="api", tone="neutral", title="Nothing honest to show yet; see the reason"),
]


def evidence_labels() -> list[EvidenceLabel]:
    out = []
    for k in EvidenceKind:
        b = evidence_badge(k)
        out.append(EvidenceLabel(key=k.value, group="evidence_kind", label=b.label, css=b.css, origin=b.origin,
                                 tone=b.tone, title=b.title))
    for s in CertificateStatus:
        b = status_badge(s)
        out.append(EvidenceLabel(key=s.value, group="certificate_status", label=b.label, css=b.css, origin=b.origin,
                                 tone=b.tone, title=b.title))
    return sorted(out + API_STATUS_LABELS, key=lambda lab: (lab.group, lab.key))


router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("", response_model=EvidenceResponse)
def evidence() -> EvidenceResponse:
    cfg = load_config()
    store = RecordStore(cfg.experiments_dir)
    recs = [
        RecordSummary(**{k: line[k] for k in RecordSummary.model_fields})
        for line in store.iter_registry()
    ]
    return EvidenceResponse(
        status="OK",
        evidence_kind=None,
        provenance=provenance("qmint.core.records.RecordStore", notes="read-only registry index"),
        data=EvidenceData(experiments_dir=str(cfg.experiments_dir.relative_to(cfg.root)), records=recs),
    )


@router.get("/labels", response_model=EvidenceLabelsResponse)
def labels() -> EvidenceLabelsResponse:
    return EvidenceLabelsResponse(
        status="OK", evidence_kind=None, provenance=provenance("qmint.ui.evidence_badges"), data=evidence_labels()
    )
