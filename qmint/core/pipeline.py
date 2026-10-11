"""Stage runner shared by scripts/run_core.py and scripts/run_all.py.

Strictness (the Python equivalent of ``set -euo pipefail``): a stage that raises is
FAIL and, unless ``keep_going``, every later stage is NOT_RUN; the run exits nonzero.
A stage whose lane module is not merged is SKIPPED with the reason recorded. A lane
module that exists but fails to import is FAIL (BROKEN), never SKIPPED. Every status,
including skips, is written to the status file and printed as a table.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from qmint.core.config import QMintConfig
from qmint.core.contracts import CONTRACT_MODELS, EvidenceKind
from qmint.core.doctor import run_doctor
from qmint.core.lanes import STAGES, LaneBroken, LaneNotAvailable, StageEntry, StageSkipped, load
from qmint.core.logging import redact
from qmint.core.manifest import build_manifest, verify_manifest, write_manifest
from qmint.core.serialization import canonical_json, file_sha256

Status = Literal["PASS", "FAIL", "SKIPPED", "NOT_RUN"]
Mode = Literal["core", "realdata"]
STAGE_FUNC: dict[Mode, str] = {"core": "run_core_stage", "realdata": "run_realdata_stage"}

FIXTURE_DIR = Path("tests") / "fixtures" / "contracts"
_FIXTURE_PREFIX = {
    "protocol": "protocol", "token": "token", "certificate": "certificate", "calibration": "calibration",
    "network": "network", "manifest": "manifest",
}


@dataclass
class StageResult:
    name: str
    lane: str
    status: Status
    reason: str = ""
    outputs: list[str] = field(default_factory=list)
    deterministic: bool | None = None


@dataclass
class RunContext:
    cfg: QMintConfig
    out_dir: Path
    seed: int
    mode: Mode = "core"
    check_determinism: bool = False


# ---------------------------------------------------------------- builtin L stages


def _stage_doctor(ctx: RunContext, out_dir: Path) -> dict[str, Any]:
    report = run_doctor(ctx.cfg)
    if report["status"] != "OK":
        raise RuntimeError(f"doctor problems: {report['problems']}")
    # Only the reproducible subset goes into the run outputs (no timestamps / disk numbers).
    stable = {k: report[k] for k in ("qmint_version", "python", "network_allowed", "seed")}
    stable["seed"] = ctx.seed
    stable["dependencies"] = {
        g: [{k: d.get(k) for k in ("distribution", "status", "version")} for d in report["dependencies"][g]]
        for g in ("required", "optional")
    }
    path = out_dir / "doctor.json"
    path.write_text(canonical_json(stable) + "\n", encoding="utf-8")
    return {"outputs": [path]}


def _stage_contract_fixtures(ctx: RunContext, out_dir: Path) -> dict[str, Any]:
    fixtures = sorted((ctx.cfg.root / FIXTURE_DIR).glob("*.json"))
    if not fixtures:
        raise FileNotFoundError(f"no contract fixtures under {FIXTURE_DIR}")
    checked = []
    for f in fixtures:
        contract = _FIXTURE_PREFIX.get(f.stem.split("_", 1)[0])
        if contract is None:
            raise ValueError(f"fixture {f.name} has no known contract prefix")
        CONTRACT_MODELS[contract].model_validate_json(f.read_text(encoding="utf-8"))  # raises if invalid
        checked.append({"fixture": f.name, "contract": contract, "file_sha256": file_sha256(f),
                        "evidence_kind": EvidenceKind.SYNTHETIC.value})
    path = out_dir / "contract_fixtures.json"
    path.write_text(canonical_json(checked) + "\n", encoding="utf-8")
    return {"outputs": [path]}


BUILTIN: dict[str, Callable[[RunContext, Path], dict[str, Any]]] = {
    "doctor": _stage_doctor,
    "contract_fixtures": _stage_contract_fixtures,
}

# ---------------------------------------------------------------- runner


def _invoke(entry: StageEntry, ctx: RunContext, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    if entry.module == "builtin":
        if ctx.mode == "realdata":
            raise StageSkipped("builtin stage already ran in core phase")
        result = BUILTIN[entry.name](ctx, out_dir)
    else:
        fn = load(entry, STAGE_FUNC[ctx.mode])
        if ctx.mode == "core":
            result = fn(seed=ctx.seed, out_dir=out_dir)  # type: ignore[operator]
        else:
            result = fn(seed=ctx.seed, out_dir=out_dir, cache_dir=ctx.cfg.cache_dir)  # type: ignore[operator]
    if not isinstance(result, dict) or not isinstance(result.get("outputs"), list):
        raise TypeError(f"stage {entry.name} must return a dict with an 'outputs' list")
    outs = [Path(p) for p in result["outputs"]]
    for p in outs:
        if not p.is_file():
            raise FileNotFoundError(f"stage {entry.name} declared missing output {p}")
    return outs


def _hashes(paths: Sequence[Path], base: Path) -> dict[str, str]:
    return {p.resolve().relative_to(base.resolve()).as_posix(): file_sha256(p) for p in paths}


def run_stages(ctx: RunContext, stages: Sequence[StageEntry] = STAGES, keep_going: bool = False) -> list[StageResult]:
    results: list[StageResult] = []
    halted = False
    for entry in stages:
        if halted:
            results.append(StageResult(entry.name, entry.lane, "NOT_RUN", "an earlier stage failed"))
            continue
        stage_dir = ctx.out_dir / entry.name
        if stage_dir.exists():
            shutil.rmtree(stage_dir)
        try:
            outs = _invoke(entry, ctx, stage_dir)
            res = StageResult(entry.name, entry.lane, "PASS", outputs=[str(p) for p in outs])
            if ctx.check_determinism:
                with tempfile.TemporaryDirectory() as td:
                    again = _invoke(entry, ctx, Path(td))
                    res.deterministic = _hashes(outs, stage_dir) == _hashes(again, Path(td))
                if not res.deterministic:
                    res.status, res.reason = "FAIL", "NONDETERMINISTIC: outputs differ across identical seeded runs"
        except (LaneNotAvailable, StageSkipped) as e:
            res = StageResult(entry.name, entry.lane, "SKIPPED", str(e))
        except LaneBroken as e:
            res = StageResult(entry.name, entry.lane, "FAIL", f"BROKEN: {e}")
        except Exception as e:  # stage boundary: recorded as FAIL, never as evidence
            res = StageResult(entry.name, entry.lane, "FAIL", f"{type(e).__name__}: {redact(str(e))}")
        results.append(res)
        if res.status == "FAIL" and not keep_going:
            halted = True
    return results


def status_table(results: Sequence[StageResult]) -> str:
    rows = [f"{'STAGE':<18} {'LANE':<5} {'STATUS':<8} REASON"]
    rows += [f"{r.name:<18} {r.lane:<5} {r.status:<8} {r.reason}" for r in results]
    counts = {s: sum(r.status == s for r in results) for s in ("PASS", "FAIL", "SKIPPED", "NOT_RUN")}
    rows.append(" ".join(f"{k}={v}" for k, v in counts.items()))
    return "\n".join(rows)


def finalize(ctx: RunContext, results: list[StageResult], *, command: str, script: Path, name: str) -> Path:
    """Write <name>_status.json and an EvidenceManifest over all outputs, then re-verify it."""
    status_path = ctx.out_dir / f"{name}_status.json"
    rel = [
        {**asdict(r), "outputs": [Path(p).resolve().relative_to(ctx.out_dir.resolve()).as_posix() for p in r.outputs]}
        for r in results
    ]
    status_path.write_text(
        json.dumps({"mode": ctx.mode, "seed": ctx.seed, "stages": rel}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    outputs = [Path(p) for r in results for p in r.outputs] + [status_path]
    manifest = build_manifest(
        manifest_id=f"{name}-seed{ctx.seed}",
        command=command,
        # Aggregate run manifest: per-result evidence kinds live in the records themselves.
        evidence_kind=EvidenceKind.UNCERTIFIED,
        root=ctx.cfg.root,
        outputs=outputs,
        scripts=[script],
        seeds=[ctx.seed],
    )
    mpath = write_manifest(manifest, ctx.out_dir / f"{name}.manifest.json")
    bad = [c for c in verify_manifest(manifest, ctx.cfg.root) if c.status != "OK"]
    if bad:
        raise RuntimeError(f"manifest self-verification failed: {bad}")
    return mpath


# ---------------------------------------------------------------- real-data preflight (run_all)

REALDATA_MANIFEST_DIR = Path("datasets") / "manifests"
_NOT_REAL = frozenset({EvidenceKind.SYNTHETIC, EvidenceKind.UNCERTIFIED, EvidenceKind.SIMULATOR_IDEAL,
                       EvidenceKind.SIMULATOR_NOISY})


def realdata_preflight(cfg: QMintConfig) -> list[str]:
    """Problems preventing a real-data run. Empty list = every declared dataset is present and verified.

    Fixtures can never satisfy this: SYNTHETIC/simulated manifests and any input under
    ``tests/`` or a ``fixtures`` path are refused, and every input must be re-hashed OK
    from ``datasets/cache``.
    """
    from qmint.core.manifest import load_manifest

    mdir = cfg.root / REALDATA_MANIFEST_DIR
    paths = sorted(mdir.glob("*.json")) if mdir.is_dir() else []
    if not paths:
        return [f"no real-data manifests in {REALDATA_MANIFEST_DIR}/ (lane E); fetch and verify datasets first"]
    cache = cfg.cache_dir.resolve()
    problems = []
    for mp in paths:
        man = load_manifest(mp)
        if man.evidence_kind in _NOT_REAL:
            problems.append(f"{mp.name}: evidence_kind {man.evidence_kind.value} is not real data")
        inputs = [e for e in man.entries if e.role == "input"]
        if not inputs:
            problems.append(f"{mp.name}: declares no input datasets")
        for e in inputs:
            p = Path(e.path_or_uri)
            p = (p if p.is_absolute() else cfg.root / p).resolve()
            if "fixtures" in p.parts or (cfg.root / "tests").resolve() in p.parents:
                problems.append(f"{mp.name}: input {e.path_or_uri} is a test fixture, not real data")
            elif cache not in p.parents:
                problems.append(f"{mp.name}: input {e.path_or_uri} is outside {cfg.cache_dir}")
        for c in verify_manifest(man, cfg.root):
            if c.status in ("MISMATCH", "MISSING"):
                problems.append(f"{mp.name}: {c.path_or_uri} {c.status}")
    return problems
