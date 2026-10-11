"""Reproduce every numerical example quoted by the registered sources and write evidence.

    python -m qmint.proofs.reproduce [--out proofs/certificates]

Writes ``reproduction_v1.json`` (paper value vs QMint value, with anchors) and example
certificates checked by ``IndependentProofChecker``. Deterministic; no network access.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

from qmint.core.contracts import GameId, Targets
from qmint.core.serialization import canonical_json, file_sha256
from qmint.proofs import finite_size as fs
from qmint.proofs import sdp_exact
from qmint.proofs.checker import IndependentProofChecker
from qmint.proofs.engine import ProofEngine
from qmint.proofs.ideal_bounds import log10_bound, min_length_for_target
from qmint.proofs.registry import OBLIGATIONS_PATH, default_registry

# Kent et al. 2022, Methods "Experimental tests and numerical example" (p.12-13)
KENT_EXP = {"N": 40_000_000, "P_det": 0.019, "gamma_det": 0.018, "mu": 0.09, "eta": 0.21, "nu_unf": 3.9e-3}
KENT_COUNTS = {
    "n": 742_491,
    "n_tu": {"00": 185_166, "10": 187_842, "01": 184_251, "11": 185_232},
    "same": {"00": 80_786, "10": 121_159, "01": 93_618, "11": 80_653},
    "error": {"00": 4_725, "10": 2_250, "01": 1_602, "11": 3_851},
}
HALF_TARGET = 1e-9 / 2  # paper sets each exponential term to 10^-9/2


def kent_p_noqub(mu: float) -> float:
    """Table 5 item 1 / Methods: P_noqub = 1 - (1 + mu) e^-mu for a Poissonian source."""
    return -math.expm1(-mu) - mu * math.exp(-mu)


def kent_fig5_beta_max(theta_deg: float, e: float, p_noqub: float) -> dict[str, float] | None:
    """Fig. 5 procedure: beta_PB = beta_PS = beta; choose nu_cor, gamma_err so each cor term and the
    second unf term are <= 10^-9/2; return the largest admissible beta (bisection)."""
    n, pdet, gdet, nu_unf = KENT_EXP["N"], KENT_EXP["P_det"], KENT_EXP["gamma_det"], KENT_EXP["nu_unf"]
    theta, ln_half = math.radians(theta_deg), math.log(HALF_TARGET)

    def tuple_for(beta: float) -> dict[str, float] | None:
        a = pdet * (1 - 2 * beta)
        nu_cor = a / 2 * (1 - math.sqrt(-4 * ln_half / (a * n)))  # first cor term == 10^-9/2
        gamma_err = e * (1 + math.sqrt(-3 * ln_half / (e * nu_cor * n)))  # second cor term == 10^-9/2
        p = dict(N=n, P_det=pdet, gamma_det=gdet, E=e, gamma_err=gamma_err, nu_cor=nu_cor, beta_PB=beta,
                 beta_PS=beta, theta=theta, P_noqub=p_noqub, nu_unf=nu_unf, M=1)
        if fs.kent_cor_domain(p) or fs.kent_unf_domain(p):
            return None
        f = fs.kent_f(gamma_err, beta, beta, theta, nu_unf, gdet)
        return p if -n * f <= ln_half else None

    if tuple_for(1e-12) is None:
        return None
    lo, hi = 1e-12, 0.1
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if tuple_for(mid) else (lo, mid)
    return tuple_for(lo)


def _row(quantity: str, anchor: str, paper: Any, ours: Any, agrees: bool, kind: str) -> dict[str, Any]:
    return {"quantity": quantity, "anchor": anchor, "paper_value": paper, "qmint_value": ours,
            "agrees": agrees, "evidence_kind": kind}


def reproduce() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for game, paper in (("W1", 73), ("W1_CV", 273), ("S1", 131)):
        n = min_length_for_target(game, 1e-9)
        rows.append(_row(f"{game} min length for eps<=1e-9", "bootstrap/ideal_bounds.py behaviour", paper, n,
                         n == paper, "PUBLISHED_THEOREM"))
    rows.append(_row("W1 log10 bound at n=10^6", "MVW2012 Thm 1", None, log10_bound("W1", 10**6), True,
                     "PUBLISHED_THEOREM"))

    k = KENT_EXP
    ln_rob = fs.kent_ln_rob({"N": k["N"], "P_det": k["P_det"], "gamma_det": k["gamma_det"]})
    rows.append(_row("S2 ln eps_rob (Lemma 2) at N=4e7,P_det=0.019,gamma_det=0.018", "KLPR2022 Methods p.12",
                     -1052, ln_rob, round(ln_rob) in (-1052, -1053), "PUBLISHED_AGGREGATE"))
    pnq = kent_p_noqub(k["mu"])
    rows.append(_row("P_noqub at mu=0.09", "KLPR2022 Methods p.13", 3.8e-3, pnq, round(pnq, 4) == 0.0038,
                     "PUBLISHED_AGGREGATE"))
    pdet_theo = 2 * (math.exp(-k["mu"] * k["eta"] / 2) - math.exp(-k["mu"] * k["eta"]))
    rows.append(_row("P_det theoretical (Eq. 17)", "KLPR2022 Eq. (17)", 0.01863, pdet_theo,
                     round(pdet_theo, 5) == 0.01863, "PUBLISHED_AGGREGATE"))
    nt, c = KENT_COUNTS["n_tu"], KENT_COUNTS
    b_pb = abs((nt["00"] + nt["10"]) / c["n"] - 0.5)
    b_ps = max(abs(nt["00"] / (nt["00"] + nt["10"]) - 0.5), abs(nt["01"] / (nt["01"] + nt["11"]) - 0.5))
    e_max = max(c["error"][t] / c["same"][t] for t in c["same"])
    rows.append(_row("beta_PB from counts", "KLPR2022 Methods p.13", 2.4e-3, b_pb, round(b_pb, 4) == 0.0024, "PUBLISHED_AGGREGATE"))
    rows.append(_row("beta_PS from counts", "KLPR2022 Methods p.13", 3.6e-3, b_ps, round(b_ps, 4) == 0.0036, "PUBLISHED_AGGREGATE"))
    rows.append(_row("E = max E_tu from counts", "KLPR2022 Methods p.13", 0.058, e_max, round(e_max, 3) == 0.058, "PUBLISHED_AGGREGATE"))
    # minimal nu_unf making the first unf term 10^-9/2 at the rounded P_noqub = 3.8e-3
    nu_min = 3.8e-3 * (1 + math.sqrt(-3 * math.log(HALF_TARGET) / (3.8e-3 * k["N"])))
    rows.append(_row("minimal nu_unf (first term of Eq. 10 = 1e-9/2)", "KLPR2022 Methods p.13", 3.9e-3, nu_min,
                     round(nu_min, 4) == 0.0039, "PUBLISHED_AGGREGATE"))
    for theta, e, paper, rel in ((10, 0.058, 6e-6, 0.2), (5, 0.03, 2.3e-4, 0.05), (1e-6, 0.01, 6e-4, 0.05)):
        best = kent_fig5_beta_max(theta, e, pnq)
        ours = best["beta_PB"] if best else None
        rows.append(_row(f"Fig.5 beta_max theta={theta}deg E={e}", "KLPR2022 Fig. 5 / Methods p.12", paper, ours,
                         ours is not None and ours >= paper * (1 - rel), "DIGITIZED_FIGURE"))
    # The experimental tuple (theta <= 10 deg) admits NO gamma_err in (E, lambda) satisfying Theorem 1.
    exp_ok = any(
        not fs.kent_unf_domain(dict(N=k["N"], P_noqub=pnq, nu_unf=k["nu_unf"], gamma_err=0.058 + i * 1e-4,
                                    beta_PS=3.6e-3, beta_PB=2.4e-3, theta=math.radians(10), gamma_det=k["gamma_det"]))
        for i in range(1, 1000)
    )
    rows.append(_row("experimental tuple (beta 2.4e-3/3.6e-3, theta 10deg) satisfies Theorem 1 for some gamma_err",
                     "KLPR2022 Results p.7 ('we need to improve some experimental parameters')",
                     False, exp_ok, exp_ok is False, "PUBLISHED_AGGREGATE"))

    d1 = dict(N=4.2e6, p_m=0.0602, delta_d=0.01, delta_h=0.031, e_h=0.03278, l_h=0.224)
    pd = math.exp(fs.schiansky_ln_pd(d1))
    rows.append(_row("D1 p_d at N=4.2e6, p_m=0.0602, delta_d=0.01", "Schiansky 2023 SI Eq. (22), SI Table 2", 5.911e-45,
                     pd, abs(pd / 5.911e-45 - 1) < 0.01, "PUBLISHED_AGGREGATE"))
    pd_si_n = math.exp(fs.schiansky_ln_pd(dict(d1, N=4_482_440)))
    rows.append(_row("D1 p_d with SI Table 2 N=4,482,440 (shows published p_d used N=4.2e6)",
                     "Schiansky 2023 SI Table 2 vs main Fig. 4b", 5.911e-45, pd_si_n, pd_si_n < 1e-46,
                     "PUBLISHED_AGGREGATE"))
    ed_main = fs.schiansky_secure_error(0.224, 0.0676)
    rows.append(_row("D1 e_d(l_m) with main-text p_m=6.76%", "Schiansky 2023 main text Results", 0.0379, ed_main,
                     round(ed_main, 4) == 0.0379, "PUBLISHED_AGGREGATE"))
    resc = math.exp(fs.schiansky_ln_pd_rescaled_assessment(d1))
    rows.append(_row("QMint assessment: p_d with Chernoff applied to mishaps rescaled into [0,1] (NOT published)",
                     "open question, see proofs/notes/P-D1.md", None, resc, True, "UNCERTIFIED"))
    m = fs.schiansky_mishaps(0.03278, 0.224)
    rows.append(_row("D1 mishaps M(e_m+-, l_m)", "Schiansky 2023 SI Eq. (18), SI Table 2", 0.448, m, round(m, 3) == 0.448, "PUBLISHED_AGGREGATE"))
    ed = fs.schiansky_secure_error(0.224, 0.0602)
    rows.append(_row("D1 dishonest error e_d(l_m)", "Schiansky 2023 SI Eq. (16), SI Table 2 / main text", 0.0382, ed,
                     round(ed, 4) == 0.0382, "PUBLISHED_AGGREGATE"))
    rows.append(_row("D1 Eq. (23) admissible at delta_h=0.031, delta_d=0.01", "Schiansky 2023 SI Eq. (23)", True,
                     not fs.schiansky_domain(d1), not fs.schiansky_domain(d1), "PUBLISHED_AGGREGATE"))
    # Lane C CERTIFIED_NUMERIC SDP claims (handoffs/C-C1-evidence.json) vs lane D exact re-verification
    for n, c_bound in ((1, 0.750000000003638), (2, 0.562500000007276)):
        ub = sdp_exact.w1_independent_upper_bound(n)
        rows.append(_row(f"W1 n={n} SDP: lane C certified upper bound vs exact dual (3/8)^n 1",
                         "MVW2012 Sec. 3.2/3.4; audits/SDP_DERIVATION.md (lane C)", c_bound, str(ub),
                         c_bound >= ub, "CERTIFIED_NUMERIC"))
    ub_cv = sdp_exact.w1cv_independent_upper_bound()
    rows.append(_row("W1_CV n=1 SDP: lane C certified upper bound vs lane D exact dual",
                     "MVW2012 Thm 2 / Sec. 4.1; lane C evidence", 0.9267766955417756, float(ub_cv),
                     0.9267766955417756 >= ub_cv, "CERTIFIED_NUMERIC"))
    return {"rows": rows, "all_agree": all(r["agrees"] for r in rows)}


def example_certificates() -> dict[str, Any]:
    reg, engine, checker = default_registry(), ProofEngine(), IndependentProofChecker()
    ev = [file_sha256(OBLIGATIONS_PATH)]
    out: dict[str, Any] = {}

    w1 = engine.draft_certificate(
        "wiesner_ideal", GameId.W1, {"n": 73, "declared_assumptions": reg.claim("P-W1").required_declarations},
        Targets(epsilon_unf=1e-9), security_model_id="mvw2012_simple_counterfeiting", evidence_hashes=ev)
    out["W1_n73"] = checker.check(w1)

    s2_decl = reg.claim("P-S2").required_declarations
    best = kent_fig5_beta_max(10, 0.058, kent_p_noqub(KENT_EXP["mu"]))
    assert best is not None
    # Paper's Fig. 5 point (beta = 6e-6 < our beta_max) with gamma_err nudged up 0.1 % so that eps_cor is
    # strictly below 1e-9 (the paper's construction makes it EXACTLY 1e-9, which float rounding can exceed).
    fig5 = dict(best, beta_PB=6e-6, beta_PS=6e-6, gamma_err=best["gamma_err"] * 1.001, beta_E=1e-10,
                noise_source="hypothetical", declared_assumptions=s2_decl)
    s2 = engine.draft_certificate(
        "s_money_kent_2022_realistic", GameId.S2, fig5,
        Targets(epsilon_unf=1e-9, epsilon_cor=1e-9, epsilon_rob=1e-9, epsilon_priv=1e-9),
        security_model_id="kent2022_qt1_table6", evidence_hashes=ev)
    out["S2_fig5_theta10_E058_hypothetical"] = checker.check(s2)

    exp_params = dict(fig5, beta_PB=2.4e-3, beta_PS=3.6e-3, noise_source="published_kent_2022")
    s2x = engine.draft_certificate(
        "s_money_kent_2022_realistic", GameId.S2, exp_params, Targets(epsilon_unf=1e-9, epsilon_cor=1e-9),
        security_model_id="kent2022_qt1_table6", evidence_hashes=ev)
    out["S2_kent_experimental_tuple"] = checker.check(s2x)

    d1 = engine.draft_certificate(
        "schiansky_payment_2023", GameId.D1,
        dict(N=4_200_000, p_m=0.0602, delta_d=0.01, delta_h=0.031, e_h=0.03278, l_h=0.224,
             noise_source="published_schiansky_2023", declared_assumptions=reg.claim("P-D1").required_declarations),
        Targets(epsilon_unf=1e-40), security_model_id="schiansky2023_si_note3", evidence_hashes=ev)
    out["D1_schiansky_published"] = checker.check(d1)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="proofs/certificates")
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rep = reproduce()
    rep["obligations_sha256"] = file_sha256(OBLIGATIONS_PATH)
    (out / "reproduction_v1.json").write_text(canonical_json(rep) + "\n", encoding="utf-8")
    for name, cert in example_certificates().items():
        (out / f"{name}.json").write_text(canonical_json(cert) + "\n", encoding="utf-8")
        print(f"{name}: {cert.proof_check_status.value}")
    for r in rep["rows"]:
        print(f"[{'ok' if r['agrees'] else 'MISMATCH'}] {r['quantity']}: paper={r['paper_value']} qmint={r['qmint_value']}")
    return 0 if rep["all_agree"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
