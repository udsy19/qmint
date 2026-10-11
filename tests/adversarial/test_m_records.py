"""Lane M red team: record store (lane L) and API evidence route (lane K) provenance (DATA_LEAKAGE_REVIEW)."""

from __future__ import annotations

import json

import pytest

from qmint.core.contracts import AttackResult, EvidenceKind, GameId, Interval, Unit
from qmint.core.records import Provenance, RecordStore
from qmint.core.serialization import canonical_hash, canonical_json

PROV = Provenance(git_sha="0123456789abcdef", environment_lock="0" * 64, command="m-redteam", seed=1)


def _attack(kind: EvidenceKind = EvidenceKind.SYNTHETIC) -> AttackResult:
    return AttackResult(
        attack_id="M_redteam", game_id=GameId.W1, attack_capability=["x"], token_n=1, attack_method="x",
        quantum_channel_description="x", verifier_rule="x", seed=1, trials=10, successes=5,
        success_rate_ci=Interval(lo=0.2, hi=0.8, unit=Unit.PROBABILITY, point=0.5), ci_method="cp",
        proof_applicability="NO_THEOREM", backend_kind="x", evidence_kind=kind, source_code_sha="x")


def _forge(store: RecordStore, base_id: str, new_id: str, kind: EvidenceKind) -> None:
    rec = json.loads(store._path(base_id).read_text())
    rec["record_id"] = new_id
    rec["payload"]["evidence_kind"] = kind.value
    rec["evidence_kind"] = kind.value
    rec["payload_sha256"] = canonical_hash(rec["payload"])
    store._path(new_id).write_text(canonical_json(rec) + "\n")


def test_store_rejects_tampered_payload_without_rehash(tmp_path):
    store = RecordStore(tmp_path)
    store.append("attack", _attack(), provenance=PROV, record_id="genuine")
    rec = json.loads(store._path("genuine").read_text())
    rec["payload"]["successes"] = 9
    store._path("genuine").write_text(json.dumps(rec))
    with pytest.raises(ValueError):
        store.get("genuine")


def test_store_rejects_unregistered_result_file(tmp_path):
    store = RecordStore(tmp_path)
    store.append("attack", _attack(), provenance=PROV, record_id="genuine")
    _forge(store, "genuine", "injected", EvidenceKind.MONTE_CARLO)
    with pytest.raises(ValueError):
        store.get("injected")


def test_store_rejects_relabelled_registered_record(tmp_path):
    store = RecordStore(tmp_path)
    store.append("attack", _attack(), provenance=PROV, record_id="genuine")
    _forge(store, "genuine", "genuine", EvidenceKind.MONTE_CARLO)
    with pytest.raises(ValueError):
        store.get("genuine")


def test_store_refuses_test_only_revelation(tmp_path):
    from qmint.core.contracts import SecretBoundaryError, SecurityCertificate

    store = RecordStore(tmp_path)
    leak = {"TEST_ONLY": True, "bases": ["Z"], "bits": [1]}
    cert = SecurityCertificate(protocol_id="wiesner_ideal", game_id=GameId.W1, security_model_id="m", reason="m",
                               parameters={"leak": leak})
    with pytest.raises(SecretBoundaryError):
        store.append("certificate", cert, provenance=PROV)


# M-K1 (originally the static workbench's --real-data path, since retired): the API evidence route is
# the remaining rendering path, so it carries the provenance gate. These are the lane-K fixture payloads
# that slipped through the workbench: MONTE_CARLO, NUMERICAL_SDP and MODELLED_LATENCY, not SYNTHETIC.
_FIXTURE_ATTACK = dict(
    attack_capability=["single_copy"], game_id="W1", proof_applicability="IN_MODEL", token_n=1,
    quantum_channel_description="FIXTURE (synthetic, UI test only; not a research result)",
    backend_kind="SYNTHETIC_FIXTURE", source_code_sha="fixture", verifier_rule="exact_projective")
FIXTURES = {
    "attack_mc_fixture": ("attack", {
        **_FIXTURE_ATTACK, "attack_id": "FIXTURE_A01_measure_resend", "attack_method": "FIXTURE_measure_resend",
        "evidence_kind": "MONTE_CARLO", "seed": 41, "trials": 1000, "successes": 741, "ci_method": "clopper_pearson_95",
        "success_rate_ci": {"lo": 0.712, "hi": 0.768, "point": 0.741, "unit": "probability"}}),
    "attack_sdp_fixture": ("attack", {
        **_FIXTURE_ATTACK, "attack_id": "FIXTURE_SDP_W1_n1", "attack_method": "FIXTURE_choi_sdp_placeholder",
        "evidence_kind": "NUMERICAL_SDP", "trials": 0, "successes": 0, "sdp_primal": 0.7499, "sdp_dual": 0.7502,
        "primal_feasibility_residual": 3e-08, "dual_feasibility_residual": 2e-08, "solver": "FIXTURE_none"}),
    "bench_c_h1_fixture": ("benchmark", {
        "classical_or_quantum": "classical", "environment_lock": "fixture", "evidence_kind": "MODELLED_LATENCY",
        "git_sha": "fixture", "method": "FIXTURE", "network_cross_check_seconds": 3.3e-05,
        "network_id": "net-synthetic-2site-10km", "pre_distribution": "FIXTURE", "privacy_game": "none",
        "protocol_id": "classical_h1_online_ledger", "record_id": "FIXTURE_bench_classical_h1",
        "security_target": {}, "site_count": 2, "spending_flexibility": "online_any_site",
        "trust_model": "honest_bank"}),
}


def _served(tmp_path, monkeypatch) -> dict[str, dict]:
    from fastapi.testclient import TestClient

    from qmint.api.app import app

    monkeypatch.setenv("QMINT_ROOT", str(tmp_path))
    body = TestClient(app).get("/api/v1/evidence").json()
    return {r["record_id"]: r for r in body["data"]["records"]}


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_api_serves_fixture_records_only_as_synthetic(name, tmp_path, monkeypatch):
    contract, payload = FIXTURES[name]
    RecordStore(tmp_path / "experiments").append(contract, payload, provenance=PROV, record_id=name)
    rec = _served(tmp_path, monkeypatch)[name]
    assert rec["recorded_evidence_kind"] != "SYNTHETIC"
    assert rec["evidence_kind"] == "SYNTHETIC" and not rec["provenance_verified"], f"{name} served as research"
    assert any("fixture" in p for p in rec["provenance_problems"])


def test_api_serves_relabelled_record_as_synthetic(tmp_path, monkeypatch):
    store = RecordStore(tmp_path / "experiments")
    store.append("attack", _attack(EvidenceKind.MONTE_CARLO), provenance=PROV, record_id="genuine")
    store.append("attack", _attack(), provenance=PROV, record_id="relabelled")
    _forge(store, "relabelled", "relabelled", EvidenceKind.MONTE_CARLO)
    served = _served(tmp_path, monkeypatch)
    assert served["genuine"]["evidence_kind"] == "MONTE_CARLO" and served["genuine"]["provenance_verified"]
    assert served["relabelled"]["evidence_kind"] == "SYNTHETIC" and not served["relabelled"]["provenance_verified"]
