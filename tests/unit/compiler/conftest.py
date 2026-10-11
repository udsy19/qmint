"""Shared fixtures for lane-I compiler tests (deterministic, offline)."""

from __future__ import annotations

import pytest

from qmint.compiler.constraints import Problem, build_grid, d1_device, make_targets, s2_device
from qmint.core.contracts import GameId


def tiny(family: str) -> dict[str, tuple[float, ...]]:
    """A sub-grid of the frozen small grid, cheap enough for exhaustive checks in unit tests."""
    g = build_grid(family, small=True)
    if family == "S2":
        return {"N": g["N"][::2], **{a: g[a][::2] for a in ("r_det", "r_err", "r_cor", "r_unf")}}
    if family == "D1":
        return {"N": g["N"][::2], "delta_d": g["delta_d"][::2], "delta_h": g["delta_h"][::2]}
    return g


@pytest.fixture
def tiny_grid():
    return tiny


@pytest.fixture
def s2_tiny():
    def make(dev: str = "K22-F5b-half", interval: bool = False, eps: float = 1e-9, honest: float = 1e-3, **kw) -> Problem:
        return Problem(f"t/S2/{dev}/{interval}/{eps}/{honest}", GameId.S2, s2_device(dev, interval=interval, **kw),
                       make_targets(GameId.S2, eps, honest), tiny("S2"))
    return make


@pytest.fixture
def d1_tiny():
    def make(dev: str = "D1-PUB-SI", eps: float = 1e-9, honest: float = 1e-3) -> Problem:
        return Problem(f"t/D1/{dev}/{eps}/{honest}", GameId.D1, d1_device(dev), make_targets(GameId.D1, eps, honest), tiny("D1"))
    return make
