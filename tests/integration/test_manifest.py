"""EvidenceManifest build / verify, and scripts/verify_manifest.py exit codes."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from qmint.core.contracts import EvidenceKind
from qmint.core.manifest import build_manifest, load_manifest, verify_manifest, write_manifest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def repo(tmp_path):
    """Minimal git repo with a lock file, input, output and script."""
    if shutil.which("git") is None:
        pytest.skip("git not installed")
    r = tmp_path / "repo"
    r.mkdir()
    (r / "requirements.lock").write_text("numpy==2.0.0\n")
    (r / "in.csv").write_text("a,b\n1,2\n")
    (r / "out.json").write_text('{"x": 1}\n')
    (r / "run.py").write_text("print('hi')\n")
    for cmd in (["git", "init", "-q"], ["git", "add", "."],
                ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"]):
        subprocess.run(cmd, cwd=r, check=True)
    return r


def _manifest(repo):
    return build_manifest(manifest_id="m1", command="run.py", evidence_kind=EvidenceKind.SYNTHETIC, root=repo,
                          inputs=["in.csv"], outputs=["out.json"], scripts=["run.py"], seeds=[42])


def test_manifest_pins_everything(repo):
    m = _manifest(repo)
    assert len(m.git_sha) == 40 and m.seeds == [42]
    assert m.environment["git_dirty"] == "false"
    roles = {e.path_or_uri: e.role for e in m.entries}
    assert roles == {"in.csv": "input", "out.json": "output", "run.py": "script", "requirements.lock": "environment"}
    assert all(c.status == "OK" for c in verify_manifest(m, repo))


def test_manifest_mismatch_detected(repo):
    m = _manifest(repo)
    (repo / "out.json").write_text('{"x": 2}\n')
    (repo / "in.csv").unlink()
    status = {c.path_or_uri: c.status for c in verify_manifest(m, repo)}
    assert status["out.json"] == "MISMATCH" and status["in.csv"] == "MISSING"


def test_env_lock_change_detected(repo):
    m = _manifest(repo)
    (repo / "requirements.lock").write_text("numpy==9.9.9\n")
    status = {c.path_or_uri: c.status for c in verify_manifest(m, repo)}
    assert status["requirements.lock"] == "MISMATCH"
    assert status["environment.env_lock_sha256"] == "MISMATCH"


def test_missing_declared_file_refused(repo):
    with pytest.raises(FileNotFoundError):
        build_manifest(manifest_id="m", command="c", evidence_kind=EvidenceKind.SYNTHETIC, root=repo,
                       outputs=["nope.json"])


def test_no_git_no_invented_sha(tmp_path):
    (tmp_path / "requirements.lock").write_text("x==1\n")
    (tmp_path / "o").write_text("1")
    with pytest.raises(RuntimeError, match="git sha"):
        build_manifest(manifest_id="m", command="c", evidence_kind=EvidenceKind.SYNTHETIC, root=tmp_path,
                       outputs=["o"])


def _verify_script(*args):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "verify_manifest.py"), *map(str, args)],
                          capture_output=True, text=True)


def test_verify_script_exit_codes(repo, tmp_path):
    mpath = write_manifest(_manifest(repo), repo / "results" / "run.manifest.json")
    assert load_manifest(mpath).manifest_id == "m1"
    ok = _verify_script(mpath, "--root", repo)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    (repo / "out.json").write_text("tampered")
    bad = _verify_script(repo / "results", "--root", repo)
    assert bad.returncode == 1 and "MISMATCH" in bad.stdout
    empty = tmp_path / "empty"
    empty.mkdir()
    assert _verify_script(empty).returncode == 2
