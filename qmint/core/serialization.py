"""Canonical JSON serialization and hashing (frozen).

Canonical form: UTF-8, sorted keys, no insignificant whitespace, NaN/Inf rejected,
enums by value. Any object graph containing an ``IssuerSecret`` is refused.
"""

from __future__ import annotations

import hashlib
import json
import math
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from qmint.core.contracts import CONTRACT_MODELS, IssuerSecret, SecretBoundaryError


def _plain(obj: Any) -> Any:
    if isinstance(obj, IssuerSecret):
        raise SecretBoundaryError("refusing to serialize IssuerSecret into a public artifact")
    if isinstance(obj, BaseModel):
        return _plain(obj.model_dump(mode="python"))
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {str(k): _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    if isinstance(obj, float) and not math.isfinite(obj):
        raise ValueError("non-finite float in canonical JSON")
    return obj


def canonical_json(obj: Any) -> str:
    return json.dumps(_plain(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def canonical_hash(obj: Any) -> str:
    return sha256_hex(canonical_json(obj))


def file_sha256(path: str | Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def json_schemas() -> dict[str, dict[str, Any]]:
    """JSON Schema for every frozen contract model."""
    return {name: model.model_json_schema() for name, model in CONTRACT_MODELS.items()}


def write_schemas(out_dir: str | Path) -> dict[str, str]:
    """Write schemas/v1/<name>.json; return {name: sha256 of canonical schema}."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    for name, schema in json_schemas().items():
        text = json.dumps(schema, sort_keys=True, indent=2) + "\n"
        (out / f"{name}.json").write_text(text, encoding="utf-8")
        hashes[name] = canonical_hash(schema)
    return hashes
