"""Load frozen-contract records (C0-C6) from JSON files for the workbench.

Each JSON file holds one record. Its contract model is inferred from a discriminating key
signature and then validated with the frozen Pydantic model -- an invalid record is reported
as skipped (with the validation reason), never silently coerced.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ValidationError

from qmint.core.contracts import (
    AttackResult,
    BenchmarkRecord,
    CalibrationRecord,
    EvidenceKind,
    EvidenceManifest,
    ProtocolSpec,
    SecurityCertificate,
    SpacetimeNetwork,
    TokenRecord,
    TransactionTrace,
)
from qmint.core.serialization import canonical_hash

# (kind, model, discriminating keys, id field or None -> derived from file name)
_SIGNATURES: tuple[tuple[str, type[BaseModel], frozenset[str], str | None], ...] = (
    ("attack", AttackResult, frozenset({"attack_id", "game_id", "trials"}), "attack_id"),
    ("trace", TransactionTrace, frozenset({"trace_id", "events"}), "trace_id"),
    ("calibration", CalibrationRecord, frozenset({"calibration_id", "data_origin"}), "calibration_id"),
    ("benchmark", BenchmarkRecord, frozenset({"record_id", "classical_or_quantum"}), "record_id"),
    ("manifest", EvidenceManifest, frozenset({"manifest_id", "entries"}), "manifest_id"),
    ("network", SpacetimeNetwork, frozenset({"network_id", "sites"}), "network_id"),
    ("protocol", ProtocolSpec, frozenset({"protocol_id", "adversary_game_id"}), None),
    ("token", TokenRecord, frozenset({"token_id", "n_prepared"}), "token_id"),
    ("certificate", SecurityCertificate, frozenset({"game_id", "security_model_id", "reason"}), None),
)


@dataclass(frozen=True)
class LoadedRecord:
    kind: str
    record_id: str  # unique within a build; used as the citation target
    model: BaseModel
    sha256: str  # canonical hash of the validated record
    source_path: str  # path relative to the records root (POSIX)

    @property
    def evidence(self) -> EvidenceKind:
        return record_evidence(self.kind, self.model)


@dataclass(frozen=True)
class Skipped:
    source_path: str
    reason: str


def record_evidence(kind: str, m: BaseModel) -> EvidenceKind:
    """The single EvidenceKind a record is labelled with (from contract fields only)."""
    if kind == "calibration":
        return m.data_origin  # type: ignore[attr-defined]
    if kind == "trace":
        return m.latency_evidence  # type: ignore[attr-defined]
    if kind == "network":
        kinds = {lk.latency_evidence for lk in m.links}  # type: ignore[attr-defined]
        return kinds.pop() if len(kinds) == 1 else EvidenceKind.UNCERTIFIED
    if kind in ("protocol", "token"):
        return EvidenceKind.UNCERTIFIED  # descriptive records carry no evidence of security
    return m.evidence_kind  # type: ignore[attr-defined]


def classify(data: dict) -> tuple[str, type[BaseModel], str | None]:
    keys = set(data)
    for kind, model, sig, id_field in _SIGNATURES:
        if sig <= keys:
            return kind, model, id_field
    raise ValueError("unrecognised record: no frozen-contract key signature matched")


def load_records(roots: list[Path]) -> tuple[list[LoadedRecord], list[Skipped]]:
    """Load every ``*.json`` under each root (sorted, deterministic)."""
    loaded: list[LoadedRecord] = []
    skipped: list[Skipped] = []
    seen: set[str] = set()
    for root in roots:
        root = Path(root)
        files = sorted(root.rglob("*.json")) if root.is_dir() else [root]
        for path in files:
            rel = f"{root.name}/{path.relative_to(root).as_posix()}" if root.is_dir() else path.name
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("top-level JSON is not an object")
                kind, model_cls, id_field = classify(data)
                model = model_cls.model_validate(data)
            except (ValueError, ValidationError) as exc:  # ValidationError subclasses ValueError
                first = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
                skipped.append(Skipped(rel, first))
                continue
            rid = str(data[id_field]) if id_field else f"{kind}:{path.stem}"
            if rid in seen:
                skipped.append(Skipped(rel, f"duplicate record id {rid!r}"))
                continue
            seen.add(rid)
            loaded.append(LoadedRecord(kind, rid, model, canonical_hash(model), rel))
    loaded.sort(key=lambda r: (r.kind, r.record_id))
    skipped.sort(key=lambda s: s.source_path)
    return loaded, skipped
