"""T0: frozen-contract, schema-hash and secret-boundary tests (lead-owned, G0)."""

import json
import pickle
from pathlib import Path

import pytest
from pydantic import ValidationError

from qmint.core.contracts import (
    AttackResult,
    Basis,
    BoundResult,
    CalibrationRecord,
    CertificateStatus,
    EvidenceManifest,
    GameId,
    Interval,
    IssuerSecret,
    ProofStatus,
    ProtocolSpec,
    SecretBoundaryError,
    SecurityAxis,
    SecurityCertificate,
    SpacetimeNetwork,
    TokenRecord,
    TransactionTrace,
    Unit,
    check_protocol_game,
)
from qmint.core.serialization import canonical_hash, canonical_json, json_schemas

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "tests" / "fixtures" / "contracts"


def load(name):
    return json.loads((FIX / f"{name}.json").read_text())


@pytest.mark.parametrize(
    "name,model",
    [
        ("protocol_wiesner", ProtocolSpec),
        ("protocol_smoney_ideal", ProtocolSpec),
        ("token_wiesner", TokenRecord),
        ("certificate_placeholder", SecurityCertificate),
        ("calibration_synthetic", CalibrationRecord),
        ("network_two_site", SpacetimeNetwork),
        ("manifest_fixture", EvidenceManifest),
    ],
)
def test_fixtures_validate_and_roundtrip(name, model):
    obj = model.model_validate(load(name))
    again = model.model_validate(json.loads(canonical_json(obj)))
    assert canonical_hash(obj) == canonical_hash(again)


def test_schema_hashes_frozen():
    frozen = json.loads((ROOT / "schemas" / "v1" / "SCHEMA_HASHES.json").read_text())
    current = {k: canonical_hash(v) for k, v in json_schemas().items()}
    assert current == frozen, "contract changed without a versioned schema migration"


def test_certificate_defaults_uncertified_with_null_bounds():
    c = SecurityCertificate.model_validate(load("certificate_placeholder"))
    assert c.proof_check_status == CertificateStatus.UNCERTIFIED
    assert c.upper_bounds.epsilon_unf is None  # null, never zero


def test_certified_requires_bound_below_target():
    base = dict(
        protocol_id="wiesner_ideal", game_id="W1", security_model_id="m", reason="r",
        targets={"epsilon_unf": 1e-9}, assumptions_met=True, proof_reference="P-W1",
        checker_id="chk", evidence_kind="PUBLISHED_THEOREM", evidence_hashes=["a" * 64],
        proof_check_status="CERTIFIED",
    )
    with pytest.raises(ValidationError):
        SecurityCertificate(**base)  # missing bound
    with pytest.raises(ValidationError):
        SecurityCertificate(**base, upper_bounds={"epsilon_unf": 1e-6})  # bound > target
    with pytest.raises(ValidationError):
        SecurityCertificate(**{**base, "evidence_kind": "MONTE_CARLO"}, upper_bounds={"epsilon_unf": 1e-10})
    ok = SecurityCertificate(**base, upper_bounds={"epsilon_unf": 1e-10})
    assert ok.proof_check_status == CertificateStatus.CERTIFIED


def test_wrong_game_for_protocol_rejected():
    with pytest.raises(ValueError):
        check_protocol_game("s_money_kent_2022_realistic", GameId.W1)
    d = load("protocol_smoney_ideal") | {"adversary_game_id": "W1"}
    with pytest.raises(ValidationError):
        ProtocolSpec.model_validate(d)


def test_bound_result_cannot_smuggle_values():
    with pytest.raises(ValidationError):
        BoundResult(protocol_id="wiesner_noisy", game_id="W2", axis=SecurityAxis.UNFORGEABILITY,
                    value=0.0, status=ProofStatus.UNSUPPORTED, evidence_kind="UNCERTIFIED")
    with pytest.raises(ValidationError):
        BoundResult(protocol_id="wiesner_ideal", game_id="W1", axis=SecurityAxis.UNFORGEABILITY,
                    value=0.75, status=ProofStatus.PUBLISHED_REPRODUCED, evidence_kind="PUBLISHED_THEOREM",
                    failed_assumptions=["exact_projective_verifier"], theorem_id="P-W1")
    r = BoundResult(protocol_id="wiesner_noisy", game_id="W2", axis=SecurityAxis.UNFORGEABILITY,
                    status=ProofStatus.UNSUPPORTED, evidence_kind="UNCERTIFIED")
    assert r.value is None


def test_issuer_secret_boundary():
    s = IssuerSecret(token_id="t", protocol_id="wiesner_ideal", bases=[Basis.Z, Basis.X], bits=[0, 1])
    assert "Z" not in repr(s) and "REDACTED" in repr(s)
    with pytest.raises(SecretBoundaryError):
        s.model_dump()
    with pytest.raises(SecretBoundaryError):
        s.model_dump_json()
    with pytest.raises(SecretBoundaryError):
        canonical_json({"wallet": s})
    with pytest.raises(SecretBoundaryError):
        pickle.dumps(s)
    assert s.reveal_for_testing_only()["TEST_ONLY"] is True


def test_token_record_rejects_secret_metadata():
    d = load("token_wiesner")
    d["public_metadata"] = {"secret_bases": "ZXZX"}
    with pytest.raises((ValidationError, SecretBoundaryError)):
        TokenRecord.model_validate(d)


def test_intervals_and_probabilities():
    with pytest.raises(ValidationError):
        Interval(lo=0.2, hi=0.1, unit=Unit.FRACTION)
    with pytest.raises(ValidationError):
        Interval(lo=0.0, hi=5.0, unit=Unit.FRACTION)  # percent, not fraction
    with pytest.raises(ValidationError):
        Interval(lo=0.0, hi=float("nan"), unit=Unit.NANOSECOND)


def test_photon_calibration_requires_hash():
    d = load("calibration_synthetic") | {"data_origin": "PHOTON_EXPERIMENT"}
    with pytest.raises(ValidationError):
        CalibrationRecord.model_validate(d)


def test_attack_result_requires_ci_and_sdp_fields():
    base = dict(attack_id="A01", game_id="W1", attack_capability=["one_copy"], token_n=1,
                attack_method="measure_resend", quantum_channel_description="Z-measure",
                verifier_rule="exact", proof_applicability="IN_MODEL", backend_kind="numpy",
                source_code_sha="x")
    with pytest.raises(ValidationError):
        AttackResult(**base, trials=10, successes=5, evidence_kind="MONTE_CARLO")
    with pytest.raises(ValidationError):
        AttackResult(**base, trials=0, successes=0, evidence_kind="NUMERICAL_SDP", sdp_primal=0.75)
    with pytest.raises(ValidationError):
        AttackResult(**base, trials=1, successes=2, evidence_kind="MONTE_CARLO",
                     success_rate_ci={"lo": 0, "hi": 1, "unit": "probability"})


def test_trace_rejects_retrocausal_edge():
    ev = [
        {"event_id": "a", "site_id": "A", "kind": "message_send", "time_ns": 100.0},
        {"event_id": "b", "site_id": "B", "kind": "message_receive", "time_ns": 50.0, "causal_parent_ids": ["a"]},
    ]
    with pytest.raises(ValidationError):
        TransactionTrace(trace_id="t", token_id="k", protocol_id="classical_h1_online_ledger", network_id="n",
                         events=ev, irrevocability_rule="r", double_spend_accepted=False,
                         latency_evidence="MODELLED_LATENCY")
