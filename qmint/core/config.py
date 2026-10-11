"""Central runtime configuration: paths, seeds, offline mode, paid-hardware gate.

Environment variables (all optional; defaults are the safe choice):
  QMINT_ALLOW_NETWORK         "1"/"true"/"yes" enables public-network access. Default: DENIED.
  QMINT_ALLOW_PAID_HARDWARE   "1"/"true"/"yes" enables paid QPU jobs. Default: DENIED.
  QMINT_SEED                  base integer seed. Default: 42.
  QMINT_ROOT                  repository root. Default: the directory containing ``qmint/``.

Network denial has two layers: ``require_network`` is the cooperative check every
fetcher must call, and ``network_guard`` blocks socket connections process-wide so a
fetcher that forgets the check still fails loudly instead of silently going online.
"""

from __future__ import annotations

import hashlib
import os
import socket
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

DEFAULT_SEED = 42
_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"", "0", "false", "no", "off"})
REPO_ROOT = Path(__file__).resolve().parents[2]


class NetworkDisabledError(RuntimeError):
    """Raised when code attempts network access while QMINT_ALLOW_NETWORK is off."""


class PaidHardwareDisabledError(RuntimeError):
    """Raised when code attempts a paid hardware job without explicit opt-in."""


def _flag(env: Mapping[str, str], name: str) -> bool:
    raw = env.get(name, "").strip().lower()
    if raw in _TRUE:
        return True
    if raw in _FALSE:
        return False
    raise ValueError(f"{name}={raw!r} is not a boolean flag (use 1/0, true/false)")


@dataclass(frozen=True)
class QMintConfig:
    root: Path
    seed: int = DEFAULT_SEED
    allow_network: bool = False
    allow_paid_hardware: bool = False

    @property
    def experiments_dir(self) -> Path:
        return self.root / "experiments"

    @property
    def results_dir(self) -> Path:
        return self.experiments_dir / "results"

    @property
    def cache_dir(self) -> Path:
        return self.root / "datasets" / "cache"

    @property
    def lock_file(self) -> Path:
        return self.root / "requirements.lock"

    def offline(self) -> QMintConfig:
        return replace(self, allow_network=False)


def load_config(env: Mapping[str, str] | None = None, **overrides: Any) -> QMintConfig:
    env = os.environ if env is None else env
    cfg = QMintConfig(
        root=Path(env.get("QMINT_ROOT") or REPO_ROOT).resolve(),
        seed=int(env.get("QMINT_SEED", DEFAULT_SEED)),
        allow_network=_flag(env, "QMINT_ALLOW_NETWORK"),
        allow_paid_hardware=_flag(env, "QMINT_ALLOW_PAID_HARDWARE"),
    )
    return replace(cfg, **overrides) if overrides else cfg


def require_network(cfg: QMintConfig, purpose: str) -> None:
    if not cfg.allow_network:
        raise NetworkDisabledError(f"network access denied (QMINT_ALLOW_NETWORK off): {purpose}")


def require_paid_hardware(cfg: QMintConfig, purpose: str) -> None:
    if not cfg.allow_paid_hardware:
        raise PaidHardwareDisabledError(f"paid hardware denied (QMINT_ALLOW_PAID_HARDWARE off): {purpose}")


def derive_seed(base: int, label: str) -> int:
    """Deterministic, platform-independent child seed (no reliance on Python's hash())."""
    digest = hashlib.sha256(f"{base}:{label}".encode()).digest()
    return int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)


def make_rng(seed: int, label: str | None = None) -> Any:
    """numpy Generator for `seed` (optionally a labelled child stream)."""
    import numpy as np

    return np.random.default_rng(derive_seed(seed, label) if label is not None else seed)


@contextmanager
def network_guard(enabled: bool = True) -> Iterator[None]:
    """Block all non-UNIX-socket connections for the duration of the block."""
    if not enabled:
        yield
        return
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_create = socket.create_connection

    def _deny(*_a: Any, **_k: Any) -> Any:
        raise NetworkDisabledError("network access denied by qmint.core.config.network_guard (offline mode)")

    def _connect(self: socket.socket, address: Any) -> Any:
        if self.family == getattr(socket, "AF_UNIX", None):
            return original_connect(self, address)
        return _deny()

    def _connect_ex(self: socket.socket, address: Any) -> Any:
        if self.family == getattr(socket, "AF_UNIX", None):
            return original_connect_ex(self, address)
        return _deny()

    socket.socket.connect = _connect  # type: ignore[method-assign]
    socket.socket.connect_ex = _connect_ex  # type: ignore[method-assign]
    socket.create_connection = _deny  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket.connect = original_connect  # type: ignore[method-assign]
        socket.socket.connect_ex = original_connect_ex  # type: ignore[method-assign]
        socket.create_connection = original_create  # type: ignore[assignment]
