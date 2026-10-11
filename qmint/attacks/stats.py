"""Binomial confidence intervals for Monte Carlo attack estimates.

A Monte Carlo success rate is an estimate of ONE attack's success probability, i.e. a
LOWER bound on the worst-case adversary. It is never an upper bound on adversaries.
"""

from __future__ import annotations

import math

from scipy.stats import beta, norm


def _check(successes: int, trials: int) -> None:
    if trials <= 0 or not 0 <= successes <= trials:
        raise ValueError("need trials > 0 and 0 <= successes <= trials")


def wilson_interval(successes: int, trials: int, confidence: float = 0.95) -> tuple[float, float]:
    _check(successes, trials)
    z = float(norm.ppf(0.5 + confidence / 2))
    p = successes / trials
    den = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / den
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / den
    return max(0.0, centre - half), min(1.0, centre + half)


def clopper_pearson_interval(successes: int, trials: int, confidence: float = 0.95) -> tuple[float, float]:
    """Exact (conservative) two-sided binomial interval."""
    _check(successes, trials)
    a = 1 - confidence
    lo = 0.0 if successes == 0 else float(beta.ppf(a / 2, successes, trials - successes + 1))
    hi = 1.0 if successes == trials else float(beta.ppf(1 - a / 2, successes + 1, trials - successes))
    return lo, hi
