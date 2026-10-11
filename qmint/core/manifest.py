"""EvidenceManifest (C6) builder and verifier.

A manifest pins every input, output and script of a run by SHA-256, plus the git
commit, the environment lock hash (sha256 of ``requirements.lock``) and the seeds.
``verify_manifest`` re-hashes every local entry and reports each mismatch; remote
URIs cannot be re-hashed offline and are reported as unverified, never as passing.
"""

from __future__ import annotations

import platform
import re
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from qmint.core.contracts import EvidenceKind, EvidenceManifest, ManifestEntry
from qmint.core.serialization import canonical_json, file_sha256

_URI = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")  # zenodo:..., https://..., but not C:\ (not on posix)
LOCK_NAME = "requirements.lock"


def git_state(root: Path) -> tuple[str, bool]:
    """(HEAD sha, dirty?). Raises RuntimeError outside a git checkout -- never invents a sha."""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain", "--untracked-files=no"],
                cwd=root, capture_output=True, text=True, check=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError) as e:
        raise RuntimeError(f"cannot determine git sha in {root}: {e}") from e
    return sha, dirty


def env_lock_hash(root: Path) -> str:
    lock = root / LOCK_NAME
    if not lock.is_file():
        raise FileNotFoundError(f"environment lock {lock} missing; cannot pin environment")
    return file_sha256(lock)


def _rel(path: Path, root: Path) -> str:
    p = path.resolve()
    try:
        return p.relative_to(root.resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def _entries(
    paths: Iterable[str | Path], role: Literal["input", "output", "script", "environment"],
    root: Path, origin: Literal["original", "derived"],
) -> list[ManifestEntry]:
    out = []
    for p in paths:
        path = Path(p) if Path(p).is_absolute() else root / p
        if not path.is_file():
            raise FileNotFoundError(f"manifest {role} {p} does not exist")
        out.append(
            ManifestEntry(path_or_uri=_rel(path, root), sha256=file_sha256(path), role=role, original_or_derived=origin)
        )
    return out


def build_manifest(
    *,
    manifest_id: str,
    command: str,
    evidence_kind: EvidenceKind,
    root: Path,
    inputs: Sequence[str | Path] = (),
    outputs: Sequence[str | Path] = (),
    scripts: Sequence[str | Path] = (),
    seeds: Sequence[int] = (),
    source_urls: Sequence[str] = (),
    retrieved_utc: str | None = None,
    original_inputs: bool = False,
) -> EvidenceManifest:
    """Hash all files and pin git sha + env lock. The lock file itself is an 'environment' entry."""
    sha, dirty = git_state(root)
    lock_hash = env_lock_hash(root)
    entries = (
        _entries(inputs, "input", root, "original" if original_inputs else "derived")
        + _entries(outputs, "output", root, "derived")
        + _entries(scripts, "script", root, "original")
        + _entries([root / LOCK_NAME], "environment", root, "original")
    )
    return EvidenceManifest(
        manifest_id=manifest_id,
        created_utc=datetime.now(UTC).isoformat(),
        source_urls=list(source_urls),
        retrieved_utc=retrieved_utc,
        command=command,
        git_sha=sha,
        environment={
            "env_lock_sha256": lock_hash,
            "git_dirty": str(dirty).lower(),
            "python": platform.python_version(),
            "platform": f"{sys.platform}-{platform.machine()}",
        },
        seeds=list(seeds),
        evidence_kind=evidence_kind,
        entries=entries,
    )


def write_manifest(manifest: EvidenceManifest, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(manifest) + "\n", encoding="utf-8")
    return path


MANIFEST_SUFFIXES = (".json", ".yaml", ".yml")


def load_manifest(path: Path) -> EvidenceManifest:
    """Load an EvidenceManifest from canonical JSON or (for hand-maintained dataset manifests) YAML."""
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        import yaml

        return EvidenceManifest.model_validate(yaml.safe_load(text))
    return EvidenceManifest.model_validate_json(text)


def is_evidence_manifest_file(path: Path) -> bool:
    """True for a JSON file, or a YAML file that declares ``manifest_id`` (an EvidenceManifest).

    Other YAML files in a manifest directory (lane E's dataset descriptors) are not manifests.
    """
    if path.suffix == ".json":
        return True
    if path.suffix not in (".yaml", ".yml"):
        return False
    import yaml

    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    return isinstance(doc, dict) and "manifest_id" in doc


@dataclass(frozen=True)
class EntryCheck:
    path_or_uri: str
    status: Literal["OK", "MISMATCH", "MISSING", "UNVERIFIED_REMOTE"]
    expected: str
    actual: str | None


def verify_manifest(manifest: EvidenceManifest, root: Path) -> list[EntryCheck]:
    checks = []
    for e in manifest.entries:
        if _URI.match(e.path_or_uri):
            checks.append(EntryCheck(e.path_or_uri, "UNVERIFIED_REMOTE", e.sha256, None))
            continue
        path = Path(e.path_or_uri)
        path = path if path.is_absolute() else root / path
        if not path.is_file():
            checks.append(EntryCheck(e.path_or_uri, "MISSING", e.sha256, None))
            continue
        actual = file_sha256(path)
        checks.append(EntryCheck(e.path_or_uri, "OK" if actual == e.sha256 else "MISMATCH", e.sha256, actual))
    lock = root / LOCK_NAME
    want = manifest.environment.get("env_lock_sha256")
    if want is not None:
        actual = file_sha256(lock) if lock.is_file() else None
        status = "MISSING" if actual is None else ("OK" if actual == want else "MISMATCH")
        checks.append(EntryCheck("environment.env_lock_sha256", status, want, actual))
    return checks
