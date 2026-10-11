"""GET /research/sources -- reference list parsed from QMINT_MASTER_RESEARCH_PLAN.md section 16.

Lane A (research / prior-art matrix) is not merged, so every entry is labelled
"from plan, unverified": the plan itself says its links are not independently verified.
"""

from __future__ import annotations

import re
from functools import lru_cache

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from qmint.core.config import REPO_ROOT

from ..common import lane_merged, provenance
from ..schemas import Envelope

PLAN = REPO_ROOT / "QMINT_MASTER_RESEARCH_PLAN.md"
SECTION = "## 16."
VERIFICATION = "from plan, unverified"


class ResearchSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    citation: str
    title: str | None
    year: str | None
    urls: list[str]
    kind: str
    verification: str


class ResearchData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sources: list[ResearchSource]
    snapshot_note: str | None


class ResearchResponse(Envelope):
    data: ResearchData


_URL = re.compile(r"https?://[^\s;)]+")
_TITLE = re.compile(r"\*([^*]+)\*")
_YEAR = re.compile(r"\((\d{4}(?:/\d{4})?)\)")


def parse_section(text: str) -> tuple[list[ResearchSource], str | None]:
    lines = text.splitlines()
    try:
        start = next(i for i, ln in enumerate(lines) if ln.startswith(SECTION))
    except StopIteration:
        return [], None
    out: list[ResearchSource] = []
    note = None
    for ln in lines[start + 1:]:
        if ln.startswith("## "):
            break
        if ln.startswith("**Research snapshot"):
            note = ln.replace("**", "").strip()
        if not ln.startswith("- "):
            continue
        body = ln[2:].strip()
        urls = _URL.findall(body)
        citation = body.split(": http")[0].strip() if urls else body
        title = _TITLE.search(body)
        year = _YEAR.search(body)
        kind = "paper" if ("arxiv" in body or "nature.com" in body or "pmc." in body) else (
            "dataset" if "zenodo" in body or "doi.org" in body else "software_or_standard")
        out.append(
            ResearchSource(
                id=f"plan16-{len(out) + 1:02d}",
                citation=citation.replace("*", ""),
                title=title.group(1) if title else None,
                year=year.group(1) if year else None,
                urls=urls,
                kind=kind,
                verification=VERIFICATION,
            )
        )
    return out, note


@lru_cache(maxsize=1)
def _sources() -> tuple[tuple[ResearchSource, ...], str | None]:
    srcs, note = parse_section(PLAN.read_text(encoding="utf-8")) if PLAN.is_file() else ([], None)
    return tuple(srcs), note


router = APIRouter(prefix="/research", tags=["research"])


@router.get("/sources", response_model=ResearchResponse)
def sources() -> ResearchResponse:
    srcs, note = _sources()
    merged, detail = lane_merged("A")
    if not srcs:
        return ResearchResponse(
            status="NOT_AVAILABLE", evidence_kind=None, reason=f"no reference list found in {PLAN.name}",
            provenance=provenance("QMINT_MASTER_RESEARCH_PLAN.md"), data=ResearchData(sources=[], snapshot_note=None),
        )
    return ResearchResponse(
        status="DEMO_ADAPTER",
        evidence_kind=None,
        reason=("lane A (research) not merged" if not merged else "lane A present but not wired yet")
        + f" ({detail}); list parsed from master plan section 16, unverified",
        provenance=provenance("QMINT_MASTER_RESEARCH_PLAN.md section 16"),
        data=ResearchData(sources=list(srcs), snapshot_note=note),
    )
