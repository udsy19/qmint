from __future__ import annotations

import itertools
import math

import pytest

from qmint.core.contracts import (
    BoundRequest,
    CalibrationRecord,
    EvidenceKind,
    Interval,
    ProofStatus,
    SecurityAxis,
    Unit,
)
from qmint.proofs import assumption_check as ac
from qmint.proofs import finite_size as fs
from qmint.proofs.finite_size import FiniteSizeBoundEvaluator
from qmint.proofs.registry import default_registry
from qmint.proofs.reproduce import kent_fig5_beta_max, kent_p_noqub, reproduce

S2 = "s_money_kent_2022_realistic"
D1 = "schiansky_payment_2023"
LN10 = math.log(10)


def _ev(protocol, game, axis, params, calibration=None):
    return FiniteSizeBoundEvaluator().evaluate(
        BoundRequest(protocol_id=protocol, game_id=game, axis=axis, parameters=params, calibration=calibration)
    )


# ------------------------------ published numbers ------------------------------


def test_every_published_example_reproduces():
    rep = reproduce()
    bad = [r for r in rep["rows"] if not r["agrees"]]
    assert not bad, bad


def test_kent_robustness_e_minus_1052():
    ln = fs.kent_ln_rob({"N": 4e7, "P_det": 0.019, "gamma_det": 0.018})
    assert ln == pytest.approx(-1052.63, abs=0.01)


def test_kent_p_noqub_and_lambda_limits():
    assert kent_p_noqub(0.09) == pytest.approx(3.8e-3, abs=5e-5)
    # Table 5: 0 < lambda < (1/2)(1 - O(theta)) < (1/2)(1 - 1/sqrt 2)
    for th in (1e-6, 0.1, 0.5, 0.78):
        lam = fs.kent_lambda(th, 1e-3)
        assert 0 < lam < 0.5 * (1 - fs.kent_overlap(th)) < 0.5 * (1 - 1 / math.sqrt(2))


@pytest.mark.parametrize("theta,e,paper", [(10, 0.058, 6e-6), (5, 0.03, 2.3e-4)])
def test_fig5_beta_max(theta, e, paper):
    best = kent_fig5_beta_max(theta, e, kent_p_noqub(0.09))
    assert best is not None
    assert best["beta_PB"] == pytest.approx(paper, rel=0.2)


def test_fig5_point_bounds_through_evaluator(kent_fig5_params):
    p = kent_fig5_params
    unf = _ev(S2, "S2", "epsilon_unf", p)
    cor = _ev(S2, "S2", "epsilon_cor", p)
    rob = _ev(S2, "S2", "epsilon_rob", p)
    priv = _ev(S2, "S2", "epsilon_priv", p)
    assert unf.log10_value <= -9 and cor.log10_value <= -9 and rob.log10_value <= -9
    assert rob.value is None and rob.log10_value * LN10 == pytest.approx(-1052.63, abs=0.01)
    assert priv.value == pytest.approx(1e-10)
    for r in (unf, cor, rob, priv):
        assert r.status == ProofStatus.PUBLISHED_REPRODUCED and r.evidence_kind == EvidenceKind.PUBLISHED_THEOREM
        assert r.theorem_id.startswith("P-S2/")


def test_paper_experimental_tuple_is_out_of_domain(kent_fig5_params):
    p = dict(kent_fig5_params, beta_PB=2.4e-3, beta_PS=3.6e-3, noise_source="published_kent_2022")
    r = _ev(S2, "S2", "epsilon_unf", p)
    assert r.value is None and r.log10_value is None and r.out_of_domain
    assert "f(" in r.notes or "beta_PS" in r.notes


@pytest.mark.parametrize(
    "change",
    [
        {"gamma_det": 0.02},  # Lemma 2 needs gamma_det < P_det
        {"theta": 0.0},  # Table 5: theta in (0, pi/4)
        {"beta_PB": 0.0},  # beta = 0 'is unsafe' (paper Discussion) and outside Table 2
        {"P_noqub": 0.0},  # Eq. 7: 0 < P_noqub
        {"nu_unf": 0.009},  # Eq. 7: nu_unf < 2 P_noqub
        {"gamma_err": 0.2},  # Eq. 7: gamma_err < lambda
    ],
)
def test_out_of_domain_has_no_value(kent_fig5_params, change):
    p = dict(kent_fig5_params, **change)
    axes = ["epsilon_rob"] if "gamma_det" in change else ["epsilon_unf"]
    for axis in axes:
        r = _ev(S2, "S2", axis, p)
        assert r.value is None and r.log10_value is None and r.out_of_domain, (change, r.notes)


def test_correctness_domain_eq4(kent_fig5_params):
    assert _ev(S2, "S2", "epsilon_cor", dict(kent_fig5_params, E=0.02)).value is None  # E < gamma_err/2
    assert _ev(S2, "S2", "epsilon_cor", dict(kent_fig5_params, E=0.07)).value is None  # E > gamma_err
    assert _ev(S2, "S2", "epsilon_cor", dict(kent_fig5_params, nu_cor=0.0095)).value is None  # nu_cor too big


def test_multi_site_theorem_2(kent_fig5_params):
    p1 = _ev(S2, "S2", "epsilon_unf", kent_fig5_params)
    pm = _ev(S2, "S2", "epsilon_unf", dict(kent_fig5_params, M=2, C=6))
    assert pm.log10_value == pytest.approx(p1.log10_value + math.log10(6), abs=1e-12)
    rob1 = _ev(S2, "S2", "epsilon_rob", kent_fig5_params)
    rob3 = _ev(S2, "S2", "epsilon_rob", dict(kent_fig5_params, M=3, C=28))
    assert rob3.log10_value == pytest.approx(rob1.log10_value + math.log10(3), abs=1e-9)
    priv = _ev(S2, "S2", "epsilon_priv", dict(kent_fig5_params, M=2, beta_E=0.01))
    assert priv.value == pytest.approx(((1.02) ** 2 - 1) / 4, rel=1e-12)
    assert _ev(S2, "S2", "epsilon_unf", dict(kent_fig5_params, M=2)).value is None  # C missing
    assert _ev(S2, "S2", "epsilon_unf", dict(kent_fig5_params, M=1, C=99)).value is not None  # C unused at M=1
    assert _ev(S2, "S2", "epsilon_unf", dict(kent_fig5_params, M=2, C=7)).value is None  # > 4*3/2 pairs


# ------------------------------ noise source / assumptions ------------------------------


@pytest.mark.parametrize("src", [None, "made_up_lab", "qiskit_noise_model"])
def test_unknown_noise_source_blocked(kent_fig5_params, src):
    p = dict(kent_fig5_params)
    p.pop("noise_source")
    if src:
        p["noise_source"] = src
    r = _ev(S2, "S2", "epsilon_unf", p)
    assert r.value is None and any(f.startswith("ASSUMPTION_MISSING:noise_source") for f in r.failed_assumptions)


def test_missing_table6_declaration_blocked(kent_fig5_params):
    p = dict(kent_fig5_params, declared_assumptions=[d for d in kent_fig5_params["declared_assumptions"]
                                                     if d != "table6_E_no_side_channels"])
    r = _ev(S2, "S2", "epsilon_unf", p)
    assert r.value is None and "ASSUMPTION_MISSING:table6_E_no_side_channels" in r.failed_assumptions


def test_missing_multiphoton_bound_blocked(kent_fig5_params):
    p = dict(kent_fig5_params)
    p.pop("P_noqub")
    r = _ev(S2, "S2", "epsilon_unf", p)
    assert r.value is None and "PARAMETER_MISSING:P_noqub" in r.failed_assumptions


def _cal(family="kent_2022", origin=EvidenceKind.PUBLISHED_AGGREGATE, **ivs):
    return CalibrationRecord(
        calibration_id="cal-test", device_id="dev", experiment_family=family, data_origin=origin,
        dataset_sha256="0" * 64 if origin == EvidenceKind.PHOTON_EXPERIMENT else None, n_events=1000,
        confidence_level=0.95, interval_method="clopper_pearson", independence_assumptions=["iid_rounds"],
        **{k: Interval(lo=lo, hi=hi, unit=Unit.FRACTION) for k, (lo, hi) in ivs.items()},
    )


@pytest.mark.parametrize(
    "family,origin",
    [("schiansky_2023", EvidenceKind.PUBLISHED_AGGREGATE), ("synthetic", EvidenceKind.SYNTHETIC),
     ("kent_2022", EvidenceKind.SYNTHETIC)],
)
def test_calibration_family_and_origin_must_match(kent_fig5_params, family, origin):
    p = dict(kent_fig5_params)
    p.pop("noise_source")
    r = _ev(S2, "S2", "epsilon_cor", p, calibration=_cal(family, origin, qber_interval=(0.055, 0.058)))
    assert r.value is None and r.failed_assumptions


def test_calibration_interval_propagates_worst_endpoint(kent_fig5_params):
    p = dict(kent_fig5_params)
    p.pop("noise_source")
    p.pop("E")
    cal = _cal(qber_interval=(0.0500, 0.0580))
    r = _ev(S2, "S2", "epsilon_cor", p, calibration=cal)
    at_hi = _ev(S2, "S2", "epsilon_cor", dict(kent_fig5_params, E=0.058))
    assert r.log10_value == pytest.approx(at_hi.log10_value, abs=1e-12)
    assert "worst-case" in r.notes


def test_interval_partially_outside_domain_is_refused(kent_fig5_params):
    # E in [0.02, 0.058]: lower part violates E > gamma_err/2 -> whole interval refused
    r = _ev(S2, "S2", "epsilon_cor", dict(kent_fig5_params, E={"lo": 0.02, "hi": 0.058}))
    assert r.value is None and r.out_of_domain


def test_hull_when_both_calibration_and_scalar_given(kent_fig5_params):
    p = dict(kent_fig5_params, E=0.050)
    p.pop("noise_source")
    r = _ev(S2, "S2", "epsilon_cor", p, calibration=_cal(qber_interval=(0.056, 0.058)))
    ref = _ev(S2, "S2", "epsilon_cor", dict(kent_fig5_params, E=0.058))
    assert r.log10_value == pytest.approx(ref.log10_value, abs=1e-12)


# ------------------------------ monotonicity directions (tested) ------------------------------


def _directions():
    out = []
    for c in default_registry().claims:
        for b in c.bounds:
            for param, direction in b.monotonicity.items():
                out.append((b.bound_id, param, direction))
    return out


@pytest.mark.parametrize("bound_id,param,direction", _directions())
def test_documented_monotonicity_is_true(bound_id, param, direction, kent_fig5_params, d1_params):
    keys, domain, ln_bound = fs.FORMULAS[bound_id]
    base = dict(d1_params if bound_id.startswith("P-D1") else kent_fig5_params)
    base.setdefault("M", 1)
    x0 = base[param]
    lo, hi = x0 * 0.995, x0 * 1.005
    p_lo, p_hi = dict(base, **{param: lo}), dict(base, **{param: hi})
    assert not domain(p_lo) and not domain(p_hi)
    if bound_id == "P-S2/unf" and param != "P_noqub":
        # at the fixture the exp(-N f) term is ~1e-30 of the total, so test the term itself: -N f
        v_lo, v_hi = (-p["N"] * fs.kent_f(p["gamma_err"], p["beta_PS"], p["beta_PB"], p["theta"], p["nu_unf"],
                                          p["gamma_det"]) for p in (p_lo, p_hi))
        assert ln_bound(p_hi if direction == "increasing" else p_lo) >= ln_bound(p_lo if direction == "increasing" else p_hi)
    else:
        v_lo, v_hi = ln_bound(p_lo), ln_bound(p_hi)
    assert (v_hi > v_lo) if direction == "increasing" else (v_lo > v_hi), (bound_id, param)


@pytest.mark.parametrize("bound_id", ["P-D1/unf", "P-D1/cor"])
def test_domain_only_parameters_do_not_change_value(bound_id, d1_params):
    _, spec = default_registry().bound(bound_id)
    _, _, ln_bound = fs.FORMULAS[bound_id]
    for param in spec.domain_only:
        assert ln_bound(dict(d1_params, **{param: d1_params[param] * 0.99})) == ln_bound(d1_params)


@pytest.mark.parametrize("bound_id", [b for b in fs.FORMULAS if b.startswith("P-S2")])
def test_worst_corner_equals_documented_endpoint(bound_id, kent_fig5_params):
    _, spec = default_registry().bound(bound_id)
    keys, domain, ln_bound = fs.FORMULAS[bound_id]
    p = dict(kent_fig5_params)
    for k in spec.monotonicity:
        p[k] = {"lo": p[k] * 0.99, "hi": p[k] * 1.01}
    point = dict(ac.worst_case({k: p[k] for k in keys}, spec.monotonicity), M=1)
    brute = max(ln_bound({**point, **c}) for c in ac.corners(p, tuple(spec.monotonicity)))
    assert ln_bound(point) == pytest.approx(brute, abs=1e-12)


def test_mutation_flipped_direction_is_optimistic(kent_fig5_params):
    """Mutation test: reversing a documented direction picks a smaller (optimistic) value."""
    _, spec = default_registry().bound("P-S2/cor")
    keys, _, ln_bound = fs.FORMULAS["P-S2/cor"]
    p = dict(kent_fig5_params, E={"lo": 0.0560, "hi": 0.0580})
    good = ln_bound(dict(ac.worst_case({k: p[k] for k in keys}, spec.monotonicity), M=1))
    flipped = {k: ("decreasing" if v == "increasing" else "increasing") for k, v in spec.monotonicity.items()}
    bad = ln_bound(dict(ac.worst_case({k: p[k] for k in keys}, flipped), M=1))
    assert bad < good


def test_interval_without_direction_refused(kent_fig5_params):
    r = _ev(S2, "S2", "epsilon_unf", dict(kent_fig5_params, nu_unf={"lo": 3.85e-3, "hi": 3.95e-3}))
    assert r.value is None and "monotonicity" in r.notes


# ------------------------------ D1 ------------------------------


def test_d1_published_pd(d1_params):
    r = _ev(D1, "D1", "epsilon_unf", d1_params)
    assert r.value == pytest.approx(5.911e-45, rel=1e-3)
    assert r.status == ProofStatus.NUMERICALLY_SUPPORTED and r.evidence_kind == EvidenceKind.PUBLISHED_AGGREGATE
    assert "de Finetti" in r.notes


def test_d1_correctness_and_no_privacy(d1_params):
    cor = _ev(D1, "D1", "epsilon_cor", d1_params)
    m = (4 + 2 * math.sqrt(2)) * 0.03278 + 0.224
    assert cor.log10_value * LN10 == pytest.approx(-(0.031**2 / 3) * m * 4.2e6, rel=1e-12)
    priv = _ev(D1, "D1", "epsilon_priv", d1_params)
    assert priv.value is None and priv.log10_value is None and priv.status == ProofStatus.UNSUPPORTED


@pytest.mark.parametrize("change", [{"delta_d": 0.1}, {"delta_h": 1.5}, {"l_h": 0.4}, {"merchants": 3}, {"p_m": 1.0}])
def test_d1_out_of_domain(d1_params, change):
    r = _ev(D1, "D1", "epsilon_unf", dict(d1_params, **change))
    assert r.value is None and r.log10_value is None


def test_d1_calibration_family(d1_params):
    p = dict(d1_params)
    p.pop("noise_source")
    for k in ("e_h", "l_h", "p_m"):
        p.pop(k)
    cal = _cal("schiansky_2023", EvidenceKind.PHOTON_EXPERIMENT, qber_interval=(0.0326, 0.0330),
               loss_interval=(0.209, 0.239), multiphoton_interval=(0.0574, 0.0630))
    r = _ev(D1, "D1", "epsilon_unf", p, calibration=cal)
    assert r.value == pytest.approx(math.exp(-(0.01**2 / 2) * 0.5 * (1 - 0.0630 / 2) * 4.2e6), rel=1e-9)
    wrong = _ev(D1, "D1", "epsilon_unf", p, calibration=_cal("kent_2022", qber_interval=(0.0326, 0.0330)))
    assert wrong.value is None


@pytest.mark.parametrize("game", ["W1", "W1_CV", "S1", "W2", "A1", "C1"])
def test_finite_size_evaluator_refuses_other_games(game):
    proto = {"W1": "wiesner_ideal", "W1_CV": "wiesner_ideal", "S1": "s_money_kent_2022_ideal_2site",
             "W2": "wiesner_noisy", "A1": "gavinsky_anon_2025", "C1": "classical_h0_bearer"}[game]
    for axis in SecurityAxis:
        r = _ev(proto, game, axis, {"N": 100})
        assert r.value is None and r.log10_value is None


def test_corners_cover_box():
    cs = list(ac.corners({"a": {"lo": 0, "hi": 1}, "b": 2.0, "c": {"lo": 3, "hi": 4}}, ("a", "b", "c")))
    assert len(cs) == 4 and {(c["a"], c["c"]) for c in cs} == set(itertools.product((0.0, 1.0), (3.0, 4.0)))
