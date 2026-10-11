"""D1 calibration from lane E's per-run Zenodo table, with a frozen-selection holdout guard.

Only the D1 (Schiansky 2023) proof model may consume these records (experiment_family
``schiansky_2023``); the DSL rejects them for S2/W1. Calibration rows are runs 0-5; holdout rows
(runs 6-10, ``benchmarks/holdouts.yaml``) are readable ONLY through ``holdout_rows`` after a selection
has been frozen with ``freeze_selection``.

Interval methods (pre-registered):
  iid    Clopper-Pearson 95 % on errors/sifted pooled over the calibration runs (assumes iid trials)
  drift  hull(iid, Student-t 95 % prediction interval for the QBER of a NEW run from the per-run QBERs);
         motivated by lane E's run-level overdispersion (chi2/dof ~ 10)
"""

from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path
from typing import Any

import yaml
from scipy import stats

from qmint.compiler.constraints import ROOT
from qmint.core.contracts import CalibrationRecord, EvidenceKind, Interval, Unit
from qmint.core.serialization import canonical_json, file_sha256, sha256_hex

HOLDOUTS_PATH = ROOT / "benchmarks" / "holdouts.yaml"
LANE_E_RECORDS = ROOT / "reports" / "data_working" / "schiansky2023" / "calibration_records.json"
CONF = 0.95


class HoldoutLocked(RuntimeError):
    """Holdout rows requested before a selection was frozen (or the frozen selection was altered)."""


def _holdout_spec() -> dict[str, Any]:
    return yaml.safe_load(HOLDOUTS_PATH.read_text(encoding="utf-8"))["holdouts"][0]


def _runs(rule: str) -> set[int]:
    m = re.search(r"(\d+)\.\.(\d+)", rule)
    if not m:
        raise ValueError(f"cannot parse run range {rule!r}")
    return set(range(int(m.group(1)), int(m.group(2)) + 1))


def _read(basis: str, runs: set[int]) -> list[dict[str, Any]]:
    spec = _holdout_spec()
    path = ROOT / spec["source_file"]
    if file_sha256(path) != spec["source_sha256_at_registration"]:
        raise HoldoutLocked(f"{path} changed since pre-registration")
    with open(path, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["client_basis"] == basis and int(r[spec["split_column"]]) in runs]
    return [{"run": int(r["chunk"]), "n_sifted": int(r["n_sifted"]), "n_errors": int(r["n_errors"]),
             "n_pairs": int(r["n_pairs"]), "qber": float(r["qber"])} for r in rows]


def calibration_rows(basis: str = "X") -> list[dict[str, Any]]:
    return _read(basis, _runs(_holdout_spec()["calibration_rows"]))


def clopper_pearson(k: int, n: int, conf: float = CONF) -> tuple[float, float]:
    a = 1 - conf
    lo = 0.0 if k == 0 else float(stats.beta.ppf(a / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(stats.beta.ppf(1 - a / 2, k + 1, n - k))
    return lo, hi


def prediction_interval(values: list[float], conf: float = CONF) -> tuple[float, float]:
    k = len(values)
    if k < 2:
        raise ValueError("prediction interval needs >= 2 runs")
    mean = sum(values) / k
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (k - 1))
    half = float(stats.t.ppf(1 - (1 - conf) / 2, k - 1)) * sd * math.sqrt(1 + 1 / k)
    return max(0.0, mean - half), min(1.0, mean + half)


def qber_interval(rows: list[dict[str, Any]], method: str) -> tuple[float, float, float]:
    """(lo, hi, point) of the QBER from calibration rows; point = pooled errors/sifted."""
    k, n = sum(r["n_errors"] for r in rows), sum(r["n_sifted"] for r in rows)
    point = k / n
    lo, hi = clopper_pearson(k, n)
    if method == "drift":
        plo, phi = prediction_interval([r["qber"] for r in rows])
        lo, hi = min(lo, plo), max(hi, phi)
    elif method != "iid":
        raise ValueError(f"unknown interval method {method!r}")
    return lo, hi, point


def calibration_record(method: str, basis: str = "X", rows: list[dict[str, Any]] | None = None,
                       tag: str = "calib-runs-0-5") -> CalibrationRecord:
    rows = calibration_rows(basis) if rows is None else rows
    lo, hi, point = qber_interval(rows, method)
    desc = {"iid": "clopper_pearson_pooled_95",
            "drift": "hull(clopper_pearson_pooled_95, student_t_95_prediction_interval_new_run)"}[method]
    return CalibrationRecord(
        calibration_id=f"laneI-sch23-{basis}-{tag}-{method}-v1",
        device_id="schiansky2023_ttp_client_641m_fiber",
        experiment_family="schiansky_2023",
        data_origin=EvidenceKind.PHOTON_EXPERIMENT,
        dataset_sha256=_zenodo_sha(),
        n_events=sum(r["n_pairs"] for r in rows),
        qber_interval=Interval(lo=lo, hi=hi, point=point, unit=Unit.FRACTION),
        confidence_level=CONF,
        interval_method=f"{desc}; runs {sorted(r['run'] for r in rows)} basis {basis}; qber = errors/sifted",
        independence_assumptions=[
            "coincidences = lane E archived pairs (authors' 3-ns rounded-bin rule)",
            "iid: Bernoulli errors within the pooled runs" if method == "iid"
            else "drift: runs exchangeable; next run drawn from the same between-run distribution",
            "loss and multiphoton NOT observable from the archive: taken from PUBLISHED_AGGREGATE values",
        ],
    )


def _zenodo_sha() -> str:
    """Archive hash of Zenodo 7979319 as recorded by lane E (the per-run table derives from it)."""
    recs = json.loads(LANE_E_RECORDS.read_text(encoding="utf-8"))
    shas = {r["dataset_sha256"] for r in recs if r["data_origin"] == "PHOTON_EXPERIMENT"}
    if len(shas) != 1:
        raise ValueError(f"expected one Zenodo archive hash in lane E records, got {shas}")
    return shas.pop()


# --------------------------------------------------------------------------- #
# Holdout guard
# --------------------------------------------------------------------------- #


def freeze_selection(selection: dict[str, Any], path: Path) -> str:
    """Write the selection (canonical JSON) and a lock file recording its SHA-256; return the SHA."""
    text = canonical_json(selection)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    sha = sha256_hex(text)
    path.with_suffix(".lock.json").write_text(json.dumps({"selection_sha256": sha}), encoding="utf-8")
    return sha


def holdout_rows(frozen_selection: Path, basis: str = "X") -> list[dict[str, Any]]:
    lock = frozen_selection.with_suffix(".lock.json")
    if not frozen_selection.exists() or not lock.exists():
        raise HoldoutLocked("holdout runs are locked until a selection is frozen (freeze_selection)")
    if file_sha256(frozen_selection) != json.loads(lock.read_text())["selection_sha256"]:
        raise HoldoutLocked("frozen selection was modified after freezing")
    return _read(basis, _runs(_holdout_spec()["holdout_rows"]))
