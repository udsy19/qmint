"""Choi-matrix SDP for optimal 1->2 counterfeiting (game W1) and controls.

Source: Molina, Vidick, Watrous (2012), arXiv:1202.4010v1, Sec. 3.1 (p.7) primal/dual,
Sec. 3.2 (p.7-8) n=1 value 3/4 with explicit primal channel and dual Y = (3/8) I,
Sec. 3.4 (p.9-10) parallel repetition (value alpha^n; cited, not re-proved here),
Sec. 3.5 (p.10-11) threshold variant, Sec. 4 / Lemma 5 (p.13-14) classical verification.

Ordering (see ``qmint.attacks.linalg``): J acts on (input, out1, out2); for n qubits each
register is itself (qubit_1, ..., qubit_n), big-endian. Objective operator

    G_n = 4^{-n} sum_s rho_s^T (x) rho_s (x) rho_s,        rho_s = (x)_i rho_{s_i}

which equals MVW's W_pi Q^{(x)n} W_pi^* up to reordering MVW's (Y, Z, X) to (X, Y, Z).

Primal:  max <G, J>  s.t.  J >= 0,  Tr_{out1,out2} J = I_{din}
Dual:    min Tr(Y)   s.t.  Y (x) I_{dout} >= G,  Y Hermitian

Everything returned here is NUMERICAL_SDP evidence (floating-point solver output). A
rigorous upper bound requires ``qmint.attacks.certify``.
"""

from __future__ import annotations

import itertools
import resource
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass

import cvxpy as cp
import numpy as np

from qmint.attacks.linalg import BB84_LABELS, choi_tp_residual, ket, kron_all, min_eig, proj

#: Largest Choi dimension (din*dout) solved densely. n=2 -> 64; n=3 -> 512 is refused.
MAX_CHOI_DIM = 64
SOLVERS = ("SCS", "CLARABEL")
_SOLVER_OPTS = {"SCS": {"eps_abs": 1e-9, "eps_rel": 1e-9, "max_iters": 200000}, "CLARABEL": {}}


class SDPSizeUnsupported(RuntimeError):
    """The requested dense SDP exceeds MAX_CHOI_DIM; refused instead of risking OOM."""


# --------------------------------------------------------------------------- #
# Objective operators -- two independent constructions
# --------------------------------------------------------------------------- #


def _product_rho(labels: Sequence[str]) -> np.ndarray:
    return kron_all(proj(ket(s)) for s in labels)


def w1_objective_numpy(n: int) -> np.ndarray:
    """G_n by direct NumPy Kronecker products, ordering (in_1..n, out1_1..n, out2_1..n)."""
    d = 2**n
    g = np.zeros((d**3, d**3), dtype=complex)
    for labels in itertools.product(BB84_LABELS, repeat=n):
        r = _product_rho(labels)
        g += np.kron(np.kron(r.T, r), r)
    return g / 4**n


def w1_objective_qutip(n: int) -> np.ndarray:
    """G_n built independently with QuTiP: single-qubit Q via ``qutip.tensor``, then the
    n-fold tensor power permuted with ``Qobj.permute`` (MVW's W_pi, Sec. 3.4)."""
    import qutip as qt

    s = 1 / np.sqrt(2)
    kets = [qt.basis(2, 0), qt.basis(2, 1), (qt.basis(2, 0) + qt.basis(2, 1)) * s, (qt.basis(2, 0) - qt.basis(2, 1)) * s]
    q1 = sum(qt.tensor(qt.ket2dm(k).trans(), qt.ket2dm(k), qt.ket2dm(k)) for k in kets) / 4
    if n == 1:
        return np.asarray(q1.full())
    qn = qt.tensor(*([q1] * n))  # order (in_1,o1_1,o2_1, in_2,o1_2,o2_2, ...)
    order = [3 * j for j in range(n)] + [3 * j + 1 for j in range(n)] + [3 * j + 2 for j in range(n)]
    return np.asarray(qn.permute(order).full())


def ensemble_objective(
    kets: Sequence[np.ndarray],
    probs: Sequence[float],
    *,
    transpose: bool = True,
    verifier_kets: Sequence[np.ndarray] | None = None,
    side_info: Sequence[np.ndarray] | None = None,
) -> np.ndarray:
    """Generic G = sum_k p_k (rho_k (x) sigma_k)^T (x) V_k (x) V_k  (used for controls).

    ``transpose=False`` reproduces the 'transpose omitted' bug; ``verifier_kets`` lets the
    verifier test a different state than was prepared; ``side_info`` appends a classical
    register (e.g. the secret basis) to the attacker's INPUT.
    """
    g = None
    for i, (v, p) in enumerate(zip(kets, probs, strict=True)):
        r_in = proj(v)
        if side_info is not None:
            r_in = np.kron(r_in, proj(side_info[i]))
        vv = proj(verifier_kets[i]) if verifier_kets is not None else proj(v)
        term = p * np.kron(np.kron(r_in.T if transpose else r_in, vv), vv)
        g = term if g is None else g + term
    assert g is not None
    return g


# --------------------------------------------------------------------------- #
# Solvers
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SDPReport:
    """Numerical SDP result. ``evidence_kind`` is always NUMERICAL_SDP."""

    label: str
    din: int
    dout: int
    solver: str
    primal_value: float
    dual_value: float
    duality_gap: float  # dual - primal
    primal_status: str
    dual_status: str
    j_min_eig: float  # primal PSD residual (negative = violation)
    tp_residual: float  # ||Tr_out J - I||_F
    dual_slack_min_eig: float  # lambda_min(Y (x) I - G) (negative = violation)
    primal_time_s: float
    dual_time_s: float
    peak_rss_mb: float  # process max RSS after solving (platform-normalised)
    J: np.ndarray
    Y: np.ndarray
    evidence_kind: str = "NUMERICAL_SDP"


def _peak_rss_mb() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / (1024 * 1024) if sys.platform == "darwin" else r / 1024


def solve_counterfeit_sdp(g: np.ndarray, din: int, dout: int, solver: str = "SCS", label: str = "") -> SDPReport:
    """Solve primal and dual of the generic 1->2 counterfeiting SDP for objective ``g``."""
    if solver not in SOLVERS:
        raise ValueError(f"solver must be one of {SOLVERS}")
    dim = din * dout
    if dim > MAX_CHOI_DIM:
        raise SDPSizeUnsupported(
            f"Choi dimension {dim} > {MAX_CHOI_DIM}: dense complex PSD cone of size {dim} "
            f"(~{2 * dim * dim * 16 / 1e6:.1f} MB per iterate, SCS/Clarabel factorisations far larger) refused"
        )
    if g.shape != (dim, dim):
        raise ValueError("objective has wrong shape")
    opts = _SOLVER_OPTS[solver]

    j = cp.Variable((dim, dim), hermitian=True)
    primal = cp.Problem(
        cp.Maximize(cp.real(cp.trace(g @ j))),
        [j >> 0, cp.partial_trace(j, [din, dout], axis=1) == np.eye(din)],
    )
    t0 = time.perf_counter()
    primal.solve(solver=solver, **opts)
    t_primal = time.perf_counter() - t0

    y = cp.Variable((din, din), hermitian=True)
    dual = cp.Problem(cp.Minimize(cp.real(cp.trace(y))), [cp.kron(y, np.eye(dout)) - g >> 0])
    t0 = time.perf_counter()
    dual.solve(solver=solver, **opts)
    t_dual = time.perf_counter() - t0

    jv = np.asarray(j.value)
    yv = np.asarray(y.value)
    pv = float(np.real(np.trace(g @ jv)))  # recomputed, not prob.value
    dv = float(np.real(np.trace(yv)))
    return SDPReport(
        label=label,
        din=din,
        dout=dout,
        solver=solver,
        primal_value=pv,
        dual_value=dv,
        duality_gap=dv - pv,
        primal_status=str(primal.status),
        dual_status=str(dual.status),
        j_min_eig=min_eig(jv),
        tp_residual=choi_tp_residual(jv, din, dout),
        dual_slack_min_eig=min_eig(np.kron(yv, np.eye(dout)) - g),
        primal_time_s=t_primal,
        dual_time_s=t_dual,
        peak_rss_mb=_peak_rss_mb(),
        J=jv,
        Y=yv,
    )


def solve_w1(n: int, solver: str = "SCS") -> SDPReport:
    """W1 SDP for n qubits (n <= 2 densely; larger n refused with SDPSizeUnsupported)."""
    d = 2**n
    if d * d * d > MAX_CHOI_DIM:
        raise SDPSizeUnsupported(f"W1 n={n} needs Choi dim {d**3} > {MAX_CHOI_DIM}; use MVW Sec. 3.4 (cited)")
    g = w1_objective_numpy(n)
    return solve_counterfeit_sdp(g, d, d * d, solver, label=f"W1 n={n}")


# --------------------------------------------------------------------------- #
# Threshold variants (n=2) -- negative control / cross-check, NOT game W1
# --------------------------------------------------------------------------- #


def _note_accept_operator(labels: Sequence[str], t: int) -> np.ndarray:
    """Projector 'at least t of the n positions pass' for ONE note prepared in ``labels``."""
    n = len(labels)
    out = np.zeros((2**n, 2**n), dtype=complex)
    for a in itertools.product((0, 1), repeat=n):
        if sum(a) >= t:
            out += kron_all(proj(ket(s)) if ai else np.eye(2) - proj(ket(s)) for s, ai in zip(labels, a, strict=True))
    return out


def threshold_objective_per_note(n: int, t: int) -> np.ndarray:
    """Two INDEPENDENT per-note threshold verifications (each note needs >= t passes)."""
    d = 2**n
    g = np.zeros((d**3, d**3), dtype=complex)
    for labels in itertools.product(BB84_LABELS, repeat=n):
        a = _note_accept_operator(labels, t)
        g += np.kron(np.kron(_product_rho(labels).T, a), a)
    return g / 4**n


def threshold_objective_mvw_eq4(n: int, t: int) -> np.ndarray:
    """MVW Sec. 3.5 operator R (permuted to our ordering): success = at least t positions
    in which BOTH copies pass. Q1 = G_1, Q0 = sum_k p_k rho_k^T (x) (I - rho_k (x) rho_k)."""
    q1 = w1_objective_numpy(1)
    q0 = sum(np.kron(proj(ket(s)).T, np.eye(4) - np.kron(proj(ket(s)), proj(ket(s)))) for s in BB84_LABELS) / 4
    r = None
    for a in itertools.product((0, 1), repeat=n):
        if sum(a) >= t:
            term = kron_all(q1 if ai else q0 for ai in a)
            r = term if r is None else r + term
    assert r is not None
    # reorder (in_1,o1_1,o2_1, ..., in_n,o1_n,o2_n) -> (in_*, o1_*, o2_*)
    dims = [2] * (3 * n)
    order = [3 * j for j in range(n)] + [3 * j + 1 for j in range(n)] + [3 * j + 2 for j in range(n)]
    k = 3 * n
    rt = r.reshape(dims + dims).transpose(order + [k + o for o in order])
    return rt.reshape(8**n, 8**n)


def mvw_eq4_value(n: int, t: int, alpha: float = 0.75) -> float:
    """MVW eq. (4): sum_{t<=j<=n} C(n,j) alpha^j (1-alpha)^(n-j)."""
    from math import comb

    return sum(comb(n, j) * alpha**j * (1 - alpha) ** (n - j) for j in range(t, n + 1))


# --------------------------------------------------------------------------- #
# W1_CV (classical-verification variant), n=1, block form of MVW Sec. 4.1/4.2
# --------------------------------------------------------------------------- #


def w1cv_blocks() -> dict[tuple[int, int], dict[tuple[int, int], np.ndarray]]:
    """B^{c1c2}_{a1a2} = sum_k p_k [ (a1,c1,k) valid and (a2,c2,k) valid ] rho_k, p_k = 1/4.

    Key k = (basis b, bit t) with b in {0 (Z), 1 (X)}; challenge c in {0,1} selects the
    measurement basis; answer a is valid iff b != c or a == t (MVW Sec. 4.2, d=2).
    """
    labels = {(0, 0): "0", (0, 1): "1", (1, 0): "+", (1, 1): "-"}
    blocks: dict[tuple[int, int], dict[tuple[int, int], np.ndarray]] = {}
    for c1, c2 in itertools.product((0, 1), repeat=2):
        blocks[(c1, c2)] = {}
        for a1, a2 in itertools.product((0, 1), repeat=2):
            b_mat = np.zeros((2, 2), dtype=complex)
            for (b, tbit), lab in labels.items():
                ok1 = b != c1 or a1 == tbit
                ok2 = b != c2 or a2 == tbit
                if ok1 and ok2:
                    b_mat += 0.25 * proj(ket(lab))
            blocks[(c1, c2)][(a1, a2)] = b_mat
    return blocks


@dataclass(frozen=True)
class W1CVReport:
    solver: str
    primal_value: float
    dual_value: float
    duality_gap: float
    primal_status: str
    dual_status: str
    povm_min_eig: float
    povm_completeness_residual: float
    dual_slack_min_eig: float
    Y: dict[tuple[int, int], np.ndarray]
    evidence_kind: str = "NUMERICAL_SDP"


def solve_w1cv_n1(solver: str = "SCS") -> W1CVReport:
    """Optimal simple counterfeiting for W1_CV, n=1 (challenge pairs uniform, prob 1/4 each)."""
    blocks = w1cv_blocks()
    opts = _SOLVER_OPTS[solver]
    xs = {(c, a): cp.Variable((2, 2), hermitian=True) for c in blocks for a in blocks[c]}
    cons = [x >> 0 for x in xs.values()]
    for c in blocks:
        cons.append(sum(xs[(c, a)] for a in blocks[c]) == np.eye(2))
    obj = sum(0.25 * cp.real(cp.trace(blocks[c][a] @ xs[(c, a)])) for c in blocks for a in blocks[c])
    primal = cp.Problem(cp.Maximize(obj), cons)
    primal.solve(solver=solver, **opts)

    ys = {c: cp.Variable((2, 2), hermitian=True) for c in blocks}
    dcons = [ys[c] - 0.25 * blocks[c][a] >> 0 for c in blocks for a in blocks[c]]
    dual = cp.Problem(cp.Minimize(sum(cp.real(cp.trace(y)) for y in ys.values())), dcons)
    dual.solve(solver=solver, **opts)

    xv = {k: np.asarray(v.value) for k, v in xs.items()}
    yv = {c: np.asarray(v.value) for c, v in ys.items()}
    pv = float(sum(0.25 * np.real(np.trace(blocks[c][a] @ xv[(c, a)])) for c in blocks for a in blocks[c]))
    dv = float(sum(np.real(np.trace(y)) for y in yv.values()))
    return W1CVReport(
        solver=solver,
        primal_value=pv,
        dual_value=dv,
        duality_gap=dv - pv,
        primal_status=str(primal.status),
        dual_status=str(dual.status),
        povm_min_eig=min(min_eig(x) for x in xv.values()),
        povm_completeness_residual=max(
            float(np.linalg.norm(sum(xv[(c, a)] for a in blocks[c]) - np.eye(2))) for c in blocks
        ),
        dual_slack_min_eig=min(min_eig(yv[c] - 0.25 * blocks[c][a]) for c in blocks for a in blocks[c]),
        Y=yv,
    )


# --------------------------------------------------------------------------- #
# MVW explicit optimal channel (Sec. 3.2) -- an achieving attack, exact value 3/4
# --------------------------------------------------------------------------- #


def mvw_optimal_kraus() -> list[np.ndarray]:
    """Kraus operators A0, A1 from MVW Sec. 3.2 (p.8), C^2 -> C^2 (x) C^2 = (out1, out2)."""
    a0 = np.array([[3, 0], [0, 1], [0, 1], [1, 0]], dtype=complex) / np.sqrt(12)
    a1 = np.array([[0, 1], [1, 0], [1, 0], [0, 3]], dtype=complex) / np.sqrt(12)
    return [a0, a1]


# --------------------------------------------------------------------------- #
# Negative controls (master plan Sec. 3.3): each must FAIL to reproduce W1 or be flagged
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ControlResult:
    name: str
    primal_value: float
    dual_value: float
    reference_value: float  # the value the CORRECT construction gives for the same ensemble
    deviates: bool  # |value - reference| > tol
    flagged: bool  # caught by deviation OR by an independent oracle / game guard
    mechanism: str
    note: str


def _six_state_kets() -> list[np.ndarray]:
    s = 1 / np.sqrt(2)
    return [ket("0"), ket("1"), ket("+"), ket("-"), np.array([s, 1j * s]), np.array([s, -1j * s])]


def bit_order_swapped_objective() -> np.ndarray:
    """n=2: prepared (s1,s2) but verifier projects copies onto (s2,s1) (endianness bug)."""
    g = np.zeros((64, 64), dtype=complex)
    for a, b in itertools.product(BB84_LABELS, repeat=2):
        r_in = _product_rho([a, b])
        r_ver = _product_rho([b, a])
        g += np.kron(np.kron(r_in.T, r_ver), r_ver)
    return g / 16


def secret_basis_objective() -> np.ndarray:
    """Attacker input = note qubit (x) |basis> (Z->|0>, X->|1>): OUT_OF_MODEL leak."""
    kets = [ket(s) for s in BB84_LABELS]
    basis = [ket("0"), ket("0"), ket("1"), ket("1")]
    return ensemble_objective(kets, [0.25] * 4, side_info=basis)


def run_negative_controls(solver: str = "SCS", tol: float = 1e-5) -> list[ControlResult]:
    from qmint.attacks.heuristic import bit_order_swap_honest_acceptance

    out: list[ControlResult] = []

    def add(name: str, g: np.ndarray, din: int, dout: int, ref: float, mech: str, note: str, extra_flag: bool = False):
        r = solve_counterfeit_sdp(g, din, dout, solver, label=name)
        dev = abs(r.primal_value - ref) > tol or abs(r.dual_value - ref) > tol
        out.append(ControlResult(name, r.primal_value, r.dual_value, ref, dev, dev or extra_flag, mech, note))

    bb = [ket(s) for s in BB84_LABELS]
    add(
        "transpose_omitted_bb84",
        ensemble_objective(bb, [0.25] * 4, transpose=False),
        2, 4, 0.75, "value deviation",
        "UNDETECTABLE on W1: BB84 states are real, so rho^T = rho and G is unchanged. Run on a complex ensemble.",
    )
    add(
        "transpose_omitted_six_state",
        ensemble_objective(_six_state_kets(), [1 / 6] * 6, transpose=False),
        2, 4, 2 / 3, "value deviation from MVW Sec. 3.3 six-state value 2/3",
        "Detected: omitting the transpose models a phase-conjugating cloner on a complex ensemble.",
    )
    add(
        "subsystem_order_mvw_YZX_fed_as_XYZ_n1",
        sum(np.kron(np.kron(proj(k), proj(k)), proj(k).T) for k in bb) / 4,
        2, 4, 0.75, "value deviation",
        "UNDETECTABLE at n=1: for BB84, G_1 is invariant under permuting its three tensor factors.",
    )
    q1 = w1_objective_numpy(1)
    add(
        "subsystem_order_missing_W_pi_n2",
        np.kron(q1, q1),
        4, 16, 0.5625, "value deviation",
        "Detected: Q (x) Q without the W_pi permutation of MVW Sec. 3.4 mislabels input/output registers.",
    )
    honest = bit_order_swap_honest_acceptance(2)
    add(
        "bit_order_swap_verifier_n2",
        bit_order_swapped_objective(),
        4, 16, 0.5625, f"honest-acceptance oracle = {honest:.6f} (must be 1)",
        "SDP value is invariant (the optimal attacker absorbs the SWAP); the bug is flagged because an "
        "honest note is accepted with probability 0.375 < 1.",
        extra_flag=abs(honest - 1) > 1e-12,
    )
    add(
        "threshold_per_note_n2_t1",
        threshold_objective_per_note(2, 1),
        4, 16, 0.5625, "value deviation + game guard (W2, not W1)",
        "Two independent per-note threshold checks (>=1 of 2 positions): value 1 (split attack). "
        "The W1 theorem does not apply.",
    )
    add(
        "threshold_mvw_R_n2_t1",
        threshold_objective_mvw_eq4(2, 1),
        4, 16, 0.5625, "value deviation; cross-check equals MVW eq. (4) = 15/16",
        "MVW Sec. 3.5 success event is '>= t positions where BOTH copies pass', a different event "
        "from two independent per-note thresholds.",
    )
    add(
        "secret_basis_given_to_attacker",
        secret_basis_objective(),
        4, 4, 0.75, "value deviation; OUT_OF_MODEL",
        "Attacker given the secret basis clones perfectly (value 1). Violates the W1 trust model.",
    )
    return out
