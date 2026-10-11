#!/usr/bin/env python
"""Full run: the offline core stages plus every lane's real-data stage.

    python scripts/run_all.py --seed 42 [--out DIR] [--keep-going]

Requires real public data already fetched and hash-verified under datasets/cache with
EvidenceManifests in datasets/manifests (canonical .json, or .yaml carrying manifest_id;
lane E, `qmint data fetch`). If anything is
missing, unverified or a fixture, the run is REFUSED (exit 2) -- fixtures are never
silently substituted. Exit 1 if any stage fails or no real-data stage ran.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from qmint.core.config import load_config, network_guard
from qmint.core.pipeline import RunContext, finalize, realdata_preflight, run_stages, status_table


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--out", type=Path, default=None, help="output dir (default experiments/run_all)")
    p.add_argument("--keep-going", action="store_true")
    a = p.parse_args(argv)

    cfg = load_config()
    problems = realdata_preflight(cfg)
    if problems:
        print("REFUSED: run_all requires verified real data; fixtures are not substituted.", file=sys.stderr)
        for prob in problems:
            print(f"  - {prob}", file=sys.stderr)
        return 2
    seed = cfg.seed if a.seed is None else a.seed
    out = (a.out or cfg.experiments_dir / "run_all").resolve()
    out.mkdir(parents=True, exist_ok=True)
    command = " ".join(["scripts/run_all.py", *(argv or sys.argv[1:])])
    results = []
    with network_guard(enabled=not cfg.allow_network):
        for mode in ("core", "realdata"):
            ctx = RunContext(cfg=cfg, out_dir=out / mode, seed=seed, mode=mode)
            ctx.out_dir.mkdir(parents=True, exist_ok=True)
            phase = run_stages(ctx, keep_going=a.keep_going)
            for r in phase:
                r.name = f"{mode}:{r.name}"
            results += phase
            if any(r.status == "FAIL" for r in phase) and not a.keep_going:
                break
    ctx = RunContext(cfg=cfg, out_dir=out, seed=seed, mode="realdata")
    manifest = finalize(ctx, results, command=command, script=Path(__file__), name="run_all")
    print(status_table(results))
    print(f"manifest: {manifest}")
    if any(r.status in ("FAIL", "NOT_RUN") for r in results):
        return 1
    if not any(r.name.startswith("realdata:") and r.status == "PASS" for r in results):
        print("FAIL: no real-data stage ran; nothing here is real-data evidence", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
