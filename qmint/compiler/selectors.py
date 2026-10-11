"""The four pre-registered selectors (master plan 4.4) on one shared discretisation.

  published_fixed    exact published parameter tuple (off-grid by definition), scored as published
  naive_analytic     documented heuristic thresholds + binary search on N
  exhaustive_oracle  every grid tuple scored; the only selector allowed to claim a global optimum (on its grid)
  compiler           monotonicity-aware pruning (conditions M1-M3, unit-tested), cached evaluations,
                     interval worst-case via the engine, exact tie-break enumeration at the optimal N

Every candidate is scored ONLY through ``qmint.compiler.scoring.Scorer`` (lane D's ProofEngine).
Ranking (frozen tie-break): (N, honest-failure log10, eps_unf log10, grid-index tuple), all minimised.
"""

from __future__ import annotations

import itertools
import math
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from qmint.compiler.constraints import Problem, frozen
from qmint.compiler.scoring import Score, Scorer, honest_log10
from qmint.core.contracts import SecurityAxis

ROB, COR, UNF, PRIV = SecurityAxis.ROBUSTNESS, SecurityAxis.CORRECTNESS, SecurityAxis.UNFORGEABILITY, SecurityAxis.PRIVACY
NEG_INF = float("-inf")


@dataclass
class Selection:
    selector: str
    scenario_id: str
    status: str  # FEASIBLE | INFEASIBLE | NOT_AVAILABLE | REJECTED
    optimality: str
    idx: tuple[int, ...] | None = None
    decisions: dict[str, Any] | None = None
    logs: dict[str, float] = field(default_factory=dict)
    honest_log10: float | None = None
    engine_calls: int = 0
    cache_hits: int = 0
    wall_seconds: float = 0.0
    note: str = ""
    feasible_points: list[tuple[int, float | None, float, tuple[int, ...]]] | None = None  # oracle only

    @property
    def N(self) -> int | None:
        if not self.decisions:
            return None
        return int(self.decisions.get("N", self.decisions.get("n")))


def _rank(n: int, honest: float | None, unf: float, idx: tuple[int, ...]) -> tuple:
    return (n, NEG_INF if honest is None else honest, unf, idx)


def _feasible(problem: Problem, scores: dict[SecurityAxis, Score]) -> bool:
    return all(scores[a].meets(problem.target_log10(a)) for a in problem.target_axes)


def _logs(scores: dict[SecurityAxis, Score]) -> dict[SecurityAxis, float]:
    return {a: s.log10 for a, s in scores.items() if s.log10 is not None}


def _finish(sel: Selection, scorer: Scorer, t0: float, calls0: int, hits0: int) -> Selection:
    sel.engine_calls = scorer.engine_calls - calls0
    sel.cache_hits = scorer.cache_hits - hits0
    sel.wall_seconds = time.perf_counter() - t0
    return sel


def _selection_from(problem: Problem, selector: str, optimality: str, idx: tuple[int, ...] | None,
                    decisions: dict[str, Any], scores: dict[SecurityAxis, Score], note: str = "") -> Selection:
    logs = _logs(scores)
    return Selection(
        selector=selector, scenario_id=problem.scenario_id,
        status="FEASIBLE" if _feasible(problem, scores) else "INFEASIBLE",
        optimality=optimality, idx=idx, decisions=decisions,
        logs={a.value: v for a, v in logs.items()}, honest_log10=honest_log10(problem, logs), note=note,
    )


def _first_true(lo: int, hi: int, pred: Callable[[int], bool]) -> int | None:
    """Smallest i in [lo, hi] with pred(i), for a predicate monotone False..True; None if pred(hi) is False."""
    if lo > hi or not pred(hi):
        return None
    while lo < hi:
        mid = (lo + hi) // 2
        if pred(mid):
            hi = mid
        else:
            lo = mid + 1
    return lo


def _last_true(lo: int, hi: int, pred: Callable[[int], bool]) -> int | None:
    """Largest i in [lo, hi] with pred(i), for a predicate monotone True..False; None if pred(lo) is False."""
    if lo > hi or not pred(lo):
        return None
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if pred(mid):
            lo = mid
        else:
            hi = mid - 1
    return lo


# --------------------------------------------------------------------------- #
# (3) Exhaustive oracle
# --------------------------------------------------------------------------- #


def exhaustive_oracle(problem: Problem, scorer: Scorer | None = None) -> Selection:
    """Score EVERY tuple of ``problem.grid`` (no pruning, no structural assumption)."""
    scorer = scorer or Scorer(cache=False)
    t0, c0, h0 = time.perf_counter(), scorer.engine_calls, scorer.cache_hits
    best: tuple | None = None
    best_payload: tuple | None = None
    feasible: list[tuple[int, float | None, float, tuple[int, ...]]] = []
    for idx in itertools.product(*(range(n) for n in problem.shape)):
        dec = problem.decision_values(idx)
        scores = scorer.score_all(problem, dec)
        if not _feasible(problem, scores):
            continue
        logs = _logs(scores)
        h = honest_log10(problem, logs)
        key = _rank(dec.get("N", dec.get("n")), h, logs[UNF], idx)
        feasible.append((key[0], h, logs[UNF], idx))
        if best is None or key < best:
            best, best_payload = key, (idx, dec, scores)
    if best_payload is None:
        sel = Selection("exhaustive_oracle", problem.scenario_id, "INFEASIBLE", "global_optimum_on_grid",
                        note="no feasible tuple on the grid")
    else:
        idx, dec, scores = best_payload
        sel = _selection_from(problem, "exhaustive_oracle", "global_optimum_on_grid", idx, dec, scores)
    sel.feasible_points = feasible
    return _finish(sel, scorer, t0, c0, h0)


# --------------------------------------------------------------------------- #
# (4) Compiler
# --------------------------------------------------------------------------- #


def compiler(problem: Problem, scorer: Scorer | None = None) -> Selection:
    scorer = scorer or Scorer(cache=True)
    t0, c0, h0 = time.perf_counter(), scorer.engine_calls, scorer.cache_hits
    impl = {"ideal": _compile_ideal, "S2": _compile_s2, "D1": _compile_d1}[problem.family]
    return _finish(impl(problem, scorer), scorer, t0, c0, h0)


OPT_COMPILER = "best_found"


def _infeasible(problem: Problem, note: str) -> Selection:
    return Selection("compiler", problem.scenario_id, "INFEASIBLE", OPT_COMPILER, note=note)


def _compile_ideal(problem: Problem, scorer: Scorer) -> Selection:
    """M1: the ideal bound b^N is decreasing in N -> binary search."""
    nN = problem.shape[0]
    t = problem.target_log10(UNF)
    for a in problem.target_axes:  # e.g. a privacy target: no theorem for the ideal games
        if a != UNF and not scorer.score(problem, a, problem.decision_values((nN - 1,))).meets(problem.target_log10(a)):
            return _infeasible(problem, f"{a.value}: no applicable bound meets the target")
    n = _first_true(0, nN - 1, lambda i: scorer.score(problem, UNF, problem.decision_values((i,))).meets(t))
    if n is None:
        return _infeasible(problem, "target not reached at the largest grid N")
    dec = problem.decision_values((n,))
    return _selection_from(problem, "compiler", OPT_COMPILER, (n,), dec, scorer.score_all(problem, dec))


def _compile_s2(problem: Problem, scorer: Scorer) -> Selection:
    g = problem.grid
    nN, nD, nE, nC, nU = problem.shape
    tl = {a: problem.target_log10(a) for a in problem.target_axes}

    def dec(n: int, d: int = 0, e: int = 0, c: int = 0, u: int = 0) -> dict[str, Any]:
        return problem.decisions_from_coords({"N": g["N"][n], "r_det": g["r_det"][d], "r_err": g["r_err"][e],
                                              "r_cor": g["r_cor"][c], "r_unf": g["r_unf"][u]})

    def s(axis: SecurityAxis, *idx: int) -> Score:
        return scorer.score(problem, axis, dec(*idx))

    if PRIV in tl and not s(PRIV, nN - 1).meets(tl[PRIV]):  # eps_priv = beta_E: independent of every decision
        return _infeasible(problem, "epsilon_priv: Lemma 4 bound (beta_E, fixed by the device) exceeds the target")
    rob_t = tl.get(ROB)
    cor_t = tl.get(COR)
    # Eq. (4) domain in gamma_err does not depend on N or nu_cor: the valid r_err indices form a prefix (M2).
    valid_e = [e for e in range(nE) if not s(COR, nN - 1, 0, e, 0).out_of_domain] if cor_t is not None else list(range(nE))
    if valid_e != list(range(len(valid_e))):
        raise RuntimeError("Eq.(4) valid gamma_err indices are not a prefix of the ascending grid (M2 violated)")
    if not valid_e:
        return _infeasible(problem, "Eq.(4): no grid gamma_err with gamma_err/2 < E < gamma_err on every corner")
    e_last = valid_e[-1]

    def rob_ok(n: int, d: int) -> bool:
        return rob_t is None or s(ROB, n, d).meets(rob_t)

    def cor_ok(n: int, e: int) -> bool:
        return cor_t is None or any(s(COR, n, 0, e, c).meets(cor_t) for c in range(nC))

    def feasible_at(n: int) -> bool:
        d_max = _last_true(0, nD - 1, lambda d: rob_ok(n, d))  # M2: rob nondecreasing in gamma_det
        if d_max is None:
            return False
        e_min = _first_true(0, e_last, lambda e: cor_ok(n, e))  # M2: min_nu cor nonincreasing in gamma_err
        if e_min is None:
            return False
        return any(s(UNF, n, d_max, e_min, 0, u).meets(tl[UNF]) for u in range(nU))  # M2: best (d, e) for unf

    n_star = _first_true(0, nN - 1, feasible_at)  # M1
    if n_star is None:
        return _infeasible(problem, "no feasible configuration at the largest grid N (see infeasibility certificate)")

    # Exact tie-break at n*: enumerate (gamma_det, gamma_err); per pair the nu_cor / nu_unf choices separate.
    rob_logs = [s(ROB, n_star, d).log10 if rob_t is not None else None for d in range(nD)]
    best: tuple | None = None
    for e in valid_e:
        cor_scores = [s(COR, n_star, 0, e, c) for c in range(nC)] if cor_t is not None else []
        for d in range(nD):
            if rob_t is not None and not (rob_logs[d] is not None and rob_logs[d] <= rob_t):
                continue
            # honest = lse(rob, cor_c): choose the c minimising (honest, c)
            hc: tuple[float, int] | None = None
            if cor_t is not None:
                for c, sc in enumerate(cor_scores):
                    if sc.meets(cor_t):
                        logs = {COR: sc.log10}
                        if rob_t is not None:
                            logs[ROB] = rob_logs[d]
                        h = honest_log10(problem, logs)
                        cand = (NEG_INF if h is None else h, c)
                        hc = cand if hc is None or cand < hc else hc
                if hc is None:
                    continue
            uc: tuple[float, int] | None = None
            for u in range(nU):
                su = s(UNF, n_star, d, e, 0, u)
                if su.meets(tl[UNF]):
                    cand = (su.log10, u)
                    uc = cand if uc is None or cand < uc else uc
            if uc is None:
                continue
            c_idx = hc[1] if hc is not None else 0
            key = (hc[0] if hc is not None else NEG_INF, uc[0], (n_star, d, e, c_idx, uc[1]))
            best = key if best is None or key < best else best
    if best is None:
        raise RuntimeError("feasible_at(n*) was True but tie-break enumeration found nothing (M2 violated)")
    idx = best[2]
    d_ = dec(*idx)
    return _selection_from(problem, "compiler", OPT_COMPILER, idx, d_, scorer.score_all(problem, d_))


def _compile_d1(problem: Problem, scorer: Scorer) -> Selection:
    g = problem.grid
    nN, nDd, nDh = problem.shape
    tl = {a: problem.target_log10(a) for a in problem.target_axes}
    for a in tl:
        if a not in (UNF, COR):
            return _infeasible(problem, f"{a.value}: no D1 theorem for this axis (never reported as 0)")

    def dec(n: int, i: int, j: int) -> dict[str, Any]:
        return problem.decisions_from_coords({"N": g["N"][n], "delta_d": g["delta_d"][i], "delta_h": g["delta_h"][j]})

    def s(axis: SecurityAxis, n: int, i: int, j: int) -> Score:
        return scorer.score(problem, axis, dec(n, i, j))

    def admissible(i: int, j: int) -> bool:  # SI Eq. (23) (+ domain) is independent of N
        return not s(UNF, nN - 1, i, j).out_of_domain

    # M3: the admissible set is downward closed in (delta_d, delta_h)
    i_max = _last_true(0, nDd - 1, lambda i: admissible(i, 0))
    j_max = _last_true(0, nDh - 1, lambda j: admissible(0, j))
    if i_max is None or j_max is None:
        return _infeasible(problem, "SI Eq. (23) not satisfiable on the grid: (1/2)(1-p_m/2)(1-delta_d) < M(e_h,l_h)(1+delta_h)")

    def ok(axis: SecurityAxis, n: int, i: int, j: int) -> bool:
        return axis not in tl or s(axis, n, i, j).meets(tl[axis])

    def feasible_at(n: int) -> bool:
        i_req = _first_true(0, i_max, lambda i: ok(UNF, n, i, 0))  # M3: p_d nonincreasing in delta_d
        j_req = _first_true(0, j_max, lambda j: ok(COR, n, 0, j))  # M3: 1-p_h bound nonincreasing in delta_h
        return i_req is not None and j_req is not None and ok(UNF, n, i_req, j_req) and ok(COR, n, i_req, j_req)

    n_star = _first_true(0, nN - 1, feasible_at)  # M1
    if n_star is None:
        return _infeasible(problem, "no admissible (delta_d, delta_h) meets the targets at the largest grid N")
    best: tuple | None = None
    for i in range(i_max + 1):
        for j in range(j_max + 1):
            sc = {a: s(a, n_star, i, j) for a in tl}
            if not _feasible(problem, sc):
                continue
            logs = _logs(sc)
            h = honest_log10(problem, logs)
            key = (NEG_INF if h is None else h, logs[UNF], (n_star, i, j))
            best = key if best is None or key < best else best
    assert best is not None
    idx = best[2]
    d_ = dec(*idx)
    return _selection_from(problem, "compiler", OPT_COMPILER, idx, d_, scorer.score_all(problem, d_))


def s2_best_unf_at_n(problem: Problem, N: int, scorer: Scorer | None = None) -> Selection:
    """Ablation A3: N fixed (possibly off-grid), thresholds optimised for the lowest eps_unf subject to the
    honest targets. Uses M2: the best (gamma_det, gamma_err) for unf is (largest rob-feasible, smallest
    cor-feasible); nu_unf is scanned over the grid."""
    scorer = scorer or Scorer(cache=True)
    t0, c0, h0 = time.perf_counter(), scorer.engine_calls, scorer.cache_hits
    g = problem.grid
    _, nD, nE, nC, nU = problem.shape
    tl = {a: problem.target_log10(a) for a in problem.target_axes}

    def dec(d: int, e: int, c: int, u: int) -> dict[str, Any]:
        return problem.decisions_from_coords({"N": N, "r_det": g["r_det"][d], "r_err": g["r_err"][e],
                                              "r_cor": g["r_cor"][c], "r_unf": g["r_unf"][u]})

    d_max = _last_true(0, nD - 1, lambda d: scorer.score(problem, ROB, dec(d, 0, 0, 0)).meets(tl[ROB]))
    e_last = _last_true(0, nE - 1, lambda e: not scorer.score(problem, COR, dec(0, e, 0, 0)).out_of_domain)
    e_min = None if e_last is None else _first_true(0, e_last, lambda e: any(scorer.score(problem, COR, dec(0, e, c, 0)).meets(tl[COR])
                                                  for c in range(nC)))
    best: tuple | None = None
    if d_max is not None and e_min is not None:
        c = next(c for c in range(nC) if scorer.score(problem, COR, dec(0, e_min, c, 0)).meets(tl[COR]))
        for u in range(nU):
            su = scorer.score(problem, UNF, dec(d_max, e_min, c, u))
            if su.log10 is not None:
                best = (su.log10, u, c) if best is None or (su.log10, u) < best[:2] else best
    if best is None:
        sel = Selection("compiler_fixed_N", problem.scenario_id, "INFEASIBLE", OPT_COMPILER,
                        note=f"no applicable eps_unf bound at N={N} under the honest targets")
    else:
        d_ = dec(d_max, e_min, best[2], best[1])
        sel = _selection_from(problem, "compiler_fixed_N", OPT_COMPILER, None, d_, scorer.score_all(problem, d_),
                              note=f"N fixed at {N}")
    return _finish(sel, scorer, t0, c0, h0)


# --------------------------------------------------------------------------- #
# (2) Naive analytic sizing
# --------------------------------------------------------------------------- #


def _nearest(vals: Sequence[float], x: float) -> int:
    return min(range(len(vals)), key=lambda i: (abs(vals[i] - x), i))


def _snap_up(vals: Sequence[float], x: float) -> int | None:
    return next((i for i, v in enumerate(vals) if v >= x), None)


def _snap_down(vals: Sequence[float], x: float) -> int | None:
    return next((i for i in range(len(vals) - 1, -1, -1) if vals[i] <= x), None)


KENT_R_DET = 0.018 / 0.019  # KLPR2022 Methods: gamma_det = 0.018 at P_det = 0.019


def naive_rule_s2(problem: Problem, n: int) -> tuple[int, ...] | None:
    """Kent Fig. 5 'each exponential = target/2' rule on the grid (None if the rule has no grid value)."""
    g, a = problem.grid, problem.anchors
    N = g["N"][n]
    t_unf = problem.targets.epsilon_unf
    t_cor = problem.targets.epsilon_cor
    d = _nearest(g["r_det"], KENT_R_DET)
    pn = a["P_noqub_hi"]
    u = _snap_up(g["r_unf"], 1 + math.sqrt(3 * math.log(2 / t_unf) / (pn * N)))
    if t_cor is None:
        return None if u is None else (n, d, 0, 0, u)
    rc = 1 - math.sqrt(4 * math.log(2 / t_cor) / (a["A_lo"] * N))
    c = _snap_down(g["r_cor"], rc) if rc > 0 else None
    if u is None or c is None:
        return None
    nu_cor = g["r_cor"][c] * a["A_lo"] / 2
    e = _snap_up(g["r_err"], 1 + math.sqrt(3 * math.log(2 / t_cor) / (a["E_hi"] * nu_cor * N)))
    return None if e is None else (n, d, e, c, u)


def naive_rule_d1(problem: Problem, n: int) -> tuple[int, ...]:
    pub = frozen()["selectors"]["published_fixed"]["D1"]["tuple"]
    return (n, _nearest(problem.grid["delta_d"], pub["delta_d"]), _nearest(problem.grid["delta_h"], pub["delta_h"]))


def naive_analytic(problem: Problem, scorer: Scorer | None = None) -> Selection:
    scorer = scorer or Scorer(cache=True)
    t0, c0, h0 = time.perf_counter(), scorer.engine_calls, scorer.cache_hits
    nN = problem.shape[0]
    rule: Callable[[int], tuple[int, ...] | None] = {
        "ideal": lambda n: (n,),
        "S2": lambda n: naive_rule_s2(problem, n),
        "D1": lambda n: naive_rule_d1(problem, n),
    }[problem.family]

    def feasible(n: int) -> bool:
        idx = rule(n)
        return idx is not None and _feasible(problem, scorer.score_all(problem, problem.decision_values(idx)))

    n = _first_true(0, nN - 1, feasible)
    # post hoc: is the rule's feasibility really monotone in N on this grid? (linear scan, reported)
    flags = [feasible(i) for i in range(nN)]
    monotone = all(flags[i] <= flags[i + 1] for i in range(nN - 1))
    note = f"rule feasibility monotone in N on grid: {monotone}"
    if n is None:
        sel = Selection("naive_analytic", problem.scenario_id, "INFEASIBLE", "heuristic", note=note)
    else:
        idx = rule(n)
        assert idx is not None
        dec = problem.decision_values(idx)
        sel = _selection_from(problem, "naive_analytic", "heuristic", idx, dec, scorer.score_all(problem, dec), note)
    sel.note = note
    return _finish(sel, scorer, t0, c0, h0)


# --------------------------------------------------------------------------- #
# (1) Published fixed recipe
# --------------------------------------------------------------------------- #


def published_decisions(problem: Problem) -> dict[str, Any] | None:
    """The published tuple exactly as published (None if no recipe exists for this game)."""
    pub = frozen()["selectors"]["published_fixed"]
    if problem.family == "S2":
        p = pub["S2"]
        dev = problem.device
        # Fig. 5 procedure uses the paper's point values: for an interval device the published tuple is
        # computed from the interval midpoint (= the point device) and then scored on the whole box.
        def mid(k: str) -> float:
            v = dev[k]
            return (v["lo"] + v["hi"]) / 2 if isinstance(v, dict) else v

        N, half = p["tuple"]["N"], math.log(2 / p["design_target"])
        A = mid("P_det") * (1 - 2 * mid("beta_PB"))
        nu_cor = A / 2 * (1 - math.sqrt(4 * half / (A * N)))
        gamma_err = mid("E") * (1 + math.sqrt(3 * half / (mid("E") * nu_cor * N))) * 1.001
        return {"N": N, "gamma_det": p["tuple"]["gamma_det"], "nu_unf": p["tuple"]["nu_unf"],
                "nu_cor": nu_cor, "gamma_err": gamma_err}
    if problem.family == "D1":
        return dict(pub["D1"]["tuple"])
    return None


def published_fixed(problem: Problem, scorer: Scorer | None = None) -> Selection:
    scorer = scorer or Scorer(cache=True)
    t0, c0, h0 = time.perf_counter(), scorer.engine_calls, scorer.cache_hits
    dec = published_decisions(problem)
    if dec is None:
        sel = Selection("published_fixed", problem.scenario_id, "NOT_AVAILABLE", "published",
                        note=frozen()["selectors"]["published_fixed"].get(problem.game.value, {}).get(
                            "expected", "NO_PUBLISHED_RECIPE"))
    else:
        sel = _selection_from(problem, "published_fixed", "published", None, dec, scorer.score_all(problem, dec),
                              note="published tuple scored exactly as published (off-grid)")
    return _finish(sel, scorer, t0, c0, h0)


SELECTORS: dict[str, Callable[..., Selection]] = {
    "published_fixed": published_fixed,
    "naive_analytic": naive_analytic,
    "exhaustive_oracle": exhaustive_oracle,
    "compiler": compiler,
}
