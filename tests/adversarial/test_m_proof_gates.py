"""Lane M red team: lane D proof engine / independent checker gates (CRYPTOGRAPHIC_REVIEW)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qmint.core.contracts import (
    CalibrationRecord,
    CertificateStatus,
    EvidenceKind,
    GameId,
    Interval,
    SecurityCertificate,
    Targets,
    Unit,
    UpperBounds,
)
from qmint.proofs.checker import IndependentProofChecker
from qmint.proofs.engine import ProofEngine
from qmint.proofs.registry import default_registry

H = ["a" * 64]
REG = default_registry()
ENGINE, CHECKER = ProofEngine(), IndependentProofChecker()
ROOT = Path(__file__).resolve().parents[2]


def _decl(cid: str) -> list[str]:
    return list(REG.claim(cid).required_declarations)


def _certify(protocol: str, game: str, params: dict, target: float = 1e-9, calibration=None) -> SecurityCertificate:
    draft = ENGINE.draft_certificate(protocol, game, params, Targets(epsilon_unf=target), security_model_id="m-redteam",
                                     evidence_hashes=H, calibration=calibration)
    return CHECKER.check(draft)


def _sdp_cert(params: dict, proof_reference: str) -> SecurityCertificate:
    sdp = {"solver": "redteam", "n": 1, "dual_objective": "0.75", "delta_shift": "0", "certified_bound": "0.75"}
    return SecurityCertificate(
        protocol_id="wiesner_ideal", game_id=GameId.W1, security_model_id="m-redteam",
        parameters={"n": 1, "sdp_certificate": sdp, **params}, upper_bounds=UpperBounds(epsilon_unf=0.75),
        targets=Targets(epsilon_unf=0.8), assumptions_met=True, proof_reference=proof_reference,
        evidence_kind=EvidenceKind.CERTIFIED_NUMERIC, reason="m-redteam", evidence_hashes=H)


# --------------------------------------------------------------- controls that must keep passing
def test_baselines_certify():
    assert _certify("wiesner_ideal", "W1", {"n": 73, "declared_assumptions": _decl("P-W1")}).proof_check_status == CertificateStatus.CERTIFIED
    assert _certify("s_money_kent_2022_ideal_2site", "S1",
                    {"N": 131, "declared_assumptions": _decl("P-S1")}).proof_check_status == CertificateStatus.CERTIFIED


def test_denylisted_noise_key_is_refused():
    c = _certify("wiesner_ideal", "W1", {"n": 73, "error_threshold": 2, "declared_assumptions": _decl("P-W1")})
    assert c.proof_check_status != CertificateStatus.CERTIFIED


def test_w1_bound_relabelled_as_w1cv_is_refused():
    d = ENGINE.draft_certificate("wiesner_ideal", "W1", {"n": 73, "declared_assumptions": _decl("P-W1")},
                                 Targets(epsilon_unf=1e-9), security_model_id="m", evidence_hashes=H)
    forged = SecurityCertificate.model_validate({**d.model_dump(), "game_id": "W1_CV"})
    assert CHECKER.check(forged).proof_check_status != CertificateStatus.CERTIFIED


def test_d1_is_never_certified():
    p = {"N": 4.2e6, "p_m": 0.0602, "delta_d": 0.01, "delta_h": 0.031, "e_h": 0.03278, "l_h": 0.224,
         "declared_assumptions": _decl("P-D1"), "noise_source": "published_schiansky_2023"}
    assert _certify("schiansky_payment_2023", "D1", p, target=1e-6).proof_check_status != CertificateStatus.CERTIFIED


@pytest.mark.parametrize(("n", "claimed"), [(1, "0.70"), (2, "0.375")])
def test_sdp_claim_below_true_optimum_is_refused(n, claimed):
    """Tampered SDP (e.g. the n=2 value 0.375 lane C reports for a missing W_pi) must not certify."""
    sdp = {"solver": "redteam", "n": n, "dual_objective": claimed, "delta_shift": "0", "certified_bound": claimed}
    c = SecurityCertificate(
        protocol_id="wiesner_ideal", game_id=GameId.W1, security_model_id="m", parameters={"n": n, "sdp_certificate": sdp},
        upper_bounds=UpperBounds(epsilon_unf=float(claimed)), targets=Targets(epsilon_unf=0.9), assumptions_met=True,
        proof_reference="P-W2/sdp", evidence_kind=EvidenceKind.CERTIFIED_NUMERIC, reason="m", evidence_hashes=H)
    assert CHECKER.check(c).proof_check_status != CertificateStatus.CERTIFIED


# --------------------------------------------------------------- M-D1: noise under an ideal bound
NOISY_IDEAL = [
    ("wiesner_ideal", "W1", "P-W1", {"n": 73, "threshold": 5}),
    ("wiesner_ideal", "W1", "P-W1", {"n": 73, "noise": {"kind": "depolarizing", "p": 0.05}}),
    ("wiesner_ideal", "W1", "P-W1", {"n": 73, "max_errors": 3, "qber": 0.03}),
    ("s_money_kent_2022_ideal_2site", "S1", "P-S1", {"N": 131, "gamma_det": 0.018, "P_det": 0.019}),
    ("s_money_kent_2022_ideal_2site", "S1", "P-S1", {"N": 131, "e_h": 0.0145, "l_h": 0.22}),
]


@pytest.mark.xfail(strict=True, reason="M-D1: ideal theorems certify requests carrying realistic noise/loss/threshold keys outside a 6-key denylist")
@pytest.mark.parametrize(("protocol", "game", "claim", "extra"), NOISY_IDEAL)
def test_ideal_bound_refuses_unknown_noise_parameters(protocol, game, claim, extra):
    c = _certify(protocol, game, {**extra, "declared_assumptions": _decl(claim)})
    assert c.proof_check_status != CertificateStatus.CERTIFIED


# --------------------------------------------------------------- M-D2: SDP path skips gates
@pytest.mark.xfail(strict=True, reason="M-D2: CERTIFIED_NUMERIC path skips the ideal-noise check")
def test_sdp_certificate_refuses_noise_threshold():
    assert CHECKER.check(_sdp_cert({"error_threshold": 1}, "P-W2/sdp")).proof_check_status != CertificateStatus.CERTIFIED


@pytest.mark.xfail(strict=True, reason="M-D2: CERTIFIED_NUMERIC path never checks the P-W1 required declarations")
def test_sdp_certificate_requires_declarations():
    assert CHECKER.check(_sdp_cert({}, "P-W2/sdp")).proof_check_status != CertificateStatus.CERTIFIED


@pytest.mark.xfail(strict=True, reason="M-D2: CERTIFIED_NUMERIC path accepts any non-empty proof_reference")
def test_sdp_certificate_requires_matching_proof_reference():
    cert = _sdp_cert({"declared_assumptions": _decl("P-W1")}, "P-S1")
    assert CHECKER.check(cert).proof_check_status != CertificateStatus.CERTIFIED


# --------------------------------------------------------------- M-D3: prefix match
@pytest.mark.xfail(strict=True, reason="M-D3: proof_reference check is startswith('P-W1'), so 'P-W1CV' passes for W1")
def test_w1_certificate_citing_w1cv_is_refused():
    d = ENGINE.draft_certificate("wiesner_ideal", "W1", {"n": 73, "declared_assumptions": _decl("P-W1")},
                                 Targets(epsilon_unf=1e-9), security_model_id="m", evidence_hashes=H)
    forged = SecurityCertificate.model_validate({**d.model_dump(), "proof_reference": "P-W1CV"})
    assert CHECKER.check(forged).proof_check_status != CertificateStatus.CERTIFIED


# --------------------------------------------------------------- M-D4: calibration poisoning
def _s2_params() -> dict:
    cert = json.loads((ROOT / "proofs/certificates/S2_fig5_theta10_E058_hypothetical.json").read_text())
    p = dict(cert["parameters"])
    p.pop("noise_source")
    return p


def _calib(**kw) -> CalibrationRecord:
    base = dict(calibration_id="m-poison", device_id="unknown", experiment_family="kent_2022",
                data_origin=EvidenceKind.PHOTON_EXPERIMENT, dataset_sha256="0" * 64, n_events=1,
                qber_interval=Interval(lo=0.0579, hi=0.0580, unit=Unit.FRACTION), confidence_level=0.95,
                interval_method="clopper_pearson", independence_assumptions=["iid"])
    base.update(kw)
    return CalibrationRecord(**base)


def test_poisoned_calibration_family_mismatch_is_refused():
    c = _certify("s_money_kent_2022_realistic", "S2", _s2_params(), calibration=_calib(experiment_family="schiansky_2023"))
    assert c.proof_check_status != CertificateStatus.CERTIFIED


@pytest.mark.xfail(strict=True, reason="M-D4: calibration with an unregistered dataset_sha256 (n_events=1) is accepted as PHOTON_EXPERIMENT")
def test_calibration_dataset_hash_must_be_registered():
    assert _certify("s_money_kent_2022_realistic", "S2", _s2_params(),
                    calibration=_calib()).proof_check_status != CertificateStatus.CERTIFIED


@pytest.mark.xfail(strict=True, reason="M-D4: calibration confidence_level is never checked (0.05 accepted)")
def test_calibration_confidence_floor():
    assert _certify("s_money_kent_2022_realistic", "S2", _s2_params(),
                    calibration=_calib(confidence_level=0.05)).proof_check_status != CertificateStatus.CERTIFIED
