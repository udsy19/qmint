"""Pre-registration integrity: the frozen experiment / holdout files may never change after registration."""

from __future__ import annotations

from pathlib import Path

from qmint.core.serialization import file_sha256

ROOT = Path(__file__).resolve().parents[3]

# Recorded at the pre-registration commit (before any optimisation was run). Do not edit.
FROZEN = {
    "benchmarks/frozen_experiments.yaml": "dc306b78bb14add47e98e89c63fdb4eec4d29133fe3b379ef4e1f4c6df44faa9",
    "benchmarks/holdouts.yaml": "c60f8f7089ed6a9a97ef55a9f108de00fa7e7d2ee7078e952e904e377d1e48da",
    "benchmarks/baseline_matrix.yaml": "83b0134ee070aa5c6f5b97e32ff83ab87bbbefdaec39487532bf44952fb5508a",
}


def test_preregistered_files_unchanged():
    for rel, sha in FROZEN.items():
        assert file_sha256(ROOT / rel) == sha, f"{rel} was modified after pre-registration"


def test_holdout_source_unchanged():
    import yaml

    h = yaml.safe_load((ROOT / "benchmarks/holdouts.yaml").read_text())["holdouts"][0]
    assert file_sha256(ROOT / h["source_file"]) == h["source_sha256_at_registration"]
