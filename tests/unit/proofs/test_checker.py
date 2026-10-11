from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

from qmint.core.contracts import (
    CertificateStatus,
    EvidenceKind,
    GameId,
    SecurityCertificate,
    Targets,
    UpperBounds,
)
from qmint.core.interfaces import IndependentChecker
from qmint.proofs import checker as checker_mod
from qmint.proofs import finite_size, ideal_bounds
from qmint.proofs.checker import IndependentProofChecker
from qmint.proofs.engine import ProofEngine
from qmint.proofs.registry import default_registry

H = ["b" * 64]
REG = default_registry()
CHK = IndependentProofChecker()
ENG = ProofEngine()


def _w1_cert(decl, n=73, **over):
    data = dict(
        protocol_id="wiesner_ideal", game_id=GameId.W1, security_model_id="mvw",
        parameters={"n": n, "declared_assumptions": decl("P-W1")},
        upper_bounds=UpperBounds(epsilon_unf=0.75**n), targets=Targets(epsilon_unf=1e-9),
        assumptions_met=True, proof_reference="P-W1", evidence_kind=EvidenceKind.PUBLISHED_THEOREM,
        reason="draft", evidence_hashes=H,
    )
    data.update(over)
    return SecurityCertificate(**data)


def _s2_draft(params, targets=None):
    return ENG.draft_certificate(
        "s_money_kent_2022_realistic", GameId.S2, params,
        targets or Targets(epsilon_unf=1e-9, epsilon_cor=1e-9, epsilon_rob=1e-9),
        security_model_id="kent2022", evidence_hashes=H,
    )


def test_implements_frozen_interface():
    assert isinstance(CHK, IndependentChecker)


def test_checker_is_a_separate_code_path():
    """The checker must not import the evaluator modules or their helpers."""
    tree = ast.parse(Path(checker_mod.__file__).read_text(encoding="utf-8"))
    mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    }
    for forbidden in ("qmint.proofs.ideal_bounds", "qmint.proofs.finite_size", "qmint.proofs.assumption_check",
                      "qmint.proofs.results", "math", "qmint.attacks"):
        assert forbidden not in mods
    sdp_tree = ast.parse(Path(checker_mod.sdp_exact.__file__).read_text(encoding="utf-8"))
    sdp_mods = {n.module for n in ast.walk(sdp_tree) if isinstance(n, ast.ImportFrom)} | {
        a.name for n in ast.walk(sdp_tree) if isinstance(n, ast.Import) for a in n.names}
    for forbidden in ("qmint.attacks", "qmint.attacks.certify", "qmint.proofs.ideal_bounds", "qmint.proofs.finite_size"):
        assert forbidden not in sdp_mods


def test_certifies_correct_w1(decl):
    out = CHK.check(_w1_cert(decl))
    assert out.proof_check_status == CertificateStatus.CERTIFIED and out.checker_id == CHK.checker_id


def test_certifies_engine_drafts_for_every_ideal_game(decl):
    for game, proto, key, claim, n in (
        ("W1", "wiesner_ideal", "n", "P-W1", 73),
        ("W1_CV", "wiesner_ideal", "n", "P-W1CV", 273),
        ("S1", "s_money_kent_2022_ideal_2site", "N", "P-S1", 131),
    ):
        d = ENG.draft_certificate(proto, game, {key: n, "declared_assumptions": decl(claim)}, Targets(epsilon_unf=1e-9),
                                  security_model_id="m", evidence_hashes=H)
        assert CHK.check(d).proof_check_status == CertificateStatus.CERTIFIED, game
        short = ENG.draft_certificate(proto, game, {key: n - 1, "declared_assumptions": decl(claim)},
                                      Targets(epsilon_unf=1e-9), security_model_id="m", evidence_hashes=H)
        assert CHK.check(short).proof_check_status == CertificateStatus.UNCERTIFIED, game


def test_certifies_s2_fig5_point(kent_fig5_params):
    out = CHK.check(_s2_draft(kent_fig5_params, Targets(epsilon_unf=1e-9, epsilon_cor=1e-9, epsilon_rob=1e-9,
                                                         epsilon_priv=1e-9)))
    assert out.proof_check_status == CertificateStatus.CERTIFIED, out.reason


def test_rejects_optimistic_parameters(decl):
    # bound computed for n=80 but the certificate's parameters say n=73
    out = CHK.check(_w1_cert(decl, n=73, upper_bounds=UpperBounds(epsilon_unf=0.75**80)))
    assert out.proof_check_status == CertificateStatus.UNCERTIFIED and "BELOW" in out.reason


def test_rejects_optimistic_interval_endpoint(kent_fig5_params):
    """Certificate claims E in [0.050, 0.058] but reports the bound at the optimistic endpoint 0.050."""
    good = _s2_draft(dict(kent_fig5_params, E=0.050), Targets(epsilon_cor=1e-9))
    bad = good.model_dump()
    bad["parameters"]["E"] = {"lo": 0.050, "hi": 0.058}
    out = CHK.check(SecurityCertificate.model_validate(bad))
    assert out.proof_check_status == CertificateStatus.UNCERTIFIED and "epsilon_cor" in out.reason


def test_rejects_invalid_inward_rounding(decl):
    true = 0.75**73
    rounded_down = float(f"{true:.1e}") if float(f"{true:.1e}") < true else true * 0.9
    out = CHK.check(_w1_cert(decl, upper_bounds=UpperBounds(epsilon_unf=rounded_down)))
    assert out.proof_check_status == CertificateStatus.UNCERTIFIED and "BELOW" in out.reason


def test_accepts_small_outward_rounding(decl):
    out = CHK.check(_w1_cert(decl, upper_bounds=UpperBounds(epsilon_unf=0.75**73 * 1.01)))
    assert out.proof_check_status == CertificateStatus.CERTIFIED


def test_rejects_reversed_epsilon_direction(decl):
    """1 - eps (an acceptance probability) reported as eps with a matching reversed target."""
    eps = 0.75**73
    out = CHK.check(_w1_cert(decl, upper_bounds=UpperBounds(epsilon_unf=1 - eps), targets=Targets(epsilon_unf=1 - 1e-12)))
    assert out.proof_check_status == CertificateStatus.UNCERTIFIED and "does not match" in out.reason


def test_rejects_log_and_linear_disagreement(decl):
    out = CHK.check(_w1_cert(decl, log10_upper_bounds={"epsilon_unf": 73 * math.log10(0.75) - 3}))
    assert out.proof_check_status == CertificateStatus.UNCERTIFIED


def test_missing_privacy_theorem_never_becomes_zero(decl):
    zero = _w1_cert(decl, upper_bounds=UpperBounds(epsilon_unf=0.75**73, epsilon_priv=0.0),
                    targets=Targets(epsilon_unf=1e-9, epsilon_priv=1e-6))
    out = CHK.check(zero)
    assert out.proof_check_status == CertificateStatus.UNCERTIFIED and "epsilon_priv" in out.reason
    # engine draft: privacy target with no theorem -> bound stays None, assumptions not met
    d = ENG.draft_certificate("wiesner_ideal", "W1", {"n": 73, "declared_assumptions": decl("P-W1")},
                              Targets(epsilon_unf=1e-9, epsilon_priv=1e-6), security_model_id="m", evidence_hashes=H)
    assert d.upper_bounds.epsilon_priv is None and not d.assumptions_met
    assert CHK.check(d).proof_check_status == CertificateStatus.UNCERTIFIED


def test_d1_is_never_certified(d1_params):
    d = ENG.draft_certificate("schiansky_payment_2023", "D1", d1_params, Targets(epsilon_unf=1e-40),
                              security_model_id="m", evidence_hashes=H)
    assert d.upper_bounds.epsilon_unf == pytest.approx(5.911e-45, rel=1e-3)
    forced = SecurityCertificate.model_validate(dict(d.model_dump(), evidence_kind=EvidenceKind.PUBLISHED_THEOREM))
    for c in (d, forced):
        out = CHK.check(c)
        assert out.proof_check_status == CertificateStatus.UNCERTIFIED and "D1" in out.reason


def test_w1_formula_on_w2_certificate_rejected(decl):
    c = SecurityCertificate(
        protocol_id="wiesner_noisy", game_id="W2", security_model_id="m", parameters={"n": 73},
        upper_bounds=UpperBounds(epsilon_unf=0.75**73), targets=Targets(epsilon_unf=1e-9), assumptions_met=True,
        proof_reference="P-W1", evidence_kind=EvidenceKind.PUBLISHED_THEOREM, reason="x", evidence_hashes=H)
    out = CHK.check(c)
    assert out.proof_check_status == CertificateStatus.UNCERTIFIED and "W2" in out.reason


def test_noise_parameter_in_ideal_certificate_rejected(decl):
    c = _w1_cert(decl, parameters={"n": 73, "error_threshold": 0.05, "declared_assumptions": decl("P-W1")})
    assert CHK.check(c).proof_check_status == CertificateStatus.UNCERTIFIED


@pytest.mark.parametrize("extra", [
    {"threshold": 5}, {"noise": {"kind": "depolarizing", "p": 0.05}}, {"qber": 0.0}, {"max_errors": 0},
    {"P_det": 0.019}, {"e_h": 0.01}, {"error_threshold": 0}, {"N": 73},
])
def test_ideal_allowlist_refuses_any_other_parameter(decl, extra):
    """M-D1: allowlist, not a denylist -- even zero-valued or unknown keys leave the ideal game."""
    c = _w1_cert(decl, parameters={"n": 73, "declared_assumptions": decl("P-W1"), **extra})
    out = CHK.check(c)
    assert out.proof_check_status == CertificateStatus.UNCERTIFIED and "allowlist" in out.reason, out.reason


def test_ideal_allowlist_accepts_ideal_control_keys(decl):
    c = _w1_cert(decl, parameters={"n": 73, "declared_assumptions": decl("P-W1"), "verifier": "exact",
                                   "verification_oracle_queries": 0})
    assert CHK.check(c).proof_check_status == CertificateStatus.CERTIFIED


@pytest.mark.parametrize(("ref", "ok"), [("P-W1", True), ("P-W1/unf", True), ("P-W1CV", False), ("P-W1/", False),
                                         ("P-W1CV/unf", False), ("p-w1", False)])
def test_proof_reference_exact_match(decl, ref, ok):
    """M-D3: no prefix match (P-W1 vs P-W1CV)."""
    out = CHK.check(_w1_cert(decl, proof_reference=ref))
    assert (out.proof_check_status == CertificateStatus.CERTIFIED) is ok, out.reason


@pytest.mark.parametrize(
    "over",
    [
        {"assumptions_met": False},
        {"failed_assumptions": ["x"]},
        {"evidence_hashes": []},
        {"proof_reference": "P-S1"},
        {"proof_reference": None},
        {"evidence_kind": EvidenceKind.MONTE_CARLO},
        {"evidence_kind": EvidenceKind.NUMERICAL_SDP},
        {"targets": Targets()},
    ],
)
def test_rejects_missing_provenance(decl, over):
    assert CHK.check(_w1_cert(decl, **over)).proof_check_status == CertificateStatus.UNCERTIFIED


def test_rejects_undeclared_hypotheses(decl):
    c = _w1_cert(decl, parameters={"n": 73, "declared_assumptions": ["exact_projective_verifier"]})
    out = CHK.check(c)
    assert out.proof_check_status == CertificateStatus.UNCERTIFIED and "undeclared" in out.reason


def test_rejects_s2_with_experimental_bias(kent_fig5_params):
    d = _s2_draft(dict(kent_fig5_params, beta_PB=2.4e-3, beta_PS=3.6e-3), Targets(epsilon_unf=1e-9))
    assert CHK.check(d).proof_check_status == CertificateStatus.UNCERTIFIED
    # even if a tamperer injects a value and flips assumptions_met
    forged = SecurityCertificate.model_validate(dict(
        d.model_dump(), upper_bounds={"epsilon_unf": 1e-12}, assumptions_met=True, failed_assumptions=[],
        evidence_kind=EvidenceKind.PUBLISHED_THEOREM, proof_reference="P-S2"))
    out = CHK.check(forged)
    assert out.proof_check_status == CertificateStatus.UNCERTIFIED and "refused" in out.reason


# ------------------------------ mutation tests ------------------------------


def test_mutated_ideal_base_is_caught(decl, monkeypatch):
    """If the evaluator's W1 base were silently replaced by a smaller one, the checker catches it."""
    monkeypatch.setitem(ideal_bounds.IDEAL_BASES, GameId.W1, (0.70, "P-W1/unf", "n"))
    d = ENG.draft_certificate("wiesner_ideal", "W1", {"n": 60, "declared_assumptions": decl("P-W1")},
                              Targets(epsilon_unf=1e-9), security_model_id="m", evidence_hashes=H)
    assert d.upper_bounds.epsilon_unf < 1e-9  # the mutant claims success...
    assert CHK.check(d).proof_check_status == CertificateStatus.UNCERTIFIED  # ...the checker refuses


def test_mutated_w1cv_using_w1_base_is_caught(decl, monkeypatch):
    monkeypatch.setitem(ideal_bounds.IDEAL_BASES, GameId.W1_CV, (0.75, "P-W1CV/unf", "n"))
    d = ENG.draft_certificate("wiesner_ideal", "W1_CV", {"n": 73, "declared_assumptions": decl("P-W1CV")},
                              Targets(epsilon_unf=1e-9), security_model_id="m", evidence_hashes=H)
    assert CHK.check(d).proof_check_status == CertificateStatus.UNCERTIFIED


@pytest.mark.parametrize(
    "name,mutant",
    [
        ("kent_ln_unf", lambda p: 2 * finite_size._lse(-(p["P_noqub"] * p["N"] / 3) * (p["nu_unf"] / p["P_noqub"] - 1) ** 2, -p["N"] * finite_size.kent_f(p["gamma_err"], p["beta_PS"], p["beta_PB"], p["theta"], p["nu_unf"], p["gamma_det"]))),
        ("kent_ln_cor", lambda p: -(p["E"] * p["nu_cor"] * p["N"] / 3) * (p["gamma_err"] / p["E"] - 1) ** 2),  # drops a term
        ("kent_ln_rob", lambda p: -(p["P_det"] * p["N"]) * (1 - p["gamma_det"] / p["P_det"]) ** 2),  # wrong factor 1/2
    ],
)
def test_mutated_finite_size_formula_is_caught(kent_fig5_params, monkeypatch, name, mutant):
    keys, dom, _ = finite_size.FORMULAS[{"kent_ln_unf": "P-S2/unf", "kent_ln_cor": "P-S2/cor", "kent_ln_rob": "P-S2/rob"}[name]]
    bid = {"kent_ln_unf": "P-S2/unf", "kent_ln_cor": "P-S2/cor", "kent_ln_rob": "P-S2/rob"}[name]
    monkeypatch.setitem(finite_size.FORMULAS, bid, (keys, dom, mutant))
    out = CHK.check(_s2_draft(kent_fig5_params))
    assert out.proof_check_status == CertificateStatus.UNCERTIFIED, name


def test_mutated_monotonicity_direction_is_caught(kent_fig5_params, monkeypatch):
    """Evaluator picks the optimistic endpoint (flipped direction); the brute-force checker refuses."""
    from qmint.proofs import assumption_check as ac

    real = ac.worst_case

    def flipped(params, mono, domain_only=()):
        return real(params, {k: ("decreasing" if v == "increasing" else "increasing") for k, v in mono.items()},
                    domain_only)

    monkeypatch.setattr(ac, "worst_case", flipped)
    d = _s2_draft(dict(kent_fig5_params, E={"lo": 0.050, "hi": 0.058}), Targets(epsilon_cor=1e-9))
    assert CHK.check(d).proof_check_status == CertificateStatus.UNCERTIFIED


# ------------------------------ CERTIFIED_NUMERIC SDP ------------------------------
# Numbers below are lane C's published evidence (handoffs/C-C1-evidence.json, "certified" blocks).

C_W1 = {
    1: {"solver": "SCS", "n": 1, "dual_objective": 0.7500000000000002, "delta_shift": 1.8189894035458565e-12,
        "certified_bound": 0.750000000003638, "certified_bound_exact": "206158430209/274877906944"},
    2: {"solver": "SCS", "n": 2, "dual_objective": 0.5624999999999998, "delta_shift": 1.8189894035458565e-12,
        "certified_bound": 0.562500000007276, "certified_bound_exact": "77309411329/137438953472"},
}
C_W1_CLARABEL_N1 = {"solver": "CLARABEL", "n": 1, "dual_objective": 0.7499999996197124,
                    "delta_shift": 3.992681740783155e-10, "certified_bound": 0.7500000004183676,
                    "certified_bound_exact": "206158430323/274877906944"}
# lane C did not export delta for W1_CV; (certified - dual)/8 = 1.837e-11 is used
C_W1CV = {"solver": "SCS+Fraction LDL", "n": 1, "dual_objective": 0.9267766953948254, "delta_shift": 1.8e-11,
          "certified_bound": 0.9267766955417756}


_SDP_DECL = {"W1": "P-W1", "W1_CV": "P-W1CV", "W2": "P-W2"}


def _sdp_cert(sdp, game="W1", bound=None, target=0.76, proof_reference="P-W2/sdp", **extra):
    cb = sdp.get("certified_bound", 0.75)
    params = {"n": sdp.get("n", 1), "sdp_certificate": sdp,
              "declared_assumptions": list(REG.claim(_SDP_DECL[game]).required_declarations), **extra}
    return SecurityCertificate(
        protocol_id="wiesner_ideal" if game in ("W1", "W1_CV") else "wiesner_noisy", game_id=game,
        security_model_id="w1_choi_sdp", parameters=params,
        upper_bounds=UpperBounds(epsilon_unf=bound if bound is not None else cb), targets=Targets(epsilon_unf=target),
        assumptions_met=True, proof_reference=proof_reference,
        evidence_kind=EvidenceKind.CERTIFIED_NUMERIC, reason="x", evidence_hashes=H)


@pytest.mark.parametrize(("game", "ref"), [("W1", "P-W1"), ("W1", "P-W2/sdp"), ("W1_CV", "P-W1CV")])
def test_sdp_accepts_exact_references(game, ref):
    sdp = C_W1[1] if game == "W1" else C_W1CV
    out = CHK.check(_sdp_cert(sdp, game=game, target=0.93, proof_reference=ref))
    assert out.proof_check_status == CertificateStatus.CERTIFIED, out.reason


@pytest.mark.parametrize(("kw", "why"), [
    ({"proof_reference": "P-W1CV"}, "proof_reference"),
    ({"proof_reference": "P-W2/sdp/extra"}, "proof_reference"),
    ({"proof_reference": "audits/SDP_DERIVATION.md"}, "proof_reference"),
    ({"qber": 0.01}, "allowlist"),
    ({"loss": 0.0}, "allowlist"),
    ({"verifier": "threshold"}, "exact verifier"),
    ({"n": 2}, "must equal sdp_certificate.n"),
    ({"declared_assumptions": []}, "undeclared"),
])
def test_sdp_path_applies_model_gates(kw, why):
    """M-D2: the CERTIFIED_NUMERIC path runs the same gates as the published-theorem path."""
    ref = kw.pop("proof_reference", "P-W2/sdp")
    out = CHK.check(_sdp_cert(C_W1[1], proof_reference=ref, **kw))
    assert out.proof_check_status == CertificateStatus.UNCERTIFIED and why in out.reason, out.reason


@pytest.mark.parametrize("sdp", [C_W1[1], C_W1[2], C_W1_CLARABEL_N1])
def test_lane_c_w1_certificates_reverified(sdp):
    out = CHK.check(_sdp_cert(sdp))
    assert out.proof_check_status == CertificateStatus.CERTIFIED, out.reason


def test_lane_c_w1cv_certificate_reverified():
    out = CHK.check(_sdp_cert(C_W1CV, game="W1_CV", target=0.93))
    assert out.proof_check_status == CertificateStatus.CERTIFIED, out.reason


def test_sdp_claim_below_true_optimum_rejected():
    """A 'certified' bound below the true optimum (3/4) cannot be confirmed."""
    bad = dict(C_W1[1], dual_objective=0.7, delta_shift=0.0, certified_bound=0.74, certified_bound_exact=None)
    out = CHK.check(_sdp_cert(bad))
    assert out.proof_check_status == CertificateStatus.UNCERTIFIED and "independently verified" in out.reason


def test_explicit_rational_dual_checked():
    good = dict(C_W1[1], dual_matrix_rational=[["3/8", "0"], ["0", "3/8"]], certified_bound=0.75,
                delta_shift=0.0, dual_objective=0.75, certified_bound_exact="3/4")
    assert CHK.check(_sdp_cert(good)).proof_check_status == CertificateStatus.CERTIFIED
    infeasible = dict(good, dual_matrix_rational=[["3/8", "0"], ["0", "37/100"]])
    out = CHK.check(_sdp_cert(infeasible))
    assert out.proof_check_status == CertificateStatus.UNCERTIFIED and "fails exact check" in out.reason


@pytest.mark.parametrize("drop", ["n", "delta_shift", "certified_bound", "dual_objective"])
def test_sdp_without_residual_fields_rejected(drop):
    sdp = {k: v for k, v in C_W1[1].items() if k != drop}
    assert CHK.check(_sdp_cert(sdp, bound=0.76)).proof_check_status == CertificateStatus.UNCERTIFIED


def test_sdp_padding_not_accounted_rejected():
    sdp = dict(C_W1_CLARABEL_N1, certified_bound=0.7500000000000001, certified_bound_exact=None)
    out = CHK.check(_sdp_cert(sdp))
    assert out.proof_check_status == CertificateStatus.UNCERTIFIED and "padding" in out.reason


def test_sdp_reported_bound_below_certified_rejected():
    assert CHK.check(_sdp_cert(C_W1[1], bound=0.75)).proof_check_status == CertificateStatus.UNCERTIFIED


def test_sdp_for_w2_refused_without_independent_path():
    out = CHK.check(_sdp_cert(dict(C_W1[1]), game="W2"))
    assert out.proof_check_status == CertificateStatus.UNCERTIFIED and "no independent" in out.reason


def test_sdp_n3_refused():
    out = CHK.check(_sdp_cert(dict(C_W1[2], n=3), target=0.5))
    assert out.proof_check_status == CertificateStatus.UNCERTIFIED


def test_sdp_numerical_only_rejected():
    c = SecurityCertificate.model_validate(dict(_sdp_cert(C_W1[1]).model_dump(), evidence_kind=EvidenceKind.NUMERICAL_SDP))
    assert CHK.check(c).proof_check_status == CertificateStatus.UNCERTIFIED
