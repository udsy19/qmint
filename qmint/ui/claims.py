"""Cited numbers and the claim panel.

Every number the workbench shows is a :class:`Cited` value: it cannot be constructed without a
source record id and an ``EvidenceKind``. A missing value renders as text (for bounds:
"no applicable bound"), never as ``0``. The :class:`ClaimPanel` additionally refuses raw
(uncited) numbers -- both as arguments and as numeric literals typed into the statement text --
and refuses citations to record ids that were not loaded.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from html import escape

from qmint.core.contracts import EvidenceKind
from qmint.ui.evidence_badges import evidence_badge

NO_BOUND = "no applicable bound"
NOT_REPORTED = "not reported"


class UncitedNumberError(ValueError):
    """A number reached a display surface without a source record id / evidence kind."""


@dataclass(frozen=True)
class Cited:
    value: float | int | None
    source_id: str
    evidence: EvidenceKind
    unit: str = ""
    missing: str = NOT_REPORTED  # text shown when value is None -- never "0"

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise UncitedNumberError("number has no source record id")
        object.__setattr__(self, "evidence", EvidenceKind(self.evidence))
        v = self.value
        if v is not None:
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise TypeError(f"Cited value must be a number or None, got {type(v).__name__}")
            if not math.isfinite(v):
                raise ValueError("Cited value must be finite")

    @property
    def text(self) -> str:
        return self.missing if self.value is None else fmt_number(self.value)


def bound(value: float | None, source_id: str, evidence: EvidenceKind | str) -> Cited:
    """A security bound: ``None`` renders as "no applicable bound"."""
    return Cited(value, source_id, EvidenceKind(evidence), unit="probability", missing=NO_BOUND)


def fmt_number(v: float | int) -> str:
    """Deterministic, compact formatting. Never turns a tiny probability into "0"."""
    if isinstance(v, int):
        return str(v)
    if v == 0.0:
        return "0"
    a = abs(v)
    if a < 1e-3 or a >= 1e6:
        return f"{v:.3e}"
    return f"{v:.6g}"


def anchor(record_id: str) -> str:
    return "rec-" + re.sub(r"[^A-Za-z0-9_-]", "-", record_id)


def badge_html(label: str, css: str, title: str) -> str:
    return f'<span class="badge b-{css}" title="{escape(title)}">{escape(label)}</span>'


def render(c: Cited, *, with_badge: bool = True) -> str:
    """HTML for a cited number: value, unit, evidence badge and a link to its source record."""
    if c.value is None:
        val = f'<span class="missing">{escape(c.missing)}</span>'
    else:
        val = f'<data value="{escape(repr(c.value))}">{escape(c.text)}</data>'
        if c.unit:
            val += f' <span class="unit">{escape(c.unit)}</span>'
    parts = [val]
    if with_badge:
        b = evidence_badge(c.evidence)
        parts.append(badge_html(b.label, b.css, b.title))
    parts.append(f'<a class="src" href="#{anchor(c.source_id)}">src: {escape(c.source_id)}</a>')
    return '<span class="cited">' + " ".join(parts) + "</span>"


# A numeric literal not glued to an identifier (so game ids like "W1" / "S2" are allowed).
_RAW_NUMBER = re.compile(r"(?<![A-Za-z0-9_.{-])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


@dataclass
class ClaimPanel:
    """Claims shown in the headline panel. Only cited numbers may enter.

    Statement text may name record/game identifiers inside backticks (rendered as ``<code>``);
    every number must be a ``{i}`` placeholder filled by a :class:`Cited` value.
    """

    known_ids: frozenset[str]
    claims: list[tuple[str, tuple[Cited, ...]]] = field(default_factory=list)

    def add(self, statement: str, values: Iterable[object] = ()) -> None:
        vals = tuple(values)
        for v in vals:
            if not isinstance(v, Cited):
                raise UncitedNumberError(f"uncited value {v!r} cannot enter the claim panel")
            if v.source_id not in self.known_ids:
                raise UncitedNumberError(f"citation {v.source_id!r} does not match any loaded record")
        stripped = re.sub(r"\{\d+\}|`[^`]*`", "", statement)  # placeholders and `identifiers`
        m = _RAW_NUMBER.search(stripped)
        if m:
            raise UncitedNumberError(f"statement contains uncited numeric literal {m.group(0)!r}")
        n_slots = len(set(re.findall(r"\{(\d+)\}", statement)))
        if n_slots != len(vals):
            raise UncitedNumberError("every placeholder needs exactly one cited value")
        self.claims.append((statement, vals))

    def render(self) -> str:
        if not self.claims:
            return '<p class="muted">No claims: no record supports one.</p>'
        items = []
        for statement, vals in self.claims:
            text = re.sub(r"`([^`]*)`", r"<code>\1</code>", escape(statement))
            for i, v in enumerate(vals):
                text = text.replace("{" + str(i) + "}", render(v))
            items.append(f"<li>{text}</li>")
        return '<ul class="claims">' + "".join(items) + "</ul>"
