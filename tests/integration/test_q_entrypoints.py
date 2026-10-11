"""Lane entrypoints wired by lane Q: CLI paths of master plan section 6 and run_core stages."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from qmint.core import lanes
from qmint.core.serialization import file_sha256

ROOT = Path(__file__).resolve().parents[2]
Q_STAGES = ("protocols", "quantum", "attacks", "proofs", "photonics")


def run_cli(*args):
    return subprocess.run([sys.executable, "-m", "qmint.cli", *map(str, args)], cwd=ROOT, capture_output=True,
                          text=True)


@pytest.mark.parametrize("cmd", ["simulate", "attacks", "proofs", "data", "qollab"])
def test_lane_commands_present_and_help(cmd):
    entry = lanes.LANE_COMMANDS[cmd]
    assert lanes.probe(entry)[0] == "PRESENT"
    assert callable(lanes.load(entry, "cli_main"))
    r = run_cli(cmd, "--help")
    assert r.returncode == 0 and "usage" in r.stdout


def test_cli_proofs_verify_w1_sdp_primal_dual():
    r = run_cli("proofs", "verify", "--game", "W1", "--n", 1, "--method", "sdp", "--primal-dual")
    assert r.returncode == 0, r.stderr
    assert "primal=0.75" in r.stdout and "[NUMERICAL_SDP]" in r.stdout
    assert "lane D independent exact upper=3/4" in r.stdout and "FAIL" not in r.stdout


def test_cli_proofs_refuses_unsupported():
    assert run_cli("proofs", "verify", "--game", "W1", "--n", 3, "--method", "sdp").returncode == 2
    r = run_cli("proofs", "verify", "--game", "W2", "--n", 4, "--method", "theorem")
    assert r.returncode == 1 and "UNSUPPORTED" in r.stdout and "value=None" in r.stdout  # never 0


def test_cli_simulate_wiesner(tmp_path):
    out = tmp_path / "w.json"
    r = run_cli("simulate", "wiesner", "--n", 8, "--honest-runs", 50, "--attack", "measure-resend",
                "--attack-runs", 50, "--seed", 41, "--out", out)
    assert r.returncode == 0, r.stderr
    res = json.loads(out.read_text())
    assert res["wiesner"]["honest"]["successes"] == 50
    assert res["attack"]["exact_success_this_attack"] == pytest.approx((5 / 8) ** 8, abs=1e-12)
    assert res["attack"]["record"]["evidence_kind"] == "MONTE_CARLO"


def test_cli_simulate_smoney_and_schiansky():
    assert run_cli("simulate", "smoney", "--protocol", "kent_2022", "--scheme", "QT2", "--N", 16,
                   "--runs", 2).returncode == 0
    assert run_cli("simulate", "schiansky", "--runs", 2).returncode == 0
    assert run_cli("simulate", "wiesner", "--noise", "depolarizing:0.1").returncode == 2  # W2 needs threshold


def test_cli_attacks_run_optimal_small(tmp_path):
    r = run_cli("attacks", "run", "--suite", "optimal-small", "--game", "W1", "--trials", 50, "--out", tmp_path)
    assert r.returncode == 0, r.stderr
    assert "certified upper=0.750000000003638 [CERTIFIED_NUMERIC]" in r.stdout
    (f,) = tmp_path.glob("attacks_optimal-small_W1_seed42.json")
    res = json.loads(f.read_text())
    assert all(row["agrees"] for row in res["crossrun_laneB"]["rows"])
    assert run_cli("attacks", "run", "--suite", "optimal-small", "--game", "S2").returncode == 2


def test_cli_data_fetch_refused_offline():
    r = subprocess.run([sys.executable, "-m", "qmint.cli", "data", "fetch", "zenodo:7979319"], cwd=ROOT,
                       capture_output=True, text=True, env={"PATH": "/usr/bin:/bin", "QMINT_ALLOW_NETWORK": "0"})
    assert r.returncode == 1 and "REFUSED" in r.stderr


@pytest.mark.parametrize("name", Q_STAGES)
def test_stage_deterministic(tmp_path, name):
    (entry,) = [s for s in lanes.STAGES if s.name == name]
    fn = lanes.load(entry, "run_core_stage")
    hashes = []
    for i in range(2):
        out = tmp_path / str(i)
        out.mkdir()
        res = fn(seed=42, out_dir=out)  # type: ignore[operator]
        assert res["outputs"] and all(Path(p).is_file() for p in res["outputs"])
        hashes.append(sorted((Path(p).relative_to(out).as_posix(), file_sha256(p)) for p in res["outputs"]))
    assert hashes[0] == hashes[1]
