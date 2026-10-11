"""Machine-readable theorem registry (master plan 3.6).

Source of truth: ``proofs/OBLIGATIONS.yaml``. This module loads it into frozen,
validated records so code never hard-codes a theorem's provenance. Every bound a
``ProofEvaluator`` emits carries a ``bound_id`` from this registry as its
``theorem_id``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from qmint.core.contracts import GameId, ProofStatus, SecurityAxis

OBLIGATIONS_PATH = Path(__file__).resolve().parents[2] / "proofs" / "OBLIGATIONS.yaml"

REQUIRED_CLAIM_IDS = frozenset(
    {"P-W1", "P-W1CV", "P-W2", "P-S1", "P-S2", "P-S3", "P-D1", "P-C1", "P-OPT", "P-PRIV"}
)


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SourceRecord(_Frozen):
    citation: str = Field(min_length=1)
    url: str = Field(min_length=1)
    retrieved_files: list[dict[str, str]] = Field(min_length=1)
    correction_status: str = Field(min_length=1)
    equation_text_source: str | None = None


class BoundSpec(_Frozen):
    bound_id: str = Field(min_length=1)
    axis: SecurityAxis
    anchor: str = Field(min_length=1)
    formula: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    # parameter -> direction in which the bound gets WORSE as the parameter grows
    monotonicity: dict[str, Literal["increasing", "decreasing"]] = Field(default_factory=dict)
    # parameters that appear only in the domain constraints (value independent of them)
    domain_only: list[str] = Field(default_factory=list)


class Claim(_Frozen):
    """One proof obligation with every field required by master plan 3.6."""

    claim_id: str
    protocol: str
    game: str  # a GameId value, or "any" for cross-cutting obligations (P-OPT)
    source: str
    source_and_theorem: str = Field(min_length=1)
    assumptions: list[str] = Field(min_length=1)
    required_declarations: list[str] = Field(default_factory=list)
    calibration_families: list[str] = Field(default_factory=list)
    finite_n_or_asymptotic: str = Field(min_length=1)
    parameters: dict[str, str]
    quantifier_over_adversaries: str = Field(min_length=1)
    mathematical_bound: str = Field(min_length=1)
    numerical_method: str = Field(min_length=1)
    verification_script: str = Field(min_length=1)
    independent_crosscheck: str = Field(min_length=1)
    caveats: list[str] = Field(min_length=1)
    status: ProofStatus
    reproduced_examples: list[str] = Field(default_factory=list)
    bounds: list[BoundSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent(self) -> Claim:
        if self.game != "any":
            GameId(self.game)
        if self.status == ProofStatus.UNSUPPORTED and self.bounds and self.claim_id != "P-PRIV":
            raise ValueError(f"{self.claim_id}: UNSUPPORTED claim must not register bounds")
        for b in self.bounds:
            if not b.bound_id.startswith(self.claim_id + "/"):
                raise ValueError(f"bound {b.bound_id} not namespaced under {self.claim_id}")
        return self


class Registry(_Frozen):
    schema_version: str
    sources: dict[str, SourceRecord]
    claims: list[Claim]

    @model_validator(mode="after")
    def _complete(self) -> Registry:
        ids = [c.claim_id for c in self.claims]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate claim_id")
        missing = REQUIRED_CLAIM_IDS - set(ids)
        if missing:
            raise ValueError(f"registry missing mandatory obligations: {sorted(missing)}")
        for c in self.claims:
            if c.source != "none" and c.source not in self.sources:
                raise ValueError(f"{c.claim_id}: unknown source {c.source}")
        bids = [b.bound_id for c in self.claims for b in c.bounds]
        if len(bids) != len(set(bids)):
            raise ValueError("duplicate bound_id")
        return self

    def claim(self, claim_id: str) -> Claim:
        for c in self.claims:
            if c.claim_id == claim_id:
                return c
        raise KeyError(claim_id)

    def bound(self, bound_id: str) -> tuple[Claim, BoundSpec]:
        for c in self.claims:
            for b in c.bounds:
                if b.bound_id == bound_id:
                    return c, b
        raise KeyError(bound_id)

    def bound_for(self, game: GameId | str, axis: SecurityAxis | str) -> tuple[Claim, BoundSpec] | None:
        """The unique registered bound for (game, axis), or None if no theorem exists."""
        g, a = GameId(game).value, SecurityAxis(axis)
        hits = [(c, b) for c in self.claims if c.game == g for b in c.bounds if b.axis == a]
        if len(hits) > 1:
            raise ValueError(f"ambiguous registry entries for {g}/{a.value}")
        return hits[0] if hits else None


def load_registry(path: str | Path = OBLIGATIONS_PATH) -> Registry:
    with open(path, encoding="utf-8") as f:
        return Registry.model_validate(yaml.safe_load(f))


@lru_cache(maxsize=1)
def default_registry() -> Registry:
    return load_registry()
