"""CLI: ``python -m qmint.ui.build --records <dir> [--records <dir> ...] --out app/site``.

Builds the static, self-contained evidence workbench. Output is deterministic: the same inputs
produce byte-identical files (no timestamps, sorted records). The site is labelled FIXTURE DATA
unless ``--real-data`` is passed AND no loaded record is SYNTHETIC.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from qmint.core.serialization import sha256_hex
from qmint.ui.app import render_site
from qmint.ui.records import LoadedRecord, Skipped, load_records


def build(record_dirs: list[Path], out: Path, *, real_data: bool = False
          ) -> tuple[dict[str, str], list[LoadedRecord], list[Skipped]]:
    recs, skipped = load_records(record_dirs)
    files = render_site(recs, skipped, real_data=real_data)
    for rel, text in files.items():
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8", newline="\n")
    return files, recs, skipped


def site_hash(files: dict[str, str]) -> str:
    return sha256_hex("".join(f"{p}\0{sha256_hex(t)}\n" for p, t in sorted(files.items())))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m qmint.ui.build", description=__doc__.splitlines()[0])
    ap.add_argument("--records", type=Path, action="append", required=True,
                    help="directory (or file) of frozen-contract JSON records; repeatable")
    ap.add_argument("--out", type=Path, required=True, help="output directory, e.g. app/site")
    ap.add_argument("--real-data", action="store_true",
                    help="drop the FIXTURE DATA label (still forced on if any record is SYNTHETIC)")
    ap.add_argument("--strict", action="store_true", help="exit non-zero if any input record is rejected")
    a = ap.parse_args(argv)
    for d in a.records:
        if not d.exists():
            ap.error(f"--records path does not exist: {d}")
    files, recs, skipped = build(a.records, a.out, real_data=a.real_data)
    print(f"wrote {len(files)} files to {a.out}; records={len(recs)} rejected={len(skipped)}; "
          f"site_sha256={site_hash(files)}")
    for s in skipped:
        print(f"  rejected {s.source_path}: {s.reason}", file=sys.stderr)
    return 1 if (a.strict and skipped) else 0


if __name__ == "__main__":
    raise SystemExit(main())
