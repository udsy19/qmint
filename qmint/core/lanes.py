"""Registry of lane entrypoints consumed by the CLI, `qmint doctor` and run_core/run_all.

Lane entrypoint convention (proposed to all lanes; see handoffs/L-L1.md):
  module ``qmint.<pkg>.entrypoints`` (lane J: ``qmint.quantum.qollab``) may define
    cli_main(argv: list[str]) -> int
        argv[0] is the top-level command (e.g. "simulate"), the rest is passed verbatim.
    run_core_stage(*, seed: int, out_dir: pathlib.Path) -> dict
        offline, deterministic for a fixed seed; returns {"outputs": [paths], ...}.
    run_realdata_stage(*, seed: int, out_dir: pathlib.Path, cache_dir: pathlib.Path) -> dict
        consumes verified real data from datasets/cache; never substitutes fixtures.
  A stage may raise ``StageSkipped(reason)`` (e.g. optional dependency absent).

A module that is absent is NOT_AVAILABLE. A module that exists but fails to import
(e.g. a missing dependency) is BROKEN and surfaces as an error -- never as a skip.
"""

from __future__ import annotations

import importlib
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType


class StageSkipped(Exception):
    """Raised by a lane stage to report an explicit, reasoned skip."""


class LaneNotAvailable(Exception):
    """The lane's entrypoint module (or the requested function) is not merged."""


class LaneBroken(Exception):
    """The lane's entrypoint module exists but fails to import."""


@dataclass(frozen=True)
class LaneEntry:
    lane: str
    module: str
    description: str


def _ep(pkg: str) -> str:
    return f"qmint.{pkg}.entrypoints"


# Master plan section 6 "Main CLI". `doctor` and `sources` are implemented by lane L itself.
LANE_COMMANDS: dict[str, LaneEntry] = {
    "data": LaneEntry("E", _ep("photonics"), "fetch/validate public photonic datasets"),
    "proofs": LaneEntry("D", _ep("proofs"), "verify published bounds / SDP primal-dual"),
    "simulate": LaneEntry("B", _ep("protocols"), "protocol simulations (wiesner, smoney, ...)"),
    "attacks": LaneEntry("C", _ep("attacks"), "attack suites"),
    "baselines": LaneEntry("H", _ep("classical"), "classical baseline protocols"),
    "compiler": LaneEntry("I", _ep("compiler"), "certificate compiler optimize/verify"),
    "benchmark": LaneEntry("N", _ep("evaluation"), "frozen benchmark plan"),
    "figures": LaneEntry("N", _ep("evaluation"), "regenerate figures from records"),
    "paper": LaneEntry("N", _ep("evaluation"), "build paper from evidence"),
    "qollab": LaneEntry("J", "qmint.quantum.qollab", "optional Qollab export"),
}


@dataclass(frozen=True)
class StageEntry:
    name: str
    lane: str
    module: str  # "builtin" for lane-L stages implemented in qmint.core.pipeline


# Order follows master plan T8: mint -> attack -> proof -> spacetime -> classical -> compiler -> figures.
STAGES: tuple[StageEntry, ...] = (
    StageEntry("doctor", "L", "builtin"),
    StageEntry("contract_fixtures", "L", "builtin"),
    StageEntry("protocols", "B", _ep("protocols")),
    StageEntry("quantum", "F", _ep("quantum")),
    StageEntry("attacks", "C", _ep("attacks")),
    StageEntry("proofs", "D", _ep("proofs")),
    StageEntry("photonics", "E", _ep("photonics")),
    StageEntry("networks", "G", _ep("networks")),
    StageEntry("classical", "H", _ep("classical")),
    StageEntry("compiler", "I", _ep("compiler")),
    StageEntry("evaluation", "N", _ep("evaluation")),
)


def probe(entry: LaneEntry | StageEntry) -> tuple[str, str]:
    """Cheap presence check without importing the module: (PRESENT|NOT_AVAILABLE, detail)."""
    try:
        spec = importlib.util.find_spec(entry.module)
    except ModuleNotFoundError:
        spec = None
    if spec is None:
        return "NOT_AVAILABLE", f"lane {entry.lane} module {entry.module} not merged"
    return "PRESENT", entry.module


def write_stage_json(out_dir: Path, name: str, obj: object) -> Path:
    """Shared lane-entrypoint helper: write ``obj`` as canonical JSON (byte-deterministic for a
    fixed seed, as run_core's determinism check requires) to ``out_dir/name``; return the path."""
    from qmint.core.serialization import canonical_json

    path = Path(out_dir) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(obj) + "\n", encoding="utf-8")
    return path


def load(entry: LaneEntry | StageEntry, func: str) -> object:
    """Import ``entry.module`` and return ``func``; distinguishes not-merged from broken."""
    status, detail = probe(entry)
    if status == "NOT_AVAILABLE":
        raise LaneNotAvailable(detail)
    try:
        mod: ModuleType = importlib.import_module(entry.module)
    except ImportError as e:
        raise LaneBroken(f"lane {entry.lane} module {entry.module} failed to import: {e!r}") from e
    fn = getattr(mod, func, None)
    if not callable(fn):
        raise LaneNotAvailable(f"lane {entry.lane} module {entry.module} has no {func}() entrypoint")
    return fn
