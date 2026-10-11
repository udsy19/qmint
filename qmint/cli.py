"""`qmint` command-line interface (master plan section 6, "Main CLI").

`doctor` and `sources` are implemented here. Every other command dispatches lazily to
its lane's entrypoint (see ``qmint.core.lanes``). If the lane is not merged the CLI
prints ``NOT_AVAILABLE: ...`` and exits 3 -- it never fabricates output.

Exit codes: 0 ok, 1 failure, 2 usage error, 3 NOT_AVAILABLE, 4 lane module BROKEN.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Sequence
from pathlib import Path

EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_NOT_AVAILABLE, EXIT_BROKEN = 0, 1, 2, 3, 4

# Lane A artefacts read by `qmint sources list` (files, not a Python module).
SOURCE_FILES = {"paper": Path("research/PRIOR_ART_MATRIX.csv"), "dataset": Path("research/DATASOURCE_REGISTER.yaml")}


def _cmd_doctor(args: argparse.Namespace) -> int:
    from qmint.core.config import load_config
    from qmint.core.doctor import format_report, run_doctor

    report = run_doctor(load_config())
    if args.report:
        out = Path(args.report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else format_report(report))
    return EXIT_OK if report["status"] == "OK" else EXIT_FAIL


def _cmd_sources(args: argparse.Namespace) -> int:
    from qmint.core.config import load_config

    root = load_config().root
    kinds = list(SOURCE_FILES) if args.type == "all" else [args.type]
    missing = [str(SOURCE_FILES[k]) for k in kinds if not (root / SOURCE_FILES[k]).is_file()]
    if missing:
        print(f"NOT_AVAILABLE: lane A artefact(s) {', '.join(missing)} not merged", file=sys.stderr)
        return EXIT_NOT_AVAILABLE
    for k in kinds:
        path = root / SOURCE_FILES[k]
        if path.suffix == ".csv":
            with open(path, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        else:
            import yaml

            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            rows = data if isinstance(data, list) else (data or {}).get("sources", data)
        for row in rows if isinstance(rows, list) else [rows]:
            print(json.dumps({"type": k, "source_file": str(SOURCE_FILES[k]), **row}, sort_keys=True, default=str))
    return EXIT_OK


def _dispatch(command: str, rest: list[str]) -> int:
    from qmint.core.lanes import LANE_COMMANDS, LaneBroken, LaneNotAvailable, load

    entry = LANE_COMMANDS[command]
    try:
        fn = load(entry, "cli_main")
    except LaneNotAvailable as e:
        print(f"NOT_AVAILABLE: {e}", file=sys.stderr)
        return EXIT_NOT_AVAILABLE
    except LaneBroken as e:
        print(f"BROKEN: {e}", file=sys.stderr)
        return EXIT_BROKEN
    rc = fn([command, *rest])  # type: ignore[operator]
    if not isinstance(rc, int):
        print(f"ERROR: lane {entry.lane} cli_main returned {rc!r}, expected int exit code", file=sys.stderr)
        return EXIT_FAIL
    return rc


def build_parser() -> argparse.ArgumentParser:
    from qmint.core.lanes import LANE_COMMANDS

    p = argparse.ArgumentParser(prog="qmint", description="QMint research platform (simulator; not a payment system)")
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("doctor", help="environment / dependency report")
    d.add_argument("--check-dependencies", action="store_true", help="accepted for plan compatibility (always on)")
    d.add_argument("--report", help="write JSON report to this path")
    d.add_argument("--json", action="store_true", help="print JSON instead of a table")
    d.set_defaults(func=_cmd_doctor)

    s = sub.add_parser("sources", help="list literature / data sources (lane A registers)")
    s_sub = s.add_subparsers(dest="action", required=True)
    sl = s_sub.add_parser("list")
    sl.add_argument("--type", choices=["paper", "dataset", "all"], default="all")
    sl.set_defaults(func=_cmd_sources)

    for cmd, entry in LANE_COMMANDS.items():
        # Listed for --help only; main() dispatches these before argparse runs.
        sub.add_parser(cmd, help=f"[lane {entry.lane}] {entry.description}", add_help=False)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    from qmint.core.lanes import LANE_COMMANDS

    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in LANE_COMMANDS:  # pass everything (incl. --help) through to the lane verbatim
        return _dispatch(argv[0], argv[1:])
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
