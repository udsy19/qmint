"""D1 calibration intervals, the frozen-selection holdout guard, and the lane entrypoints."""

from __future__ import annotations

import json

import pytest

from qmint.compiler import calibration as cal
from qmint.compiler.entrypoints import cli_main, run_core_stage
from qmint.core.contracts import EvidenceKind


def test_calibration_reads_only_calibration_runs():
    rows = cal.calibration_rows("X")
    assert sorted(r["run"] for r in rows) == [0, 1, 2, 3, 4, 5]


def test_clopper_pearson_and_drift_interval_contains_iid():
    lo, hi = cal.clopper_pearson(5, 100)
    assert 0.0164 < lo < 0.0165 and 0.1128 < hi < 0.1129  # standard exact CP 95 % for 5/100
    iid, drift = cal.calibration_record("iid"), cal.calibration_record("drift")
    assert drift.qber_interval.lo <= iid.qber_interval.lo and drift.qber_interval.hi >= iid.qber_interval.hi
    assert iid.experiment_family == "schiansky_2023" and iid.data_origin == EvidenceKind.PHOTON_EXPERIMENT
    assert iid.loss_interval is None and iid.multiphoton_interval is None  # not observable: never invented


def test_holdout_locked_until_selection_frozen(tmp_path):
    sel = tmp_path / "sel.json"
    with pytest.raises(cal.HoldoutLocked):
        cal.holdout_rows(sel)
    cal.freeze_selection({"N": 1}, sel)
    rows = cal.holdout_rows(sel)
    assert sorted(r["run"] for r in rows) == [6, 7, 8, 9, 10]
    sel.write_text(json.dumps({"N": 2}))
    with pytest.raises(cal.HoldoutLocked, match="modified"):
        cal.holdout_rows(sel)


def test_cli_optimize_verify_and_unsupported(tmp_path, capsys):
    out = tmp_path / "w1.json"
    assert cli_main(["compiler", "optimize", "--game", "W1", "--eps-unf", "1e-9", "--out", str(out)]) == 0
    data = json.loads(out.read_text())
    assert data["N"] == 73 and data["released"]
    assert cli_main(["compiler", "verify", str(out)]) == 0
    assert cli_main(["compiler", "optimize", "--game", "W2", "--eps-unf", "1e-9"]) == 2
    assert cli_main(["compiler", "optimize", "--game", "S2", "--device", "K22-EXP", "--eps-unf", "1e-9",
                     "--honest", "1e-3", "--small"]) == 1
    assert "INFEASIBLE" in capsys.readouterr().out


def test_run_core_stage(tmp_path):
    res = run_core_stage(seed=0, out_dir=tmp_path)
    assert res["summary"]["small_grid_oracle_agreement"] and all(res["summary"]["released"].values())
    assert all((tmp_path / p).exists() or __import__("pathlib").Path(p).exists() for p in res["outputs"])
