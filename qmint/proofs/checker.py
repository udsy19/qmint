"""Independent certificate checker (``qmint.core.interfaces.IndependentChecker``).

This is a deliberately SEPARATE code path from ``ideal_bounds`` / ``finite_size`` /
``assumption_check``: it imports none of them. Every formula is re-derived here from the
source equations in 60-digit ``decimal`` arithmetic with its own series for sin/cos, its own
domain predicates, and brute-force maximisation over all corners of any parameter interval
(the evaluator instead picks endpoints from documented monotonicity directions). The only
shared input is the YAML registry *data* (claim ids and required declarations).

A certificate is returned ``CERTIFIED`` only if
  * its game has a certifiable published theorem (W1, W1_CV, S1, S2) or it is a
    CERTIFIED_NUMERIC SDP certificate with complete residual accounting;
  * proof reference (exact match, never a prefix), evidence hashes, declared assumptions and
    ``assumptions_met`` are in order, and an ideal game (W1, W1_CV, S1) carries no parameter outside
    its allowlist -- on BOTH the published-theorem and the CERTIFIED_NUMERIC SDP path;
  * every reported bound re-derives within tolerance and is never smaller than the re-derived
    value (no optimistic parameters or inward rounding); reported bounds may exceed the re-derived
    value by at most ``OUTWARD_SLACK_DEX`` (conservative rounding), anything larger is a mismatch
    (e.g. a reversed epsilon such as 1 - eps);
  * every target axis has a re-derived bound <= target;
  * no bound (e.g. privacy) is reported for an axis without a theorem;
  * for CERTIFIED_NUMERIC SDP certificates (W1 n<=2, W1_CV n=1 only): the residual-accounting
    fields are consistent AND the bound is re-verified in exact rational arithmetic by
    ``qmint.proofs.sdp_exact`` (own G construction, own PSD test; either the supplied rational dual
    matrix is checked, or the claimed bound must be >= an independently verified exact dual bound).
    SDP certificates for any other game (e.g. W2) are refused: no independent re-verification exists.
Otherwise it returns ``UNCERTIFIED`` with every reason listed. D1 (Schiansky 2023) is never
certified: its published bound rests on a fitted SDP boundary and an informal de Finetti step.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping
from decimal import Decimal, localcontext
from fractions import Fraction
from typing import Any

from qmint.core.contracts import CertificateStatus, EvidenceKind, GameId, SecurityCertificate
from qmint.proofs import sdp_exact
from qmint.proofs.registry import Claim, Registry, default_registry

PREC = 60
ABS_TOL_DEX = Decimal("1e-9")  # allowed float noise in a reported log10 bound
OUTWARD_SLACK_DEX = Decimal("0.01")  # max conservative outward rounding accepted (~2.3 %)
AXES = ("epsilon_unf", "epsilon_cor", "epsilon_rob", "epsilon_priv")

_CLAIM_OF_GAME = {"W1": "P-W1", "W1_CV": "P-W1CV", "S1": "P-S1", "S2": "P-S2", "D1": "P-D1"}
_CERTIFIABLE = frozenset({"W1", "W1_CV", "S1", "S2"})


class _Refuse(Exception):
    """Raised inside a derivation when the theorem does not apply."""


# --------------------------------------------------------------------------- #
# Decimal elementary functions (no math module, no shared helpers)
# --------------------------------------------------------------------------- #


def _D(x: Any) -> Decimal:
    if isinstance(x, bool):
        raise _Refuse("boolean where a number was expected")
    if isinstance(x, float):
        return Decimal(repr(x))
    return Decimal(x)


def _pi() -> Decimal:
    # Machin: pi = 16 atan(1/5) - 4 atan(1/239)
    def atan_inv(k: int) -> Decimal:
        x, x2 = Decimal(1) / k, Decimal(1) / (k * k)
        total, term, n, sign = Decimal(0), x, 1, 1
        while term > Decimal(10) ** -(PREC + 5):
            total += sign * term / n
            term *= x2
            n += 2
            sign = -sign
        return total

    return 16 * atan_inv(5) - 4 * atan_inv(239)


def _sin_cos(x: Decimal) -> tuple[Decimal, Decimal]:
    s, c, term_s, term_c, k = Decimal(0), Decimal(0), x, Decimal(1), 0
    while abs(term_s) > Decimal(10) ** -(PREC + 5) or abs(term_c) > Decimal(10) ** -(PREC + 5):
        s += term_s
        c += term_c
        term_s = -term_s * x * x / ((2 * k + 2) * (2 * k + 3))
        term_c = -term_c * x * x / ((2 * k + 1) * (2 * k + 2))
        k += 1
    return s, c


def _ln_sum_exp(a: Decimal, b: Decimal) -> Decimal:
    m = max(a, b)
    return m + ((a - m).exp() + (b - m).exp()).ln()


# --------------------------------------------------------------------------- #
# Re-derivations: each returns ln(bound) as Decimal or raises _Refuse
# --------------------------------------------------------------------------- #


def _positive_int(p: Mapping[str, Any], name: str) -> int:
    v = p.get(name)
    if v is None:
        raise _Refuse(f"missing length parameter {name}")
    if isinstance(v, bool) or not isinstance(v, int) or v < 1:
        raise _Refuse(f"{name} must be a positive integer")
    return v


# Per-game ALLOWLIST of request parameters for the ideal theorems (M-D1). Kept here, independently
# of the evaluator's registry-derived list: anything else (noise, loss, thresholds, QBER, detector
# parameters under any spelling) means the request is not the ideal game and is refused.
_IDEAL_PARAMS = {"W1": frozenset({"n"}), "W1_CV": frozenset({"n"}), "S1": frozenset({"N", "M"})}
_IDEAL_CONTROL = frozenset({"declared_assumptions", "verifier", "verification_oracle_queries"})


def _ideal_gate(game: str, p: Mapping[str, Any], extra: frozenset[str] = frozenset()) -> None:
    """Raise ``_Refuse`` unless ``p`` is a pure ideal-game request (shared by both checker paths)."""
    stray = sorted(k for k in p if k not in _IDEAL_PARAMS[game] | _IDEAL_CONTROL | extra)
    if stray:
        raise _Refuse(f"ideal {game} theorem but parameters outside its allowlist: {', '.join(stray)}")
    if p.get("verifier", "exact") != "exact" or p.get("verification_oracle_queries", 0) not in (0, None):
        raise _Refuse("ideal theorem requires exact verifier and no oracle access")
    if game == "S1" and p.get("M", 1) != 1:
        raise _Refuse("S1 bound is two-site only")


def _ideal(game: str, axis: str, p: Mapping[str, Any]) -> Decimal:
    if axis != "epsilon_unf":
        raise _Refuse(f"no theorem for {game}/{axis}")
    _ideal_gate(game, p)
    root2 = Decimal(2).sqrt()
    if game == "W1":
        return _positive_int(p, "n") * (Decimal(3) / 4).ln()
    if game == "W1_CV":
        return _positive_int(p, "n") * ((6 + root2) / 8).ln()  # 3/4 + sqrt2/8
    return _positive_int(p, "N") * ((2 + root2) / 4).ln()  # 1/2 + 1/(2 sqrt2)


def _kent_point(axis: str, q: Mapping[str, Decimal], m: int, c: int | None) -> Decimal:
    """One corner of the S2 parameter box: domain check then ln bound."""
    one, two, half = Decimal(1), Decimal(2), Decimal("0.5")
    n = q.get("N", Decimal(0))
    if axis == "epsilon_rob":
        pdet, gdet = q["P_det"], q["gamma_det"]
        if not (0 < gdet < pdet):
            raise _Refuse("Lemma 2 domain 0<gamma_det<P_det violated")
        return -(pdet * n / two) * (one - gdet / pdet) ** 2 + _D(m).ln()
    if axis == "epsilon_cor":
        pdet, bpb, e, ge, nuc = q["P_det"], q["beta_PB"], q["E"], q["gamma_err"], q["nu_cor"]
        a = pdet * (one - two * bpb)
        if not (0 < bpb < half and 0 < ge / two < e < ge and 0 < nuc < a / two):
            raise _Refuse("Lemma 3 domain (Eq. 4) violated")
        t1 = -(a * n / 4) * (one - two * nuc / a) ** 2
        t2 = -(e * nuc * n / 3) * (ge / e - one) ** 2
        return _ln_sum_exp(t1, t2) + _D(m).ln()
    if axis == "epsilon_priv":
        be = q["beta_E"]
        if not (0 < be < half):
            raise _Refuse("Lemma 4 needs 0<beta_E<1/2")
        return (((one + two * be) ** m - one) / (two**m)).ln()
    # epsilon_unf: Theorem 1
    th, bpb, bps = q["theta"], q["beta_PB"], q["beta_PS"]
    ge, gd, nu, pn = q["gamma_err"], q["gamma_det"], q["nu_unf"], q["P_noqub"]
    if not (0 < th < _pi() / 4 and 0 < bpb < half and 0 < bps < half and 0 < gd < one and 0 < ge < one):
        raise _Refuse("Theorem 1 parameter ranges violated")
    s, co = _sin_cos(th)
    ov = (co + s) / two.sqrt()
    lam = half * (one - (one - (one - ov * ov) * (one - 4 * bpb * bpb)).sqrt())
    if not (0 < ge < lam):
        raise _Refuse("Eq. 7: gamma_err >= lambda")
    if not (0 < pn < nu < min(two * pn, gd * (one - ge / lam))):
        raise _Refuse("Eq. 7: nu_unf constraint violated")
    dl = gd * ge / (gd - nu)
    core = lam / two * (one - dl / lam) ** 2
    if not (0 < bps < half * (core.exp() - one)):
        raise _Refuse("Eq. 7: beta_PS constraint violated")
    s2, _ = _sin_cos(two * th)
    hh = two * bps * (half + two * bpb * bpb + (half - two * bpb * bpb) * s2).sqrt()
    g = gd - nu
    f = g * (core - (one + two * bps).ln()) - (one - g) * (one + hh).ln()
    if f <= 0:
        raise _Refuse("Theorem 1 requires f > 0")
    t1 = -(pn * n / 3) * (nu / pn - one) ** 2
    t2 = -n * f
    if m == 1:
        return _ln_sum_exp(t1, t2)
    if c is None or c < 1:
        raise _Refuse("Theorem 2: M>1 needs C >= 1 spacelike pairs")
    return _ln_sum_exp(t1, t2) + _D(c).ln()


_KENT_KEYS = {
    "epsilon_rob": ("N", "P_det", "gamma_det"),
    "epsilon_cor": ("N", "P_det", "beta_PB", "E", "gamma_err", "nu_cor"),
    "epsilon_priv": ("beta_E",),
    "epsilon_unf": ("N", "P_noqub", "nu_unf", "gamma_err", "beta_PS", "beta_PB", "theta", "gamma_det"),
}


def _kent(axis: str, p: Mapping[str, Any]) -> Decimal:
    m = p.get("M", 1)
    if isinstance(m, bool) or not isinstance(m, int) or m < 1:
        raise _Refuse("M must be a positive integer")
    c = p.get("C")
    if c is not None and (isinstance(c, bool) or not isinstance(c, int) or c > 2**m * (2**m - 1) // 2):
        raise _Refuse("C must be an integer number of point pairs")
    choices = []
    for k in _KENT_KEYS[axis]:
        v = p.get(k)
        if v is None:
            raise _Refuse(f"missing parameter {k}")
        if isinstance(v, Mapping):
            lo, hi = _D(v["lo"]), _D(v["hi"])
            if lo > hi:
                raise _Refuse(f"interval {k} has lo > hi")
            choices.append((lo, hi))
        else:
            choices.append((_D(v),))
    worst = None
    for combo in itertools.product(*choices):  # brute force: every corner must be in-domain
        val = _kent_point(axis, dict(zip(_KENT_KEYS[axis], combo, strict=True)), m, c)
        worst = val if worst is None or val > worst else worst
    assert worst is not None
    return worst


def _derive(game: str, axis: str, p: Mapping[str, Any]) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = PREC
        if game in ("W1", "W1_CV", "S1"):
            return _ideal(game, axis, p)
        if game == "S2":
            return _kent(axis, p)
        raise _Refuse(f"no certifiable theorem for game {game}")


# --------------------------------------------------------------------------- #
# Checker
# --------------------------------------------------------------------------- #

# Fields of a CERTIFIED_NUMERIC SDP certificate (names follow lane C's evidence records:
# handoffs/C-C1-evidence.json "certified" blocks). The checker never trusts them alone: the bound is
# re-verified in exact arithmetic by qmint.proofs.sdp_exact with an independently built G.
_SDP_FIELDS = ("solver", "n", "dual_objective", "delta_shift", "certified_bound")
_SDP_GAMES = {"W1": "wiesner_ideal", "W1_CV": "wiesner_ideal"}
# Registry obligation for the SDP support (P-W2, audits/SDP_DERIVATION.md); an SDP certificate must cite
# exactly this or its own game's claim (P-W1 / P-W1CV), never another game's theorem (M-D2).
_SDP_DERIVATION_REF = "P-W2/sdp"


class IndependentProofChecker:
    checker_id = "qmint.proofs.checker/decimal-v1"

    def __init__(self, registry: Registry | None = None) -> None:
        self._registry = registry or default_registry()

    # -- public API (qmint.core.interfaces.IndependentChecker) ------------------
    def check(self, certificate: SecurityCertificate) -> SecurityCertificate:
        reasons = self._common(certificate)
        if certificate.evidence_kind == EvidenceKind.CERTIFIED_NUMERIC:
            reasons += self._check_sdp(certificate)
        else:
            reasons += self._check_published(certificate)
        return self._verdict(certificate, reasons)

    # -- checks ---------------------------------------------------------------
    def _common(self, cert: SecurityCertificate) -> list[str]:
        r = []
        if cert.evidence_kind not in (EvidenceKind.PUBLISHED_THEOREM, EvidenceKind.CERTIFIED_NUMERIC):
            r.append(f"evidence_kind {cert.evidence_kind.value} cannot be certified")
        if not cert.assumptions_met or cert.failed_assumptions:
            r.append("assumptions not met: " + ", ".join(cert.failed_assumptions or ["assumptions_met=False"]))
        if not cert.evidence_hashes:
            r.append("no evidence hashes")
        if all(getattr(cert.targets, a) is None for a in AXES):
            r.append("no target to certify")
        return r

    def _check_published(self, cert: SecurityCertificate) -> list[str]:
        game = cert.game_id.value
        if game == GameId.D1.value:
            return ["D1 (Schiansky 2023) bound is NUMERICALLY_SUPPORTED only (fitted SDP boundary, informal de Finetti); never certified"]
        if game not in _CERTIFIABLE:
            return [f"no published theorem registered for game {game}"]
        claim = self._registry.claim(_CLAIM_OF_GAME[game])
        r = self._model_gates(cert, claim, {claim.claim_id, *(b.bound_id for b in claim.bounds)})
        for axis in AXES:
            r += self._check_axis(cert, game, axis)
        return r

    def _model_gates(self, cert: SecurityCertificate, claim: Claim, refs: set[str],
                     extra_params: frozenset[str] = frozenset()) -> list[str]:
        """Gates shared by the published and the SDP path (M-D2): exact proof reference (M-D3),
        the claim's required declarations, and for ideal games the parameter allowlist (M-D1)."""
        r = []
        if cert.proof_reference not in refs:
            r.append(f"proof_reference must be exactly one of {sorted(refs)}, got {cert.proof_reference!r}")
        declared = set(cert.parameters.get("declared_assumptions") or [])
        missing = [d for d in claim.required_declarations if d not in declared]
        if missing:
            r.append("undeclared theorem hypotheses: " + ", ".join(missing))
        if cert.game_id.value in _IDEAL_PARAMS:
            try:
                _ideal_gate(cert.game_id.value, cert.parameters, extra_params)
            except _Refuse as e:
                r.append(str(e))
        return r

    def _check_axis(self, cert: SecurityCertificate, game: str, axis: str) -> list[str]:
        target = getattr(cert.targets, axis)
        lin = getattr(cert.upper_bounds, axis)
        lg = cert.log10_upper_bounds.get(axis)
        if target is None and lin is None and lg is None:
            return []
        try:
            derived_ln = _derive(game, axis, cert.parameters)
        except _Refuse as e:
            if lin is not None or lg is not None:
                return [f"{axis}: bound reported but re-derivation refused ({e}); a missing theorem is never 0"]
            return [f"{axis}: target set but no applicable bound ({e})"]
        r = []
        with localcontext() as ctx:
            ctx.prec = PREC
            derived = derived_ln / Decimal(10).ln()
            reported = []
            if lg is not None:
                reported.append(("log10", _D(lg)))
            if lin is not None:
                if lin <= 0:
                    return [f"{axis}: reported bound {lin} <= 0 is never a valid upper bound"]
                reported.append(("linear", _D(lin).log10()))
            if target is not None and not reported:
                r.append(f"{axis}: target set but certificate reports no bound")
            for kind, val in reported:
                tol = ABS_TOL_DEX * max(Decimal(1), abs(derived))
                if val < derived - tol:
                    r.append(f"{axis}: reported {kind} bound 10^{val:.6f} is BELOW re-derived 10^{derived:.6f} (optimistic parameters or inward rounding)")
                elif val > derived + OUTWARD_SLACK_DEX + tol:
                    r.append(f"{axis}: reported {kind} bound 10^{val:.6f} does not match re-derived 10^{derived:.6f} (wrong formula, parameters or epsilon direction)")
            if target is not None:
                if target <= 0:
                    r.append(f"{axis}: target must be > 0")
                elif derived > _D(target).log10():
                    r.append(f"{axis}: re-derived bound 10^{derived:.6f} exceeds target {target}")
                elif any(val > _D(target).log10() for _, val in reported):
                    r.append(f"{axis}: reported bound exceeds target {target}")
        return r

    def _check_sdp(self, cert: SecurityCertificate) -> list[str]:
        game = cert.game_id.value
        if game not in _SDP_GAMES:
            return [f"CERTIFIED_NUMERIC for game {game}: no independent exact re-verification available; refused"]
        sdp = cert.parameters.get("sdp_certificate")
        if not isinstance(sdp, Mapping):
            return ["CERTIFIED_NUMERIC requires parameters.sdp_certificate"]
        missing = [k for k in _SDP_FIELDS if sdp.get(k) is None]
        if missing:
            return ["SDP certificate lacks residual-accounting fields: " + ", ".join(missing)]
        n = sdp["n"]
        if isinstance(n, bool) or not isinstance(n, int) or n < 1 or (game == "W1_CV" and n != 1):
            return [f"SDP certificate n={n!r} unsupported for exact re-verification of {game}"]
        claim = self._registry.claim(_CLAIM_OF_GAME[game])
        r = self._model_gates(cert, claim, {claim.claim_id, _SDP_DERIVATION_REF}, frozenset({"sdp_certificate"}))
        if cert.parameters.get("n") != n:
            r.append(f"parameters.n={cert.parameters.get('n')!r} must equal sdp_certificate.n={n}")
        try:
            dual, delta, cb = Fraction(str(sdp["dual_objective"])), Fraction(str(sdp["delta_shift"])), Fraction(str(sdp["certified_bound"]))
            exact = Fraction(str(sdp["certified_bound_exact"])) if sdp.get("certified_bound_exact") is not None else None
        except (ValueError, ZeroDivisionError) as e:
            return [f"SDP certificate has malformed numbers: {e}"]
        dim = 2**n if game == "W1" else 8  # trace dimension of the dual variable(s)
        # residual accounting: bound = Tr(Y_rounded) + delta * dim; dyadic rounding moves the trace by <= dim 2^-40
        if delta < 0:
            r.append("delta_shift must be >= 0")
        if cb < dual + delta * dim - dim * Fraction(1, 2**40):
            r.append(f"certified_bound {float(cb)} < dual objective + delta*dim (residual padding not accounted)")
        if exact is not None and cb < exact:
            r.append("certified_bound (float) is below its own exact rational value")
        # independent exact re-verification (separate code path, own G, own PSD test)
        try:
            if sdp.get("dual_matrix_rational") is not None:
                if game != "W1":
                    return r + ["explicit dual matrix re-verification implemented for W1 only"]
                tr = sdp_exact.verify_w1_dual(sdp_exact.parse_rational_matrix(sdp["dual_matrix_rational"]), n)
                if tr is None:
                    r.append("supplied rational dual Y fails exact check Y(x)1 - G >= 0")
                elif tr > cb:
                    r.append(f"Tr(Y) = {float(tr)} exceeds certified_bound")
            else:
                indep = sdp_exact.w1_independent_upper_bound(n) if game == "W1" else sdp_exact.w1cv_independent_upper_bound()
                if cb < indep:
                    r.append(
                        f"certified_bound {float(cb)} is below QMint's independently verified bound {float(indep)}; "
                        "claim cannot be confirmed without the rational dual matrix"
                    )
        except ValueError as e:
            return r + [f"exact re-verification refused: {e}"]
        for axis in AXES:
            target = getattr(cert.targets, axis)
            lin = getattr(cert.upper_bounds, axis)
            if target is None and lin is None:
                continue
            if axis != "epsilon_unf":
                r.append(f"{axis}: SDP certificate bounds epsilon_unf only")
                continue
            if lin is None or Fraction(str(lin)) < cb:
                r.append(f"{axis}: reported bound must be >= certified_bound {float(cb)}")
            if target is not None and cb > Fraction(str(target)):
                r.append(f"{axis}: certified_bound {float(cb)} exceeds target {target}")
        return r

    def _verdict(self, cert: SecurityCertificate, reasons: list[str]) -> SecurityCertificate:
        data = cert.model_dump(mode="python")
        if reasons:
            data.update(
                proof_check_status=CertificateStatus.UNCERTIFIED,
                checker_id=self.checker_id,
                reason="UNCERTIFIED by independent checker: " + " | ".join(reasons),
            )
        else:
            data.update(
                proof_check_status=CertificateStatus.CERTIFIED,
                checker_id=self.checker_id,
                reason=f"all bounds re-derived independently ({self.checker_id}) and every target met",
            )
        return SecurityCertificate.model_validate(data)
