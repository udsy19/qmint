"""Small helpers shared by the API routers: git sha, provenance, lane probing, conversions."""

from __future__ import annotations

import importlib.util
import pkgutil
from datetime import UTC, datetime
from functools import lru_cache

from qmint.core.config import REPO_ROOT
from qmint.core.contracts import Interval
from qmint.core.manifest import git_state
from qmint.quantum.channels import NoiseSpec

from .schemas import ApiProvenance, ConfidenceInterval, NoiseIn

API_VERSION = "1.0.0"

# Lane -> package (or module) whose real content indicates the lane has been merged.
# A placeholder package containing only ``__init__.py`` counts as NOT merged.
LANE_PACKAGES: dict[str, tuple[str, str]] = {
    "A": ("qmint.research", "research / prior-art matrix"),
    "B": ("qmint.protocols", "protocol simulations"),
    "C": ("qmint.attacks", "attack suites"),
    "D": ("qmint.proofs", "proofs / SDP bounds"),
    "E": ("qmint.photonics", "photonic datasets"),
    "F": ("qmint.quantum", "BB84 circuits, noise, cloners"),
    "G": ("qmint.networks", "relativistic networking / latency"),
    "H": ("qmint.classical", "classical baselines"),
    "I": ("qmint.compiler", "certificate compiler"),
    "J": ("qmint.quantum.ionq", "IonQ / Qollab hardware path"),
    "L": ("qmint.core", "core contracts, records, pipeline"),
    "N": ("qmint.evaluation", "evaluation / figures"),
}


def lane_merged(lane: str) -> tuple[bool, str]:
    """(merged?, detail) without importing the lane: module must exist and carry real code."""
    pkg, _ = LANE_PACKAGES[lane]
    try:
        spec = importlib.util.find_spec(pkg)
    except ModuleNotFoundError:
        spec = None
    if spec is None:
        return False, f"{pkg} not present"
    if spec.submodule_search_locations is None:  # plain module
        return True, pkg
    subs = sorted(m.name for m in pkgutil.iter_modules(spec.submodule_search_locations))
    if not subs:
        return False, f"{pkg} is a placeholder package (lane {lane} not merged)"
    return True, f"{pkg}: {', '.join(subs)}"


@lru_cache(maxsize=1)
def git_sha() -> str:
    try:
        sha, dirty = git_state(REPO_ROOT)
    except RuntimeError:
        return "unknown"
    return sha + ("-dirty" if dirty else "")


@lru_cache(maxsize=1)
def quantum_software() -> dict[str, str]:
    from qmint.quantum.records import software_versions

    return software_versions()


def provenance(
    source: str, *, seed: int | None = None, notes: str | None = None, quantum: bool = False
) -> ApiProvenance:
    return ApiProvenance(
        source=source,
        git_sha=git_sha(),
        generated_at_utc=datetime.now(UTC).isoformat(timespec="seconds"),
        seed=seed,
        software=quantum_software() if quantum else {},
        notes=notes,
    )


def noise_spec(noise: NoiseIn | None) -> NoiseSpec:
    if noise is None:
        return NoiseSpec()
    return NoiseSpec(noise.channel, noise.param, noise.readout_p01, noise.readout_p10)


def ci_from_interval(iv: Interval, confidence: float, method: str) -> ConfidenceInterval:
    return ConfidenceInterval(lo=iv.lo, hi=iv.hi, confidence=confidence, method=method)
