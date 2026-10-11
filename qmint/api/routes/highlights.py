"""GET /evidence/highlights: the headline numbers, read live from the committed artefacts they come from.

Each highlight names its source file (repo-relative path + sha256 of the bytes read) and the field
it was read from, and each number is a :class:`Quantity` with its own evidence kind. Nothing here is
recomputed or typed in: if an artefact is missing or lacks the field, that highlight is listed under
``unavailable`` with the reason instead of being invented.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from qmint.core.config import REPO_ROOT
from qmint.core.contracts import EvidenceKind, Unit
from qmint.core.serialization import file_sha256

from ..common import provenance
from ..schemas import ApiStatus, ConfidenceInterval, Envelope, Quantity
from .benchmarks import E_DIR, H_DIR, SCHIANSKY_URL
from .lab import C_EVIDENCE

D_REPRODUCTION = "proofs/certificates/reproduction_v1.json"
MATCHED_CASE = "paper_jinan_2.766km_fibre"
MATCHED_PROC = "jiang_dTproc_1507ns"
MATCHED_PROTOCOLS = {
    "S1_s_money": "S-money S1 (lane G event model)",
    "H3_late_commit_ot_private": "H3 late-commit escrow with OT (classical, computational)",
    "H1": "H1 online ledger at L0 (classical)",
}


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HighlightSource(_M):
    path: str
    sha256: str
    field: str


class Highlight(_M):
    id: str
    title: str
    evidence_kind: EvidenceKind
    quantities: list[Quantity]
    sources: list[HighlightSource]
    note: str | None = None


class Unavailable(_M):
    id: str
    reason: str


class HighlightsData(_M):
    highlights: list[Highlight]
    unavailable: list[Unavailable]


class HighlightsResponse(Envelope):
    data: HighlightsData


def _src(path: Path, field: str) -> HighlightSource:
    return HighlightSource(path=path.relative_to(REPO_ROOT).as_posix(), sha256=file_sha256(path), field=field)


def _sdp_bracket() -> Highlight:
    c_path, d_path = REPO_ROOT / C_EVIDENCE, REPO_ROOT / D_REPRODUCTION
    sdp = json.loads(c_path.read_text(encoding="utf-8"))["w1_sdp"]
    d_rows = json.loads(d_path.read_text(encoding="utf-8"))["rows"]
    qs, n_texts = [], []
    for n in (1, 2):
        cert = sdp[f"n{n}_SCS"]["certified"]
        lower = Fraction(cert["exact_lower_bound_from_mvw_channel"])
        upper = cert["upper_bound_float_up"]
        d_row = next(r for r in d_rows if r["quantity"].startswith(f"W1 n={n} SDP"))
        if not (d_row["agrees"] and d_row["paper_value"] == upper and Fraction(d_row["qmint_value"]) == lower):
            raise ValueError(f"lane D reproduction row for W1 n={n} does not confirm lane C's bracket")
        src = f"{C_EVIDENCE} w1_sdp.n{n}_SCS.certified"
        qs += [
            Quantity(id=f"w1_opt_n{n}_lower", label=f"W1 optimal counterfeit, n={n}: lower bound", value=float(lower),
                     unit=Unit.PROBABILITY, evidence_kind=EvidenceKind.CERTIFIED_NUMERIC, method="closed_form",
                     source=src, formula=f"{lower} (exact value of the MVW 2012 optimal channel)"),
            Quantity(id=f"w1_opt_n{n}_upper", label=f"W1 optimal counterfeit, n={n}: certified upper bound",
                     value=upper, unit=Unit.PROBABILITY, evidence_kind=EvidenceKind.CERTIFIED_NUMERIC,
                     method="numerical_sdp", source=src, formula=cert["upper_bound_exact"],
                     note=f"exact rational LDL^T check of the shifted SCS dual; lane D's exact dual gives "
                          f"{d_row['qmint_value']} ({D_REPRODUCTION}, agrees=true)"),
        ]
        n_texts.append(f"{lower} <= OPT_{n} <= {upper}")
    return Highlight(
        id="w1_sdp_bracket", title="W1 Choi-matrix SDP, certified bracket", evidence_kind=EvidenceKind.CERTIFIED_NUMERIC,
        quantities=qs, sources=[_src(c_path, "w1_sdp.{n1,n2}_SCS.certified"), _src(d_path, "rows[W1 n=1,2 SDP]")],
        note="; ".join(n_texts) + ". Ideal game W1 only (one note, two outputs, exact verifier, no oracle).",
    )


def _qber() -> Highlight:
    path = E_DIR / "summary.json"
    summary = json.loads(path.read_text(encoding="utf-8"))
    qs = []
    for b, label, key in (("Z", "H/V (Z basis)", "qber_Z_percent"), ("X", "D/A (X basis)", "qber_X_percent")):
        s = summary["basis_summaries"][b]
        v, se = s["qber_state_avg"], s["qber_state_avg_se"]
        pub = summary["published_aggregates"][key]
        qs += [
            Quantity(id=f"qber_{b}_state_avg", label=f"QBER {label}, reproduced from raw data", value=v,
                     unit=Unit.FRACTION, evidence_kind=EvidenceKind.PHOTON_EXPERIMENT, method="measured_dataset",
                     interval=ConfidenceInterval(lo=v - se, hi=v + se, confidence=None, method="plus_minus_1_se"),
                     source=f"{path.relative_to(REPO_ROOT).as_posix()} basis_summaries.{b}.qber_state_avg",
                     note=f"{s['n_pairs']} pairs over {s['n_runs']} runs; state-averaged (the paper's estimator)"),
            Quantity(id=f"qber_{b}_published", label=f"QBER {label}, published", value=pub["value"] / 100,
                     unit=Unit.FRACTION, evidence_kind=EvidenceKind.PUBLISHED_AGGREGATE, method="published_value",
                     interval=ConfidenceInterval(lo=(pub["value"] - pub["pm"]) / 100, hi=(pub["value"] + pub["pm"]) / 100,
                                                 confidence=None, method="published_plus_minus"),
                     source=f"Schiansky et al. 2023, {SCHIANSKY_URL} ({pub['anchor']})"),
        ]
    ds = summary["dataset"]
    return Highlight(
        id="schiansky2023_qber", title="Schiansky et al. 2023 QBER, reproduced from Zenodo",
        evidence_kind=EvidenceKind.PHOTON_EXPERIMENT, quantities=qs,
        sources=[_src(path, "basis_summaries.{Z,X}, published_aggregates")],
        note=f"Zenodo record {ds['zenodo_record']}, {ds['file']} sha256 {ds['sha256']}, {ds['license']}",
    )


def _matched_topology() -> Highlight:
    res_path, mat_path = H_DIR / "matched_topology_results.csv", H_DIR / "comparability_matrix.csv"
    with open(res_path, encoding="utf-8", newline="") as f:
        rows = {r["protocol"]: r for r in csv.DictReader(f)
                if r["case_id"] == MATCHED_CASE and r["proc_model"] == MATCHED_PROC and r["b"] == "1"}
    qs = []
    for proto, label in MATCHED_PROTOCOLS.items():
        r = rows[proto]
        if r["evidence_kind"] != EvidenceKind.MODELLED_LATENCY.value:
            raise ValueError(f"{proto} row is {r['evidence_kind']}, expected MODELLED_LATENCY")
        qs.append(Quantity(
            id=f"choice_to_accept_{proto}", label=f"Choice to local accept, {label}",
            value=float(r["choice_to_local_accept_ns"]), unit=Unit.NANOSECOND,
            evidence_kind=EvidenceKind.MODELLED_LATENCY, method="event_simulation",
            source=f"{res_path.relative_to(REPO_ROOT).as_posix()} case={MATCHED_CASE} proc={MATCHED_PROC} b=1",
            note=f"comparability vs S1: {r['comparability_status']}; link input {r['input_latency_evidence']}",
        ))
    with open(mat_path, encoding="utf-8", newline="") as f:
        counts = Counter(r["comparability_status"] for r in csv.DictReader(f))
    for status in ("COMPARABLE", "QUALIFIED", "INCOMPARABLE"):
        qs.append(Quantity(
            id=f"comparability_{status.lower()}", label=f"Classical constructions {status} with S1",
            value=float(counts.get(status, 0)), unit=Unit.COUNT, evidence_kind=EvidenceKind.MODELLED_LATENCY,
            method="closed_form", source=f"{mat_path.relative_to(REPO_ROOT).as_posix()} comparability_status",
            note="count of matrix rows; a classification of the modelled comparison, not a measurement",
        ))
    return Highlight(
        id="matched_topology_jinan", title="S-money vs classical on one engine (Jinan 2.766 km)",
        evidence_kind=EvidenceKind.MODELLED_LATENCY, quantities=qs,
        sources=[_src(res_path, "choice_to_local_accept_ns"), _src(mat_path, "comparability_status")],
        note="Modelled lower bounds on a published topology, not measurements. S1 and H3 late-commit share the "
             "Stage-II relay, so equal latency; the difference is the adversary model (reports/classical_baseline_notes"
             "/README.md).",
    )


BUILDERS: dict[str, Callable[[], Highlight]] = {
    "w1_sdp_bracket": _sdp_bracket,
    "schiansky2023_qber": _qber,
    "matched_topology_jinan": _matched_topology,
}

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("/highlights", response_model=HighlightsResponse)
def highlights() -> HighlightsResponse:
    """Headline numbers (SDP bracket, reproduced QBER, matched-topology latency) with source files and evidence."""
    out: list[Highlight] = []
    missing: list[Unavailable] = []
    for hid, build in BUILDERS.items():
        try:
            out.append(build())
        except (OSError, KeyError, StopIteration, ValueError, TypeError) as e:
            missing.append(Unavailable(id=hid, reason=f"{type(e).__name__}: {e}"))
    status: ApiStatus = "OK" if out else "NOT_AVAILABLE"
    return HighlightsResponse(
        status=status,
        evidence_kind=None,
        reason=None if out else "no highlight artefact could be read",
        provenance=provenance("committed lane artefacts (C, D, E, H/GH)",
                              notes="read live from the files listed per highlight; mixed evidence kinds"),
        data=HighlightsData(highlights=out, unavailable=missing),
    )
