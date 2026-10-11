"""Smoke: the bootstrap ideal-bound reference still runs (superseded later by qmint.proofs)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_bootstrap_unittests_pass():
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "bootstrap", "-p", "test_*.py"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
