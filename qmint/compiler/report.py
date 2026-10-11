"""Markdown summary and Fig. 8/9 data plots for the lane-I compiler experiments (generated, never hand-edited)."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _fmt(x: Any, digits: int = 3) -> str:
    if x is None:
        return "-"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, int):
        return f"{x:,}"
    if isinstance(x, float):
        return f"{x:.{digits}g}"
    return str(x)


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(_fmt(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def _pick(rows: list[dict[str, Any]], **kw: Any) -> dict[str, Any] | None:
    hits = [r for r in rows if all(r.get(k) == v for k, v in kw.items())]
    return hits[0] if hits else None


def write_markdown(results: dict[str, Any], rows: list[dict[str, Any]], path: Path) -> None:
    m, g5, x12, x13 = results["meta"], results["g5"], results["x12"], results["x13"]
    out: list[str] = [
        "# Lane I: certificate compiler experiments X12 / X13 (generated)",
        "",
        f"Pre-registration commit `{m['preregistration_commit']}`; frozen_experiments.yaml sha256 `{m['frozen_experiments_sha256'][:16]}...`; "
        f"software revision `{m['software_revision']}`; runtime {m['runtime_seconds']} s.",
        "",
        "Evidence: bounds = PUBLISHED_THEOREM re-derived by lane D's independent checker (S2/W1/S1); D1 = PUBLISHED_AGGREGATE, "
        "never certified. Kent Fig. 5 devices are DIGITIZED_FIGURE; half-beta devices and all interval boxes are HYPOTHETICAL. "
        "Issuance seconds use a HYPOTHETICAL 1e8 Hz rate (MODELLED). These are bounds under declared Table 6 idealisations, "
        "not experimental security evidence for any device.",
        "",
        "## G5 verdict",
        "",
        f"**{g5['verdict']}**. Rule: {g5['rule']}",
        "",
        f"Released certificates: {g5['released_certificates']}; independent-checker rejections among emitted candidates: "
        f"{g5['checker_rejections_total']}.",
        "",
    ]
    t = []
    for d in g5["per_device"]:
        for unc in ("point", "interval"):
            r = d[unc]
            t.append([d["device"], unc, r["published_N"] or r["published_status"], r["naive_N"] or r["naive_status"],
                      r["compiler_N"] or r["compiler_status"], r["ratio_naive_over_compiler"], r["ratio_published_over_compiler"]])
    out += ["Primary cell (eps_unf <= 1e-9, honest failure <= 1e-3, M = 1). N = prepared pulses per token; only CERTIFIED results get a number.", "",
            _table(["device", "uncertainty", "published N", "naive N", "compiler N", "naive/compiler", "published/compiler"], t), ""]

    # eps sweep at honest 1e-3
    out += ["## X12: S2 target sweep (honest failure <= 1e-3, M = 1, certified N)", ""]
    t = []
    for dev in sorted({r["device"] for r in rows if r["experiment"] == "X12-S2"}):
        for unc in ("point", "interval"):
            for eps in (1e-3, 1e-6, 1e-9, 1e-12):
                cells = []
                for sel in ("published_fixed", "naive_analytic", "compiler"):
                    r = _pick(rows, experiment="X12-S2", device=dev, uncertainty=unc, eps_unf_target=eps, selector=sel,
                              honest_target=1e-3)
                    cells.append(r["N"] if r and r["released"] else (r["status"] if r else "-"))
                t.append([dev, unc, eps, *cells])
    out += [_table(["device", "unc", "eps_unf", "published", "naive", "compiler"], t), ""]

    out += ["## X12: ideal games (all four selectors, CERTIFIED)", ""]
    t = [[r["game"], r["eps_unf_target"], r["selector"], r["N"], r["closed_form_n_min"], r["certificate_status"]]
         for r in x12["ideal"]]
    out += [_table(["game", "eps_unf", "selector", "N", "closed form", "checker"], t), ""]

    out += ["## X12: compiler vs exhaustive oracle on the small grids", ""]
    t = [[a["scenario_id"], a["grid_points"], a["oracle_N"] or a["oracle_status"], a["compiler_N"] or a["compiler_status"],
          a["identical"], a["oracle_engine_calls"], a["compiler_engine_calls"], a["oracle_seconds"], a["compiler_seconds"],
          a["oracle_peak_bytes"], a["compiler_peak_bytes"]] for a in x12["oracle_agreement"]]
    out += [_table(["scenario", "grid pts", "oracle N", "compiler N", "identical", "oracle calls", "compiler calls",
                    "oracle s", "compiler s", "oracle peak B", "compiler peak B"], t), ""]

    out += ["## X12: published recipes at matched security", ""]
    t = [[x["scenario"], x["mode"], x.get("published_N"), x.get("compiler_N"), x.get("ratio_published_over_compiler"),
          x.get("caveat") or x.get("certification") or x.get("published", "")] for x in x12["published_matched"]]
    out += [_table(["scenario", "match", "published N", "compiler N", "published/compiler", "note"], t), ""]

    out += ["## X12: rejections and infeasibility certificates", ""]
    t = [[x["case"], x["outcome"], (x.get("reason") or "")[:160]] for x in x12["rejections_and_infeasibility"]]
    out += [_table(["request", "outcome", "reason"], t), ""]

    out += ["## X12: D1 (Schiansky 2023) -- UNCERTIFIED by construction", "",
            "Lane D's checker never certifies D1 (fitted SDP boundary, informal de Finetti, open Chernoff question). "
            "Numbers below are numerical support only and are excluded from every certified comparison and Pareto front.", ""]
    t = []
    for dev in ("D1-PUB-SI", "D1-PUB-INT", "D1-ZEN-IID", "D1-ZEN-DRIFT"):
        for eps in (1e-6, 1e-9, 1e-12):
            cells = []
            for sel in ("published_fixed", "naive_analytic", "compiler"):
                r = _pick(rows, experiment="X12-D1", device=dev, eps_unf_target=eps, honest_target=1e-3, selector=sel)
                cells.append(r["N"] if r and r["status"] == "FEASIBLE" else (r["status"] if r else "-"))
            t.append([dev, eps, *cells])
    out += [_table(["device", "eps_unf", "published", "naive", "compiler"], t), ""]

    out += ["## X13: uncertainty ablation (S2, honest <= 1e-3)", ""]
    t = [[u["device"], u["eps_unf"], u["selector"], u["N_point"] or u["point_status"], u["N_interval"] or u["interval_status"],
          u["point_selection_under_interval"]] for u in x13["uncertainty"] if u["honest"] == 1e-3]
    out += [_table(["device", "eps_unf", "selector", "N point", "N interval", "point selection re-scored on interval box"], t), ""]

    d = x13["drift_holdout"]
    out += ["## X13: IID vs drift-aware calibration, frozen selection, holdout runs 6-10 (D1, UNCERTIFIED)", "",
            f"Frozen selection sha256 `{d['frozen_selection_sha256'][:16]}...`. Calibration e_h intervals: "
            f"IID {_fmt(d['calibration_intervals']['iid']['lo'], 4)}-{_fmt(d['calibration_intervals']['iid']['hi'], 4)}, "
            f"drift-aware {_fmt(d['calibration_intervals']['drift']['lo'], 4)}-{_fmt(d['calibration_intervals']['drift']['hi'], 4)}. "
            f"Holdout coverage: IID {d['coverage_iid']:.0%}, drift-aware {d['coverage_drift']:.0%}.", ""]
    t = [[h["run"], h["qber"], h["inside_iid"], h["inside_drift"], h.get("D1-ZEN-IID_frozen_config_on_holdout"),
          h.get("D1-ZEN-DRIFT_frozen_config_on_holdout")] for h in d["holdout_runs"]]
    out += [_table(["run", "QBER (X)", "in IID", "in drift", "IID-selected config", "drift-selected config"], t), ""]

    out += ["## X13: fixed N vs joint thresholds (S2, primary cell)", ""]
    t = [[f["device"], f["uncertainty"], f["published_log10_eps_unf_at_4e7"], f["thresholds_optimised_log10_eps_unf_at_4e7"],
          f["N_thresholds_fixed_by_rule (naive)"], f["N_joint (compiler)"]] for f in x13["fixed_n_vs_joint"]]
    out += [_table(["device", "unc", "log10 eps_unf published @4e7", "log10 eps_unf thresholds optimised @4e7",
                    "N naive", "N joint"], t), ""]

    out += ["## X13: presentation points (Theorem 2, C = L(L-1)/2)", ""]
    t = [[s["device"], s["uncertainty"], s["presentation_points"], s["C"], s["N"] if s["released"] else s["status"]]
         for s in x13["sites"]]
    out += [_table(["device", "unc", "points 2^M", "C", "compiler N"], t), ""]

    c = x13["checker"]
    out += ["## Checker accounting", "",
            f"Released (CERTIFIED by lane D's independent checker): {c['released']}. Rejected by the checker: {c['checker_rejections']}. "
            f"D1 certificates UNCERTIFIED by construction: {c['uncertified_by_construction_D1']}.", ""]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def write_figures(pareto: list[dict[str, Any]], unc: list[dict[str, Any]], out_dir: Path) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    paths = []
    devs = sorted({p["device"] for p in pareto})
    styles = {"published_fixed": ("s", "-"), "naive_analytic": ("^", "--"), "compiler": ("o", ":")}
    fig, axes = plt.subplots(1, max(1, len(devs)), figsize=(4 * max(1, len(devs)), 3.6), squeeze=False)
    for ax, dev in zip(axes[0], devs, strict=False):
        for sel, (mk, ls) in styles.items():
            for unc_kind, fill in (("point", True), ("interval", False)):
                pts = sorted((p["eps_unf_target"], p["N"]) for p in pareto
                             if p["device"] == dev and p["selector"] == sel and p["uncertainty"] == unc_kind and p["honest_target"] == 1e-3)
                if pts:
                    ax.plot([x for x, _ in pts], [y for _, y in pts], marker=mk, linestyle=ls,
                            fillstyle="full" if fill else "none", label=f"{sel} ({unc_kind})")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.invert_xaxis()
        ax.set_title(dev, fontsize=9)
        ax.set_xlabel("target eps_unf (honest <= 1e-3)")
        ax.set_ylabel("certified N (pulses)")
    axes[0][0].legend(fontsize=6)
    fig.suptitle("Fig. 8 data: CERTIFIED S2 resource vs target (KLPR2022 bound; devices DIGITIZED/HYPOTHETICAL)", fontsize=8)
    fig.tight_layout()
    p = out_dir / "fig8_pareto_s2.png"
    fig.savefig(p, dpi=120, bbox_inches="tight")
    plt.close(fig)
    paths.append(p)

    rows = [u for u in unc if u["selector"] == "compiler" and u["honest"] == 1e-3 and u["eps_unf"] == 1e-9]
    fig, ax = plt.subplots(figsize=(7, 3.4))
    xs = range(len(rows))
    ax.bar([x - 0.2 for x in xs], [u["N_point"] or 0 for u in rows], width=0.4, label="point device")
    ax.bar([x + 0.2 for x in xs], [u["N_interval"] or 0 for u in rows], width=0.4, label="interval box (worst case)")
    for x, u in zip(xs, rows, strict=True):
        if u["N_interval"] is None:
            ax.text(x + 0.2, 1, "INFEASIBLE", rotation=90, fontsize=7, ha="center", va="bottom")
    ax.set_yscale("log")
    ax.set_xticks(list(xs))
    ax.set_xticklabels([u["device"] for u in rows], rotation=20, fontsize=7)
    ax.set_ylabel("compiler certified N")
    ax.set_title("Fig. 9 data: cost of uncertainty (eps_unf 1e-9, honest 1e-3; boxes HYPOTHETICAL)", fontsize=8)
    ax.legend(fontsize=7)
    p = out_dir / "fig9_uncertainty_ablation.png"
    fig.savefig(p, dpi=120, bbox_inches="tight")
    plt.close(fig)
    paths.append(p)
    return paths
