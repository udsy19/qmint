"""Regenerate paper figures and tables from merged code and committed evidence.

    python -m qmint.evaluation.make_figures --out figures [--tables-out reports/paper] [--only fig02,fig05]
                                            [--force] [--check]

Per figure ``<stem>`` the output directory gets ``<stem>.svg/.png/.csv``, ``<stem>.manifest.json``
(C6 EvidenceManifest pinning every input, executed module and output by sha256, plus git sha and
environment lock) and ``<stem>.caption.json`` (status, caption, evidence kinds, manifest id/sha).

Stale-cache rejection: a figure is rebuilt when its manifest is missing, any pinned hash differs,
the spec's input/script set changed, or the caption no longer matches the manifest. ``--check``
only reports staleness (exit 1 if anything is stale). PENDING figures are always re-evaluated.
"""

from __future__ import annotations

import argparse
import csv
import json
import shlex
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

from qmint.core.contracts import EvidenceKind
from qmint.core.manifest import build_manifest, load_manifest, verify_manifest, write_manifest
from qmint.core.serialization import file_sha256
from qmint.evaluation import plots
from qmint.evaluation.experiments import FIGURES, ROOT, FigureSpec, FigureStatus
from qmint.evaluation.tables import build_tables


class StaleFigureError(RuntimeError):
    """A figure's pinned inputs, code or outputs no longer match its manifest."""


def paths(out: Path, spec: FigureSpec) -> dict[str, Path]:
    base = out / spec.stem
    return {k: base.with_name(f"{spec.stem}{ext}") for k, ext in
            (("svg", ".svg"), ("png", ".png"), ("csv", ".csv"), ("caption", ".caption.json"),
             ("manifest", ".manifest.json"))}


def _rel(p: Path, root: Path) -> str:
    try:
        return p.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return p.resolve().as_posix()


def _write_csv(rows: list[dict[str, Any]], path: Path, status: FigureStatus) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        if not rows:  # a missing result is written as PENDING, never as a zero
            f.write(f"status\n{status.value}\n")
            return
        cols: list[str] = []
        for r in rows:
            cols += [k for k in r if k not in cols]
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def build_figure(spec: FigureSpec, root: Path, out: Path, command: str) -> dict[str, Any]:
    p = paths(out, spec)
    out.mkdir(parents=True, exist_ok=True)
    res = spec.build(root)
    synthetic = EvidenceKind.SYNTHETIC in res.evidence_kinds
    res.fig.savefig(p["svg"], format="svg", metadata={"Date": None})
    res.fig.savefig(p["png"], dpi=200, metadata={"Software": None})
    legend = plots.legend_labels(res.fig)
    plt.close(res.fig)
    _write_csv(res.rows, p["csv"], res.status)
    kind = spec.primary_evidence if res.status == FigureStatus.READY else EvidenceKind.UNCERTIFIED
    manifest = build_manifest(
        manifest_id=f"figure-{spec.stem}", command=command, evidence_kind=kind, root=root,
        inputs=list(spec.inputs), outputs=[p["svg"], p["png"], p["csv"]], scripts=list(spec.scripts),
        source_urls=res.sources,
    )
    write_manifest(manifest, p["manifest"])
    caption = {
        "figure_id": spec.fig_id, "title": spec.title, "status": res.status.value, "caption": res.caption,
        "evidence_kinds": [k.value for k in res.evidence_kinds],
        "evidence_tags": sorted({plots.TAG_OF_KIND[k] for k in res.evidence_kinds}),
        "synthetic_content": synthetic, "legend": legend,
        "manifest_id": manifest.manifest_id, "manifest_path": _rel(p["manifest"], root),
        "manifest_sha256": file_sha256(p["manifest"]),
        "inputs": [{"path": e.path_or_uri, "sha256": e.sha256} for e in manifest.entries if e.role == "input"],
        "data_csv": _rel(p["csv"], root), "outputs": [_rel(p[k], root) for k in ("svg", "png", "csv")],
        "sources": res.sources, "notes": res.notes, "generated_by": command,
    }
    p["caption"].write_text(json.dumps(caption, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return caption


def staleness(spec: FigureSpec, root: Path, out: Path) -> list[str]:
    """Reasons the cached figure must be rebuilt; empty list = fresh."""
    p = paths(out, spec)
    if not p["caption"].is_file() or not p["manifest"].is_file():
        return ["no cached caption/manifest"]
    caption = json.loads(p["caption"].read_text(encoding="utf-8"))
    if caption.get("status") != FigureStatus.READY.value:
        return [f"status {caption.get('status')}: always re-evaluated"]
    reasons = []
    if caption.get("manifest_sha256") != file_sha256(p["manifest"]):
        reasons.append("caption does not match manifest")
    m = load_manifest(p["manifest"])
    reasons += [f"{c.status}: {c.path_or_uri}" for c in verify_manifest(m, root) if c.status != "OK"]
    pinned = {e.path_or_uri for e in m.entries if e.role in ("input", "script")}
    if pinned != set(spec.inputs) | set(spec.scripts):
        reasons.append("figure spec inputs/scripts changed")
    return reasons


def require_fresh(spec: FigureSpec, root: Path, out: Path) -> dict[str, Any]:
    """Return the caption of a fresh READY figure, or raise :class:`StaleFigureError`."""
    reasons = staleness(spec, root, out)
    if reasons:
        raise StaleFigureError(f"{spec.fig_id} is stale: " + "; ".join(reasons))
    return json.loads(paths(out, spec)["caption"].read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="figures")
    ap.add_argument("--tables-out", default="reports/paper")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--only", default="", help="comma-separated figure ids (default: all)")
    ap.add_argument("--force", action="store_true", help="rebuild even when fresh")
    ap.add_argument("--check", action="store_true", help="report staleness only; exit 1 if any figure is stale")
    ap.add_argument("--no-tables", action="store_true")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    out = Path(args.out) if Path(args.out).is_absolute() else root / args.out
    wanted = {s.strip() for s in args.only.split(",") if s.strip()}
    specs = [s for s in FIGURES if not wanted or s.fig_id in wanted]
    if wanted - {s.fig_id for s in FIGURES}:
        ap.error(f"unknown figure ids: {sorted(wanted - {s.fig_id for s in FIGURES})}")
    command = "python -m qmint.evaluation.make_figures " + " ".join(shlex.quote(a) for a in (argv or sys.argv[1:]))
    stale_any, index = False, []
    for spec in specs:
        reasons = staleness(spec, root, out)
        if args.check:
            pending = bool(reasons) and reasons[0].startswith("status ")
            stale_any |= bool(reasons) and not pending
            state = "PENDING (re-evaluated on every build)" if pending else (
                "STALE (" + "; ".join(reasons) + ")" if reasons else "FRESH")
            print(f"{spec.fig_id}: {state}")
            continue
        if reasons or args.force:
            cap = build_figure(spec, root, out, command)
            print(f"{spec.fig_id}: built {cap['status']}")
        else:
            cap = require_fresh(spec, root, out)
            print(f"{spec.fig_id}: fresh {cap['status']}")
        index.append({"figure_id": spec.fig_id, "status": cap["status"], "title": spec.title,
                      "caption": _rel(paths(out, spec)["caption"], root), "manifest_id": cap["manifest_id"]})
    if args.check:
        return 1 if stale_any else 0
    if not wanted:
        (out / "index.json").write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
    if not args.no_tables:
        t_out = Path(args.tables_out) if Path(args.tables_out).is_absolute() else root / args.tables_out
        for p in build_tables(root, t_out):
            print(f"table: {_rel(p, root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
