"""Paper tables 1, 4 and 5 (master plan section 9) as Markdown + CSV.

* Table 1 is generated from ``research/THEOREM_REGISTRY_SEED.yaml`` (lane A) joined with the
  validated obligation registry ``proofs/OBLIGATIONS.yaml`` (lane D).
* Tables 4 and 5 are curated ledgers, but every row is pinned to its source: each ``anchor`` must
  occur verbatim in ``source`` (whitespace-normalised), and every number in ``finding`` must occur
  in one of the row's anchors. The build fails otherwise, so a number cannot be hand-typed.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from qmint.core.contracts import GameId
from qmint.proofs.registry import load_registry

THEOREM_SEED = "research/THEOREM_REGISTRY_SEED.yaml"
OBLIGATIONS = "proofs/OBLIGATIONS.yaml"
_NUM = re.compile(r"\d+(?:\.\d+)?(?:e-?\d+)?")


@dataclass(frozen=True)
class LedgerRow:
    row_id: str
    category: str
    finding: str
    evidence_kind: str
    source: str  # repository-relative file
    anchors: tuple[str, ...]  # verbatim excerpts of ``source``


class AnchorError(ValueError):
    """A ledger row is not backed by its cited source."""


def _norm(s: str) -> str:
    return " ".join(s.split())


def check_row(root: Path, row: LedgerRow) -> None:
    text = _norm((root / row.source).read_text(encoding="utf-8"))
    for a in row.anchors:
        if _norm(a) not in text:
            raise AnchorError(f"{row.row_id}: anchor not found in {row.source}: {a!r}")
    allowed = set(_NUM.findall(" ".join(row.anchors)))
    stray = [n for n in _NUM.findall(row.finding) if n not in allowed]
    if stray:
        raise AnchorError(f"{row.row_id}: numbers {stray} in finding are not in any anchor")


# --------------------------------------------------------------------------- Table 1
def _alias(obligation: str | None) -> str | None:
    """Lane A's seed writes ``P-W1-CV``; lane D's registry id is ``P-W1CV``. Map, and report it."""
    return None if obligation is None else {"P-W1-CV": "P-W1CV"}.get(obligation, obligation)


def table1(root: Path) -> list[dict[str, Any]]:
    seed = yaml.safe_load((root / THEOREM_SEED).read_text(encoding="utf-8"))
    reg = load_registry(root / OBLIGATIONS)
    frozen = {g.value for g in GameId}
    rows, used = [], set()
    for t in seed["theorems"]:
        cid = _alias(t.get("proof_obligation"))
        claim = next((c for c in reg.claims if c.claim_id == cid), None)
        notes = []
        if cid != t.get("proof_obligation"):
            notes.append(f"seed obligation id {t['proof_obligation']} differs from registry id {cid}")
        if t["game"] not in frozen:
            notes.append("game not in frozen GameId enum (proposal only)")
        if claim is None:
            notes.append("no registry obligation")
        else:
            used.add(claim.claim_id)
        rows.append({
            "theorem_id": t["theorem_id"], "game": t["game"], "source_url": t["source_url"],
            "anchor": t["anchor"], "bound": t.get("bound_plain", ""), "transcription_status": t["status"],
            "obligation": claim.claim_id if claim else "", "proof_status": claim.status.value if claim else "",
            "finite_n_or_asymptotic": claim.finite_n_or_asymptotic if claim else "",
            "n_assumptions": len(claim.assumptions) if claim else "", "notes": "; ".join(notes),
        })
    for c in reg.claims:
        if c.claim_id not in used:
            rows.append({
                "theorem_id": "(none in seed)", "game": c.game, "source_url": reg.sources[c.source].url if c.source in reg.sources else "",
                "anchor": c.source_and_theorem, "bound": c.mathematical_bound, "transcription_status": "",
                "obligation": c.claim_id, "proof_status": c.status.value, "finite_n_or_asymptotic": c.finite_n_or_asymptotic,
                "n_assumptions": len(c.assumptions), "notes": "registry obligation without a seed theorem",
            })
    return rows


# --------------------------------------------------------------------------- Table 4
TABLE4: tuple[LedgerRow, ...] = (
    LedgerRow("N01", "CORRECTION", "Measure-resend is not the optimal W1 attack: both copies pass with only 5/8 per qubit.",
              "MONTE_CARLO", "handoffs/B-B1.md", ("the W1 event (both copies valid) is 5/8 per qubit",)),
    LedgerRow("N02", "CORRECTION", "Lane C confirms independently: A01 does NOT reach 3/4.", "MONTE_CARLO",
              "handoffs/C-C1.md", ("A01 does NOT reach 3/4.",)),
    LedgerRow("N03", "UNSUPPORTED_CLAIM", "The Schiansky payment protocol (game D1) is never certified by QMint.", "UNCERTIFIED",
              "handoffs/D-D1.md", ("D1 is therefore never certified.",)),
    LedgerRow("N04", "OPEN_QUESTION",
              "Chernoff is applied to the weighted mishap sum (4+2√2)e + l, which is not a {0,1} variable; rescaling into [0,1] weakens p_d to 3.3e-7.",
              "UNCERTIFIED", "handoffs/D-D1.md",
              ("Schiansky applies Chernoff to the weighted mishap sum (4+2√2)e + l. That variable takes values in {0, 1, 6.83}, outside the {0,1} hypothesis of the Chernoff bound.",
               "weakens p_d to 3.3e-7")),
    LedgerRow("N05", "BROKEN_ASSUMPTION", "Kent's own experimental tuple lies outside the Theorem 1 domain (UNCERTIFIED).",
              "PUBLISHED_AGGREGATE", "handoffs/D-D1.md", ("Kent's experimental tuple falls outside the Theorem 1 domain.",)),
    LedgerRow("N06", "INCONSISTENCY",
              "Published p_d = 5.911e-45 recomputes only with N = 4.2e6 and p_m = 6.02%, not the SI Table N or the main-text p_m.",
              "PUBLISHED_AGGREGATE", "handoffs/D-D1.md",
              ("p_d = 5.911e-45 reproduces exactly, but only with N = 4.2e6 and p_m = 6.02%, not the SI Table N or the main-text p_m.",)),
    LedgerRow("N07", "INCONSISTENCY", "Schiansky SI Choi normalisation and the '2×2 dual' are inconsistent.",
              "PUBLISHED_AGGREGATE", "handoffs/A-A1.md", ('The SI Choi normalisation and the "2×2 dual" are inconsistent.',)),
    LedgerRow("N08", "QUALIFICATION",
              "S1 is not coordination-free: the Stage-II bit c must be relayed to both sites before presentation (Kent 2022 Table I steps 7–9).",
              "PUBLISHED_THEOREM", "handoffs/H-H1.md",
              ("S1 itself needs the Stage-II bit `c` relayed to both sites (Kent 2022 Table I steps 7–9).",)),
    LedgerRow("N09", "QUALIFICATION",
              "A classical escrow with ideal OT (H3) reproduces late choice, local acceptance and issuer-blind commit; the remaining difference is computational vs information-theoretic security.",
              "MODELLED_LATENCY", "handoffs/H-H1.md",
              ("H3 with OT reproduces late choice, local acceptance and issuer-blind commit.",
               "What remains different is that the classical version is computational, while S1's ideal model is information-theoretic.")),
    LedgerRow("N10", "NEGATIVE_RESULT",
              "Honest acceptance with the exact verifier collapses under small noise: readout 1%/2% alone gives 0.886 at n=8 and 0.144 at n=128.",
              "SYNTHETIC", "handoffs/F-F1.md",
              ("Honest exact-match acceptance is fragile (SYNTHETIC): readout 1%/2% alone → 0.886 at n=8, 0.144 at n=128.",)),
    LedgerRow("N11", "DATA_LIMITATION",
              "Photon runs are overdispersed (χ²/dof≈10): run-to-run heterogeneity, not temporal drift. Run-level Welch test of contiguous halves: p = 0.334 (D/A), 0.587 (H/V); per-run Clopper-Pearson intervals understate the spread, so calibration intervals are widened. (Earlier pooled-iid p = 0.0034 was invalid; corrected after red-team review.)",
              "PHOTON_EXPERIMENT", "handoffs/FDE-1.md",
              ("overdispersed / heterogeneous across runs (χ²/dof≈10)", "no evidence of monotone drift", "p = 0.334 (D/A), 0.587 (H/V)", "pooled_iid_p_value` (0.0034) and labelled invalid")),
    LedgerRow("N12", "DATA_LIMITATION", "Loss, efficiency and multiphoton probability are not observable from the Schiansky archive.",
              "PHOTON_EXPERIMENT", "handoffs/E-E1.md",
              ("Loss, efficiency and multiphoton probability can't be observed from this archive",)),
    LedgerRow("N13", "UNUSABLE_ARTIFACT",
              "Authors' code (8020667) ships an AGPL-3.0 licence against CC-BY-4.0 metadata and cannot run as published (missing find_start_alt and requirements); nothing copied.",
              "PUBLISHED_AGGREGATE", "handoffs/E-E1.md",
              ("The authors' code (8020667) ships with an AGPL-3.0 license file although its metadata says CC-BY-4.0.",
               "It also can't run as published: it is missing `find_start_alt` and its requirements file.")),
    LedgerRow("N14", "OUT_OF_MODEL",
              "Split-and-report-loss wins the toy lossy threshold verifier with success 1.0 at a 50% loss allowance; W2 has no theorem.",
              "MONTE_CARLO", "handoffs/C-C1.md",
              ("A06 split-and-report-loss on the toy W2 gives success 1.0 at a 50% loss allowance (NO_THEOREM).",)),
    LedgerRow("N15", "OUT_OF_MODEL", "A leaky verification oracle is fatal: 0.996 at n=8 with 84 queries (outside MVW's model).",
              "MONTE_CARLO", "handoffs/C-C1.md", ("A08 leaky oracle at n=8 gives 0.996 using 84 queries (OUT_OF_MODEL).",)),
    LedgerRow("N16", "UNSUPPORTED_CLAIM", "No bound exists for the noisy/threshold game W2; SDP certificates for W2 are refused.",
              "UNCERTIFIED", "handoffs/D-D1.md", ("SDP certificates for W2 are refused.", "W2 itself still has no bound.")),
    LedgerRow("N17", "SCOPE", "MVW Sec 3.5's binomial tail is a joint-success threshold game and does not cover W2.",
              "PUBLISHED_THEOREM", "handoffs/A-A1.md",
              ("MVW Sec 3.5's binomial tail is a *joint*-success threshold game and doesn't cover W2.",)),
    LedgerRow("N18", "METHOD_LIMITATION", "Transpose-omission and factor-order SDP bugs are invisible on BB84 n=1; complex ensembles are needed as controls.",
              "NUMERICAL_SDP", "handoffs/C-C1.md", ("transpose-omission and factor-order bugs are invisible on BB84 n=1",)),
    LedgerRow("N19", "UNREACHABLE", "The counterfeiting SDP at n=3 is refused by the size guard; Clarabel needs 6.5 GB and ends optimal_inaccurate.",
              "NUMERICAL_SDP", "handoffs/C-C1.md", ("n=3 refused by the size guard", "Clarabel 24 s, 6.5 GB, primal optimal_inaccurate")),
    LedgerRow("N20", "UNREACHABLE_BACKEND", "No QPU job was run; Qollab integration is BLOCKED.", "QPU", "handoffs/J-J1.md",
              ("Paid jobs run: none.", "Qollab integration is **BLOCKED**.")),
    LedgerRow("N21", "INCONSISTENCY", "Jiang et al. inter-city coordinates give about 49.55 km by haversine, not the stated 51.60 km.",
              "PUBLISHED_AGGREGATE", "handoffs/G-G1.md",
              ("The haversine distance between the paper's published coordinates is about 49.55 km, not the stated 51.60 km.",)),
    LedgerRow("N22", "QUALIFICATION", "RIPE-based S-money vs online-ledger latencies are not a matched benchmark (trust, privacy, processing differ).",
              "MEASURED_LATENCY", "handoffs/G-G1.md", ("The RIPE numbers are not a matched benchmark",)),
    LedgerRow("N23", "SECURITY_FINDING", "Frozen canonical_json emits IssuerSecret bases/bits when nested in an Any field (worked around; fix proposed).",
              "SYNTHETIC", "handoffs/L-L1.md",
              ("The frozen `canonical_json` writes out IssuerSecret bases and bits when the secret sits inside an `Any` field",)),
    LedgerRow("N24", "EVIDENCE_GAP", "Lane C did not export its rational dual matrices; lane D confirmed the bound values, not C's matrices.",
              "CERTIFIED_NUMERIC", "handoffs/D-D1.md", ("C did not export its rational Y matrices",)),
)

# --------------------------------------------------------------------------- Table 5
TABLE5: tuple[LedgerRow, ...] = (
    LedgerRow("S01", "PUBLIC_KEY", "All QMint protocols are private-key or relativistic; BB84 money cannot become public-key by publishing its bases.",
              "PUBLISHED_THEOREM", "QMINT_MASTER_RESEARCH_PLAN.md",
              ("Ordinary BB84 money cannot be made public-key by publishing its secret bases.",)),
    LedgerRow("S02", "TRANSFERABILITY", "Transferability is listed as a scope constraint; no registered game models a payee re-spending a received token, so no claim is made.",
              "UNCERTIFIED", "QMINT_MASTER_RESEARCH_PLAN.md",
              ("(public key, transferability, long-term quantum memory, optical vs ion backend)",)),
    LedgerRow("S03", "QUANTUM_MEMORY", "Memory-based quantum money with a measured secure regime is prior art read only at abstract level; QMint models no memory decoherence.",
              "UNCERTIFIED", "research/NOVELTY_HYPOTHESES.md",
              ("Quantum money with a quantum memory and a secure regime derived from measured memory efficiency/noise",)),
    LedgerRow("S04", "BACKEND", "Trapped-ion measurement noise is never equated with photon link loss; IonQ results would not make an optical banknote.",
              "SIMULATOR_NOISY", "QMINT_MASTER_RESEARCH_PLAN.md",
              ("Never equate trapped-ion measurement noise with photon link loss.",)),
    LedgerRow("S05", "GAME_SCOPE", "The simple-counterfeiting optimum is not a bound for noisy/threshold verifiers, lossy channels, oracle access, or S-money.",
              "PUBLISHED_THEOREM", "proofs/OBLIGATIONS.yaml",
              ("Not a bound for noisy/threshold verifiers (that is game W2), lossy channels, oracle access, or S-money.",)),
    LedgerRow("S06", "SITES", "The S1 bound is evaluated for two sites only (M=1); multi-point presentation is not implemented.", "PUBLISHED_THEOREM",
              "qmint/proofs/ideal_bounds.py", ("OUT_OF_MODEL:S1_is_two_site_only(M=1)",)),
    LedgerRow("S07", "PRIVACY", "Privacy has no theorem for W1, W1_CV, S1, D1, A1, C1; the evaluator returns None, never 0.",
              "UNCERTIFIED", "proofs/OBLIGATIONS.yaml",
              ("Privacy has NO theorem for W1, W1_CV, S1 (ideal; prose only), D1 (MAC hides merchant; no epsilon stated), A1, C1: the evaluator returns UNSUPPORTED with value None, never 0.",)),
    LedgerRow("S08", "CALIBRATION", "Schiansky photon calibration records are refused for S-money and Wiesner consumers (no cross-protocol transfer).",
              "PHOTON_EXPERIMENT", "handoffs/E-E1.md", ("`check_consumer` rejects them for S-money and Wiesner.",)),
    LedgerRow("S09", "SIMULATION", "Circuit simulation does not demonstrate no-cloning or physical security.", "SIMULATOR_IDEAL",
              "handoffs/F-F1.md", ("simulation does not demonstrate no-cloning.",)),
    LedgerRow("S10", "TIMING_ONLY", "The S-money network model covers timing only and says nothing about security.", "MODELLED_LATENCY",
              "handoffs/G-G1.md", ("The S-money model covers timing only; it says nothing about security.",)),
    LedgerRow("S11", "IDEAL_MODEL", "The S1 bound applies to the ideal lossless/noiseless model only.", "PUBLISHED_THEOREM",
              "reports/classical_baseline_notes/comparability_matrix.csv", ("PUBLISHED_THEOREM Lemma 1 eq.(1) (ideal model only)",)),
    LedgerRow("S12", "PHOTONIC_MODEL", "The phenomenological photonic source/detector model is not yet compared to measured data.",
              "SYNTHETIC", "handoffs/F-F1.md", ("phenomenological photonic model not yet compared to measured data",)),
)

TABLE1_COLUMNS = ("theorem_id", "game", "source_url", "anchor", "bound", "transcription_status", "obligation",
                  "proof_status", "finite_n_or_asymptotic", "n_assumptions", "notes")
LEDGER_COLUMNS = ("row_id", "category", "finding", "evidence_kind", "source", "anchors")


def ledger_rows(root: Path, rows: tuple[LedgerRow, ...]) -> list[dict[str, Any]]:
    for r in rows:
        check_row(root, r)
    return [{"row_id": r.row_id, "category": r.category, "finding": r.finding, "evidence_kind": r.evidence_kind,
             "source": r.source, "anchors": " | ".join(r.anchors)} for r in rows]


def _md_cell(v: Any) -> str:
    return str(v).replace("|", "\\|").replace("\n", " ")


def write_table(rows: list[dict[str, Any]], columns: tuple[str, ...], stem: Path, title: str, preamble: str) -> list[Path]:
    stem.parent.mkdir(parents=True, exist_ok=True)
    csv_path, md_path = stem.with_suffix(".csv"), stem.with_suffix(".md")
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(columns), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    lines = [f"# {title}", "", preamble, "", "| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    lines += ["| " + " | ".join(_md_cell(r[c]) for c in columns) + " |" for r in rows]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return [csv_path, md_path]


def build_tables(root: Path, out: Path) -> list[Path]:
    gen = "Generated by `python -m qmint.evaluation.make_figures`; do not edit by hand."
    paths = write_table(table1(root), TABLE1_COLUMNS, out / "table1_theorem_families", "Table 1. Theorem families",
                        f"{gen} Sources: `{THEOREM_SEED}` (lane A transcription) joined with `{OBLIGATIONS}` (lane D "
                        "registry). A theorem is valid only for its game.")
    paths += write_table(ledger_rows(root, TABLE4), LEDGER_COLUMNS, out / "table4_negative_results",
                         "Table 4. Negative results, broken assumptions, unreachable backends, unsupported claims",
                         f"{gen} Each anchor occurs verbatim in its source; every number in a finding occurs in an anchor.")
    paths += write_table(ledger_rows(root, TABLE5), LEDGER_COLUMNS, out / "table5_scope_constraints",
                         "Table 5. Scope and impossibility constraints",
                         f"{gen} Each anchor occurs verbatim in its source.")
    return paths
