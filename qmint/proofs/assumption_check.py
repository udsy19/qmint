"""Theorem precondition predicates and confidence-interval propagation.

Two jobs:

1. Decide whether a request is inside a registered theorem's hypotheses. Hypotheses that
   cannot be verified from numbers (e.g. "no side channels") must be *declared* by the caller in
   ``parameters["declared_assumptions"]``; undeclared ones fail as ``ASSUMPTION_MISSING:<name>``.
   Checkable ones (calibration family, noise present in an ideal game, multiphoton bound present,
   declared noise source, ...) are tested here.

2. Propagate parameter intervals. A parameter may be a scalar or an interval ``{"lo", "hi"}``
   (or a ``qmint.core.contracts.Interval``). The bound is evaluated at the WORST endpoint of each
   interval according to the registry's documented monotonicity direction, and the theorem domain
   must hold on every corner of the parameter box (each constraint is monotone in each variable, so
   corner checks cover the whole box). A confidence interval is *not* a theorem about an adversary;
   this only moves the measured uncertainty into the bound in the conservative direction.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from qmint.core.contracts import CalibrationRecord, EvidenceKind, Interval
from qmint.proofs.registry import Claim

# Where a noisy-game parameter tuple may come from. Anything else is an unknown noise source.
KNOWN_NOISE_SOURCES = frozenset({"calibration", "published_kent_2022", "published_schiansky_2023", "hypothetical"})

# CalibrationRecord interval field -> (game, parameter, transform). Loss l maps to P_det = 1 - l.
_CALIBRATION_MAP: dict[str, dict[str, tuple[str, bool]]] = {
    "S2": {
        "qber_interval": ("E", False),
        "multiphoton_interval": ("P_noqub", False),
        "basis_bias_interval": ("beta_PB", False),
        "loss_interval": ("P_det", True),
    },
    "D1": {
        "qber_interval": ("e_h", False),
        "multiphoton_interval": ("p_m", False),
        "loss_interval": ("l_h", False),
    },
}


@dataclass(frozen=True)
class AssumptionReport:
    checked: tuple[str, ...] = ()
    failed: tuple[str, ...] = ()
    notes: tuple[str, ...] = field(default=())

    @property
    def ok(self) -> bool:
        return not self.failed

    def merged(self, other: AssumptionReport) -> AssumptionReport:
        return AssumptionReport(self.checked + other.checked, self.failed + other.failed, self.notes + other.notes)


# --------------------------------------------------------------------------- #
# Precondition predicates
# --------------------------------------------------------------------------- #


def check_declarations(claim: Claim, params: Mapping[str, Any]) -> AssumptionReport:
    declared = set(params.get("declared_assumptions") or [])
    checked = tuple(n for n in claim.required_declarations if n in declared)
    failed = tuple(f"ASSUMPTION_MISSING:{n}" for n in claim.required_declarations if n not in declared)
    return AssumptionReport(checked, failed)


def check_noise_free(params: Mapping[str, Any], calibration: CalibrationRecord | None) -> AssumptionReport:
    """Ideal games (W1, W1_CV, S1) require an exact verifier on a noise-free, loss-free channel."""
    failed = []
    for key in ("error_threshold", "gamma_err", "loss_tolerance", "loss_threshold", "E", "P_noqub"):
        v = params.get(key)
        if v not in (None, 0, 0.0):
            failed.append(f"OUT_OF_MODEL:ideal_theorem_requires_{key}_absent_or_zero")
    if params.get("verifier", "exact") != "exact":
        failed.append("OUT_OF_MODEL:ideal_theorem_requires_exact_verifier")
    if params.get("verification_oracle_queries", 0) not in (0, None):
        failed.append("OUT_OF_MODEL:verification_oracle_access")
    if calibration is not None:
        for name in ("qber_interval", "loss_interval", "multiphoton_interval"):
            iv = getattr(calibration, name)
            if iv is not None and iv.hi > 0:
                failed.append(f"OUT_OF_MODEL:calibration_{name}_nonzero_use_noisy_game")
    return AssumptionReport(("ideal_noise_free_exact_verifier",) if not failed else (), tuple(failed))


def check_calibration(claim: Claim, calibration: CalibrationRecord | None, params: Mapping[str, Any]) -> AssumptionReport:
    """Noise source must be known: a matching-family calibration or a declared provenance."""
    if calibration is None:
        src = params.get("noise_source")
        if src not in KNOWN_NOISE_SOURCES:
            return AssumptionReport(failed=(f"ASSUMPTION_MISSING:noise_source(got {src!r})",))
        return AssumptionReport(checked=(f"noise_source={src}",))
    failed = []
    if calibration.experiment_family not in claim.calibration_families:
        failed.append(
            f"CALIBRATION_FAMILY_MISMATCH:{calibration.experiment_family!r} not in {claim.calibration_families}"
        )
    if calibration.data_origin not in (EvidenceKind.PHOTON_EXPERIMENT, EvidenceKind.PUBLISHED_AGGREGATE):
        failed.append(f"CALIBRATION_ORIGIN_NOT_EXPERIMENTAL:{calibration.data_origin.value}")
    if not calibration.independence_assumptions:
        failed.append("ASSUMPTION_MISSING:independence_assumptions")
    checked = () if failed else (f"calibration_family={calibration.experiment_family}",)
    return AssumptionReport(checked, tuple(failed))


def check_required_params(params: Mapping[str, Any], names: tuple[str, ...]) -> AssumptionReport:
    missing = tuple(f"PARAMETER_MISSING:{n}" for n in names if params.get(n) is None)
    return AssumptionReport((), missing)


# --------------------------------------------------------------------------- #
# Interval propagation
# --------------------------------------------------------------------------- #


def endpoints(value: Any) -> tuple[float, float]:
    """(lo, hi) of a scalar, an ``Interval`` or a ``{"lo", "hi"}`` mapping."""
    if isinstance(value, Interval):
        return float(value.lo), float(value.hi)
    if isinstance(value, Mapping):
        lo, hi = float(value["lo"]), float(value["hi"])
        if lo > hi:
            raise ValueError("interval lo > hi")
        return lo, hi
    if isinstance(value, bool):
        raise TypeError("boolean is not a numeric parameter")
    x = float(value)
    return x, x


def is_interval(value: Any) -> bool:
    lo, hi = endpoints(value)
    return lo != hi


def worst_case(
    params: Mapping[str, Any], monotonicity: Mapping[str, str], domain_only: tuple[str, ...] | list[str] = ()
) -> dict[str, float]:
    """Scalarise ``params``: each interval goes to the endpoint that makes the bound largest.

    An interval-valued parameter with NO documented direction is refused, never guessed
    (``domain_only`` parameters do not affect the value; their domain is checked on all corners).
    """
    out: dict[str, float] = {}
    for k, v in params.items():
        if k in ("declared_assumptions", "noise_source", "verifier") or v is None or isinstance(v, (str, list, bool)):
            continue
        lo, hi = endpoints(v)
        if lo == hi:
            out[k] = lo
        elif k in monotonicity:
            out[k] = hi if monotonicity[k] == "increasing" else lo
        elif k in domain_only:
            out[k] = hi
        else:
            raise ValueError(f"no documented monotonicity direction for interval parameter {k!r}")
    return out


def corners(params: Mapping[str, Any], keys: tuple[str, ...]) -> Iterator[dict[str, float]]:
    """All corners of the box spanned by the interval parameters among ``keys``."""
    base = {k: endpoints(params[k]) for k in keys if params.get(k) is not None}
    names = list(base)
    for combo in itertools.product(*[sorted(set(base[n])) for n in names]):
        yield dict(zip(names, combo, strict=True))


def params_from_calibration(game: str, calibration: CalibrationRecord) -> dict[str, dict[str, float]]:
    """Map calibration intervals to theorem parameters (documented in the P-S2 / P-D1 dossiers)."""
    out: dict[str, dict[str, float]] = {}
    for fname, (pname, complement) in _CALIBRATION_MAP.get(game, {}).items():
        iv = getattr(calibration, fname)
        if iv is None:
            continue
        lo, hi = (1.0 - iv.hi, 1.0 - iv.lo) if complement else (iv.lo, iv.hi)
        out[pname] = {"lo": lo, "hi": hi}
    return out


def merge_calibration(game: str, params: Mapping[str, Any], calibration: CalibrationRecord | None) -> dict[str, Any]:
    """Fill theorem parameters from calibration intervals; where both are given take the hull
    (never the more optimistic of the two)."""
    out: dict[str, Any] = dict(params)
    if calibration is None:
        return out
    for k, iv in params_from_calibration(game, calibration).items():
        if out.get(k) is None:
            out[k] = iv
        else:
            lo, hi = endpoints(out[k])
            out[k] = {"lo": min(lo, iv["lo"]), "hi": max(hi, iv["hi"])}
    return out
