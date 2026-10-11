"""GET /evidence (record store index, provenance-gated) and /evidence/labels (display labels).

Labels are derived from ``qmint.api.evidence_labels`` (the single source of the enum -> label
mapping) plus the two API-only statuses DEMO_ADAPTER and NOT_AVAILABLE.

Provenance gate (red-team M-K1/M-L1): a record is served with its own evidence kind only if
``RecordStore.get`` verifies it against the registry (hash, contract, evidence kind) and neither
its provenance nor its payload is marked as a fixture. Anything else is served as SYNTHETIC with
``provenance_verified=false`` and the reasons, so a fixture can never surface as research evidence.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from qmint.core.config import load_config
from qmint.core.contracts import CertificateStatus, EvidenceKind
from qmint.core.records import ExperimentRecord, RecordStore

from ..common import provenance
from ..evidence_labels import Origin, Tone, evidence_badge, status_badge
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
    evidence_kind: EvidenceKind = Field(
        description="Evidence kind as served: the record's own kind only when provenance_verified, else SYNTHETIC"
    )
    recorded_evidence_kind: EvidenceKind = Field(description="Evidence kind the registry line claims")
    provenance_verified: bool
    provenance_problems: list[str] = Field(description="Why the record was downgraded to SYNTHETIC (empty if verified)")
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


_GIT_SHA = re.compile(r"[0-9a-f]{7,40}(-dirty)?")


def _strings(obj: Any) -> Iterator[str]:
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from _strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _strings(v)


def provenance_problems(store: RecordStore, line: dict[str, Any]) -> list[str]:
    """Reasons a registry line may NOT be served as its claimed evidence kind (empty = verified)."""
    try:
        rec: ExperimentRecord = store.get(str(line.get("record_id", "")))
    except (OSError, ValueError) as e:  # missing file, unsafe id, validation / registry mismatch
        return [f"record store verification failed: {e}"]
    problems = []
    if not _GIT_SHA.fullmatch(rec.provenance.git_sha):
        problems.append(f"provenance git_sha {rec.provenance.git_sha!r} is not a commit sha")
    if any("fixture" in s.casefold() for s in _strings(rec.provenance.model_dump())):
        problems.append("provenance is marked as a fixture")
    if any("fixture" in s.casefold() for s in _strings(rec.payload)):
        problems.append("payload is marked as a fixture")
    return problems


def gated_summary(store: RecordStore, line: dict[str, Any]) -> RecordSummary:
    """Registry line -> summary; fixture or unverifiable records are served as SYNTHETIC."""
    problems = provenance_problems(store, line)
    claimed = EvidenceKind(line["evidence_kind"])
    return RecordSummary(
        record_id=line["record_id"],
        contract=line["contract"],
        evidence_kind=EvidenceKind.SYNTHETIC if problems else claimed,
        recorded_evidence_kind=claimed,
        provenance_verified=not problems,
        provenance_problems=problems,
        payload_sha256=line["payload_sha256"],
        reproducibility=line["reproducibility"],
        flags=line["flags"],
        created_utc=line["created_utc"],
    )


router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("", response_model=EvidenceResponse)
def evidence() -> EvidenceResponse:
    """Index of experiment records in the RecordStore registry, newest first (may be empty).

    Each record passes the provenance gate: unverifiable or fixture records are served as SYNTHETIC.
    """
    cfg = load_config()
    store = RecordStore(cfg.experiments_dir)
    recs = sorted(
        (gated_summary(store, line) for line in store.iter_registry()),
        key=lambda r: r.created_utc,
        reverse=True,
    )
    return EvidenceResponse(
        status="OK",
        evidence_kind=None,
        provenance=provenance("qmint.core.records.RecordStore", notes="read-only registry index, newest first; provenance-gated"),
        data=EvidenceData(experiments_dir=str(cfg.experiments_dir.relative_to(cfg.root)), records=recs),
    )


@router.get("/labels", response_model=EvidenceLabelsResponse)
def labels() -> EvidenceLabelsResponse:
    """Display labels for every EvidenceKind, CertificateStatus and API status."""
    return EvidenceLabelsResponse(
        status="OK", evidence_kind=None, provenance=provenance("qmint.api.evidence_labels"), data=evidence_labels()
    )
