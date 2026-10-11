"""Lane M red team: record store (lane L) and evidence workbench (lane K) provenance (DATA_LEAKAGE_REVIEW)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qmint.core.contracts import AttackResult, EvidenceKind, GameId, Interval, Unit
from qmint.core.records import Provenance, RecordStore
from qmint.core.serialization import canonical_hash, canonical_json
from qmint.ui.app import is_fixture
from qmint.ui.records import load_records

ROOT = Path(__file__).resolve().parents[2]
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


@pytest.mark.xfail(strict=True, reason="M-L1: get() trusts a results file that has no run_registry.jsonl entry")
def test_store_rejects_unregistered_result_file(tmp_path):
    store = RecordStore(tmp_path)
    store.append("attack", _attack(), provenance=PROV, record_id="genuine")
    _forge(store, "genuine", "injected", EvidenceKind.MONTE_CARLO)
    with pytest.raises(ValueError):
        store.get("injected")


@pytest.mark.xfail(strict=True, reason="M-L1: get() does not compare against the registry's record_sha256 (SYNTHETIC relabelled)")
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


@pytest.mark.xfail(strict=True, reason="M-K1: --real-data drops the FIXTURE label for fixture records labelled MONTE_CARLO/NUMERICAL_SDP")
@pytest.mark.parametrize("name", ["attack_mc_fixture.json", "attack_sdp_fixture.json", "bench_c_h1_fixture.json"])
def test_workbench_keeps_fixture_label_for_fixture_records(name):
    recs, skipped = load_records([ROOT / "tests/unit/ui/fixtures" / name])
    assert recs and not skipped
    assert is_fixture(recs, real_data=True), f"{name} would be published as a research result"
