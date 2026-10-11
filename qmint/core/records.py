"""Append-only experiment record store.

Layout (master plan section 6):
  experiments/run_registry.jsonl   one canonical-JSON index line per record, append-only
  experiments/results/<id>.json    the full ``ExperimentRecord`` envelope, created exclusively

Every record wraps exactly one frozen contract payload (C0-C7), validated on write and on
read. A record is refused when it lacks an evidence kind or provenance (git sha,
environment-lock sha256, command), when an id already exists (no overwrite), or when
any issuer-secret material would be written: ``IssuerSecret`` objects (refused by the
frozen canonical serializer), TEST_ONLY revelations, or credential env-var values.

Stochastic results are never silently trusted: a ``ReproCheck`` (same seed, run twice,
compare canonical hashes) sets ``reproducibility``; a mismatch flags
``IRREPRODUCIBLE_STOCHASTIC_RESULT``.

``ExperimentRecord`` is a lane-L envelope, not a frozen contract; the payload inside it is.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from qmint.core.config import QMintConfig
from qmint.core.contracts import CONTRACT_MODELS, EvidenceKind, IssuerSecret, SecretBoundaryError, Sha256Hex
from qmint.core.logging import env_secret_values
from qmint.core.manifest import env_lock_hash, git_state
from qmint.core.serialization import canonical_hash, canonical_json

# Contract field carrying the payload's evidence kind; None = contract has no such field.
EVIDENCE_FIELD: dict[str, str | None] = {
    "protocol": None,
    "token": None,
    "measurement": "source_kind",
    "photon": None,
    "calibration": "data_origin",
    "attack": "evidence_kind",
    "network": None,
    "trace": "latency_evidence",
    "certificate": "evidence_kind",
    "bound_request": None,
    "bound_result": "evidence_kind",
    "benchmark": "evidence_kind",
    "manifest": "evidence_kind",
}
assert set(EVIDENCE_FIELD) == set(CONTRACT_MODELS), "EVIDENCE_FIELD out of sync with frozen contracts"

STOCHASTIC_EVIDENCE = frozenset(
    {EvidenceKind.MONTE_CARLO, EvidenceKind.SIMULATOR_NOISY, EvidenceKind.SIMULATOR_IDEAL, EvidenceKind.QPU}
)
_ID_SAFE = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")


class RecordExistsError(FileExistsError):
    """Append-only store: a record id may be written once."""


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    git_sha: str = Field(min_length=7)
    environment_lock: Sha256Hex  # sha256 of requirements.lock
    command: str = Field(min_length=1)
    seed: int | None = None
    manifest_id: str | None = None


class ExperimentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    record_id: str = Field(min_length=1)
    contract: Literal[tuple(CONTRACT_MODELS)]  # type: ignore[valid-type]
    schema_version: Literal["1.0.0"] = "1.0.0"
    evidence_kind: EvidenceKind
    provenance: Provenance
    payload: dict[str, Any]
    payload_sha256: Sha256Hex
    reproducibility: Literal["DETERMINISTIC_VERIFIED", "NONDETERMINISTIC", "UNCHECKED"]
    flags: list[str] = Field(default_factory=list)
    created_utc: str


@dataclass(frozen=True)
class ReproCheck:
    seed: int
    hashes: tuple[str, ...]

    @property
    def deterministic(self) -> bool:
        return len(set(self.hashes)) == 1


def check_reproducible(producer: Callable[[int], Any], seed: int, runs: int = 2) -> ReproCheck:
    """Run ``producer(seed)`` ``runs`` times and compare canonical hashes of the outputs."""
    if runs < 2:
        raise ValueError("reproducibility needs at least two runs")
    return ReproCheck(seed=seed, hashes=tuple(canonical_hash(producer(seed)) for _ in range(runs)))


def current_provenance(cfg: QMintConfig, command: str, seed: int | None = None) -> Provenance:
    sha, dirty = git_state(cfg.root)
    return Provenance(
        git_sha=f"{sha}-dirty" if dirty else sha, environment_lock=env_lock_hash(cfg.root), command=command, seed=seed
    )


def contains_issuer_secret(obj: Any) -> bool:
    """True if an ``IssuerSecret`` is reachable from ``obj`` through model fields or containers.

    Needed because the frozen ``canonical_json`` only catches an IssuerSecret at the top of a
    branch it reaches before ``model_dump``: a secret nested in an ``Any``-typed contract field
    (``parameters``, ``configuration``, ``detail``, ``extra``) is dumped by pydantic's core
    serializer, which bypasses IssuerSecret's overridden ``model_dump`` and emits bases/bits.
    """
    if isinstance(obj, IssuerSecret):
        return True
    if isinstance(obj, BaseModel):
        return any(contains_issuer_secret(getattr(obj, name)) for name in type(obj).model_fields)
    if isinstance(obj, Mapping):
        return any(contains_issuer_secret(k) or contains_issuer_secret(v) for k, v in obj.items())
    if isinstance(obj, (list, tuple, set, frozenset)):
        return any(contains_issuer_secret(v) for v in obj)
    return False


def _assert_no_secret_material(obj: Any, text: str) -> None:
    def walk(o: Any) -> None:
        if isinstance(o, Mapping):
            if "TEST_ONLY" in o:
                raise SecretBoundaryError("refusing to store a TEST_ONLY issuer-secret revelation")
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(obj)
    for s in env_secret_values():
        if s in text:
            raise SecretBoundaryError("refusing to store a record containing a credential env-var value")


class RecordStore:
    def __init__(self, experiments_dir: Path):
        self.experiments_dir = Path(experiments_dir)
        self.results_dir = self.experiments_dir / "results"
        self.registry = self.experiments_dir / "run_registry.jsonl"

    def _path(self, record_id: str) -> Path:
        if not record_id or set(record_id) - _ID_SAFE or record_id.startswith("."):
            raise ValueError(f"unsafe record id {record_id!r}")
        return self.results_dir / f"{record_id}.json"

    def append(
        self,
        contract: str,
        payload: BaseModel | Mapping[str, Any],
        *,
        provenance: Provenance,
        evidence_kind: EvidenceKind | str | None = None,
        record_id: str | None = None,
        repro: ReproCheck | None = None,
    ) -> ExperimentRecord:
        if contract not in CONTRACT_MODELS:
            raise ValueError(f"unknown contract {contract!r}; expected one of {sorted(CONTRACT_MODELS)}")
        if not isinstance(provenance, Provenance):
            raise TypeError("provenance must be a Provenance (git sha, env lock sha256, command)")
        model = CONTRACT_MODELS[contract]
        if contains_issuer_secret(payload):
            raise SecretBoundaryError("refusing to store a record containing an IssuerSecret")
        obj = payload if isinstance(payload, model) else model.model_validate(payload)
        if contains_issuer_secret(obj):
            raise SecretBoundaryError("refusing to store a record containing an IssuerSecret")
        text = canonical_json(obj)  # frozen serializer: refuses top-level IssuerSecret, NaN/Inf
        plain = json.loads(text)
        _assert_no_secret_material(plain, text)

        field = EVIDENCE_FIELD[contract]
        payload_kind = EvidenceKind(plain[field]) if field else None
        explicit = EvidenceKind(evidence_kind) if evidence_kind is not None else None
        if payload_kind and explicit and payload_kind != explicit:
            raise ValueError(f"evidence_kind {explicit.value} contradicts payload {field}={payload_kind.value}")
        kind = payload_kind or explicit
        if kind is None:
            raise ValueError(f"contract {contract!r} carries no evidence kind; pass evidence_kind explicitly")

        payload_sha = canonical_hash(plain)
        flags: list[str] = []
        if repro is None:
            reproducibility = "UNCHECKED"
            if kind in STOCHASTIC_EVIDENCE:
                flags.append("REPRODUCIBILITY_UNCHECKED")
        elif not repro.deterministic:
            reproducibility = "NONDETERMINISTIC"
            flags.append("IRREPRODUCIBLE_STOCHASTIC_RESULT")
        else:
            reproducibility = "DETERMINISTIC_VERIFIED"
            if repro.hashes[0] != payload_sha:
                flags.append("REPRO_HASH_DIFFERS_FROM_PAYLOAD")
        if kind in STOCHASTIC_EVIDENCE and provenance.seed is None:
            flags.append("NO_SEED")

        rid = record_id or f"{contract}-{payload_sha[:16]}"
        record = ExperimentRecord(
            record_id=rid,
            contract=contract,
            evidence_kind=kind,
            provenance=provenance,
            payload=plain,
            payload_sha256=payload_sha,
            reproducibility=reproducibility,
            flags=flags,
            created_utc=datetime.now(UTC).isoformat(),
        )
        path = self._path(rid)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        body = canonical_json(record) + "\n"
        try:
            with open(path, "x", encoding="utf-8") as f:
                f.write(body)
        except FileExistsError as e:
            raise RecordExistsError(f"record {rid} already exists; store is append-only") from e
        index = {
            "record_id": rid,
            "contract": contract,
            "evidence_kind": kind.value,
            "payload_sha256": payload_sha,
            "record_sha256": canonical_hash(record),
            "result_path": path.relative_to(self.experiments_dir).as_posix(),
            "reproducibility": reproducibility,
            "flags": flags,
            "created_utc": record.created_utc,
        }
        with open(self.registry, "a", encoding="utf-8") as f:
            f.write(canonical_json(index) + "\n")
            f.flush()
            os.fsync(f.fileno())
        return record

    def get(self, record_id: str) -> ExperimentRecord:
        record = ExperimentRecord.model_validate_json(self._path(record_id).read_text(encoding="utf-8"))
        CONTRACT_MODELS[record.contract].model_validate(record.payload)
        if canonical_hash(record.payload) != record.payload_sha256:
            raise ValueError(f"record {record_id} payload hash mismatch (tampered?)")
        return record

    def iter_registry(self) -> Iterator[dict[str, Any]]:
        if not self.registry.is_file():
            return
        with open(self.registry, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)
