"""`qmint` CLI: executable via `python -m qmint.cli`, lazy lane dispatch, never fakes output."""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from qmint import cli
from qmint.core import lanes

ROOT = Path(__file__).resolve().parents[2]


def run_cli(*args, env=None):
    return subprocess.run([sys.executable, "-m", "qmint.cli", *args], cwd=ROOT, capture_output=True, text=True,
                          env=env)


def test_doctor_executable_json(tmp_path):
    report_path = tmp_path / "env.json"
    r = run_cli("doctor", "--json", "--report", str(report_path))
    assert r.returncode == 0, r.stderr
    rep = json.loads(r.stdout)
    assert rep == json.loads(report_path.read_text())
    assert rep["status"] == "OK" and isinstance(rep["network_allowed"], bool)
    assert {d["status"] for d in rep["dependencies"]["optional"]} <= {"OK", "SKIPPED", "LOCK_MISMATCH"}
    assert all(isinstance(v, bool) for v in rep["secrets_present"].values())


def test_doctor_table_mode():
    r = run_cli("doctor")
    assert r.returncode == 0 and "status: OK" in r.stdout


def test_optional_dependency_skipped_not_failed(monkeypatch):
    from qmint.core import doctor
    from qmint.core.config import load_config

    monkeypatch.setattr(doctor, "OPTIONAL", [("qmint_no_such_pkg", "qmint-no-such-pkg", "sdp")])
    rep = doctor.run_doctor(load_config())
    (dep,) = rep["dependencies"]["optional"]
    assert dep["status"] == "SKIPPED" and "install extra [sdp]" in dep["reason"]
    assert rep["status"] == "OK"
    monkeypatch.setattr(doctor, "REQUIRED", [("qmint_no_such_pkg", "qmint-no-such-pkg", "core")])
    assert doctor.run_doctor(load_config())["status"] == "FAIL"


@pytest.mark.parametrize("cmd", sorted(lanes.LANE_COMMANDS))
def test_every_plan_command_registered(cmd):
    status, detail = lanes.probe(lanes.LANE_COMMANDS[cmd])
    if status == "NOT_AVAILABLE":
        r = run_cli(cmd, "--help")
        assert r.returncode == cli.EXIT_NOT_AVAILABLE
        assert r.stderr.startswith("NOT_AVAILABLE: lane ") and "not merged" in r.stderr
        assert r.stdout == ""  # no fabricated output


@pytest.fixture
def fake_lanes(tmp_path, monkeypatch):
    pkg = tmp_path / "fakelane"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "good.py").write_text(textwrap.dedent("""
        CALLS = []
        def cli_main(argv):
            CALLS.append(argv)
            return 0
    """))
    (pkg / "noentry.py").write_text("X = 1\n")
    (pkg / "broken.py").write_text("import qmint_definitely_missing_dependency\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    reg = {
        "good": lanes.LaneEntry("Z", "fakelane.good", ""),
        "noentry": lanes.LaneEntry("Z", "fakelane.noentry", ""),
        "broken": lanes.LaneEntry("Z", "fakelane.broken", ""),
        "absent": lanes.LaneEntry("Z", "fakelane.absent", ""),
    }
    monkeypatch.setattr(lanes, "LANE_COMMANDS", reg)
    return reg


def test_dispatch_passes_argv_verbatim(fake_lanes):
    assert cli.main(["good", "run", "--suite", "x", "--help"]) == 0
    import fakelane.good

    assert fakelane.good.CALLS == [["good", "run", "--suite", "x", "--help"]]


def test_dispatch_not_available_and_broken(fake_lanes, capsys):
    assert cli.main(["absent", "x"]) == cli.EXIT_NOT_AVAILABLE
    assert "NOT_AVAILABLE: lane Z module fakelane.absent not merged" in capsys.readouterr().err
    assert cli.main(["noentry"]) == cli.EXIT_NOT_AVAILABLE
    assert "has no cli_main()" in capsys.readouterr().err
    assert cli.main(["broken"]) == cli.EXIT_BROKEN  # missing dependency is an error, not a skip
    assert "BROKEN" in capsys.readouterr().err


def test_sources_not_available_without_lane_a(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("QMINT_ROOT", str(tmp_path))
    assert cli.main(["sources", "list", "--type", "paper"]) == cli.EXIT_NOT_AVAILABLE
    assert "NOT_AVAILABLE: lane A" in capsys.readouterr().err


def test_sources_lists_lane_a_register(monkeypatch, tmp_path, capsys):
    (tmp_path / "research").mkdir()
    (tmp_path / "research" / "PRIOR_ART_MATRIX.csv").write_text("paper_id,title\nP01,Wiesner\n")
    monkeypatch.setenv("QMINT_ROOT", str(tmp_path))
    assert cli.main(["sources", "list", "--type", "paper"]) == 0
    row = json.loads(capsys.readouterr().out.strip())
    assert row["paper_id"] == "P01" and row["type"] == "paper"


def test_unknown_command_is_usage_error():
    assert run_cli("frobnicate").returncode == 2
