"""Statistical summaries for figures and tables (master plan section 8, "Statistical practice").

Binomial intervals are delegated to :mod:`qmint.attacks.stats` (one implementation in the repo);
this module only adds what figures need on top: a labelled estimate object, the zero-observation
upper bound, and an explicit refusal to turn a worst-case theorem bound into a "CI".

* A Monte Carlo success rate estimates ONE attack: a LOWER bound on the worst-case adversary.
* A theorem bound is a worst-case mathematical bound, never a frequentist interval; it is drawn
  with a different line style and never gets error bars.
* Zero observed successes are reported as an upper confidence limit, never as ``P = 0``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from qmint.attacks.stats import clopper_pearson_interval, wilson_interval

CIMethod = Literal["clopper_pearson", "wilson"]
_METHODS = {"clopper_pearson": clopper_pearson_interval, "wilson": wilson_interval}


@dataclass(frozen=True)
class BinomialEstimate:
    """``successes``/``trials`` with a two-sided interval; ``unit`` names the independent sampling unit."""

    successes: int
    trials: int
    lo: float
    hi: float
    method: CIMethod
    confidence: float
    unit: str

    @property
    def point(self) -> float:
        return self.successes / self.trials

    @property
    def yerr(self) -> tuple[float, float]:
        """(lower, upper) distances from the point, for matplotlib ``errorbar``."""
        return self.point - self.lo, self.hi - self.point

    def label(self) -> str:
        pct = round(self.confidence * 100, 1)
        name = "Clopper-Pearson" if self.method == "clopper_pearson" else "Wilson"
        return f"{name} {pct:g}% (unit: {self.unit})"


def binomial(
    successes: int, trials: int, *, method: CIMethod = "clopper_pearson", confidence: float = 0.95,
    unit: str = "independent trial",
) -> BinomialEstimate:
    if method not in _METHODS:
        raise ValueError(f"unknown CI method {method!r}; expected one of {sorted(_METHODS)}")
    lo, hi = _METHODS[method](successes, trials, confidence)
    return BinomialEstimate(successes, trials, lo, hi, method, confidence, unit)


def zero_success_upper(trials: int, confidence: float = 0.95) -> float:
    """One-sided upper confidence limit when 0 of ``trials`` succeeded: 1 - (1-c)^(1/n).

    This is the only honest summary of "no attack succeeded"; it is not a security bound.
    """
    if trials <= 0:
        raise ValueError("trials must be positive")
    return 1.0 - (1.0 - confidence) ** (1.0 / trials)

