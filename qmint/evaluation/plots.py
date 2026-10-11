"""Matplotlib renderers for the paper figures (master plan section 9).

Renderers take already-extracted data (see :mod:`qmint.evaluation.experiments`) and never read
files or invent numbers. Evidence is encoded redundantly -- colour, line style, marker AND a
bracketed tag in every legend label -- so a theorem curve, a Monte Carlo estimate, real photon
data and synthetic/modelled output are distinguishable in greyscale and under colour-vision
deficiency. Palette: categorical slots 1-3 of the dataviz reference palette (blue, orange, aqua;
validated all-pairs, light mode), ink for theorems/published values, muted grey for synthetic or
modelled output, and red reserved for out-of-model attacks (only ever paired with blue).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.ticker import MaxNLocator, PercentFormatter  # noqa: E402

from qmint.core.contracts import (  # noqa: E402
    BenchmarkRecord,
    CertificateStatus,
    EvidenceKind,
    SecurityCertificate,
    TransactionTrace,
)

INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
BLUE, ORANGE, AQUA, RED = "#2a78d6", "#eb6834", "#1baf7a", "#e34948"
SEQ_BLUE = ("#86b6ef", "#2a78d6", "#104281")  # sequential ramp steps 250/450/650 (ordered magnitude)


@dataclass(frozen=True)
class Style:
    tag: str
    color: str
    linestyle: str  # "none" for markers-only evidence
    marker: str  # "" for line-only evidence
    filled: bool = True


# One style per evidence class. (color, linestyle, marker, filled) is unique per tag (tested).
STYLES: dict[str, Style] = {
    "THEOREM": Style("THEOREM", INK, "-", ""),
    "PUBLISHED": Style("PUBLISHED", INK, "--", ""),
    "DIGITIZED": Style("DIGITIZED", INK, "none", "*", filled=False),
    "SDP": Style("SDP", INK, "none", "D"),
    "MC": Style("MC", BLUE, "none", "o"),
    "PHOTON-EXPERIMENT": Style("PHOTON-EXPERIMENT", ORANGE, "none", "s"),
    "SIM-IDEAL": Style("SIM-IDEAL", AQUA, "none", "^", filled=False),
    "SIM-NOISY": Style("SIM-NOISY", AQUA, "none", "^"),
    "SYNTHETIC": Style("SYNTHETIC", MUTED, "-.", ""),
    "MODELLED": Style("MODELLED", MUTED, ":", ""),
    "OUT-OF-MODEL": Style("OUT-OF-MODEL", RED, "none", "X"),
    "PENDING": Style("PENDING", MUTED, "none", ""),
}

TAG_OF_KIND: dict[EvidenceKind, str] = {
    EvidenceKind.PUBLISHED_THEOREM: "THEOREM",
    EvidenceKind.NUMERICAL_SDP: "SDP",
    EvidenceKind.CERTIFIED_NUMERIC: "SDP",
    EvidenceKind.MONTE_CARLO: "MC",
    EvidenceKind.PHOTON_EXPERIMENT: "PHOTON-EXPERIMENT",
    EvidenceKind.PUBLISHED_AGGREGATE: "PUBLISHED",
    EvidenceKind.DIGITIZED_FIGURE: "DIGITIZED",
    EvidenceKind.SYNTHETIC: "SYNTHETIC",
    EvidenceKind.SIMULATOR_IDEAL: "SIM-IDEAL",
    EvidenceKind.SIMULATOR_NOISY: "SIM-NOISY",
    EvidenceKind.QPU: "QPU",
    EvidenceKind.MODELLED_LATENCY: "MODELLED",
    EvidenceKind.MEASURED_LATENCY: "MEASURED",
    EvidenceKind.UNCERTIFIED: "UNCERTIFIED",
}

FIXTURE_WATERMARK = "FIXTURE DATA - NOT A RESULT"


class FixtureDataError(ValueError):
    """Synthetic/fixture records were passed to a renderer as if they were results."""


def label(tag: str, text: str) -> str:
    if tag not in STYLES and tag not in TAG_OF_KIND.values():
        raise KeyError(f"unknown evidence tag {tag!r}")
    return f"[{tag}] {text}"


def kw(tag: str, **extra: Any) -> dict[str, Any]:
    """Matplotlib keyword arguments for an evidence class."""
    s = STYLES[tag]
    out: dict[str, Any] = {"color": s.color, "linestyle": s.linestyle}
    if s.marker:
        out.update(marker=s.marker, markersize=7, markeredgecolor=s.color,
                   markerfacecolor=s.color if s.filled else "white", markeredgewidth=1.4)
    out.update(linewidth=2.0)
    out.update(extra)
    return out


def setup_style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": MUTED, "axes.labelcolor": INK, "text.color": INK,
        "xtick.color": MUTED, "ytick.color": MUTED, "font.size": 9, "axes.titlesize": 10,
        "axes.titlelocation": "left", "legend.frameon": False, "legend.fontsize": 7.5,
        "axes.spines.top": False, "axes.spines.right": False,
        "svg.hashsalt": "qmint-figures", "svg.fonttype": "none",
    })


def _grid(ax: Any, axis: str = "y") -> None:
    ax.grid(axis=axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _errorbar(ax: Any, x: Sequence[float], est: Sequence[Any], tag: str, text: str, **extra: Any) -> None:
    pts = [e.point for e in est]
    yerr = [[e.yerr[0] for e in est], [e.yerr[1] for e in est]]
    ax.errorbar(x, pts, yerr=yerr, capsize=0, elinewidth=1.5, label=label(tag, text), **kw(tag, **extra))


def legend_labels(fig: Figure) -> list[str]:
    out: list[str] = []
    for ax in fig.axes:
        leg = ax.get_legend()
        if leg is not None:
            out.extend(t.get_text() for t in leg.get_texts())
    return out


def stamp(fig: Figure, text: str) -> None:
    fig.text(0.5, 0.5, text, ha="center", va="center", fontsize=26, color=RED, alpha=0.25, rotation=20,
             zorder=100)


# --------------------------------------------------------------------------- Fig 2
def fig2_w1_oracle(theory: Mapping[str, Any], mc: Sequence[tuple[int, Any]], sdp: Sequence[Mapping[str, Any]],
                   honest: tuple[int, Any] | None) -> Figure:
    setup_style()
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(10.5, 4.2), gridspec_kw={"width_ratios": [2.2, 1]},
                                 constrained_layout=True)
    ax.semilogy(theory["n"], theory["w1"], label=label("THEOREM", "W1 optimum (3/4)^n, MVW 2012 Thm 1"), **kw("THEOREM"))
    ax.semilogy(theory["n"], theory["w1_cv"],
                label=label("THEOREM", "W1_CV (3/4+sqrt2/8)^n - DIFFERENT GAME (classical verification), MVW Thm 2"),
                **kw("PUBLISHED", color=MUTED))
    _errorbar(ax, [n for n, _ in mc], [e for _, e in mc], "MC", "optimal MVW channel attack, 95% CP (lane C)")
    if honest is not None:
        _errorbar(ax, [honest[0]], [honest[1]], "SIM-IDEAL", "honest note acceptance, 95% CP")
    for s in sdp:
        ax.semilogy([s["n"]], [s["upper"]], **kw("SDP", markersize=6))
    ax.plot([], [], label=label("SDP", "certified bracket [exact lower, certified upper], n=1,2"), **kw("SDP"))
    ax.set_xscale("log", base=2)
    ax.set_xlabel("note length n (qubits)")
    ax.set_ylabel("probability both counterfeits pass (log scale)")
    ax.set_title("W1 simple counterfeiting: theorem, attacks, SDP")
    _grid(ax)
    ax.legend(loc="lower left")
    # (b) certified bracket widths -- invisible on the left panel's scale
    for i, s in enumerate(sdp):
        width = s["upper"] - s["lower"]
        bx.semilogy([i], [width], **kw("SDP"))
        bx.annotate(f"n={s['n']} {s['solver']}", (i, width), textcoords="offset points", xytext=(0, 8),
                    ha="center", fontsize=7.5, color=MUTED)
    bx.set_xticks(range(len(sdp)), [f"n={s['n']}\n{s['solver']}" for s in sdp], fontsize=7.5)
    bx.set_xlim(-0.6, len(sdp) - 0.4)
    bx.set_ylabel("certified upper - exact lower bound")
    bx.set_title("SDP bracket width")
    _grid(bx)
    bx.plot([], [], label=label("SDP", "exact rational LDL^T dual (lane C), re-verified by lane D"), **kw("SDP"))
    bx.legend(loc="lower right")
    return fig


# --------------------------------------------------------------------------- Fig 3
def fig3_attacker_zoo(in_model: Sequence[Mapping[str, Any]], out_model: Sequence[Mapping[str, Any]],
                      bound: float) -> Figure:
    setup_style()
    fig, (ax, bx) = plt.subplots(2, 1, figsize=(9.5, 8.6), gridspec_kw={"height_ratios": [1, 1]},
                                 constrained_layout=True)
    y = list(range(len(in_model)))
    ax.barh(y, [r["exact"] for r in in_model], height=0.55, color=GRID, edgecolor=MUTED, linewidth=0.8,
            label=label("THEOREM", "exact per-qubit both-pass value of the attack (closed form in label)"))
    for yi, r in zip(y, in_model, strict=True):
        e = r["mc"]
        ax.errorbar([e.point], [yi], xerr=[[e.yerr[0]], [e.yerr[1]]], capsize=0, elinewidth=1.5, **kw("MC"))
    ax.plot([], [], label=label("MC", "Monte Carlo n=1, 10^4 notes, 95% CP (lower bound on worst case)"), **kw("MC"))
    ax.axvline(bound, label=label("THEOREM", "W1 optimum 3/4 over ALL channels (MVW Thm 1)"), **kw("PUBLISHED"))
    ax.set_yticks(y, [f"{r['name']}  = {r['closed_form']}" for r in in_model], fontsize=7.5)
    ax.set_xlim(0.55, 0.8)
    ax.set_xlabel("P(both copies pass), one qubit, game W1")
    ax.set_title("(a) In-model attacks on W1 (one note, exact projective verifier, no oracle)")
    _grid(ax, "x")
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), fontsize=7)
    yb = list(range(len(out_model)))
    for yi, r in zip(yb, out_model, strict=True):
        e = r["mc"]
        bx.barh([yi], [e.point], height=0.5, color=RED, alpha=0.85)
        bx.errorbar([e.point], [yi], xerr=[[e.yerr[0]], [e.yerr[1]]], capsize=0, color=INK, elinewidth=1.2)
        bx.plot([r["w1_contrast"]], [yi], **kw("THEOREM", marker="|", markersize=14, linestyle="none"))
    handles = [Patch(color=RED, alpha=0.85, label=label("OUT-OF-MODEL", "breaks a W1 hypothesis: NOT a counterexample to Thm 1")),
               Line2D([], [], **kw("THEOREM", marker="|", markersize=12, linestyle="none"),
                      label=label("THEOREM", "(3/4)^n for the same n, contrast only"))]
    bx.set_yticks(yb, [r["name"] for r in out_model], fontsize=7.5)
    bx.set_xlim(0, 1.05)
    bx.set_xlabel("attack success (Monte Carlo, 95% CP)")
    bx.set_title("(b) Out-of-model attacks (different game or leaked/oracle access)")
    _grid(bx, "x")
    bx.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.0, 1.0), fontsize=7)
    return fig

# --------------------------------------------------------------------------- Fig 4
def fig4_photon_qber(runs: Mapping[str, Sequence[Mapping[str, Any]]], published: Mapping[str, Mapping[str, float]],
                     reproduced: Mapping[str, float]) -> Figure:
    setup_style()
    fig, axes = plt.subplots(1, 3, figsize=(14, 5.0), constrained_layout=True)
    names = {"Z": "H/V (Z basis)", "X": "D/A (X basis)"}
    for ax, b in zip(axes[:2], ("Z", "X"), strict=True):
        rs = runs[b]
        _errorbar(ax, [r["run"] for r in rs], [r["qber"] for r in rs], "PHOTON-EXPERIMENT",
                  "per-run errors/sifted, 95% CP (Zenodo 7979319 raw tags)")
        pub = published[b]
        ax.axhline(pub["value"], label=label("PUBLISHED", f"paper: {pub['value'] * 100:.2f} +/- {pub['pm'] * 100:.2f} %"),
                   **kw("PUBLISHED"))
        ax.axhspan(published[b]["value"] - published[b]["pm"], published[b]["value"] + published[b]["pm"],
                   color=INK, alpha=0.08)
        ax.axhline(reproduced[b], label=label("PHOTON-EXPERIMENT", f"this work, state-averaged: {reproduced[b] * 100:.3f} %"),
                   color=ORANGE, linestyle="-", linewidth=1.2)
        ax.set_xlabel("run (archive chunk index; acquisition order assumed)")
        ax.set_ylabel("error rate")
        ax.yaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=2))
        ax.set_title(f"Error rate per run, {names[b]}")
        _grid(ax)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.legend(loc="upper left", bbox_to_anchor=(0, -0.2), fontsize=7)
    ax = axes[2]
    for b, mk in (("Z", "s"), ("X", "D")):
        rs = runs[b]
        ax.errorbar([r["run"] for r in rs], [r["drift"] for r in rs], yerr=[r["drift_se"] for r in rs],
                    capsize=0, elinewidth=1.2, label=label("PHOTON-EXPERIMENT", f"{names[b]} residual drift +/- 1 SE"),
                    **kw("PHOTON-EXPERIMENT", marker=mk, markerfacecolor="white" if b == "X" else ORANGE))
    ax.axhline(0, color=MUTED, linewidth=0.8)
    ax.set_xlabel("run (archive chunk index)")
    ax.set_ylabel("residual timing drift within run (ns/s)")
    ax.set_title("Timing drift after alignment")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    _grid(ax)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.2), fontsize=7)
    return fig


# --------------------------------------------------------------------------- Fig 5
def fig5_kent_region(curves: Sequence[Mapping[str, Any]], paper_points: Sequence[Mapping[str, Any]],
                     experimental: Mapping[str, Any]) -> Figure:
    setup_style()
    fig, ax = plt.subplots(figsize=(8.2, 6.0), constrained_layout=True)
    for c, color in zip(curves, SEQ_BLUE, strict=False):
        pts = [(t, b) for t, b in zip(c["theta_deg"], c["beta_max"], strict=True) if b is not None]
        ax.semilogy([p[0] for p in pts], [p[1] for p in pts], color=color, linestyle="-", linewidth=2,
                    label=label("THEOREM", f"beta_max, E = {c['E']:g} (Kent 2022 Thm 1, hypothetical tuple)"))
        ax.fill_between([p[0] for p in pts], [1e-9] * len(pts), [p[1] for p in pts], color=color, alpha=0.08)
        none = [t for t, b in zip(c["theta_deg"], c["beta_max"], strict=True) if b is None]
        if none:
            ax.axvspan(min(none), max(none), ymin=0, ymax=0.04, color=color, alpha=0.5)
            ax.text(min(none), 1.6e-9, f"E={c['E']:g}: no admissible beta", fontsize=7, color=INK)
    for p in paper_points:
        ax.semilogy([p["theta_deg"]], [p["beta"]], **kw("DIGITIZED", markersize=11))
    ax.plot([], [], label=label("DIGITIZED", "paper Fig. 5 values quoted in Methods"), **kw("DIGITIZED"))
    ax.semilogy([experimental["theta_deg"]], [experimental["beta"]], linestyle="none", marker="X", markersize=9,
                color=INK, label=label("PUBLISHED", "Kent experimental tuple (max beta): OUTSIDE Thm 1 domain, UNCERTIFIED"))
    ax.set_ylim(1e-9, 2e-2)
    ax.set_xlabel("theta: maximum state misalignment (degrees)")
    ax.set_ylabel("beta_max = beta_PB = beta_PS (log scale)")
    ax.set_title("Kent et al. 2022 S-token (game S2 only): largest bias meeting all eps <= 1e-9")
    ax.text(0.2, 2.5e-9, "shaded: Theorem 1 certifies (hypothetical tuple, N=4e7); above curve: UNCERTIFIED",
            fontsize=7.5, color=MUTED)
    _grid(ax)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.14), fontsize=7.5)
    return fig


# --------------------------------------------------------------------------- Fig 10
def fig10_hardware_truth(channels: Sequence[Mapping[str, Any]], jrun: Mapping[str, Any], caption: str) -> Figure:
    setup_style()
    fig, axes = plt.subplots(2, 2, figsize=(11, 7.4), constrained_layout=True)
    for ax, ch in zip(axes.flat[:3], channels, strict=False):
        ax.axhline(1.0, label=label("THEOREM", "ideal honest acceptance = 1 (noiseless exact verifier)"), **kw("THEOREM"))
        for curve, ls in zip(ch["curves"], ("-.", (0, (1, 1.5))), strict=False):
            ax.semilogx(curve["n"], curve["accept"], **kw("SYNTHETIC", linestyle=ls),
                        label=label("SYNTHETIC", f"analytic, {ch['channel']} p={curve['param']:g} + readout 1%/2%"))
        _errorbar(ax, [p["n"] for p in ch["aer"]], [p["est"] for p in ch["aer"]], "SIM-NOISY",
                  f"Aer density-matrix, {ch['channel']} p=0.05, 95% Wilson")
        ax.set_xscale("log", base=2)
        ax.set_ylim(-0.02, 1.08)
        ax.set_xlabel("note length n (qubits)")
        ax.set_ylabel("honest acceptance (exact verifier)")
        ax.set_title(f"BB84 honest verification: {ch['channel']} (hypothetical noise)")
        _grid(ax)
        ax.legend(loc="lower left", fontsize=6.8, handlelength=4)
    ax = axes.flat[3]
    xs = [0, 1]
    _errorbar(ax, [0], [jrun["ideal"]], "SIM-IDEAL", "Aer ideal, 8 qubits, 95% Wilson")
    _errorbar(ax, [1], [jrun["noisy"]], "SIM-NOISY", "Aer noisy (hypothetical, not IonQ-calibrated), 95% Wilson")
    ax.text(2, 0.5, "QPU:\nNOT RUN", ha="center", va="center", fontsize=14, color=RED, fontweight="bold")
    ax.set_xticks(xs + [2], ["ideal\nsimulator", "noisy\nsimulator", "IonQ QPU\n(no authorized job)"])
    ax.set_xlim(-0.6, 2.6)
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("honest acceptance")
    ax.set_title("8-qubit BB84 note (lane J): ideal vs noisy; hardware not run")
    _grid(ax)
    ax.legend(loc="lower left", fontsize=6.8)
    fig.suptitle(caption, fontsize=13, fontweight="bold", color=INK)
    return fig


# --------------------------------------------------------------------------- PENDING figures
def pending_figure(fig_id: str, title: str, reason: str) -> Figure:
    """A placeholder with NO axes and NO numbers: a missing result is never drawn as zero."""
    setup_style()
    fig = plt.figure(figsize=(8, 3))
    fig.text(0.5, 0.62, f"{fig_id}: PENDING", ha="center", fontsize=24, color=MUTED, fontweight="bold")
    fig.text(0.5, 0.45, title, ha="center", fontsize=10, color=INK)
    fig.text(0.5, 0.28, reason, ha="center", fontsize=8, color=MUTED, wrap=True)
    return fig


def _guard(items: Sequence[Any], ids: Sequence[str], kinds: Sequence[EvidenceKind], fixture_ok: bool) -> bool:
    """True if the inputs are fixtures. Raises unless ``fixture_ok`` (then the caller watermarks)."""
    fixture = any(k == EvidenceKind.SYNTHETIC for k in kinds) or any("fixture" in i.lower() for i in ids)
    if fixture and not fixture_ok:
        raise FixtureDataError("fixture/SYNTHETIC records cannot be rendered as a result; pass fixture_ok=True "
                               "to draw a watermarked fixture preview")
    if not items:
        raise ValueError("no records: render pending_figure(...) instead of an empty plot")
    return fixture


def fig6_spacetime(traces: Sequence[TransactionTrace], *, fixture_ok: bool = False) -> Figure:
    """Space-time diagram from C4 traces: x = site, y = time; causal edges drawn parent -> child."""
    fixture = _guard(traces, [t.trace_id + t.network_id for t in traces], [t.latency_evidence for t in traces], fixture_ok)
    setup_style()
    fig, axes = plt.subplots(1, len(traces), figsize=(4.2 * len(traces), 4.6), squeeze=False, constrained_layout=True)
    for ax, tr in zip(axes[0], traces, strict=True):
        sites = sorted({e.site_id for e in tr.events})
        x = {s: i for i, s in enumerate(sites)}
        by_id = {e.event_id: e for e in tr.events}
        tag = TAG_OF_KIND[tr.latency_evidence]
        for e in tr.events:
            for p in e.causal_parent_ids:
                q = by_id[p]
                ax.plot([x[q.site_id], x[e.site_id]], [q.time_ns / 1e3, e.time_ns / 1e3], color=MUTED, linewidth=1)
        ax.plot([x[e.site_id] for e in tr.events], [e.time_ns / 1e3 for e in tr.events], linestyle="none",
                marker="o", color=INK, label=label(tag, f"{tr.protocol_id} events"))
        for e in tr.events:
            if e.kind in ("verification_result_available_local", "merchant_funds_irrevocable", "reject"):
                ax.annotate(e.kind.replace("_", " "), (x[e.site_id], e.time_ns / 1e3), fontsize=6.5,
                            xytext=(4, 0), textcoords="offset points", color=INK)
        ax.set_xticks(range(len(sites)), sites)
        ax.set_ylabel("time (microseconds)")
        ax.set_title(f"{tr.protocol_id}\ndouble spend accepted: {tr.double_spend_accepted}", fontsize=8.5)
        _grid(ax)
        ax.legend(loc="upper left")
    if fixture:
        stamp(fig, FIXTURE_WATERMARK)
    return fig


def fig7_latency(records: Sequence[BenchmarkRecord], comparability: Mapping[str, str], *, fixture_ok: bool = False) -> Figure:
    """Local redemption latency per protocol; every bar carries its comparability status (C6 records)."""
    fixture = _guard(records, [r.record_id for r in records], [r.evidence_kind for r in records], fixture_ok)
    setup_style()
    fig, ax = plt.subplots(figsize=(9, 0.45 * len(records) + 1.8), constrained_layout=True)
    for i, r in enumerate(records):
        tag = TAG_OF_KIND[r.evidence_kind]
        v = r.redemption_local_seconds
        status = comparability.get(r.protocol_id, "UNASSESSED")
        if v is None:
            ax.text(1e-7, i, "PENDING (no value)", va="center", fontsize=7.5, color=MUTED)
        else:
            ax.barh([i], [v], height=0.55, color=BLUE if r.classical_or_quantum == "quantum" else MUTED)
        ax.text(1.0, i, f"[{tag}] {status}", transform=ax.get_yaxis_transform(), fontsize=7, va="center")
    ax.set_xscale("log")
    ax.set_yticks(range(len(records)), [r.protocol_id for r in records], fontsize=7.5)
    ax.set_xlabel("local redemption latency (s, log scale)")
    ax.set_title("Local verification latency with comparability status (no single 'better' number)")
    _grid(ax, "x")
    if fixture:
        stamp(fig, FIXTURE_WATERMARK)
    return fig


def fig8_pareto(points: Sequence[tuple[BenchmarkRecord, SecurityCertificate]], *, fixture_ok: bool = False) -> Figure:
    """Certified-only Pareto view: photons prepared vs certified epsilon_unf, by method (C5+C6)."""
    fixture = _guard(points, [b.record_id for b, _ in points], [b.evidence_kind for b, _ in points], fixture_ok)
    setup_style()
    fig, ax = plt.subplots(figsize=(8, 4.6), constrained_layout=True)
    excluded = 0
    for b, c in points:
        eps = c.upper_bounds.epsilon_unf
        if c.proof_check_status != CertificateStatus.CERTIFIED or eps is None or b.photons_prepared is None:
            excluded += 1
            continue
        ax.loglog([b.photons_prepared], [eps], **kw("THEOREM", marker="o", linestyle="none"))
    ax.set_xlabel("photons prepared")
    ax.set_ylabel("certified epsilon_unf upper bound")
    ax.set_title(f"Certified configurations only ({excluded} uncertified/infeasible excluded)")
    _grid(ax)
    if fixture:
        stamp(fig, FIXTURE_WATERMARK)
    return fig


def fig9_ablation(pairs: Sequence[tuple[BenchmarkRecord, BenchmarkRecord]], *, fixture_ok: bool = False) -> Figure:
    """Paired ablation: same scenario with point-estimate vs interval calibration (photons prepared)."""
    flat = [r for p in pairs for r in p]
    fixture = _guard(flat, [r.record_id for r in flat], [r.evidence_kind for r in flat], fixture_ok)
    setup_style()
    fig, ax = plt.subplots(figsize=(7, 4.4), constrained_layout=True)
    for i, (a, b) in enumerate(pairs):
        if a.photons_prepared is None or b.photons_prepared is None:
            ax.text(i, 1, "PENDING", rotation=90, fontsize=7, color=MUTED)
            continue
        ax.semilogy([i, i], [a.photons_prepared, b.photons_prepared], color=MUTED, linewidth=1)
        ax.semilogy([i], [a.photons_prepared], **kw("MODELLED", marker="o", linestyle="none"))
        ax.semilogy([i], [b.photons_prepared], **kw("THEOREM", marker="s", linestyle="none"))
    ax.set_xlabel("scenario")
    ax.set_ylabel("photons prepared")
    ax.set_title("Cost of calibration uncertainty (point vs interval)")
    _grid(ax)
    if fixture:
        stamp(fig, FIXTURE_WATERMARK)
    return fig
