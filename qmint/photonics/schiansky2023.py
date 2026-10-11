"""Reproduce Schiansky et al. 2023 error rates from Zenodo 7979319 and emit calibration (X07).

Usage (from a worktree root; raw archive must already be in the shared cache)::

    python -m qmint.photonics.schiansky2023 --out reports/data_working/schiansky2023

Writes only small derived files (JSON/CSV/PNG) + an EvidenceManifest. Raw data are never
copied into the repository.
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from qmint.core.contracts import Basis, EvidenceKind, EvidenceManifest, ManifestEntry
from qmint.core.serialization import canonical_json, file_sha256
from qmint.photonics.calibration import (
    PUBLISHED_2023,
    RunResult,
    analyze_archive,
    calibration_record,
    published_aggregate_record,
    summarize,
)
from qmint.photonics.zenodo import data_cache_dir

DATASET_RECORD = 7979319
ARCHIVE_UPSTREAM_MD5 = "md5:fd708578a613b63f57c31f986a56bf94"
ARCHIVE_URL = "https://zenodo.org/api/records/7979319/files/Archive.zip/content"
SERIES = {Basis.Z: "#2a78d6", Basis.X: "#eb6834"}  # dataviz reference categorical slots 1, 2


def default_archive() -> Path:
    return data_cache_dir() / f"zenodo_{DATASET_RECORD}" / "Archive.zip"


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def _per_run_rows(runs: list[RunResult]) -> list[dict]:
    rows = []
    for r in runs:
        rows.append(
            {
                "folder": r.folder,
                "chunk": r.chunk,
                "client_basis": r.basis.value,
                "n_pairs": r.n_pairs,
                "n_sifted": r.n_sifted,
                "n_errors": r.n_errors,
                "qber": round(r.n_errors / r.n_sifted, 8),
                "ttp_z_frac": round(r.n_ttp_z / r.n_pairs, 8),
                "dt_median_ns": round(r.dt_quantiles["median"], 6),
                "residual_drift_ns_per_s": round(r.drift_ns_per_s, 6),
                "residual_drift_se": round(r.drift_ns_per_s_se, 6),
                "pairing_violations": r.pairing_violations,
                "rematch_identical": r.rematch_identical,
                "decode_malformed": r.decode_status["malformed"],
                "decode_duplicate": r.decode_status["duplicate"],
                "decode_out_of_range": r.decode_status["out_of_range"],
                "duration_s": round((r.t_last_ns - r.t_first_ns) / 1e9, 6),
            }
        )
    return rows


def _figure(runs: list[RunResult], summaries: dict, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ink, muted, grid = "#0b0b0b", "#52514e", "#e4e3df"
    plt.rcParams.update({"axes.edgecolor": muted, "axes.labelcolor": ink, "xtick.color": muted,
                         "ytick.color": muted, "font.size": 9})
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8), constrained_layout=True)
    # (a) per-run QBER with CP intervals, paper value
    from qmint.photonics.confidence import clopper_pearson

    for ax, b in zip(axes[:2], (Basis.Z, Basis.X), strict=True):
        rs = [r for r in runs if r.basis == b]
        x = np.array([r.chunk for r in rs])
        q = np.array([r.n_errors / r.n_sifted for r in rs]) * 100
        ci = np.array([clopper_pearson(r.n_errors, r.n_sifted) for r in rs]) * 100
        ax.errorbar(x, q, yerr=[q - ci[:, 0], ci[:, 1] - q], fmt="o", ms=5, color=SERIES[b], lw=1.5,
                    capsize=0, label="per run, pooled errors/sifted (95% CP)")
        s = summaries[b]
        pub = PUBLISHED_2023[f"qber_{b.value}_percent"]["value"]
        ax.axhline(pub, color=ink, lw=1, ls="--", label=f"paper: {pub:.2f}%")
        ax.axhline(s.qber_state_avg * 100, color=SERIES[b], lw=1, ls=":",
                   label=f"this work, state-avg: {s.qber_state_avg * 100:.3f}%")
        ax.axhline(s.qber * 100, color=muted, lw=1, ls="-", alpha=0.6,
                   label=f"this work, pooled: {s.qber * 100:.3f}%")
        name = "H/V (Z, folder linear)" if b == Basis.Z else "D/A (X, folder diagonal)"
        ax.set_title(f"Error rate per run, {name}", color=ink, loc="left")
        ax.set_xlabel("run (chunk index; acquisition order assumed)")
        ax.set_ylabel("error rate (%)")
        ax.grid(axis="y", color=grid, lw=0.8)
        ax.set_axisbelow(True)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        lo, hi = ax.get_ylim()
        ax.set_ylim(lo, hi + 0.6 * (hi - lo))  # headroom so the legend never covers data
        ax.legend(frameon=False, fontsize=7.5, loc="upper left")
    # (c) residual offset vs per-run QBER relative to basis mean
    ax = axes[2]
    for b in (Basis.Z, Basis.X):
        rs = [r for r in runs if r.basis == b]
        dm = np.array([r.dt_quantiles["median"] for r in rs])
        rel = np.array([r.n_errors / r.n_sifted for r in rs]) / summaries[b].qber
        ax.plot(dm, rel, "o", ms=6, color=SERIES[b], label=f"{b.value} runs")
    ax.set_title("Residual timing offset vs error rate", color=ink, loc="left")
    ax.set_xlabel("median client - TTP time within run (ns)")
    ax.set_ylabel("run error rate / basis pooled error rate")
    ax.grid(color=grid, lw=0.8)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.legend(frameon=False, fontsize=8)
    fig.savefig(path, dpi=150, metadata={"Software": None})
    plt.close(fig)


def run(archive: Path, out: Path, *, verify_upstream: bool = True) -> dict:
    from qmint.photonics.zenodo import verify_upstream_checksum

    if verify_upstream:
        verify_upstream_checksum(archive, ARCHIVE_UPSTREAM_MD5)
    sha = file_sha256(archive)
    out.mkdir(parents=True, exist_ok=True)
    runs = analyze_archive(archive)
    summaries = {b: summarize(runs, b) for b in (Basis.Z, Basis.X)}
    records = [calibration_record(summaries[b], dataset_sha256=sha, dataset_tag="zenodo7979319", runs=runs)
               for b in (Basis.Z, Basis.X)]
    pub_rec = published_aggregate_record()

    repro = []
    for b in (Basis.Z, Basis.X):
        s, p = summaries[b], PUBLISHED_2023[f"qber_{b.value}_percent"]
        repro.append({
            "quantity": f"average error rate {'H/V' if b == Basis.Z else 'D/A'}",
            "paper_percent": p["value"], "paper_pm_percent": p["pm"], "paper_anchor": p["anchor"],
            "reproduced_state_avg_percent": round(s.qber_state_avg * 100, 4),
            "reproduced_state_avg_se_percent": round(s.qber_state_avg_se * 100, 4),
            "reproduced_pooled_percent": round(s.qber * 100, 4),
            "deviation_state_avg_pp": round(s.qber_state_avg * 100 - p["value"], 4),
            "deviation_pooled_pp": round(s.qber * 100 - p["value"], 4),
            "agrees_within_paper_rounding": abs(round(s.qber_state_avg * 100, 2) - p["value"]) < 1e-9,
            "evidence_kind": EvidenceKind.PHOTON_EXPERIMENT.value,
        })

    def sdict(s):
        d = {k: v for k, v in s.__dict__.items()}
        d["basis"] = s.basis.value
        return d

    summary = {
        "dataset": {"zenodo_record": DATASET_RECORD, "file": "Archive.zip", "sha256": sha,
                    "upstream_checksum": ARCHIVE_UPSTREAM_MD5, "license": "CC-BY-4.0"},
        "format_by_inspection": "ASCII TSV, header 'channel\\ttag', LF; float ns; ttp/client files row-paired",
        "coincidence_rule": "all archived pairs satisfy rint(t_ttp/3ns) == rint(t_client/3ns)",
        "pairing_violations_total": int(sum(r.pairing_violations for r in runs)),
        "rematch_identical_all_runs": all(r.rematch_identical for r in runs),
        "reproduction": repro,
        "basis_summaries": {b.value: sdict(s) for b, s in summaries.items()},
        "residual_drift_ns_per_s": {b.value: [r.drift_ns_per_s for r in runs if r.basis == b]
                                    for b in (Basis.Z, Basis.X)},
        "not_observable_from_archive": ["detection efficiency", "channel loss", "multiphoton probability",
                                        "singles rates / accidental-coincidence rate", "absolute run times"],
        "published_aggregates": PUBLISHED_2023,
    }
    files = {
        "summary.json": json.dumps(json.loads(canonical_json(summary)), indent=1, sort_keys=True) + "\n",
        "calibration_records.json": json.dumps(
            [json.loads(canonical_json(r)) for r in [*records, pub_rec]], indent=1, sort_keys=True) + "\n",
    }
    for name, text in files.items():
        (out / name).write_text(text, encoding="utf-8")
    rows = _per_run_rows(runs)
    with open(out / "per_run.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    _figure(runs, summaries, out / "qber_per_run.png")

    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    entries = [ManifestEntry(path_or_uri=ARCHIVE_URL, sha256=sha, role="input", original_or_derived="original",
                             upstream_checksum=ARCHIVE_UPSTREAM_MD5)]
    for name in ("summary.json", "calibration_records.json", "per_run.csv", "qber_per_run.png"):
        entries.append(ManifestEntry(path_or_uri=str(out / name), sha256=file_sha256(out / name), role="output",
                                     original_or_derived="derived"))
    script = Path(__file__)
    entries.append(ManifestEntry(path_or_uri=f"qmint/photonics/{script.name}", sha256=file_sha256(script),
                                 role="script", original_or_derived="derived"))
    man = EvidenceManifest(
        manifest_id="schiansky2023-x07-reproduction",
        created_utc=now,
        source_urls=["https://zenodo.org/api/records/7979319", "https://zenodo.org/api/records/8020667",
                     "https://www.nature.com/articles/s41467-023-39519-w",
                     "https://www.nature.com/articles/s41467-023-40866-x"],
        retrieved_utc=now,
        command=" ".join([Path(sys.executable).name, "-m", "qmint.photonics.schiansky2023", *sys.argv[1:]]),
        git_sha=_git_sha(),
        environment={"python": platform.python_version(), "numpy": np.__version__},
        seeds=[0],
        evidence_kind=EvidenceKind.PHOTON_EXPERIMENT,
        entries=entries,
    )
    (out / "manifest.json").write_text(
        json.dumps(json.loads(canonical_json(man)), indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--archive", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=Path("reports/data_working/schiansky2023"))
    a = ap.parse_args(argv)
    archive = a.archive or default_archive()
    if not archive.exists():
        print(f"BLOCKED: archive not found at {archive}; download with qmint.photonics.zenodo", file=sys.stderr)
        return 2
    s = run(archive, a.out)
    print(json.dumps(s["reproduction"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
