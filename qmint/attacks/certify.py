"""Rigorous (exact rational) certification of SDP dual bounds.

Derivation: audits/SDP_DERIVATION.md, Sec. "Certified dual bound".

Weak duality is an exact theorem: if Y is Hermitian and Y (x) I - G >= 0 then
Tr(Y) >= <G, J> for every primal-feasible J. Hence ANY exactly-verified dual-feasible Y
gives a rigorous upper bound on the optimal 1->2 counterfeiting probability of the
specific finite-dimensional game encoded by G. Procedure:

1. Take the solver's Y, keep its real-symmetric part (G is real symmetric for BB84, so if
   Y is feasible then conj(Y) is, and by convexity so is Re Y = (Y + conj Y)/2, with the
   same trace), and round entries to dyadic rationals with denominator 2^bits.
2. Estimate lambda_min(Y_r (x) I - G) in floating point and choose a rational shift
   delta >= max(0, -lambda_min) + pad. The float estimate is only a guess.
3. VERIFY EXACTLY that M = (Y_r + delta I) (x) I - G is positive definite: symmetric
   Gaussian elimination (LDL^T without pivoting) in ``fractions.Fraction`` arithmetic;
   M > 0 iff every pivot is > 0 (Sylvester / LDL^T inertia). If verification fails,
   increase pad x10 and retry.
4. The certified bound is Tr(Y_r + delta I), an exact rational, reported rounded UP to
   the next float.

G itself is rebuilt in exact rational arithmetic from the BB84 states (entries in
{0, +-1/2, 1} per factor), independently of the floating-point construction.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from fractions import Fraction

import numpy as np

Mat = list[list[Fraction]]

_H = Fraction(1, 2)
_EXACT_RHO = {
    "0": [[Fraction(1), Fraction(0)], [Fraction(0), Fraction(0)]],
    "1": [[Fraction(0), Fraction(0)], [Fraction(0), Fraction(1)]],
    "+": [[_H, _H], [_H, _H]],
    "-": [[_H, -_H], [-_H, _H]],
}


def fkron(a: Mat, b: Mat) -> Mat:
    ra, ca, rb, cb = len(a), len(a[0]), len(b), len(b[0])
    return [[a[i // rb][j // cb] * b[i % rb][j % cb] for j in range(ca * cb)] for i in range(ra * rb)]


def fidentity(d: int) -> Mat:
    return [[Fraction(int(i == j)) for j in range(d)] for i in range(d)]


def fadd(a: Mat, b: Mat, sb: Fraction = Fraction(1)) -> Mat:
    return [[x + sb * y for x, y in zip(ra, rb, strict=True)] for ra, rb in zip(a, b, strict=True)]


def ftranspose(a: Mat) -> Mat:
    return [list(r) for r in zip(*a, strict=True)]


def ftrace(a: Mat) -> Fraction:
    return sum((a[i][i] for i in range(len(a))), Fraction(0))


def exact_rho(labels: Sequence[str]) -> Mat:
    out: Mat = [[Fraction(1)]]
    for s in labels:
        out = fkron(out, _EXACT_RHO[s])
    return out


def exact_w1_objective(n: int) -> Mat:
    """G_n in exact rationals (ordering (input, out1, out2), as in coherent_sdp)."""
    d = 2**n
    g = [[Fraction(0)] * d**3 for _ in range(d**3)]
    w = Fraction(1, 4**n)
    for labels in itertools.product("01+-", repeat=n):
        r = exact_rho(labels)
        g = fadd(g, fkron(fkron(ftranspose(r), r), r), w)
    return g


def is_positive_definite_exact(m: Mat) -> tuple[bool, Fraction | None]:
    """Exact LDL^T test. Returns (is_PD, smallest pivot or the first non-positive pivot)."""
    n = len(m)
    a = [list(r) for r in m]
    for i in range(n):
        for j in range(i):
            if a[i][j] != a[j][i]:
                raise ValueError("matrix is not exactly symmetric")
    min_piv: Fraction | None = None
    for k in range(n):
        p = a[k][k]
        if p <= 0:
            return False, p
        min_piv = p if min_piv is None or p < min_piv else min_piv
        for i in range(k + 1, n):
            if a[i][k] == 0:
                continue
            f = a[i][k] / p
            row_k = a[k]
            row_i = a[i]
            for j in range(k + 1, n):
                if row_k[j] != 0:
                    row_i[j] -= f * row_k[j]
            row_i[k] = Fraction(0)
    return True, min_piv


def to_dyadic(a: np.ndarray, bits: int) -> tuple[Mat, float]:
    """Real-symmetric part of ``a`` rounded to multiples of 2^-bits. Returns (matrix, dropped imag norm)."""
    a = np.asarray(a)
    herm = (a + a.conj().T) / 2
    imag_norm = float(np.linalg.norm(herm.imag))
    re = herm.real
    scale = 2**bits
    n = re.shape[0]
    out = [[Fraction(round(float(re[i, j]) * scale), scale) for j in range(n)] for i in range(n)]
    for i in range(n):
        for j in range(i):
            out[i][j] = out[j][i]
    return out, imag_norm


def _ceil_dyadic(x: float, bits: int) -> Fraction:
    return Fraction(math.ceil(x * 2**bits), 2**bits)


def _float_up(q: Fraction) -> float:
    f = float(q)
    return f if Fraction(f) >= q else math.nextafter(f, math.inf)


@dataclass(frozen=True)
class CertifiedBound:
    """Rigorous upper bound from an exactly verified dual-feasible point."""

    bound: Fraction  # exact
    bound_float_up: float  # next float >= bound
    numerical_dual_value: float
    delta: Fraction
    min_pivot: Fraction
    attempts: int
    imag_part_dropped_norm: float
    evidence_kind: str = "CERTIFIED_NUMERIC"


def certify_dual(
    ys: Sequence[np.ndarray],
    constraints: Callable[[list[Mat]], list[Mat]],
    numerical_value: float,
    bits: int = 40,
    pad: float = 1e-12,
    max_attempts: int = 8,
) -> CertifiedBound:
    """Generic certifier for duals min sum_c Tr(Y_c) s.t. constraints(Y) all PD.

    ``constraints`` must build, in EXACT arithmetic, the matrices that must be positive
    semidefinite; each must be monotone in a shift Y_c -> Y_c + delta I (true for all
    constraints here: Y (x) I - G and Y_c - B).
    """
    rounded = [to_dyadic(y, bits) for y in ys]
    yr = [r[0] for r in rounded]
    imag = max(r[1] for r in rounded)
    # float guess of the violation
    viol = 0.0
    for m in constraints(yr):
        viol = max(viol, -float(np.linalg.eigvalsh(np.array(m, dtype=float)).min()))
    for attempt in range(1, max_attempts + 1):
        delta = _ceil_dyadic(viol + pad, bits) if viol + pad > 0 else Fraction(0)
        yd = [fadd(y, fidentity(len(y)), delta) for y in yr]
        ok, piv = True, None
        for m in constraints(yd):
            okm, pm = is_positive_definite_exact(m)
            if not okm:
                ok = False
                break
            piv = pm if piv is None or (pm is not None and pm < piv) else piv
        if ok:
            bound = sum((ftrace(y) for y in yd), Fraction(0))
            assert piv is not None
            return CertifiedBound(
                bound=bound,
                bound_float_up=_float_up(bound),
                numerical_dual_value=numerical_value,
                delta=delta,
                min_pivot=piv,
                attempts=attempt,
                imag_part_dropped_norm=imag,
            )
        pad *= 10
    raise RuntimeError("could not certify dual feasibility; bound remains UNCERTIFIED")


def certify_w1_dual(y: np.ndarray, n: int, numerical_value: float, **kw: float) -> CertifiedBound:
    """Certify Tr(Y') >= optimum of W1 n-qubit SDP, via exact check of Y' (x) I - G_n > 0."""
    g = exact_w1_objective(n)
    dout = 4**n
    eye = fidentity(dout)

    def cons(ys: list[Mat]) -> list[Mat]:
        return [fadd(fkron(ys[0], eye), g, Fraction(-1))]

    return certify_dual([y], cons, numerical_value, **kw)  # type: ignore[arg-type]


def certify_w1cv_dual(ydict: dict[tuple[int, int], np.ndarray], numerical_value: float) -> CertifiedBound:
    """Certify the W1_CV n=1 dual: Y_c - B^c_a / 4 > 0 for all challenge pairs c, answers a."""
    labels = {(0, 0): "0", (0, 1): "1", (1, 0): "+", (1, 1): "-"}
    keys = sorted(ydict)
    blocks: dict[tuple[int, int], list[Mat]] = {}
    for c1, c2 in keys:
        blocks[(c1, c2)] = []
        for a1, a2 in itertools.product((0, 1), repeat=2):
            b = [[Fraction(0)] * 2 for _ in range(2)]
            for (bb, t), lab in labels.items():
                if (bb != c1 or a1 == t) and (bb != c2 or a2 == t):
                    b = fadd(b, _EXACT_RHO[lab], Fraction(1, 16))  # p_k * 1/|C|^2 = 1/4 * 1/4
            blocks[(c1, c2)].append(b)

    def cons(ys: list[Mat]) -> list[Mat]:
        return [fadd(y, b, Fraction(-1)) for y, c in zip(ys, keys, strict=True) for b in blocks[c]]

    return certify_dual([ydict[c] for c in keys], cons, numerical_value)


def exact_choi_value_of_mvw_channel(n: int = 1) -> Fraction:
    """<G_n, J> for the n-fold product of MVW's Sec. 3.2 channel, in exact rationals.

    Kraus ops are B_k / sqrt(12) with integer B_k, so J = (1/12) sum_k choi(B_k) is rational.
    Returns exactly (3/4)^n: a rigorous LOWER bound (an explicit achieving attack).
    """
    b0 = [[3, 0], [0, 1], [0, 1], [1, 0]]
    b1 = [[0, 1], [1, 0], [1, 0], [0, 3]]

    def choi(bs: list[list[list[int]]]) -> Mat:
        j = [[Fraction(0)] * 8 for _ in range(8)]
        for b in bs:
            for i1, j1 in itertools.product(range(2), repeat=2):
                # |i1><j1| (x) B|i1><j1|B^T  (real Kraus)
                for r in range(4):
                    for c in range(4):
                        j[i1 * 4 + r][j1 * 4 + c] += Fraction(b[r][i1] * b[c][j1], 12)
        return j

    j1 = choi([b0, b1])
    # single-qubit value; product channel on product objective gives the n-th power exactly
    g1 = exact_w1_objective(1)
    v1 = sum((g1[i][k] * j1[k][i] for i in range(8) for k in range(8)), Fraction(0))
    return v1**n
