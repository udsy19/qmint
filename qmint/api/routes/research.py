"""GET /research/sources and /research/sources/{entry_id}: the lane A research library.

Built only from merged lane A / D / E files, never from memory:

* ``research/PRIOR_ART_MATRIX.csv``          -> papers (kind ``paper``)
* ``research/THEOREM_REGISTRY_SEED.yaml``    -> transcribed theorems (``theorem``)
* ``proofs/OBLIGATIONS.yaml``                -> lane D proof obligations (``obligation``)
* ``research/CORRECTIONS.md``                -> published corrections + open discrepancies (``correction``)
* ``research/NOVELTY_HYPOTHESES.md``         -> hypotheses H1-H6, conflicts C1-C7, disallowed statements (``novelty``)
* ``research/DATASOURCE_REGISTER.yaml`` + ``datasets/manifests/*.yaml`` -> datasets (``dataset``)

Every entry keeps the verification status written in its own file (e.g. ``VERIFIED_FROM_SOURCE``,
``FULL_TEXT_READ``, ``PUBLISHED_REPRODUCED``); the API does not upgrade or merge them. Paper titles
are not in the matrix; where the master plan section 16 link index names the same arXiv/DOI the
title is attached with ``title_source`` saying so.
"""

from __future__ import annotations

import csv
import hashlib
import re
from functools import lru_cache
from typing import Any, Literal

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from qmint.core.config import REPO_ROOT

from ..common import provenance
from ..schemas import ERROR_RESPONSES, Envelope

MATRIX = "research/PRIOR_ART_MATRIX.csv"
THEOREMS = "research/THEOREM_REGISTRY_SEED.yaml"
OBLIGATIONS = "proofs/OBLIGATIONS.yaml"
CORRECTIONS = "research/CORRECTIONS.md"
NOVELTY = "research/NOVELTY_HYPOTHESES.md"
DATASOURCES = "research/DATASOURCE_REGISTER.yaml"
MANIFEST_DIR = "datasets/manifests"
PLAN = "QMINT_MASTER_RESEARCH_PLAN.md"
SOURCE_FILES = (MATRIX, THEOREMS, OBLIGATIONS, CORRECTIONS, NOVELTY, DATASOURCES)

EntryKind = Literal["paper", "theorem", "obligation", "correction", "novelty", "dataset"]
FieldKind = Literal["text", "latex", "list", "code"]

# Definitions are quoted / condensed from the header comments of the file that uses each value.
GLOSSARY: dict[str, tuple[str, str]] = {
    "FULL_TEXT_READ": (MATRIX, "Lane A read the full text of the primary source."),
    "ABSTRACT_READ": (MATRIX, "Only the abstract (and possibly skimmed PDF) was read; theorem details are not verified."),
    "METADATA_ONLY": (MATRIX, "Only bibliographic metadata was checked; content is not verified."),
    "VERIFIED_FROM_SOURCE": (THEOREMS, "Field read in the primary source at the anchor given."),
    "NOT_VERIFIED": (THEOREMS, "Field not checked against the primary source; see the reason."),
    "RECOMPUTED_BY_LANE_A": (THEOREMS, "Lane A recomputed a published number from the transcribed formula "
                                       "(a consistency check, not a proof)."),
    "PUBLISHED_REPRODUCED": (OBLIGATIONS, "Lane D reproduced the published bound in code with an independent check."),
    "NUMERICALLY_SUPPORTED": (OBLIGATIONS, "Numerically reproduced, but a hypothesis is open; never certified."),
    "CERTIFIED_NUMERIC": (OBLIGATIONS, "Numerical value with exactly verified residual accounting."),
    "CONJECTURE": (OBLIGATIONS, "Stated, not proven."),
    "UNSUPPORTED": (OBLIGATIONS, "No theorem or evidence supports this obligation yet."),
    "PUBLISHED_CORRECTION": (CORRECTIONS, "Correction issued by the authors or publisher."),
    "VERSION_CHANGE": (CORRECTIONS, "Dataset/code version differences recorded by lane A."),
    "OPEN_DISCREPANCY": (CORRECTIONS, "Inconsistency observed by lane A; not an erratum, to be resolved by the named lanes."),
    "RESOLVED": (CORRECTIONS, "Discrepancy checked and found consistent."),
    "HYPOTHESIS": (NOVELTY, "Possible contribution; must survive the listed conflicts and outside review."),
    "CONFLICT": (NOVELTY, "Prior art that blocks a novelty claim until resolved."),
    "DISALLOWED": (NOVELTY, "Statements that must never appear in code, docs, UI or paper."),
    "VERIFIED_LISTING": (DATASOURCES, "Record metadata and archive listing checked via the public API."),
    "VERIFIED_DOWNLOAD": (DATASOURCES, "File downloaded and checksum verified."),
    "PARTIALLY_VERIFIED": (DATASOURCES, "Some fields verified; see caveats."),
}


class EntryField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    label: str
    kind: FieldKind
    text: str | None = None
    items: list[str] = []


class ResearchEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    kind: EntryKind
    title: str
    title_source: str | None = None
    subtitle: str | None = None
    year: str | None = None
    games: list[str]
    status: str
    verification: str
    summary: str
    anchor: str | None = None
    urls: list[str]
    dois: list[str]
    source_file: str
    related: list[str]


class GlossaryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    source_file: str
    definition: str


class SourceFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    sha256: str | None
    entries: int


class ResearchData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sources: list[ResearchEntry]
    files: list[SourceFile]
    glossary: list[GlossaryItem]
    snapshot_date: str | None


class ResearchResponse(Envelope):
    data: ResearchData


class ResearchEntryDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entry: ResearchEntry
    fields: list[EntryField]
    related: list[ResearchEntry]


class ResearchEntryResponse(Envelope):
    data: ResearchEntryDetail


# ---------------------------------------------------------------- helpers

_URL = re.compile(r"https?://[^\s;,)\"'>]+")
_DOI = re.compile(r"\b10\.\d{4,9}/[^\s;,)\"']+")
_ARXIV = re.compile(r"\b(\d{4}\.\d{4,5})\b")
_YEAR = re.compile(r"\b(19|20)\d{2}\b")
_GAME = re.compile(r"\b(W1_CV|W1|W2|S1|S2|D1|A1|C1)\b")
_PAPER_ID = re.compile(r"\bP\d{2}\b")


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def _urls(text: str) -> list[str]:
    return list(dict.fromkeys(u.rstrip(".") for u in _URL.findall(text)))


def _dois(text: str) -> list[str]:
    return list(dict.fromkeys(d.rstrip(".") for d in _DOI.findall(text)))


def _games(text: str) -> list[str]:
    return sorted(set(_GAME.findall(text)))


def _label(key: str) -> str:
    s = key.replace("_", " ").strip()
    return s[:1].upper() + s[1:]


def _plain(s: str) -> str:
    return re.sub(r"\*\*|`", "", s).strip()


def _field(key: str, value: Any) -> EntryField | None:
    if value is None or value == "" or value == [] or value == {}:
        return None
    if isinstance(value, list) and all(not isinstance(v, (dict, list)) for v in value):
        return EntryField(key=key, label=_label(key), kind="list", items=[str(v) for v in value])
    if isinstance(value, (dict, list)):
        dumped = yaml.safe_dump(value, sort_keys=False, allow_unicode=True, width=100).strip()
        return EntryField(key=key, label=_label(key), kind="code", text=dumped)
    kind: FieldKind = "latex" if key.endswith("_latex") else "text"
    return EntryField(key=key, label=_label(key), kind=kind, text=str(value).strip())


def _fields(record: dict[str, Any], skip: frozenset[str] = frozenset()) -> list[EntryField]:
    out = []
    for k, v in record.items():
        if k in skip:
            continue
        f = _field(k, v)
        if f is not None:
            out.append(f)
    return out


_ABBREV = ("Eq", "Eqs", "Fig", "Figs", "al", "Sec", "p", "pp", "Thm", "vs", "e.g", "i.e", "No", "Ref", "cf", "approx")


def _first_sentence(s: str, limit: int = 260) -> str:
    """First sentence, not fooled by 'Eq.', 'et al.', 'Fig.' or decimals; truncated with an ellipsis."""
    s = " ".join(_plain(s).split())
    end = len(s)
    for m in re.finditer(r"[.!?](?=\s+[A-Z(\[]|$)", s):
        word = re.search(r"([\w.]+)$", s[: m.start()])
        if m.group(0) == "." and word and (word.group(1) in _ABBREV or len(word.group(1)) == 1):
            continue
        end = m.end()
        break
    out = s[:end]
    if len(out) < 12:  # e.g. "Theorem 1." -> keep the statement itself
        out = s
    return out if len(out) <= limit else out[: limit - 1].rstrip() + "…"


def _identifiers(text: str) -> set[str]:
    ids = set(_ARXIV.findall(text))
    ids |= {m.lower() for m in re.findall(r"s4\d{4}-\d{3}-\d{5}-\w", text)}
    ids |= set(re.findall(r"PMC\d+", text))
    return ids


@lru_cache(maxsize=1)
def _plan_titles() -> dict[str, str]:
    """identifier (arXiv id / Nature slug / PMC id) -> title, from master plan section 16."""
    path = REPO_ROOT / PLAN
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    in16 = False
    for ln in path.read_text(encoding="utf-8").splitlines():
        if ln.startswith("## "):
            in16 = ln.startswith("## 16.")
            continue
        m = re.search(r"\*([^*]+)\*", ln)
        if in16 and ln.startswith("- ") and m:
            for ident in _identifiers(ln):
                out.setdefault(ident, m.group(1))
    return out


# ---------------------------------------------------------------- per-file loaders


def _author_line(authors: list[str]) -> str:
    """'Molina, Vidick & Watrous' style short form; parentheticals and 'et al.' respected."""
    names = [re.sub(r"\(.*?\)", "", a).strip() for a in authors]
    etal = any("et al" in n for n in names)
    names = [re.sub(r"\s*et al\.?", "", n).strip() for n in names if n]
    surnames = [n.split()[-1] for n in names if n]
    if not surnames:
        return ""
    if etal or len(surnames) > 3:
        return f"{surnames[0]} et al."
    return surnames[0] if len(surnames) == 1 else ", ".join(surnames[:-1]) + f" & {surnames[-1]}"


@lru_cache(maxsize=1)
def _paper_short() -> dict[str, str]:
    """paper id -> 'Molina, Vidick & Watrous 2012' (used to title theorem entries)."""
    with open(REPO_ROOT / MATRIX, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out = {}
    for r in rows:
        y = _YEAR.search(r["publication_date"])
        out[r["id"]] = f"{_author_line(r['authors'].split(';'))} {y.group(0) if y else ''}".strip()
    return out


def _papers() -> list[tuple[ResearchEntry, list[EntryField]]]:
    with open(REPO_ROOT / MATRIX, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    titles = _plan_titles()
    out = []
    for r in rows:
        title = next((titles[i] for i in _identifiers(r["canonical_link"]) if i in titles), None)
        authors = [a.strip() for a in r["authors"].split(";") if a.strip()]
        author_line = _author_line(authors) or r["id"]
        year = _YEAR.search(r["publication_date"])
        access = r["access_status"].split()[0].strip("(;,") if r["access_status"].strip() else "NOT_VERIFIED"
        entry = ResearchEntry(
            id=r["id"],
            kind="paper",
            title=title or f"{author_line} ({year.group(0) if year else 'n.d.'})",
            title_source=f"{PLAN} section 16" if title else None,
            subtitle=f"{'; '.join(authors)} · {r['publication_date']}",
            year=year.group(0) if year else None,
            games=_games(r["qmint_game"]),
            status=access,
            verification=r["access_status"],
            summary=_first_sentence(r["precise_theorem"]),
            anchor=None,
            urls=_urls(r["canonical_link"]),
            dois=_dois(r["canonical_link"] + " " + r["version"]),
            source_file=MATRIX,
            related=[],
        )
        out.append((entry, _fields({k: v for k, v in r.items() if k != "id"})))
    return out


@lru_cache(maxsize=1)
def theorem_seed() -> dict[str, Any]:
    return yaml.safe_load(_read(THEOREMS))


def _theorems() -> list[tuple[ResearchEntry, list[EntryField]]]:
    seed = theorem_seed()
    sources = seed.get("sources", {})
    out = []
    for t in seed["theorems"]:
        src = sources.get(t.get("source_paper_id"), {})
        statement = t.get("statement_verbatim") or t.get("statement_summary") or ""
        urls = [u for u in (t.get("source_url"), src.get("pdf_url"), src.get("si_url")) if u]
        verification = t.get("verification") or {}
        nv = [k for k, v in verification.items() if v == "NOT_VERIFIED"]
        entry = ResearchEntry(
            id=t["theorem_id"],
            kind="theorem",
            title=f"{_paper_short().get(t.get('source_paper_id'), t.get('source_paper_id'))} · "
            f"{re.split(r'[,;(]', str(t.get('anchor') or t['theorem_id']))[0].strip()}",
            subtitle=f"{t.get('source_paper_id')} · {src.get('version', '')}".strip(" ·"),
            year=None,
            games=[str(t["game"])] if t.get("game") else [],
            status=t["status"],
            verification=f"{t['status']}" + (f"; NOT_VERIFIED fields: {', '.join(nv)}" if nv else ""),
            summary=_first_sentence(statement),
            anchor=t.get("anchor"),
            urls=urls,
            dois=_dois(" ".join(urls)),
            source_file=THEOREMS,
            related=[x for x in (t.get("source_paper_id"), t.get("proof_obligation")) if x],
        )
        out.append((entry, _fields(t, frozenset({"theorem_id"}))))
    return out


@lru_cache(maxsize=1)
def obligations() -> dict[str, Any]:
    return yaml.safe_load(_read(OBLIGATIONS))


def _obligation_title(text: str) -> str:
    head = text.split(":")[0]
    return _first_sentence(head if len(head) >= 20 else text, 120)


def _obligations() -> list[tuple[ResearchEntry, list[EntryField]]]:
    doc = obligations()
    sources = doc.get("sources", {})
    out = []
    for c in doc["claims"]:
        src = sources.get(c.get("source"), {})
        anchors = "; ".join(b.get("anchor", "") for b in c.get("bounds", []) if b.get("anchor")) or None
        entry = ResearchEntry(
            id=c["claim_id"],
            kind="obligation",
            title=_obligation_title(c["source_and_theorem"]),
            subtitle=f"{c['protocol']} · {src.get('citation', c.get('source'))}",
            games=[] if c["game"] == "any" else [c["game"]],
            status=c["status"],
            verification=c["status"],
            summary=_first_sentence(c["mathematical_bound"]),
            anchor=anchors,
            urls=[src["url"]] if src.get("url") else [],
            dois=_dois(src.get("citation", "")),
            source_file=OBLIGATIONS,
            related=[],
        )
        out.append((entry, _fields(c, frozenset({"claim_id"}))))
    return out


def _md_sections(text: str, level: str) -> list[tuple[str, str]]:
    parts = re.split(rf"^{level} (.+)$", text, flags=re.M)
    return [(parts[i].strip(), parts[i + 1].strip()) for i in range(1, len(parts) - 1, 2)]


def _corrections() -> list[tuple[ResearchEntry, list[EntryField]]]:
    text = _read(CORRECTIONS)
    sections = dict(_md_sections(text, "##"))
    out = []
    pub = next((v for k, v in sections.items() if k.startswith("1.")), "")
    for head, body in _md_sections(pub, "###"):
        if not head.startswith("P"):
            continue  # "Other papers" is folded into the per-paper status in the matrix
        pid = head.split()[0]
        bullets = [_plain(b) for b in re.findall(r"^\* (.+)$", body, flags=re.M)]
        entry = ResearchEntry(
            id=f"CORR-{pid}", kind="correction", title=f"Published correction: {_plain(head.split(',', 1)[0])}",
            subtitle=_plain(head), games=[], status="PUBLISHED_CORRECTION",
            verification="read in full by lane A (see file)", summary=_first_sentence(bullets[0] if bullets else body),
            urls=_urls(body), dois=_dois(body), source_file=f"{CORRECTIONS}#1-published-corrections", related=[pid],
        )
        out.append((entry, [EntryField(key="body", label="Correction", kind="list", items=bullets)]))
    ver = next((v for k, v in sections.items() if k.startswith("2.")), "")
    if ver:
        bullets = [_plain(b) for b in re.findall(r"^\* (.+)$", ver, flags=re.M)]
        entry = ResearchEntry(
            id="CORR-VERSIONS", kind="correction", title="Dataset and code version changes (Zenodo)",
            subtitle="Zenodo concept records 7979318 and 7985330", games=["D1"], status="VERSION_CHANGE",
            verification="checked via Zenodo API by lane A", summary=_first_sentence(bullets[0] if bullets else ver),
            urls=_urls(ver), dois=_dois(ver), source_file=f"{CORRECTIONS}#2-datasetcode-version-changes", related=["P04"],
        )
        out.append((entry, [EntryField(key="body", label="Changes", kind="list", items=bullets)]))
    disc = next((v for k, v in sections.items() if k.startswith("3.")), "")
    for ln in disc.splitlines():
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) != 5 or not re.fullmatch(r"D-\d+", cells[0]):
            continue
        did, src, obs, check, who = cells
        resolved = who.strip() in ("—", "-", "")
        entry = ResearchEntry(
            id=f"CORR-{did}", kind="correction", title=_first_sentence(_plain(obs), 140), subtitle=_plain(src),
            games=_games(obs), status="RESOLVED" if resolved else "OPEN_DISCREPANCY",
            verification=f"lane A check: {_plain(check)}", summary=_first_sentence(_plain(obs)),
            urls=[], dois=[], source_file=f"{CORRECTIONS}#3-discrepancies-observed-by-lane-a-not-errata-to-be-resolved",
            related=sorted(set(_PAPER_ID.findall(src))),
        )
        fields = [
            EntryField(key="source", label="Source", kind="text", text=_plain(src)),
            EntryField(key="observation", label="Observation", kind="text", text=_plain(obs)),
            EntryField(key="lane_a_check", label="Lane A check", kind="text", text=_plain(check)),
            EntryField(key="resolves", label="Who resolves", kind="text", text=_plain(who)),
        ]
        out.append((entry, fields))
    return out


def _novelty() -> list[tuple[ResearchEntry, list[EntryField]]]:
    text = _read(NOVELTY)
    out = []
    for m in re.finditer(r"^(?:\* |\d+\. )\*\*([HC]\d) – (.+?)\.?\*\*\s*(.+)$", text, flags=re.M):
        code, title, body = m.group(1), _plain(m.group(2)).replace("*", ""), _plain(m.group(3))
        hyp = code.startswith("H")
        entry = ResearchEntry(
            id=f"NOV-{code}", kind="novelty", title=f"{code} · {title}",
            subtitle="Novelty hypothesis" if hyp else "Novelty conflict (prior art)", games=_games(body),
            status="HYPOTHESIS" if hyp else "CONFLICT",
            verification="unverified hypothesis; requires outside review" if hyp else "prior art identified by lane A",
            summary=_first_sentence(body), urls=_urls(body), dois=_dois(body),
            source_file=f"{NOVELTY}#{'2' if hyp else '3'}", related=sorted(set(_PAPER_ID.findall(body))),
        )
        out.append((entry, [EntryField(key="text", label="Statement", kind="text", text=body)]))
    sec = next((v for k, v in _md_sections(text, "##") if k.startswith("4.")), "")
    items = [_plain(i) for i in re.findall(r"^\d+\. (.+)$", sec, flags=re.M)]
    if items:
        entry = ResearchEntry(
            id="NOV-DISALLOWED", kind="novelty", title="Disallowed false statements",
            subtitle=f"{len(items)} statements that must never appear in code, docs, UI or paper", games=[],
            status="DISALLOWED", verification="binding content rule", summary=_first_sentence(items[0]),
            urls=[], dois=[], source_file=f"{NOVELTY}#4", related=[],
        )
        out.append((entry, [EntryField(key="statements", label="Statements", kind="list", items=items)]))
    return out


def _manifest_for(doi: str | None) -> tuple[str, dict[str, Any]] | None:
    if not doi:
        return None
    recid = doi.rsplit(".", 1)[-1]
    for path in sorted((REPO_ROOT / MANIFEST_DIR).glob("*.yaml")):
        m = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if any(str(v.get("record_id")) == recid for v in m.get("versions", [])):
            return str(path.relative_to(REPO_ROOT)), m
    return None


def _dataset_summary(d: dict[str, Any]) -> str:
    for key in ("content_declared", "description_delta", "reuse_policy", "caveats", "source"):
        v = d.get(key)
        if isinstance(v, list) and v:
            v = v[0]
        if isinstance(v, str) and v.strip():
            return v
    return ""


def _datasets() -> list[tuple[ResearchEntry, list[EntryField]]]:
    reg = yaml.safe_load(_read(DATASOURCES))
    out = []
    for d in reg.get("datasets", []):
        doi = d.get("doi")
        manifest = _manifest_for(doi)
        urls = [u for u in (d.get("url"), d.get("api_url"), d.get("related_repo")) if u]
        fields = _fields(d, frozenset({"id", "title"}))
        if manifest:
            mpath, m = manifest
            fields.append(EntryField(key="manifest", label="QMint manifest", kind="text", text=mpath))
            for v in m.get("versions", []):
                if str(v.get("record_id")) == doi.rsplit(".", 1)[-1]:
                    f = _field("manifest_files", v.get("files"))
                    if f:
                        fields.append(f.model_copy(update={"label": "Manifest files (upstream md5 + local sha256)"}))
        entry = ResearchEntry(
            id=d["id"], kind="dataset", title=d["title"], subtitle=doi or d.get("source"),
            year=(d.get("publication_date") or "")[:4] or None, games=_games(str(d.get("cited_by_paper", ""))),
            status=d.get("access_status", "NOT_VERIFIED"), verification=d.get("access_status", "NOT_VERIFIED"),
            summary=_first_sentence(_dataset_summary(d)),
            anchor=d.get("evidence_kind_when_used"), urls=urls, dois=[doi] if doi else [],
            source_file=DATASOURCES,
            related=sorted(set(_PAPER_ID.findall(str(d.get("cited_by_paper", "")) + str(d.get("source", ""))))),
        )
        out.append((entry, fields))
    return out


LOADERS = (_papers, _theorems, _obligations, _corrections, _novelty, _datasets)


@lru_cache(maxsize=1)
def library() -> tuple[dict[str, tuple[ResearchEntry, tuple[EntryField, ...]]], tuple[SourceFile, ...]]:
    entries: dict[str, tuple[ResearchEntry, tuple[EntryField, ...]]] = {}
    per_file: dict[str, int] = {}
    for loader in LOADERS:
        for e, fields in loader():
            assert e.id not in entries, f"duplicate research entry id {e.id}"
            entries[e.id] = (e, tuple(fields))
            base = e.source_file.split("#")[0]
            per_file[base] = per_file.get(base, 0) + 1
    # back-links: papers list the theorems/obligations/corrections that cite them
    for eid, (e, _f) in list(entries.items()):
        for rid in e.related:
            if rid in entries and eid not in entries[rid][0].related:
                r, rf = entries[rid]
                entries[rid] = (r.model_copy(update={"related": [*r.related, eid]}), rf)
    files = []
    for rel in sorted(set(SOURCE_FILES) | set(per_file)):
        p = REPO_ROOT / rel
        sha = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
        files.append(SourceFile(path=rel, sha256=sha, entries=per_file.get(rel, 0)))
    return entries, tuple(files)


router = APIRouter(prefix="/research", tags=["research"])


@router.get("/sources", response_model=ResearchResponse, responses=ERROR_RESPONSES)
def sources() -> ResearchResponse:
    """Research library index: papers, theorems, obligations, datasets, corrections, novelty audit."""
    entries, files = library()
    return ResearchResponse(
        status="OK",
        evidence_kind=None,
        provenance=provenance(", ".join(SOURCE_FILES), notes="lane A/D/E research files; statuses as written in each file"),
        data=ResearchData(
            sources=[e for e, _ in entries.values()],
            files=list(files),
            glossary=[GlossaryItem(status=k, source_file=f, definition=d) for k, (f, d) in GLOSSARY.items()],
            snapshot_date=str(theorem_seed().get("snapshot_date")) or None,
        ),
    )


@router.get(
    "/sources/{entry_id}",
    response_model=ResearchEntryResponse,
    responses={**ERROR_RESPONSES, 404: ERROR_RESPONSES[422] | {"description": "Unknown entry id"}},
)
def source_entry(entry_id: str) -> ResearchEntryResponse:
    """One research entry with every field of its source record and related entries (404 if unknown)."""
    entries, _ = library()
    if entry_id not in entries:
        raise HTTPException(status_code=404, detail=f"unknown research entry {entry_id!r}")
    e, fields = entries[entry_id]
    return ResearchEntryResponse(
        status="OK",
        evidence_kind=None,
        provenance=provenance(e.source_file),
        data=ResearchEntryDetail(entry=e, fields=list(fields), related=[entries[r][0] for r in e.related if r in entries]),
    )

