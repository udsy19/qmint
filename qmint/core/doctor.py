"""`qmint doctor`: environment report.

Reports required/optional dependency status (optional deps never fail the run; they
are explicitly SKIPPED with a reason), installed-vs-lock version drift, free disk
space, network/paid-hardware flags, git state, which lane entrypoints are merged, and
the PRESENCE (booleans only, never values) of known credential env vars.
Imports are checked with ``importlib.util.find_spec`` so heavy packages are not loaded.
"""

from __future__ import annotations

import importlib.util
import os
import platform
import re
import shutil
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

import qmint
from qmint.core.config import QMintConfig
from qmint.core.manifest import LOCK_NAME, git_state

# (import name, distribution name, extra)
REQUIRED = [("numpy", "numpy", "core"), ("scipy", "scipy", "core"), ("pydantic", "pydantic", "core"),
            ("yaml", "pyyaml", "core")]
OPTIONAL = [
    ("cvxpy", "cvxpy", "sdp"), ("scs", "scs", "sdp"), ("clarabel", "clarabel", "sdp"),
    ("qiskit", "qiskit", "quantum"), ("qiskit_aer", "qiskit-aer", "quantum"), ("qutip", "qutip", "quantum"),
    ("dilithium_py", "dilithium-py", "pqc"), ("requests", "requests", "data"),
    ("matplotlib", "matplotlib", "plots"), ("pytest", "pytest", "dev"), ("hypothesis", "hypothesis", "dev"),
    ("ruff", "ruff", "dev"),
]
KNOWN_SECRET_ENV = ("IONQ_API_KEY",)
MIN_FREE_GB = 2.0


def _lock_pins(root: Path) -> dict[str, str]:
    lock = root / LOCK_NAME
    if not lock.is_file():
        return {}
    pins = {}
    for line in lock.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([A-Za-z0-9_.-]+)==([^\s;]+)", line)
        if m:
            pins[m.group(1).lower().replace("_", "-")] = m.group(2)
    return pins


def _dep(import_name: str, dist: str, extra: str, required: bool, pins: dict[str, str]) -> dict[str, Any]:
    entry: dict[str, Any] = {"import": import_name, "distribution": dist, "extra": extra}
    try:
        found = importlib.util.find_spec(import_name) is not None
    except (ImportError, ValueError):
        found = False
    if not found:
        entry["status"] = "MISSING" if required else "SKIPPED"
        entry["reason"] = f"not importable; install extra [{extra}]"
        return entry
    try:
        entry["version"] = metadata.version(dist)
    except metadata.PackageNotFoundError:
        entry["version"] = None
    pinned = pins.get(dist.lower())
    entry["locked"] = pinned
    entry["status"] = "OK" if pinned is None or pinned == entry["version"] else "LOCK_MISMATCH"
    return entry


def lane_availability() -> dict[str, dict[str, str]]:
    from qmint.core.lanes import LANE_COMMANDS, probe

    return {cmd: {"lane": e.lane, "module": e.module, "status": probe(e)[0]} for cmd, e in LANE_COMMANDS.items()}


def run_doctor(cfg: QMintConfig) -> dict[str, Any]:
    pins = _lock_pins(cfg.root)
    required = [_dep(*d, required=True, pins=pins) for d in REQUIRED]
    optional = [_dep(*d, required=False, pins=pins) for d in OPTIONAL]
    free_gb = shutil.disk_usage(cfg.root).free / 1e9
    try:
        sha, dirty = git_state(cfg.root)
        git = {"sha": sha, "dirty": dirty}
    except RuntimeError as e:
        git = {"sha": None, "dirty": None, "error": str(e)}
    problems = [f"required dependency {d['distribution']} missing" for d in required if d["status"] == "MISSING"]
    warnings = [
        f"{d['distribution']} {d['version']} != locked {d['locked']}"
        for d in required + optional if d["status"] == "LOCK_MISMATCH"
    ]
    if free_gb < MIN_FREE_GB:
        warnings.append(f"low disk space: {free_gb:.2f} GB free < {MIN_FREE_GB} GB")
    if not (cfg.root / LOCK_NAME).is_file():
        problems.append(f"{LOCK_NAME} missing")
    return {
        "qmint_version": qmint.__version__,
        "python": platform.python_version(),
        "platform": f"{sys.platform}-{platform.machine()}",
        "root": str(cfg.root),
        "git": git,
        "dependencies": {"required": required, "optional": optional},
        "disk_free_gb": round(free_gb, 2),
        "network_allowed": cfg.allow_network,
        "paid_hardware_allowed": cfg.allow_paid_hardware,
        "seed": cfg.seed,
        "secrets_present": {name: bool(os.environ.get(name)) for name in KNOWN_SECRET_ENV},
        "lanes": lane_availability(),
        "problems": problems,
        "warnings": warnings,
        "status": "FAIL" if problems else "OK",
    }


def format_report(report: dict[str, Any]) -> str:
    lines = [
        f"qmint {report['qmint_version']}  python {report['python']}  {report['platform']}",
        f"git {report['git'].get('sha')} dirty={report['git'].get('dirty')}",
        f"disk free {report['disk_free_gb']} GB  network_allowed={report['network_allowed']}  "
        f"paid_hardware_allowed={report['paid_hardware_allowed']}  seed={report['seed']}",
    ]
    for group in ("required", "optional"):
        for d in report["dependencies"][group]:
            extra = d.get("version") or d.get("reason", "")
            lines.append(f"  [{d['status']:<13}] {group:<8} {d['distribution']:<14} {extra}")
    for cmd, lane in report["lanes"].items():
        lines.append(f"  [{lane['status']:<13}] lane {lane['lane']}   {cmd:<14} {lane['module']}")
    for name, present in report["secrets_present"].items():
        lines.append(f"  secret {name}: {'present' if present else 'absent'}")
    lines += [f"  PROBLEM: {p}" for p in report["problems"]] + [f"  WARNING: {w}" for w in report["warnings"]]
    lines.append(f"status: {report['status']}")
    return "\n".join(lines)
