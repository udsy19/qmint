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

H = ["b" * 64]
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
                      "qmint.proofs.results", "math"):
        assert forbidden not in mods


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


def _sdp_cert(sdp, bound=0.7500001):
    return SecurityCertificate(
        protocol_id="wiesner_noisy", game_id="W2", security_model_id="w2_threshold_n1",
        parameters={"sdp_certificate": sdp}, upper_bounds=UpperBounds(epsilon_unf=bound),
        targets=Targets(epsilon_unf=0.76), assumptions_met=True, proof_reference="audits/SDP_DERIVATION.md",
        evidence_kind=EvidenceKind.CERTIFIED_NUMERIC, reason="x", evidence_hashes=H)


GOOD_SDP = {
    "solver": "clarabel", "game_definition_sha256": "c" * 64, "primal_objective": 0.7499999,
    "dual_objective": 0.75, "dual_min_eigenvalue": -2e-9, "eigenvalue_error_bound": 1e-10,
    "dual_variable_dim": 2, "certified_bound": 0.7500001,
}


def test_sdp_certificate_with_residual_accounting_accepted():
    assert CHK.check(_sdp_cert(GOOD_SDP)).proof_check_status == CertificateStatus.CERTIFIED


@pytest.mark.parametrize("drop", ["dual_min_eigenvalue", "eigenvalue_error_bound", "dual_variable_dim", "certified_bound"])
def test_sdp_without_residual_fields_rejected(drop):
    sdp = {k: v for k, v in GOOD_SDP.items() if k != drop}
    assert CHK.check(_sdp_cert(sdp)).proof_check_status == CertificateStatus.UNCERTIFIED


def test_sdp_padding_too_small_rejected():
    sdp = dict(GOOD_SDP, dual_min_eigenvalue=-1e-4)  # needs 0.75 + 2e-4 padding
    out = CHK.check(_sdp_cert(sdp))
    assert out.proof_check_status == CertificateStatus.UNCERTIFIED and "padding" in out.reason


def test_sdp_reported_bound_below_certified_rejected():
    assert CHK.check(_sdp_cert(GOOD_SDP, bound=0.75)).proof_check_status == CertificateStatus.UNCERTIFIED


def test_sdp_numerical_only_rejected():
    c = SecurityCertificate.model_validate(dict(_sdp_cert(GOOD_SDP).model_dump(), evidence_kind=EvidenceKind.NUMERICAL_SDP))
    assert CHK.check(c).proof_check_status == CertificateStatus.UNCERTIFIED
