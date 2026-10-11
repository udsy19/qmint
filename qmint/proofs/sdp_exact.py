"""Exact-arithmetic re-verification of SDP dual certificates (checker side only).

Used by ``qmint.proofs.checker`` to re-verify CERTIFIED_NUMERIC SDP upper bounds through a code
path that shares nothing with lane C (``qmint.attacks``) or the lane-D evaluators:

* own exact construction of the objective operators from rational BB84 projectors
  (entries in {0, +-1/2, 1});
* own exact positive-SEMIdefinite test (symmetric Gaussian elimination with zero-pivot handling,
  valid for singular matrices), unlike lane C's positive-definite LDL^T without pivoting;
* own dual candidates: the analytic MVW dual Y = (3/8)^n 1 for W1, and, for W1_CV, a dual found by
  an independent small CVXPY problem, rounded to dyadic rationals and shifted until the exact test
  passes (the floating-point solve only proposes; acceptance is exact).

Weak duality (exact): if Y (x) 1 - G >= 0 then every CPTP attack has success <= Tr Y.
Ordering convention (same as audits/SDP_DERIVATION.md): registers (input, out1, out2), each
big-endian over its qubits; G_n = 4^-n sum_s rho_s^T (x) rho_s (x) rho_s.
"""

from __future__ import annotations

import itertools
from fractions import Fraction

Mat = list[list[Fraction]]
F0, F1, HALF = Fraction(0), Fraction(1), Fraction(1, 2)

# rational BB84 projectors, C7 labels: (Z,0)=|0>, (Z,1)=|1>, (X,0)=|+>, (X,1)=|->
_BB84: dict[tuple[int, int], Mat] = {
    (0, 0): [[F1, F0], [F0, F0]],
    (0, 1): [[F0, F0], [F0, F1]],
    (1, 0): [[HALF, HALF], [HALF, HALF]],
    (1, 1): [[HALF, -HALF], [-HALF, HALF]],
}
MAX_EXACT_DIM = 64


def _kron(a: Mat, b: Mat) -> Mat:
    return [[x * y for x in ra for y in rb] for ra in a for rb in b]


def _kron_all(ms: list[Mat]) -> Mat:
    out: Mat = [[F1]]
    for m in ms:
        out = _kron(out, m)
    return out


def _eye(d: int) -> Mat:
    return [[F1 if i == j else F0 for j in range(d)] for i in range(d)]


def _transpose(a: Mat) -> Mat:
    return [list(r) for r in zip(*a, strict=True)]


def is_psd_exact(m: Mat) -> bool:
    """Exact PSD test for a rational symmetric matrix (handles singular matrices).

    Recursion: pick the first diagonal entry; if negative -> not PSD; if zero, its whole row must be
    zero (else a 2x2 principal minor is negative) and it is dropped; if positive, take the Schur
    complement, which is PSD iff the matrix is (given the positive pivot).
    """
    a = [list(r) for r in m]
    n = len(a)
    if any(len(r) != n for r in a) or any(a[i][j] != a[j][i] for i in range(n) for j in range(i)):
        return False
    while a:
        p = a[0][0]
        if p < 0:
            return False
        if p == 0:
            if any(x != 0 for x in a[0]):
                return False
            a = [r[1:] for r in a[1:]]
            continue
        col = [r[0] for r in a[1:]]
        a = [[a[i + 1][j + 1] - col[i] * col[j] / p for j in range(len(col))] for i in range(len(col))]
    return True


def w1_objective(n: int) -> Mat:
    if 8**n > MAX_EXACT_DIM:
        raise ValueError(f"W1 n={n}: dimension {8**n} exceeds exact-verification limit {MAX_EXACT_DIM}")
    d = 2**n
    g = [[F0] * (d**3) for _ in range(d**3)]
    for s in itertools.product(_BB84, repeat=n):
        rho = _kron_all([_BB84[k] for k in s])
        t = _kron(_kron(_transpose(rho), rho), rho)
        for i in range(d**3):
            gi, ti = g[i], t[i]
            for j in range(d**3):
                if ti[j]:
                    gi[j] += ti[j]
    w = Fraction(1, 4**n)
    return [[x * w for x in r] for r in g]


def verify_w1_dual(y: Mat, n: int) -> Fraction | None:
    """Return Tr(Y) if Y (x) 1_{out} - G_n >= 0 exactly, else None."""
    g = w1_objective(n)
    d = 2**n
    if len(y) != d:
        return None
    m = _kron(y, _eye(d * d))
    m = [[m[i][j] - g[i][j] for j in range(len(g))] for i in range(len(g))]
    return sum((y[i][i] for i in range(d)), F0) if is_psd_exact(m) else None


def w1_independent_upper_bound(n: int) -> Fraction:
    """Exactly verified W1 upper bound from the analytic dual Y = (3/8)^n 1 (MVW Sec. 3.2/3.4)."""
    y = [[Fraction(3, 8) ** n * e for e in row] for row in _eye(2**n)]
    tr = verify_w1_dual(y, n)
    if tr is None:
        raise AssertionError("analytic MVW dual failed exact verification")
    return tr


def w1cv_blocks() -> dict[tuple[int, int], list[Mat]]:
    """MVW Sec. 4.1-4.2, n = 1: per challenge pair c, operators B^c_a / 4 (uniform c) for a in {0,1}^2,
    B^c_a = sum_k (1/4)[a1 valid for (c1,k)][a2 valid for (c2,k)] rho_k; an answer a to challenge
    basis c on state k=(basis,bit) is valid iff basis != c or a == bit."""

    def valid(a: int, c: int, k: tuple[int, int]) -> bool:
        return k[0] != c or a == k[1]

    out: dict[tuple[int, int], list[Mat]] = {}
    for c in itertools.product((0, 1), repeat=2):
        blocks = []
        for a in itertools.product((0, 1), repeat=2):
            b = [[F0, F0], [F0, F0]]
            for k, rho in _BB84.items():
                if valid(a[0], c[0], k) and valid(a[1], c[1], k):
                    b = [[b[i][j] + Fraction(1, 16) * rho[i][j] for j in range(2)] for i in range(2)]
            blocks.append(b)
        out[c] = blocks
    return out


def verify_w1cv_dual(ys: dict[tuple[int, int], Mat]) -> Fraction | None:
    """Return sum_c Tr(Y_c) if Y_c - B^c_a/4 >= 0 exactly for all c, a; else None."""
    for c, blocks in w1cv_blocks().items():
        for b in blocks:
            if not is_psd_exact([[ys[c][i][j] - b[i][j] for j in range(2)] for i in range(2)]):
                return None
    return sum((y[0][0] + y[1][1] for y in ys.values()), F0)


def w1cv_independent_upper_bound(bits: int = 40) -> Fraction:
    """Own numerical dual (CVXPY) -> dyadic rounding -> shift until exactly feasible."""
    import cvxpy as cp
    import numpy as np

    blocks = {c: [np.array(b, dtype=float) for b in bl] for c, bl in w1cv_blocks().items()}
    yv = {c: cp.Variable((2, 2), symmetric=True) for c in blocks}
    cons = [yv[c] - b >> 0 for c in blocks for b in blocks[c]]
    cp.Problem(cp.Minimize(sum(cp.trace(y) for y in yv.values())), cons).solve(solver="SCS", eps=1e-10)
    scale = 2**bits
    base = {
        c: [[Fraction(round(float(v) * scale), scale) for v in row] for row in np.asarray(y.value)]
        for c, y in yv.items()
    }
    base = {c: [[y[0][0], y[0][1]], [y[0][1], y[1][1]]] for c, y in base.items()}  # exact symmetry
    shift = Fraction(1, scale)
    for _ in range(40):
        ys = {c: [[y[i][j] + (shift if i == j else 0) for j in range(2)] for i in range(2)] for c, y in base.items()}
        tr = verify_w1cv_dual(ys)
        if tr is not None:
            return tr
        shift *= 2
    raise AssertionError("could not produce an exactly feasible W1_CV dual")


def parse_rational_matrix(rows: object) -> Mat:
    """Rows of strings like '3/8' (or ints) -> exact matrix; raises ValueError on anything else."""
    if not isinstance(rows, list) or not all(isinstance(r, list) for r in rows):
        raise ValueError("dual matrix must be a list of rows")
    return [[Fraction(str(x)) for x in r] for r in rows]
