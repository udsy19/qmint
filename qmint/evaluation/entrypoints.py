"""Lane-N entrypoints (convention in ``qmint.core.lanes``)."""

from __future__ import annotations

from pathlib import Path

from qmint.evaluation import make_figures


def cli_main(argv: list[str]) -> int:
    cmd, rest = (argv[0], argv[1:]) if argv else ("figures", [])
    if cmd == "figures":
        return make_figures.main(rest)
    print(f"NOT_AVAILABLE: '{cmd}' (lane N phase 1 implements only 'figures'; manuscript build is pending)")
    return 3


def run_core_stage(*, seed: int, out_dir: Path) -> dict:
    """Offline and deterministic: figures + tables from committed evidence (``seed`` unused: no sampling)."""
    del seed
    figs, tables = out_dir / "figures", out_dir / "paper"
    make_figures.main(["--out", str(figs), "--tables-out", str(tables), "--force"])
    return {"outputs": sorted(str(p) for p in (*figs.glob("*"), *tables.glob("*")) if p.is_file())}
