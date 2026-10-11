"""Structured JSON logging with secret redaction.

Every record is one JSON object per line: ``ts``, ``level``, ``logger``, ``event`` and
``fields``. Before emission, ``redact`` is applied to the message and every field:

  * keys that look like credentials or issuer secrets (``api_key``, ``password``,
    ``bases``, ``bits``, ``secret*``, ``*_key``, ``*_token`` ...) have their values replaced;
  * any ``IssuerSecret`` instance is replaced (its repr is already redacted; this also
    keeps it out of ``fields``);
  * the literal values of credential-named environment variables (e.g. ``IONQ_API_KEY``)
    are scrubbed from every string, wherever they appear;
  * ``Bearer <token>`` substrings are scrubbed.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from qmint.core.contracts import _FORBIDDEN_PUBLIC_KEYS, IssuerSecret

REDACTED = "<REDACTED>"
_CRED_KEY = re.compile(
    r"(secret|passw|api[_-]?key|apikey|credential|private[_-]?key|authorization|bearer|(^|_)token$|_key$)",
    re.IGNORECASE,
)
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
_MIN_ENV_SECRET_LEN = 6


def is_secret_key(key: str) -> bool:
    return key.lower() in _FORBIDDEN_PUBLIC_KEYS or bool(_CRED_KEY.search(key))


def env_secret_values(env: Mapping[str, str] | None = None) -> list[str]:
    """Values of environment variables whose names look like credentials (longest first)."""
    env = os.environ if env is None else env
    vals = {v for k, v in env.items() if _CRED_KEY.search(k) and len(v) >= _MIN_ENV_SECRET_LEN}
    return sorted(vals, key=len, reverse=True)


def _scrub(text: str, secrets: list[str]) -> str:
    for s in secrets:
        if s in text:
            text = text.replace(s, REDACTED)
    return _BEARER.sub("Bearer " + REDACTED, text)


def redact(obj: Any, *, _secrets: list[str] | None = None) -> Any:
    secrets = env_secret_values() if _secrets is None else _secrets
    if isinstance(obj, IssuerSecret):
        return "<IssuerSecret REDACTED>"
    if isinstance(obj, BaseModel):  # walk fields so secret-like keys nested in models are redacted too
        return redact({name: getattr(obj, name) for name in type(obj).model_fields}, _secrets=secrets)
    if isinstance(obj, Mapping):
        return {
            str(k): (REDACTED if is_secret_key(str(k)) else redact(v, _secrets=secrets)) for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [redact(v, _secrets=secrets) for v in obj]
    if isinstance(obj, str):
        return _scrub(obj, secrets)
    if obj is None or isinstance(obj, (bool, int, float)):
        return obj
    return _scrub(repr(obj), secrets)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        secrets = env_secret_values()
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": redact(record.getMessage(), _secrets=secrets),
            "fields": redact(getattr(record, "fields", {}), _secrets=secrets),
        }
        if record.exc_info:
            payload["exc"] = redact(self.formatException(record.exc_info), _secrets=secrets)
        return json.dumps(payload, sort_keys=True, default=str)


_CONFIGURED = False


def get_logger(name: str = "qmint", stream: Any = None, level: int = logging.INFO) -> logging.Logger:
    """Logger under the ``qmint`` hierarchy emitting redacted JSON lines (stderr by default)."""
    global _CONFIGURED
    root = logging.getLogger("qmint")
    if not _CONFIGURED or stream is not None:
        for h in list(root.handlers):
            root.removeHandler(h)
        handler = logging.StreamHandler(stream or sys.stderr)
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)
        root.setLevel(level)
        root.propagate = False
        _CONFIGURED = True
    return logging.getLogger(name if name.startswith("qmint") else f"qmint.{name}")


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields: Any) -> None:
    logger.log(level, event, extra={"fields": fields})
