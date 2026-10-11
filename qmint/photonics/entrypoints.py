"""Lane E entrypoints for ``qmint data ...``, run_core and run_all (see ``qmint.core.lanes``).

    qmint data fetch zenodo:7979319 [--out DIR]          (needs QMINT_ALLOW_NETWORK=1)
    qmint data validate --source zenodo:7979319 [--report reports/data_audit.json] [--out DIR]

Raw data live in the shared cache outside the repository (``qmint.photonics.zenodo.data_cache_dir``,
default /Users/udsy/PycharmProjects/qmint-data-cache, override QMINT_DATA_CACHE).

* ``run_core_stage``: SYNTHETIC timetag fixtures with known ground truth (lane E's generator in
  tests/unit/photonics/photonics_synth.py); checks the analysis pipeline recovers the planted error
  counts. Every number is labelled SYNTHETIC -- never experimental evidence, never a CalibrationRecord.
* ``run_realdata_stage``: the Schiansky 2023 reproduction on the verified Zenodo 7979319 archive
  (PHOTON_EXPERIMENT). A missing archive is a reasoned skip; fixtures are never substituted.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from qmint.core.contracts import Basis, EvidenceKind
from qmint.core.lanes import StageSkipped, write_stage_json

REPO_ROOT = Path(__file__).resolve().parents[2]
SYNTH_FIXTURE = REPO_ROOT / "tests" / "unit" / "photonics" / "photonics_synth.py"
#: Planted ground truth of ``photonics_synth.standard_archive`` (errors, sifted) per basis.
SYNTH_TRUTH = {Basis.Z: (8, 400), Basis.X: (6, 400)}


def _archive(cache_dir: Path | None, record: int) -> Path:
    """Prefer ``<cache_dir>/zenodo_<id>/Archive.zip`` (run_all convention), else the shared cache."""
    from qmint.photonics.zenodo import data_cache_dir

    for base in [p for p in (cache_dir, data_cache_dir()) if p is not None]:
        cand = Path(base) / f"zenodo_{record}" / "Archive.zip"
        if cand.is_file():
            return cand
    raise FileNotFoundError(f"zenodo:{record} Archive.zip not in {cache_dir} or {data_cache_dir()}")


def _summary_dict(s: Any) -> dict[str, Any]:
    d = dict(s.__dict__)
    d["basis"] = s.basis.value
    return d


def run_core_stage(*, seed: int, out_dir: Path) -> dict[str, Any]:
    del seed  # the fixture generator uses its own fixed seeds (ground truth is planted, not sampled)
    if not SYNTH_FIXTURE.is_file():
        raise StageSkipped(f"synthetic fixture generator not present: {SYNTH_FIXTURE}")
    from qmint.photonics.calibration import analyze_archive, summarize

    spec = importlib.util.spec_from_file_location("qmint_photonics_synth_fixture", SYNTH_FIXTURE)
    synth = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(synth)  # type: ignore[union-attr]
    with tempfile.TemporaryDirectory() as td:
        runs = analyze_archive(synth.standard_archive(Path(td) / "synthetic.zip"))
    summaries = {b: summarize(runs, b) for b in (Basis.Z, Basis.X)}
    got = {b: (s.n_errors, s.n_sifted) for b, s in summaries.items()}
    if got != SYNTH_TRUTH:
        raise RuntimeError(f"pipeline did not recover planted counts: {got} != {SYNTH_TRUTH}")
    res = {
        "evidence_kind": EvidenceKind.SYNTHETIC.value,
        "label": synth.SYNTHETIC_TAG,
        "planted_truth_errors_sifted": {b.value: list(v) for b, v in SYNTH_TRUTH.items()},
        "recovered": {b.value: _summary_dict(s) for b, s in summaries.items()},
        "pairing_violations": sum(r.pairing_violations for r in runs),
    }
    return {"outputs": [write_stage_json(out_dir, "photonics_synthetic.json", res)]}


def run_realdata_stage(*, seed: int, out_dir: Path, cache_dir: Path) -> dict[str, Any]:
    del seed
    from qmint.photonics import schiansky2023

    try:
        archive = _archive(cache_dir, schiansky2023.DATASET_RECORD)
    except FileNotFoundError as e:
        raise StageSkipped(f"real dataset absent (fetch with `qmint data fetch`): {e}") from e
    summary = schiansky2023.run(archive, out_dir, verify_upstream=True)
    if not all(r["agrees_within_paper_rounding"] for r in summary["reproduction"]):
        raise RuntimeError(f"published QBERs not reproduced: {summary['reproduction']}")
    return {"outputs": sorted(p for p in out_dir.iterdir() if p.is_file())}


def _parse_source(src: str) -> int:
    kind, _, rid = src.partition(":")
    if kind != "zenodo" or not rid.isdigit():
        raise ValueError(f"source must look like zenodo:<record id>, got {src!r}")
    return int(rid)


def _fetch(record: int, out: Path | None) -> int:
    from qmint.core.config import load_config
    from qmint.photonics import zenodo

    if not load_config().allow_network:
        print("REFUSED: network access is denied by default; set QMINT_ALLOW_NETWORK=1 to fetch", file=sys.stderr)
        return 1
    dest = out or zenodo.data_cache_dir() / f"zenodo_{record}"
    files = zenodo.record_files(zenodo.fetch_record(record))
    paths = [zenodo.download(f, dest) for f in files]  # upstream checksum verified per file
    for f, p in zip(files, paths, strict=True):
        print(f"OK {f.key} -> {p} (upstream {f.upstream_checksum} verified)")
    return 0


def _validate(record: int, report: Path | None, out: Path) -> int:
    from qmint.photonics import schiansky2023

    if record != schiansky2023.DATASET_RECORD:
        print(f"UNSUPPORTED: validation is implemented for zenodo:{schiansky2023.DATASET_RECORD} only",
              file=sys.stderr)
        return 2
    try:
        archive = _archive(None, record)
    except FileNotFoundError as e:
        print(f"BLOCKED: {e}", file=sys.stderr)
        return 1
    summary = schiansky2023.run(archive, out, verify_upstream=True)
    doc = {"source": f"zenodo:{record}", "dataset": summary["dataset"], "reproduction": summary["reproduction"],
           "pairing_violations_total": summary["pairing_violations_total"], "derived_outputs": str(out)}
    if report is not None:
        write_stage_json(report.parent, report.name, doc)
    print(json.dumps(doc, indent=1, sort_keys=True))
    return 0 if all(r["agrees_within_paper_rounding"] for r in summary["reproduction"]) else 1


def cli_main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="qmint data", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="action", required=True)
    f = sub.add_parser("fetch", help="download a Zenodo record into the shared cache (checksum-verified)")
    f.add_argument("source", help="zenodo:<record id>")
    f.add_argument("--out", type=Path, help="destination dir (default <cache>/zenodo_<id>)")
    f.add_argument("--verify-hash", action="store_true", help="accepted for plan compatibility (always on)")
    v = sub.add_parser("validate", help="verify and re-analyse a cached dataset")
    v.add_argument("--source", required=True)
    v.add_argument("--report", type=Path)
    v.add_argument("--out", type=Path, default=Path("experiments/data_validate/zenodo_7979319"))
    a = ap.parse_args(argv[1:])
    try:
        record = _parse_source(a.source)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    return _fetch(record, a.out) if a.action == "fetch" else _validate(record, a.report, a.out)
