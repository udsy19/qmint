"""Evidence loaders and the figure registry (master plan sections 8-9).

Every figure is produced ONLY by
  (a) re-executing merged package APIs (``qmint.proofs``, ``qmint.attacks``), or
  (b) reading committed evidence: lane handoff evidence JSON, ``reports/data_working``,
      ``proofs/certificates``, ``qollab/evidence``, or the lane-L record store ``experiments/``.
No number is typed in here. Closed-form labels (e.g. "(3+sqrt5)/8") are checked against the
re-executed value at build time and the build fails on disagreement.

Each :class:`FigureSpec` names its input files and the modules it executes; ``make_figures``
pins both in a C6 ``EvidenceManifest`` and rebuilds when any hash changes.
"""

from __future__ import annotations

import csv
import json
import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction
from pathlib import Path
from typing import Any

from matplotlib.figure import Figure

from qmint.core.contracts import CONTRACT_MODELS, EvidenceKind, GameId
from qmint.core.records import RecordStore
from qmint.evaluation import plots
from qmint.evaluation.statistics import binomial

ROOT = Path(__file__).resolve().parents[2]

# Committed evidence (paths relative to the repository root).
C_EVIDENCE = "handoffs/C-C1-evidence.json"
F_EVIDENCE = "handoffs/F-F1_evidence.json"
J_LOCAL_RUNS = "qollab/evidence/local_aer_runs.json"
E_DIR = "reports/data_working/schiansky2023"
E_PER_RUN, E_SUMMARY, E_MANIFEST = f"{E_DIR}/per_run.csv", f"{E_DIR}/summary.json", f"{E_DIR}/manifest.json"
D_REPRO = "proofs/certificates/reproduction_v1.json"
D_KENT_EXP = "proofs/certificates/S2_kent_experimental_tuple.json"
RECORD_STORE = "experiments"

_EVAL = ("qmint/evaluation/experiments.py", "qmint/evaluation/plots.py", "qmint/evaluation/statistics.py")
FIG10_CAPTION = "Quantum-circuit primitive demonstration, not proof of a physically deployable quantum-cash system."


class FigureStatus(str, Enum):
    READY = "READY"
    PENDING = "PENDING"  # producing lane/record not yet available; rendered as a placeholder, never as zero
    BLOCKED = "BLOCKED"


@dataclass
class FigureResult:
    status: FigureStatus
    fig: Figure
    caption: str
    evidence_kinds: tuple[EvidenceKind, ...]
    rows: list[dict[str, Any]] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FigureSpec:
    fig_id: str
    slug: str
    title: str
    inputs: tuple[str, ...]
    scripts: tuple[str, ...]
    primary_evidence: EvidenceKind  # C6 manifests carry ONE kind; the caption lists all of them
    build: Callable[[Path], FigureResult]

    @property
    def stem(self) -> str:
        return f"{self.fig_id}_{self.slug}"


def load_json(root: Path, rel: str) -> Any:
    return json.loads((root / rel).read_text(encoding="utf-8"))


def _f(x: float) -> float:
    return float(f"{x:.12g}")


# --------------------------------------------------------------------------- Fig 2
def build_fig2(root: Path) -> FigureResult:
    from qmint.proofs.ideal_bounds import log10_bound

    c = load_json(root, C_EVIDENCE)
    ns = list(range(1, 129))
    theory = {"n": ns, "w1": [10 ** log10_bound(GameId.W1, n) for n in ns],
              "w1_cv": [10 ** log10_bound(GameId.W1_CV, n) for n in ns]}
    mc = sorted((r["record"]["token_n"], binomial(r["record"]["successes"], r["record"]["trials"],
                                                  unit="independent note (fresh secret per trial)"))
                for r in c["w1_monte_carlo"] if r["record"]["attack_id"] == "A04_mvw_optimal_channel")
    h = c["honest_acceptance_w1_n8"]
    honest = (8, binomial(h["accepted"], h["trials"], unit="independent note"))
    sdp = []
    for key in ("n1_SCS", "n1_CLARABEL", "n2_SCS", "n2_CLARABEL"):
        if key in c["w1_sdp"]:
            cert = c["w1_sdp"][key]["certified"]
            sdp.append({"n": int(key[1]), "solver": key.split("_")[1],
                        "lower": float(Fraction(cert["exact_lower_bound_from_mvw_channel"])),
                        "upper": cert["upper_bound_float_up"]})
    rows = [{"series": "W1 theorem (3/4)^n", "evidence_kind": "PUBLISHED_THEOREM", "game": "W1", "n": n,
             "value": _f(v), "lo": "", "hi": ""} for n, v in zip(ns, theory["w1"], strict=True)]
    rows += [{"series": "W1_CV theorem (different game)", "evidence_kind": "PUBLISHED_THEOREM", "game": "W1_CV",
              "n": n, "value": _f(v), "lo": "", "hi": ""} for n, v in zip(ns, theory["w1_cv"], strict=True)]
    rows += [{"series": "A04 MVW channel MC", "evidence_kind": "MONTE_CARLO", "game": "W1", "n": n,
              "value": _f(e.point), "lo": _f(e.lo), "hi": _f(e.hi)} for n, e in mc]
    rows.append({"series": "honest acceptance", "evidence_kind": "SIMULATOR_IDEAL", "game": "W1", "n": 8,
                 "value": _f(honest[1].point), "lo": _f(honest[1].lo), "hi": _f(honest[1].hi)})
    rows += [{"series": f"SDP certified bracket {s['solver']}", "evidence_kind": "CERTIFIED_NUMERIC", "game": "W1",
              "n": s["n"], "value": "", "lo": _f(s["lower"]), "hi": repr(s["upper"])} for s in sdp]
    fig = plots.fig2_w1_oracle(theory, mc, sdp, honest)
    caption = (
        "Game W1 (Wiesner simple 1->2 counterfeiting, exact projective verifier, no oracle). Solid line: "
        "MVW 2012 Theorem 1 optimum (3/4)^n, evaluated by qmint.proofs.ideal_bounds. Grey dashed: "
        "(3/4+sqrt2/8)^n is the optimum of the DIFFERENT classical-verification game W1_CV (MVW Theorem 2) "
        "and is not a bound for W1. Blue circles: Monte Carlo success of the optimal MVW channel attack "
        "(lane C, 10^4 independent notes per n, Clopper-Pearson 95%), a lower bound on the worst case. "
        "Diamonds: Choi-matrix SDP optimum for n=1,2 with a certified bracket [exact achieving channel, "
        "exact-rational dual upper bound]; right panel shows the bracket width. Lane D re-verified the "
        "upper bounds independently (proofs/certificates/reproduction_v1.json). n>=3 SDP: UNSUPPORTED "
        "(size guard); no large-n numerical extrapolation is drawn."
    )
    return FigureResult(FigureStatus.READY, fig, caption,
                        (EvidenceKind.PUBLISHED_THEOREM, EvidenceKind.MONTE_CARLO, EvidenceKind.CERTIFIED_NUMERIC,
                         EvidenceKind.SIMULATOR_IDEAL), rows,
                        sources=["https://arxiv.org/abs/1202.4010"])


# --------------------------------------------------------------------------- Fig 3
# attack_id -> (display name, closed form label, closed form value). Values are CHECKED against the
# re-executed exact per-qubit both-pass probability; a mismatch aborts the build.
_CLOSED_FORMS: dict[str, tuple[str, str, float]] = {
    "A01_basis_guess_resend": ("A01 random-basis measure-resend", "5/8", 5 / 8),
    "A02_breidbart_resend": ("A02 Breidbart measure-resend", "5/8", 5 / 8),
    "A01b_basis_guess_bayes_resend": ("A01b measure + Bayes resend", "(3+sqrt5)/8", (3 + math.sqrt(5)) / 8),
    "A02b_breidbart_bayes_resend": ("A02b Breidbart + Bayes resend", "(3+sqrt5)/8", (3 + math.sqrt(5)) / 8),
    "A03_universal_buzek_hillery": ("A03 universal Buzek-Hillery cloner", "2/3", 2 / 3),
    "A03b_phase_covariant_xz": ("A03b phase-covariant x-z cloner", "(3+2sqrt2)/8", (3 + 2 * math.sqrt(2)) / 8),
    "A04_mvw_optimal_channel": ("A04 MVW optimal channel", "3/4", 3 / 4),
}


def _kraus(attack_id: str) -> list[Any]:
    from qmint.attacks import heuristic as h
    from qmint.attacks.coherent_sdp import mvw_optimal_kraus

    return {
        "A01_basis_guess_resend": lambda: h.a01_kraus(),
        "A01b_basis_guess_bayes_resend": lambda: h.a01_kraus(bayes=True),
        "A02_breidbart_resend": lambda: h.a02_kraus(),
        "A02b_breidbart_bayes_resend": lambda: h.a02_kraus(bayes=True),
        "A03_universal_buzek_hillery": h.buzek_hillery_kraus,
        "A03b_phase_covariant_xz": h.phase_covariant_xz_kraus,
        "A04_mvw_optimal_channel": mvw_optimal_kraus,
    }[attack_id]()


def _rule_label(rule: str) -> str:
    m = re.search(r"lost<=floor\(([\d.]+)n\) and errors<=floor\(([\d.]+)", rule)
    return f"loss<={m.group(1)}n, err<={m.group(2)}" if m else rule


def build_fig3(root: Path) -> FigureResult:
    from qmint.attacks.heuristic import w1_product_exact
    from qmint.proofs.ideal_bounds import log10_bound

    c = load_json(root, C_EVIDENCE)
    mc1 = {r["record"]["attack_id"]: r for r in c["w1_monte_carlo"] if r["record"]["token_n"] == 1}
    in_model, rows = [], []
    for aid, (name, form, value) in _CLOSED_FORMS.items():
        exact = w1_product_exact(_kraus(aid), 1)
        if not math.isclose(exact, value, abs_tol=1e-12):
            raise AssertionError(f"{aid}: re-executed exact value {exact} != closed form {form}")
        if not math.isclose(exact, mc1[aid]["exact_analytic"], abs_tol=1e-12):
            raise AssertionError(f"{aid}: re-executed value disagrees with lane C evidence")
        r = mc1[aid]["record"]
        est = binomial(r["successes"], r["trials"], unit="independent note")
        in_model.append({"name": name, "closed_form": form, "exact": exact, "mc": est})
        rows.append({"attack_id": aid, "game": r["game_id"], "proof_applicability": r["proof_applicability"],
                     "n": 1, "exact_value": _f(exact), "closed_form": form, "mc_successes": r["successes"],
                     "mc_trials": r["trials"], "mc_lo": _f(est.lo), "mc_hi": _f(est.hi),
                     "evidence_kind": "MONTE_CARLO+exact"})
    out_model = []
    for key in ("a06_toy_w2", "a08_oracle_out_of_model"):
        for e in c[key]:
            r = e["record"]
            est = binomial(r["successes"], r["trials"], unit="independent note")
            tag = r["proof_applicability"]
            name = (f"A06 n={r['token_n']} toy W2 ({_rule_label(r['verifier_rule'])}) [{tag}]" if key == "a06_toy_w2"
                    else f"A08 leaky oracle n={r['token_n']} [{tag}]")
            out_model.append({"name": name, "mc": est, "w1_contrast": e["w1_value_for_contrast_only"]})
            rows.append({"attack_id": r["attack_id"], "game": r["game_id"], "proof_applicability": tag,
                         "n": r["token_n"], "exact_value": _f(e["exact_analytic"]), "closed_form": "",
                         "mc_successes": r["successes"], "mc_trials": r["trials"], "mc_lo": _f(est.lo),
                         "mc_hi": _f(est.hi), "evidence_kind": "MONTE_CARLO"})
    ctrl = c["ctrl_secret_leak"]["record"]
    est = binomial(ctrl["successes"], ctrl["trials"], unit="independent note")
    out_model.append({"name": f"CTRL secret-basis leak n={ctrl['token_n']} [{ctrl['proof_applicability']}]",
                      "mc": est, "w1_contrast": 10 ** log10_bound(GameId.W1, ctrl["token_n"])})
    rows.append({"attack_id": ctrl["attack_id"], "game": ctrl["game_id"], "proof_applicability": ctrl["proof_applicability"],
                 "n": ctrl["token_n"], "exact_value": "", "closed_form": "", "mc_successes": ctrl["successes"],
                 "mc_trials": ctrl["trials"], "mc_lo": _f(est.lo), "mc_hi": _f(est.hi), "evidence_kind": "MONTE_CARLO"})
    bound = 10 ** log10_bound(GameId.W1, 1)
    fig = plots.fig3_attacker_zoo(in_model, out_model, bound)
    caption = (
        "Attacker zoo. Left, game W1 only (one note, exact projective verifier, no oracle): grey bars are the "
        "exact per-qubit both-pass probabilities re-computed from each attack's Kraus operators "
        "(qmint.attacks.heuristic) and checked against the closed forms shown; blue points are lane C Monte "
        "Carlo estimates at n=1 (Clopper-Pearson 95%). Measure-resend reaches 5/8, not 3/4. No in-model attack "
        "exceeds the MVW optimum 3/4. Right, red: attacks that break a W1 hypothesis (A06 runs on a toy lossy "
        "threshold verifier, game W2, NO_THEOREM; A08 uses a leaky accept/reject oracle; CTRL is given the "
        "secret basis). They are OUT_OF_MODEL and are NOT counterexamples to MVW Theorem 1; ticks show (3/4)^n "
        "for the same n for contrast only."
    )
    return FigureResult(FigureStatus.READY, fig, caption,
                        (EvidenceKind.PUBLISHED_THEOREM, EvidenceKind.MONTE_CARLO), rows, sources=["https://arxiv.org/abs/1202.4010"])


# --------------------------------------------------------------------------- Fig 4
def build_fig4(root: Path) -> FigureResult:
    from qmint.photonics.calibration import PUBLISHED_2023

    summ = load_json(root, E_SUMMARY)["basis_summaries"]
    man = load_json(root, E_MANIFEST)
    with open(root / E_PER_RUN, encoding="utf-8") as f:
        per_run = list(csv.DictReader(f))
    runs: dict[str, list[dict[str, Any]]] = {"Z": [], "X": []}
    rows = []
    for r in per_run:
        est = binomial(int(r["n_errors"]), int(r["n_sifted"]), unit="sifted coincidence (runs overdispersed)")
        runs[r["client_basis"]].append({"run": int(r["chunk"]), "qber": est, "drift": float(r["residual_drift_ns_per_s"]),
                                        "drift_se": float(r["residual_drift_se"])})
        rows.append({"folder": r["folder"], "chunk": r["chunk"], "basis": r["client_basis"], "n_errors": r["n_errors"],
                     "n_sifted": r["n_sifted"], "qber": _f(est.point), "cp95_lo": _f(est.lo), "cp95_hi": _f(est.hi),
                     "residual_drift_ns_per_s": r["residual_drift_ns_per_s"], "residual_drift_se": r["residual_drift_se"],
                     "evidence_kind": "PHOTON_EXPERIMENT"})
    published = {b: {"value": PUBLISHED_2023[f"qber_{b}_percent"]["value"] / 100,
                     "pm": PUBLISHED_2023[f"qber_{b}_percent"]["pm"] / 100} for b in ("Z", "X")}
    reproduced = {b: summ[b]["qber_state_avg"] for b in ("Z", "X")}
    for b in ("Z", "X"):
        rows.append({"folder": "PUBLISHED", "chunk": "", "basis": b, "n_errors": "", "n_sifted": "",
                     "qber": published[b]["value"], "cp95_lo": "", "cp95_hi": "", "residual_drift_ns_per_s": "",
                     "residual_drift_se": "", "evidence_kind": "PUBLISHED_AGGREGATE"})
    archive = next(e for e in man["entries"] if "7979319" in e["path_or_uri"])
    split = summ["X"]["split"]
    fig = plots.fig4_photon_qber(runs, published, reproduced)
    caption = (
        "Reproduction from real photon data: Schiansky et al., Nat. Commun. 14, 3849 (2023), doi:10.1038/"
        "s41467-023-39519-w; dataset Zenodo record 7979319 (doi:10.5281/zenodo.7979319), Archive.zip "
        f"sha256 {archive['sha256']} (upstream {archive.get('upstream_checksum')}). Orange squares: per-run "
        "error rate (errors/sifted coincidences) with Clopper-Pearson 95% intervals, which understate the spread "
        f"because runs are overdispersed (X runs chi2/dof = {summ['X']['het_runs']['dispersion']:.1f}). Dashed "
        "line and band: published value +/- quoted uncertainty (PUBLISHED_AGGREGATE). Thin orange line: this "
        "work's state-averaged estimator. Right: residual timing drift after alignment. Non-stationarity: the "
        f"X-basis holdout runs {split['holdout_runs']} differ from calibration runs {split['calibration_runs']} "
        f"(two-proportion p = {split['p_value']:.3f}). Run order is the archive chunk index (assumed acquisition "
        f"order). Lane E manifest: {man['manifest_id']}."
    )
    return FigureResult(FigureStatus.READY, fig, caption,
                        (EvidenceKind.PHOTON_EXPERIMENT, EvidenceKind.PUBLISHED_AGGREGATE), rows,
                        sources=list(man["source_urls"]))


# --------------------------------------------------------------------------- Fig 5
KENT_E_GRID = (0.01, 0.03, 0.058)  # the three E values of the paper's Fig. 5 examples (see D_REPRO rows)
_FIG5 = re.compile(r"^Fig\.5 beta_max theta=([\d.e+-]+)deg E=([\d.]+)$")


def build_fig5(root: Path) -> FigureResult:
    from qmint.proofs.reproduce import KENT_EXP, kent_fig5_beta_max, kent_p_noqub

    repro = load_json(root, D_REPRO)
    paper = []
    for r in repro["rows"]:
        m = _FIG5.match(r["quantity"])
        if m:
            paper.append({"theta_deg": float(m.group(1)), "E": float(m.group(2)), "beta": r["paper_value"],
                          "qmint": r["qmint_value"]})
    if sorted(p["E"] for p in paper) != sorted(KENT_E_GRID):
        raise AssertionError("Fig. 5 E grid no longer matches lane D's reproduction rows")
    pnq = kent_p_noqub(KENT_EXP["mu"])
    thetas = [1e-6] + [i * 0.25 for i in range(1, 81)]  # Kent Table 5 item 2 needs 0 < theta < pi/4
    curves, rows = [], []
    for e in KENT_E_GRID:
        betas = []
        for t in thetas:
            best = kent_fig5_beta_max(t, e, pnq)
            betas.append(best["beta_PB"] if best else None)
            rows.append({"series": f"beta_max E={e}", "theta_deg": t, "E": e,
                         "beta_max": "" if best is None else _f(best["beta_PB"]),
                         "status": "CERTIFIED_REGION_EDGE" if best else "NO_ADMISSIBLE_BETA",
                         "evidence_kind": "PUBLISHED_THEOREM"})
        curves.append({"E": e, "theta_deg": thetas, "beta_max": betas})
    for p in paper:
        rows.append({"series": "paper Fig.5 value", "theta_deg": p["theta_deg"], "E": p["E"], "beta_max": p["beta"],
                     "status": "DIGITIZED", "evidence_kind": "DIGITIZED_FIGURE"})
    cert = load_json(root, D_KENT_EXP)
    prm = cert["parameters"]
    exp = {"theta_deg": math.degrees(prm["theta"]), "beta": max(prm["beta_PB"], prm["beta_PS"]), "E": prm["E"]}
    rows.append({"series": "Kent experimental tuple", "theta_deg": _f(exp["theta_deg"]), "E": exp["E"],
                 "beta_max": exp["beta"], "status": cert["proof_check_status"], "evidence_kind": "PUBLISHED_AGGREGATE"})
    fig = plots.fig5_kent_region(curves, paper, exp)
    caption = (
        "Game S2 only: Kent, Lowndes, Pitalua-Garcia, Rarity, npj Quantum Inf. 8, 28 (2022), Theorem 1 "
        "(eps_unf) with Lemmas 2-3, re-evaluated by qmint.proofs.finite_size following the paper's Fig. 5 "
        f"procedure (N = {KENT_EXP['N']:.0e}, each exponential term <= 1e-9/2, beta_PB = beta_PS = beta). "
        "Curves: largest admissible bias per misalignment theta for three error rates E; below a curve the "
        "hypothetical tuple is certified, above it UNCERTIFIED; where no beta is admissible the curve stops "
        "(no value is drawn, never zero). Stars: values quoted in the paper (DIGITIZED_FIGURE). X: the paper's "
        f"experimental tuple (E = {exp['E']}, theta = {exp['theta_deg']:.0f} deg) lies outside the Theorem 1 domain; "
        f"lane D's independent checker returns {cert['proof_check_status']}. This is NOT the Schiansky 2023 "
        "payment protocol (game D1) and no hybrid of the two proofs is drawn."
    )
    return FigureResult(FigureStatus.READY, fig, caption,
                        (EvidenceKind.PUBLISHED_THEOREM, EvidenceKind.DIGITIZED_FIGURE, EvidenceKind.PUBLISHED_AGGREGATE),
                        rows, sources=["https://www.nature.com/articles/s41534-022-00524-4"])


# --------------------------------------------------------------------------- Fig 10
def build_fig10(root: Path) -> FigureResult:
    f = load_json(root, F_EVIDENCE)
    j = load_json(root, J_LOCAL_RUNS)
    if f.get("caption") != FIG10_CAPTION:
        raise AssertionError("lane F caption changed; re-check Fig. 10 wording")
    channels, rows = [], []
    for ch in ("depolarizing", "dephasing", "amplitude_damping"):
        curves = []
        for p in (0.0, 0.05):
            pts = sorted((r["n"], r["mean_accept_exact_verifier"]) for r in f["honest_acceptance_curves"]
                         if r["channel"] == ch and r["param"] == p)
            curves.append({"param": p, "n": [n for n, _ in pts], "accept": [a for _, a in pts]})
            rows += [{"panel": ch, "series": f"analytic p={p}", "n": n, "value": _f(a), "lo": "", "hi": "",
                      "evidence_kind": "SYNTHETIC"} for n, a in pts]
        aer = []
        for r in sorted((r for r in f["aer_noisy_points"] if r["channel"] == ch), key=lambda r: r["n"]):
            est = binomial(r["accepted"], r["shots"], method="wilson", unit="shot (one Aer job; drift-free simulator)")
            aer.append({"n": r["n"], "est": est})
            rows.append({"panel": ch, "series": f"Aer noisy p={r['param']}", "n": r["n"], "value": _f(est.point),
                         "lo": _f(est.lo), "hi": _f(est.hi), "evidence_kind": r["evidence_kind"]})
        channels.append({"channel": ch, "curves": curves, "aer": aer})
    jrun = {}
    for mode in ("ideal", "noisy"):
        vp = j[mode]["verify_pass"]
        jrun[mode] = binomial(vp["successes"], vp["trials"], method="wilson", unit="shot")
        rows.append({"panel": "lane J 8q", "series": f"Aer {mode}", "n": len(j["bases"]), "value": _f(jrun[mode].point),
                     "lo": _f(jrun[mode].lo), "hi": _f(jrun[mode].hi), "evidence_kind": j[mode]["record"]["evidence_kind"]})
    rows.append({"panel": "lane J 8q", "series": "IonQ QPU", "n": "", "value": "NOT_RUN", "lo": "", "hi": "",
                 "evidence_kind": "QPU"})
    fig = plots.fig10_hardware_truth(channels, jrun, FIG10_CAPTION)
    caption = (
        f"{FIG10_CAPTION} Honest BB84 note verification with the exact (zero-tolerance) verifier. Lines: analytic "
        "product formula under HYPOTHETICAL qubit noise plus readout error (SYNTHETIC, lane F). Filled triangles: "
        "Qiskit Aer density-matrix runs (SIMULATOR_NOISY, 20000 shots, Wilson 95%; shots from one job are the "
        "sampling unit, valid only because a simulator has no drift). Bottom right: lane J 8-qubit note, Aer "
        "ideal vs a different hypothetical noise model. QPU: not run - no authorized hardware job exists; "
        "no paid job was submitted. Acceptance collapses with n under small noise: the exact verifier is not "
        "noise tolerant (that requires a threshold game W2, for which no bound is registered)."
    )
    return FigureResult(FigureStatus.READY, fig, caption,
                        (EvidenceKind.SIMULATOR_IDEAL, EvidenceKind.SIMULATOR_NOISY, EvidenceKind.SYNTHETIC), rows)


# --------------------------------------------------------------------------- PENDING (record store)
def real_records(root: Path, contract: str) -> list[Any]:
    """Non-SYNTHETIC, unflagged-fixture contract payloads of one kind from the lane-L record store."""
    store = RecordStore(root / RECORD_STORE)
    out = []
    for idx in store.iter_registry():
        if idx["contract"] != contract or idx["evidence_kind"] == EvidenceKind.SYNTHETIC.value:
            continue
        rec = store.get(idx["record_id"])
        out.append(CONTRACT_MODELS[contract].model_validate(rec.payload))
    return out


def _pending(fig_id: str, title: str, reason: str) -> FigureResult:
    return FigureResult(FigureStatus.PENDING, plots.pending_figure(fig_id, title, reason),
                        f"PENDING: {title}. {reason}", (EvidenceKind.UNCERTIFIED,), [], notes=[reason])


def _record_figure(fig_id: str, title: str, contract: str, reason: str,
                   render: Callable[[list[Any]], Figure], kinds: tuple[EvidenceKind, ...]) -> Callable[[Path], FigureResult]:
    def build(root: Path) -> FigureResult:
        recs = real_records(root, contract)
        if not recs:
            return _pending(fig_id, title, reason)
        rows = [r.model_dump(mode="json") for r in recs]
        return FigureResult(FigureStatus.READY, render(recs), title, kinds, [{"record": json.dumps(r)} for r in rows])
    return build


def _comparability(root: Path) -> dict[str, str]:
    path = root / "reports/classical_baseline_notes/comparability_matrix.csv"
    if not path.is_file():
        return {}
    with open(path, encoding="utf-8") as f:
        return {r["left_protocol"].split("[")[0]: r["comparability_status"] for r in csv.DictReader(f)}


FIGURES: tuple[FigureSpec, ...] = (
    FigureSpec("fig02", "w1_counterfeiting_oracle", "Exact counterfeiting oracle (W1)", (C_EVIDENCE,),
               ("qmint/proofs/ideal_bounds.py", *_EVAL), EvidenceKind.PUBLISHED_THEOREM, build_fig2),
    FigureSpec("fig03", "attacker_zoo", "The attacker zoo (W1, out-of-model in red)", (C_EVIDENCE,),
               ("qmint/attacks/heuristic.py", "qmint/attacks/coherent_sdp.py", "qmint/proofs/ideal_bounds.py", *_EVAL),
               EvidenceKind.MONTE_CARLO, build_fig3),
    FigureSpec("fig04", "photon_qber_reproduction", "Reproduction of the 2023 optical experiment (Zenodo 7979319)",
               (E_PER_RUN, E_SUMMARY, E_MANIFEST), ("qmint/photonics/calibration.py", *_EVAL),
               EvidenceKind.PHOTON_EXPERIMENT, build_fig4),
    FigureSpec("fig05", "kent2022_secure_region", "Kent 2022 S-token secure region (beta_max vs theta)",
               (D_REPRO, D_KENT_EXP), ("qmint/proofs/finite_size.py", "qmint/proofs/reproduce.py", *_EVAL),
               EvidenceKind.PUBLISHED_THEOREM, build_fig5),
    FigureSpec("fig06", "spacetime_double_spend", "Double-spend space-time diagram", (), _EVAL,
               EvidenceKind.MODELLED_LATENCY,
               _record_figure("fig06", "Double-spend space-time diagram", "trace",
                              "Awaiting lane G/H integration: needs C4 TransactionTrace records in experiments/ "
                              "(paper-faithful S-money and lane-H classical race on one SpacetimeNetwork).",
                              lambda r: plots.fig6_spacetime(r), (EvidenceKind.MODELLED_LATENCY,))),
    FigureSpec("fig07", "classical_vs_quantum_latency", "Classical vs quantum local verification", (), _EVAL,
               EvidenceKind.MODELLED_LATENCY, lambda root: _record_figure(
                   "fig07", "Classical vs quantum local verification", "benchmark",
                   "Awaiting lane G/H integration: needs C6 BenchmarkRecords for BOTH the quantum S-token and "
                   "H0-H6 in experiments/, plus the X11 comparability matrix.",
                   lambda r: plots.fig7_latency(r, _comparability(root)), (EvidenceKind.MODELLED_LATENCY,))(root)),
    FigureSpec("fig08", "certificate_pareto", "Security-certificate Pareto frontier", (), _EVAL,
               EvidenceKind.PUBLISHED_THEOREM,
               lambda root: _pending("fig08", "Security-certificate Pareto frontier",
                                     "Awaiting lane I (compiler): needs CERTIFIED C5 certificates paired with C6 "
                                     "records (pairing convention to be agreed; renderer plots.fig8_pareto).")),
    FigureSpec("fig09", "ablations_robustness", "Ablations and robustness", (), _EVAL, EvidenceKind.PUBLISHED_THEOREM,
               lambda root: _pending("fig09", "Ablations and robustness",
                                     "Awaiting lane I: needs paired point-vs-interval calibration C6 records "
                                     "(renderer plots.fig9_ablation).")),
    FigureSpec("fig10", "hardware_truthfulness", "Hardware truthfulness (simulator only; QPU not run)",
               (F_EVIDENCE, J_LOCAL_RUNS), _EVAL, EvidenceKind.SIMULATOR_NOISY, build_fig10),
)


def figure_spec(fig_id: str) -> FigureSpec:
    for s in FIGURES:
        if s.fig_id == fig_id:
            return s
    raise KeyError(fig_id)
