"""scripts/run_core.py (offline, deterministic, strict) and scripts/run_all.py (real data only)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from qmint.core import lanes, pipeline
from qmint.core.config import load_config

ROOT = Path(__file__).resolve().parents[2]


def run_script(name, *args, env=None):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / name), *map(str, args)], cwd=ROOT,
                          capture_output=True, text=True, env=env)


def test_run_core_offline_deterministic(tmp_path):
    outs = []
    for i in range(2):
        out = tmp_path / f"run{i}"
        r = run_script("run_core.py", "--offline", "--seed", 42, "--out", out)
        assert r.returncode == 0, r.stdout + r.stderr
        assert "STAGE" in r.stdout and "PASS=" in r.stdout
        status = json.loads((out / "run_core_status.json").read_text())
        outs.append(status)
        by = {s["name"]: s for s in status["stages"]}
        assert by["doctor"]["status"] == by["contract_fixtures"]["status"] == "PASS"
        for s in status["stages"]:
            assert s["status"] in ("PASS", "SKIPPED")
            if s["status"] == "SKIPPED":
                assert s["reason"], "every skip must carry a reason"
        v = run_script("verify_manifest.py", out)
        assert v.returncode == 0, v.stdout + v.stderr
    assert outs[0] == outs[1]
    assert (tmp_path / "run0/doctor/doctor.json").read_bytes() == (tmp_path / "run1/doctor/doctor.json").read_bytes()


def test_run_core_require_all_fails_on_skips(tmp_path):
    if all(lanes.probe(s)[0] == "PRESENT" for s in lanes.STAGES if s.module != "builtin"):
        pytest.skip("all lanes merged; nothing is skipped")
    r = run_script("run_core.py", "--seed", 1, "--out", tmp_path, "--require-all")
    assert r.returncode == 1 and "--require-all" in r.stderr


def _ctx(tmp_path, **kw):
    return pipeline.RunContext(cfg=load_config(env={}), out_dir=tmp_path, seed=3, **kw)


@pytest.fixture
def fake_stages(tmp_path, monkeypatch):
    pkg = tmp_path / "lanepkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "ok.py").write_text(
        "def run_core_stage(*, seed, out_dir):\n"
        "    p = out_dir / 'r.json'; p.write_text(str(seed)); return {'outputs': [p]}\n")
    (pkg / "boom.py").write_text("def run_core_stage(*, seed, out_dir):\n    raise ValueError('stage exploded')\n")
    (pkg / "skip.py").write_text(
        "from qmint.core.lanes import StageSkipped\n"
        "def run_core_stage(*, seed, out_dir):\n    raise StageSkipped('optional dep cvxpy absent')\n")
    (pkg / "broken.py").write_text("import qmint_missing_dep_xyz\n")
    (pkg / "nondet.py").write_text(
        "import os\n"
        "def run_core_stage(*, seed, out_dir):\n"
        "    p = out_dir / 'r.bin'; p.write_bytes(os.urandom(8)); return {'outputs': [p]}\n")
    (pkg / "network.py").write_text(
        "import socket\n"
        "def run_core_stage(*, seed, out_dir):\n"
        "    socket.create_connection(('127.0.0.1', 9), timeout=0.1)\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    return {n: lanes.StageEntry(n, "Z", f"lanepkg.{n}") for n in ("ok", "boom", "skip", "broken", "nondet", "network")}


def test_strict_failure_halts_later_stages(tmp_path, fake_stages):
    st = fake_stages
    absent = lanes.StageEntry("absent", "Z", "lanepkg.absent")
    res = pipeline.run_stages(_ctx(tmp_path / "o"), [st["ok"], absent, st["skip"], st["boom"], st["ok"]])
    assert [r.status for r in res] == ["PASS", "SKIPPED", "SKIPPED", "FAIL", "NOT_RUN"]
    assert "not merged" in res[1].reason and "cvxpy" in res[2].reason
    assert "stage exploded" in res[3].reason
    res2 = pipeline.run_stages(_ctx(tmp_path / "o2"), [st["boom"], st["ok"]], keep_going=True)
    assert [r.status for r in res2] == ["FAIL", "PASS"]


def test_broken_lane_is_fail_not_skip(tmp_path, fake_stages):
    (r,) = pipeline.run_stages(_ctx(tmp_path), [fake_stages["broken"]])
    assert r.status == "FAIL" and r.reason.startswith("BROKEN")


def test_nondeterministic_stage_flagged(tmp_path, fake_stages):
    res = pipeline.run_stages(_ctx(tmp_path, check_determinism=True), [fake_stages["ok"], fake_stages["nondet"]])
    assert res[0].status == "PASS" and res[0].deterministic is True
    assert res[1].status == "FAIL" and res[1].reason.startswith("NONDETERMINISTIC")


def test_stage_network_access_fails_offline(tmp_path, fake_stages):
    from qmint.core.config import network_guard

    with network_guard():
        (r,) = pipeline.run_stages(_ctx(tmp_path), [fake_stages["network"]])
    assert r.status == "FAIL" and "network access denied" in r.reason


def test_run_all_refuses_without_real_data(tmp_path):
    r = run_script("run_all.py", "--out", tmp_path)
    assert r.returncode == 2 and "REFUSED" in r.stderr
    assert not any(tmp_path.iterdir())


def test_realdata_preflight_rejects_fixtures(tmp_path):
    from qmint.core.contracts import EvidenceKind, EvidenceManifest, ManifestEntry
    from qmint.core.manifest import write_manifest
    from qmint.core.serialization import file_sha256

    root = tmp_path
    fx = root / "tests" / "fixtures" / "data.bin"
    fx.parent.mkdir(parents=True)
    fx.write_bytes(b"synthetic")
    real = root / "datasets" / "cache" / "real.bin"
    real.parent.mkdir(parents=True)
    real.write_bytes(b"photons")

    def man(mid, kind, path):
        return EvidenceManifest(
            manifest_id=mid, created_utc="2026-01-01T00:00:00Z", command="fetch", git_sha="a" * 40,
            evidence_kind=kind, entries=[ManifestEntry(path_or_uri=path.relative_to(root).as_posix(),
                                                       sha256=file_sha256(path), role="input",
                                                       original_or_derived="original")])

    cfg = load_config(env={"QMINT_ROOT": str(root)})
    mdir = root / "datasets" / "manifests"
    write_manifest(man("fx", EvidenceKind.PHOTON_EXPERIMENT, fx), mdir / "fx.json")
    write_manifest(man("syn", EvidenceKind.SYNTHETIC, real), mdir / "syn.json")
    problems = pipeline.realdata_preflight(cfg)
    assert any("test fixture" in p for p in problems)
    assert any("SYNTHETIC is not real data" in p for p in problems)
    (mdir / "fx.json").unlink()
    (mdir / "syn.json").unlink()
    write_manifest(man("ok", EvidenceKind.PHOTON_EXPERIMENT, real), mdir / "ok.json")
    assert pipeline.realdata_preflight(cfg) == []
    real.write_bytes(b"tampered")
    assert any("MISMATCH" in p for p in pipeline.realdata_preflight(cfg))
