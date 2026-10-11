"""Guard: no nested git repository / worktree is ever staged or committed as a gitlink."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


@pytest.fixture(scope="module")
def in_git():
    if shutil.which("git") is None or _git("rev-parse", "--is-inside-work-tree").stdout.strip() != "true":
        pytest.skip("not a git checkout")


def test_no_gitlinks_in_index(in_git):
    # Mode 160000 = gitlink (submodule or accidentally-added nested repo/worktree).
    staged = _git("ls-files", "--stage").stdout.splitlines()
    gitlinks = [line for line in staged if line.startswith("160000 ")]
    assert gitlinks == [], f"nested git repo/worktree staged as gitlink: {gitlinks}"


def test_no_nested_git_metadata_tracked(in_git):
    tracked = _git("ls-files").stdout.splitlines()
    bad = [p for p in tracked if "/.git/" in f"/{p}" or p.endswith("/.git") or p == ".git"]
    assert bad == []


def test_no_gitmodules(in_git):
    assert ".gitmodules" not in _git("ls-files").stdout.splitlines()
