#!/usr/bin/env python
"""Offline, deterministic core run over every merged lane stage.

    python scripts/run_core.py --offline --seed 42 [--out DIR] [--keep-going] [--require-all]

Network is always denied (QMINT_ALLOW_NETWORK forced off and sockets blocked). Stages
whose lane is not merged are SKIPPED with a reason; any FAIL exits 1 (strict, like
`set -euo pipefail`). Ends with a status table, a status JSON and a verified manifest.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import _bootstrap  # noqa: F401  (puts this checkout first on sys.path)

from qmint.core.config import load_config, network_guard
from qmint.core.pipeline import RunContext, finalize, run_stages, status_table


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--offline", action="store_true", help="accepted for clarity; run_core is always offline")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--out", type=Path, default=None, help="output dir (default experiments/run_core)")
    p.add_argument("--keep-going", action="store_true", help="run later stages after a FAIL (still exits 1)")
    p.add_argument("--require-all", action="store_true", help="treat SKIPPED stages as failure")
    p.add_argument("--check-determinism", action="store_true", help="run each stage twice and compare outputs")
    a = p.parse_args(argv)

    os.environ["QMINT_ALLOW_NETWORK"] = "0"
    cfg = load_config().offline()
    seed = cfg.seed if a.seed is None else a.seed
    out = (a.out or cfg.experiments_dir / "run_core").resolve()
    out.mkdir(parents=True, exist_ok=True)
    ctx = RunContext(cfg=cfg, out_dir=out, seed=seed, mode="core", check_determinism=a.check_determinism)
    with network_guard():
        results = run_stages(ctx, keep_going=a.keep_going)
    manifest = finalize(ctx, results, command=" ".join(["scripts/run_core.py", *(argv or sys.argv[1:])]),
                        script=Path(__file__), name="run_core")
    print(status_table(results))
    print(f"manifest: {manifest}")
    failed = any(r.status in ("FAIL", "NOT_RUN") for r in results)
    skipped = any(r.status == "SKIPPED" for r in results)
    if failed:
        return 1
    if a.require_all and skipped:
        print("FAIL: --require-all set and some stages were SKIPPED", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
