"""Published finite-size bounds for realistic quantum tokens (games S2 and D1).

S2 -- Kent, Lowndes, Pitalua-Garcia, Rarity, npj Quantum Inf. 8, 28 (2022), schemes QT1/QT2:
      Lemma 2 (Eqs. 2-3) robustness, Lemma 3 (Eqs. 4-5) correctness, Lemma 4 (Eq. 6) privacy,
      Theorem 1 (Eqs. 7-10) unforgeability, Theorem 2 (Eq. 11) 2^M presentation points;
      lambda and O(theta) from Table 5 items 2-3.
D1 -- Schiansky et al., Nat. Commun. 14, 3849 (2023), Supplementary Note 3:
      Eq. (18) secure region (fitted), Eqs. (19)-(20) honest abort, Eqs. (22)-(23) dishonest success.

Every formula is transcribed verbatim (see proofs/notes/P-S2.md, P-D1.md for anchors). Parameter
tuples outside a theorem's stated domain return a value-less, out-of-domain ``BoundResult``; nothing
is extrapolated. All arithmetic is in natural-log space (values like e^-1052 are representable).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from typing import Any

from qmint.core.contracts import (
    BoundRequest,
    BoundResult,
    EvidenceKind,
    GameId,
    SecurityAxis,
)
from qmint.proofs import assumption_check as ac
from qmint.proofs.registry import Registry, default_registry
from qmint.proofs.results import bounded, unsupported

LN10 = math.log(10.0)
SQRT2 = math.sqrt(2.0)


def _lse(a: float, b: float) -> float:
    """ln(e^a + e^b) without overflow/underflow."""
    hi, lo = max(a, b), min(a, b)
    return hi + math.log1p(math.exp(lo - hi))


# --------------------------------------------------------------------------- #
# Kent et al. 2022 (S2)
# --------------------------------------------------------------------------- #


def kent_overlap(theta: float) -> float:
    """Table 5 item 2: O(theta) = (cos theta + sin theta)/sqrt 2."""
    return (math.cos(theta) + math.sin(theta)) / SQRT2


def kent_lambda(theta: float, beta_pb: float) -> float:
    """Table 5 item 3: lambda = (1/2)(1 - sqrt(1 - [1 - O(theta)^2](1 - 4 beta_PB^2)))."""
    o = kent_overlap(theta)
    return 0.5 * (1.0 - math.sqrt(1.0 - (1.0 - o * o) * (1.0 - 4.0 * beta_pb * beta_pb)))


def kent_h(beta_ps: float, beta_pb: float, theta: float) -> float:
    """Eq. (9): h = 2 beta_PS sqrt(1/2 + 2 beta_PB^2 + (1/2 - 2 beta_PB^2) sin 2 theta)."""
    b2 = beta_pb * beta_pb
    return 2.0 * beta_ps * math.sqrt(0.5 + 2.0 * b2 + (0.5 - 2.0 * b2) * math.sin(2.0 * theta))


def kent_delta(gamma_det: float, gamma_err: float, nu_unf: float) -> float:
    """Eq. (9): delta = gamma_det gamma_err / (gamma_det - nu_unf)."""
    return gamma_det * gamma_err / (gamma_det - nu_unf)


def kent_f(gamma_err: float, beta_ps: float, beta_pb: float, theta: float, nu_unf: float, gamma_det: float) -> float:
    """Eq. (8)."""
    lam = kent_lambda(theta, beta_pb)
    d = kent_delta(gamma_det, gamma_err, nu_unf)
    g = gamma_det - nu_unf
    return g * (lam / 2.0 * (1.0 - d / lam) ** 2 - math.log(1.0 + 2.0 * beta_ps)) - (1.0 - g) * math.log(
        1.0 + kent_h(beta_ps, beta_pb, theta)
    )


def kent_rob_domain(p: Mapping[str, float]) -> list[str]:
    """Lemma 2, Eq. (2): 0 < gamma_det < P_det."""
    return [] if 0 < p["gamma_det"] < p["P_det"] else ["Eq.(2): need 0 < gamma_det < P_det"]


def kent_ln_rob(p: Mapping[str, float]) -> float:
    """Lemma 2, Eq. (3)."""
    return -(p["P_det"] * p["N"] / 2.0) * (1.0 - p["gamma_det"] / p["P_det"]) ** 2


def kent_cor_domain(p: Mapping[str, float]) -> list[str]:
    """Lemma 3, Eq. (4)."""
    bad = []
    if not (0 < p["gamma_err"] / 2.0 < p["E"] < p["gamma_err"]):
        bad.append("Eq.(4): need 0 < gamma_err/2 < E < gamma_err")
    if not (0 < p["nu_cor"] < p["P_det"] * (1.0 - 2.0 * p["beta_PB"]) / 2.0):
        bad.append("Eq.(4): need 0 < nu_cor < P_det(1-2 beta_PB)/2")
    if not (0 < p["beta_PB"] < 0.5):
        bad.append("Table 2 step 1: need 0 < beta_PB < 1/2")
    return bad


def kent_ln_cor(p: Mapping[str, float]) -> float:
    """Lemma 3, Eq. (5) (two exponential terms, log-sum-exp)."""
    a = p["P_det"] * (1.0 - 2.0 * p["beta_PB"])
    t1 = -(a * p["N"] / 4.0) * (1.0 - 2.0 * p["nu_cor"] / a) ** 2
    t2 = -(p["E"] * p["nu_cor"] * p["N"] / 3.0) * (p["gamma_err"] / p["E"] - 1.0) ** 2
    return _lse(t1, t2)


def kent_unf_domain(p: Mapping[str, float]) -> list[str]:
    """Theorem 1, Eq. (7), plus f > 0 and the Table 5/Table 2 parameter ranges."""
    bad = []
    th, bpb, bps = p["theta"], p["beta_PB"], p["beta_PS"]
    if not (0 < th < math.pi / 4):
        bad.append("Table 5 item 2: need 0 < theta < pi/4")
    if not (0 < bpb < 0.5) or not (0 < bps < 0.5):
        bad.append("Table 2 step 1: need 0 < beta_PB, beta_PS < 1/2")
    if not (0 < p["gamma_det"] < 1) or not (0 < p["gamma_err"] < 1):
        bad.append("need gamma_det, gamma_err in (0,1)")
    if bad:
        return bad
    lam = kent_lambda(th, bpb)
    ge, gd, nu, pn = p["gamma_err"], p["gamma_det"], p["nu_unf"], p["P_noqub"]
    if not (0 < ge < lam):
        bad.append(f"Eq.(7): need 0 < gamma_err < lambda = {lam:.6g}")
        return bad
    if not (0 < pn < nu < min(2.0 * pn, gd * (1.0 - ge / lam))):
        bad.append("Eq.(7): need 0 < P_noqub < nu_unf < min{2 P_noqub, gamma_det(1 - gamma_err/lambda)}")
        return bad
    d = kent_delta(gd, ge, nu)
    if not (0 < bps < 0.5 * (math.exp(lam / 2.0 * (1.0 - d / lam) ** 2) - 1.0)):
        bad.append("Eq.(7): need beta_PS < (1/2)[exp((lambda/2)(1-delta/lambda)^2) - 1]")
    if kent_f(ge, bps, bpb, th, nu, gd) <= 0:
        bad.append("Theorem 1: need f(gamma_err, beta_PS, beta_PB, theta, nu_unf, gamma_det) > 0")
    return bad


def kent_ln_unf(p: Mapping[str, float]) -> float:
    """Theorem 1, Eq. (10)."""
    pn = p["P_noqub"]
    t1 = -(pn * p["N"] / 3.0) * (p["nu_unf"] / pn - 1.0) ** 2
    t2 = -p["N"] * kent_f(p["gamma_err"], p["beta_PS"], p["beta_PB"], p["theta"], p["nu_unf"], p["gamma_det"])
    return _lse(t1, t2)


def kent_priv_domain(p: Mapping[str, float]) -> list[str]:
    return [] if 0 < p["beta_E"] < 0.5 else ["Table 3 step 2 / Table 5 item 7: need 0 < beta_E < 1/2"]


def kent_ln_priv(p: Mapping[str, float]) -> float:
    """Lemma 4 Eq. (6) (M = 1) and Theorem 2 Eq. (11): 2^-M[(1+2 beta_E)^M - 1]."""
    m = int(p.get("M", 1))
    return math.log(math.expm1(m * math.log1p(2.0 * p["beta_E"]))) - m * math.log(2.0)


# --------------------------------------------------------------------------- #
# Schiansky et al. 2023 (D1)
# --------------------------------------------------------------------------- #

MISHAP_ERROR_WEIGHT = 4.0 + 2.0 * SQRT2  # SI Eq. (18)


def schiansky_mishaps(e: float, l: float) -> float:  # noqa: E741  (paper's symbol)
    """SI Eq. (18): M(e, l) = (4 + 2 sqrt 2) e + l."""
    return MISHAP_ERROR_WEIGHT * e + l


def schiansky_secure_error(l: float, p_m: float) -> float:  # noqa: E741
    """SI Eq. (16) (fitted SDP boundary): e = -l/(4+2 sqrt 2) + (1 - p_m/2)/(8+4 sqrt 2)."""
    return -l / MISHAP_ERROR_WEIGHT + (1.0 - p_m / 2.0) / (2.0 * MISHAP_ERROR_WEIGHT)


def schiansky_domain(p: Mapping[str, float]) -> list[str]:
    bad = []
    if not (0 < p["delta_d"] <= 1) or not (0 < p["delta_h"] <= 1):
        bad.append("SI Eqs.(7)-(8): Chernoff tolerances delta_d, delta_h must lie in (0,1]")
    if not (0 <= p["p_m"] < 1) or not (0 <= p["e_h"] <= 1) or not (0 <= p["l_h"] <= 1):
        bad.append("p_m in [0,1), e_h and l_h in [0,1]")
    if bad:
        return bad
    m_h = schiansky_mishaps(p["e_h"], p["l_h"])
    if m_h <= 0:
        bad.append("SI Eq.(19): need M(e_h, l_h) > 0")
    if not (0.5 * (1.0 - p["p_m"] / 2.0) * (1.0 - p["delta_d"]) >= m_h * (1.0 + p["delta_h"])):
        bad.append("SI Eq.(23): need (1/2)(1-p_m/2)(1-delta_d) >= M(e_h,l_h)(1+delta_h)")
    if p.get("merchants", 2) != 2:
        bad.append("SI Note 3A: analysis is for two merchants (one committed bit per sub-token)")
    return bad


def schiansky_ln_pd(p: Mapping[str, float]) -> float:
    """SI Eq. (22): p_d <= exp(-(delta_d^2/2) (1/2)(1 - p_m/2) N)."""
    return -(p["delta_d"] ** 2 / 2.0) * 0.5 * (1.0 - p["p_m"] / 2.0) * p["N"]


def schiansky_ln_fail_honest(p: Mapping[str, float]) -> float:
    """SI Eqs. (19)-(20): 1 - p_h <= exp(-(delta_h^2/3) M(e_h,l_h) N)."""
    return -(p["delta_h"] ** 2 / 3.0) * schiansky_mishaps(p["e_h"], p["l_h"]) * p["N"]


# --------------------------------------------------------------------------- #
# Dispatch table: bound_id -> (required parameters, domain, ln-bound)
# --------------------------------------------------------------------------- #

_S2_UNF_KEYS = ("N", "P_noqub", "nu_unf", "gamma_err", "beta_PS", "beta_PB", "theta", "gamma_det")
_D1_KEYS = ("N", "p_m", "delta_d", "delta_h", "e_h", "l_h")

FORMULAS: dict[str, tuple[tuple[str, ...], Callable[[Mapping[str, float]], list[str]], Callable[[Mapping[str, float]], float]]] = {
    "P-S2/rob": (("N", "P_det", "gamma_det"), kent_rob_domain, kent_ln_rob),
    "P-S2/cor": (("N", "P_det", "beta_PB", "E", "gamma_err", "nu_cor"), kent_cor_domain, kent_ln_cor),
    "P-S2/unf": (_S2_UNF_KEYS, kent_unf_domain, kent_ln_unf),
    "P-S2/priv": (("beta_E",), kent_priv_domain, kent_ln_priv),
    "P-D1/unf": (_D1_KEYS, schiansky_domain, schiansky_ln_pd),
    "P-D1/cor": (_D1_KEYS, schiansky_domain, schiansky_ln_fail_honest),
}

_EVIDENCE = {GameId.S2: EvidenceKind.PUBLISHED_THEOREM, GameId.D1: EvidenceKind.PUBLISHED_AGGREGATE}


def _site_factor(bound_id: str, params: Mapping[str, Any]) -> tuple[float, list[str]]:
    """Theorem 2 / Eq. (11) multiplier for 2^M presentation points (priv handled in its formula)."""
    if not bound_id.startswith("P-S2/"):
        return 1.0, []
    m = params.get("M", 1)
    if isinstance(m, bool) or not isinstance(m, int) or m < 1:
        return 1.0, ["Theorem 2: M must be an integer >= 1"]
    if bound_id in ("P-S2/rob", "P-S2/cor"):
        return float(m), []
    if bound_id == "P-S2/unf":
        if m == 1:
            return 1.0, []
        c = params.get("C")
        max_pairs = 2**m * (2**m - 1) // 2
        if isinstance(c, bool) or not isinstance(c, int) or not (0 <= c <= max_pairs):
            return 1.0, [f"Theorem 2: M > 1 requires integer C (spacelike pairs) in [0, {max_pairs}]"]
        return float(c), []
    return 1.0, []


class FiniteSizeBoundEvaluator:
    """``ProofEvaluator`` for games S2 (Kent 2022) and D1 (Schiansky 2023)."""

    evaluator_id = "qmint.proofs.finite_size/v1"

    def __init__(self, registry: Registry | None = None) -> None:
        self._registry = registry or default_registry()

    def evaluate(self, request: BoundRequest) -> BoundResult:
        game = request.game_id
        if game not in _EVIDENCE:
            return unsupported(request, f"no finite-size theorem registered for game {game.value}", out_of_domain=True)
        hit = self._registry.bound_for(game, request.axis)
        if hit is None:
            extra = " (privacy is never reported as 0)" if request.axis == SecurityAxis.PRIVACY else ""
            return unsupported(request, f"no published theorem for {game.value}/{request.axis.value}{extra}")
        claim, spec = hit
        keys, domain, ln_bound = FORMULAS[spec.bound_id]

        params = ac.merge_calibration(game.value, request.parameters, request.calibration)
        report = ac.check_declarations(claim, params).merged(
            ac.check_calibration(claim, request.calibration, params)
        )
        report = report.merged(ac.check_required_params(params, keys))
        factor, site_bad = _site_factor(spec.bound_id, params)
        if site_bad:
            report = report.merged(ac.AssumptionReport(failed=tuple(f"OUT_OF_DOMAIN:{b}" for b in site_bad)))
        if not report.ok:
            return unsupported(request, f"{spec.bound_id} preconditions not met", report=report)

        violations: set[str] = set()
        extra_keys = tuple(k for k in ("merchants",) if k in params)
        for corner in ac.corners(params, keys + extra_keys):
            corner.setdefault("M", params.get("M", 1))
            violations.update(domain(corner))
        if violations:
            return unsupported(
                request,
                f"{spec.bound_id} ({spec.anchor}) not applicable: " + "; ".join(sorted(violations)),
                out_of_domain=True,
                report=ac.AssumptionReport(report.checked),
            )
        try:
            point = ac.worst_case({k: params[k] for k in keys}, spec.monotonicity, spec.domain_only)
        except ValueError as e:
            return unsupported(request, str(e), out_of_domain=True, report=ac.AssumptionReport(report.checked))
        if factor == 0:  # C = 0: Theorem 2 gives unf^M = 0; QMint never reports a zero bound
            return unsupported(request, "Theorem 2 with C = 0 (no spacelike-separated pair): not reported as 0")
        point["M"] = params.get("M", 1)
        ln_val = ln_bound(point) + math.log(factor)
        used_interval = any(ac.is_interval(params[k]) for k in keys)
        notes = f"{spec.anchor}: {spec.formula}"
        if used_interval:
            notes += f" | evaluated at worst-case interval endpoints {point}"
        if game == GameId.D1:
            notes += " | D1: fitted SDP boundary + informal de Finetti reduction; excludes MAC forgery p_t"
        return bounded(
            request,
            spec.bound_id,
            ln_val / LN10,
            status=claim.status,
            evidence_kind=_EVIDENCE[game],
            report=report,
            notes=notes,
        )
