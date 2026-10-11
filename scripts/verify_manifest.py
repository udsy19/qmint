#!/usr/bin/env python
"""Re-hash every entry of one or more EvidenceManifests; exit 1 on any mismatch.

    python scripts/verify_manifest.py PATH [PATH ...]

PATH is a manifest JSON file or a directory searched recursively for ``*.manifest.json``
and ``manifest*.json``. Exit codes: 0 all OK, 1 mismatch/missing file, 2 no manifest found
or invalid manifest. Remote URIs cannot be re-hashed offline and are reported as
UNVERIFIED_REMOTE (not counted as OK; fail with --strict-remote).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import _bootstrap  # noqa: F401
from pydantic import ValidationError

from qmint.core.config import load_config
from qmint.core.manifest import load_manifest, verify_manifest


def _find(paths: list[Path]) -> list[Path]:
    found: list[Path] = []
    for p in paths:
        if p.is_dir():
            found += sorted({*p.rglob("*.manifest.json"), *p.rglob("manifest*.json")})
        elif p.is_file():
            found.append(p)
    return found


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", type=Path)
    ap.add_argument("--root", type=Path, default=None, help="base for relative entry paths (default repo root)")
    ap.add_argument("--strict-remote", action="store_true")
    a = ap.parse_args(argv)
    root = (a.root or load_config().root).resolve()
    manifests = _find(a.paths)
    if not manifests:
        print(f"ERROR: no manifest found in {[str(p) for p in a.paths]}", file=sys.stderr)
        return 2
    rc = 0
    for m in manifests:
        try:
            man = load_manifest(m)
        except (ValidationError, ValueError) as e:
            print(f"INVALID {m}: {e}", file=sys.stderr)
            rc = max(rc, 2)
            continue
        for c in verify_manifest(man, root):
            bad = c.status in ("MISMATCH", "MISSING") or (a.strict_remote and c.status == "UNVERIFIED_REMOTE")
            if bad:
                rc = max(rc, 1)
            print(f"{c.status:<17} {m.name}: {c.path_or_uri}"
                  + (f" expected {c.expected} got {c.actual}" if c.status == "MISMATCH" else ""))
    print("RESULT:", "OK" if rc == 0 else "FAILED")
    return rc


if __name__ == "__main__":
    sys.exit(main())
