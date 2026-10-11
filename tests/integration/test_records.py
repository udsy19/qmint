"""Append-only record store: contract validation, evidence/provenance, reproducibility flags."""

import json
import random
from pathlib import Path

import pytest
from pydantic import ValidationError

from qmint.core.contracts import EvidenceKind
from qmint.core.records import (
    Provenance,
    RecordExistsError,
    check_reproducible,
)

ROOT = Path(__file__).resolve().parents[2]


def test_append_writes_result_and_registry(store, prov, make_attack):
    rec = store.append("attack", make_attack(1), provenance=prov, repro=check_reproducible(make_attack, 1))
    assert rec.reproducibility == "DETERMINISTIC_VERIFIED" and rec.flags == []
    assert (store.results_dir / f"{rec.record_id}.json").is_file()
    lines = list(store.iter_registry())
    assert len(lines) == 1 and lines[0]["record_id"] == rec.record_id
    assert store.get(rec.record_id).payload_sha256 == rec.payload_sha256


def test_append_only_rejects_duplicate_id(store, prov, make_attack):
    store.append("attack", make_attack(1), provenance=prov, record_id="r1")
    with pytest.raises(RecordExistsError):
        store.append("attack", make_attack(2), provenance=prov, record_id="r1")
    assert len(list(store.iter_registry())) == 1


def test_nondeterministic_result_flagged(store, prov, make_attack):
    def unseeded(seed):
        return make_attack(seed, deterministic=False)

    repro = check_reproducible(unseeded, seed=3, runs=3)
    assert not repro.deterministic
    rec = store.append("attack", unseeded(3), provenance=prov, repro=repro)
    assert rec.reproducibility == "NONDETERMINISTIC"
    assert "IRREPRODUCIBLE_STOCHASTIC_RESULT" in rec.flags
    assert "IRREPRODUCIBLE_STOCHASTIC_RESULT" in next(store.iter_registry())["flags"]


def test_stochastic_without_check_or_seed_flagged(store, make_attack):
    no_seed = Provenance(git_sha="a" * 40, environment_lock="b" * 64, command="t", seed=None)
    rec = store.append("attack", make_attack(5), provenance=no_seed)
    assert rec.reproducibility == "UNCHECKED"
    assert {"REPRODUCIBILITY_UNCHECKED", "NO_SEED"} <= set(rec.flags)


def test_repro_must_match_stored_payload(store, prov, make_attack):
    rec = store.append("attack", make_attack(9), provenance=prov, repro=check_reproducible(make_attack, 8))
    assert "REPRO_HASH_DIFFERS_FROM_PAYLOAD" in rec.flags


def test_rejects_missing_evidence_kind(store, prov):
    proto = json.loads((ROOT / "tests/fixtures/contracts/protocol_wiesner.json").read_text())
    with pytest.raises(ValueError, match="no evidence kind"):
        store.append("protocol", proto, provenance=prov)
    rec = store.append("protocol", proto, provenance=prov, evidence_kind="PUBLISHED_AGGREGATE")
    assert rec.evidence_kind == EvidenceKind.PUBLISHED_AGGREGATE


def test_rejects_contradicting_evidence_kind(store, prov, make_attack):
    with pytest.raises(ValueError, match="contradicts"):
        store.append("attack", make_attack(1), provenance=prov, evidence_kind="PUBLISHED_THEOREM")


def test_rejects_missing_or_bad_provenance(store, make_attack):
    with pytest.raises(TypeError):
        store.append("attack", make_attack(1), provenance=None)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        Provenance(git_sha="", environment_lock="b" * 64, command="x")
    with pytest.raises(ValidationError):
        Provenance(git_sha="a" * 40, environment_lock="not-a-hash", command="x")
    assert not store.results_dir.exists()


def test_rejects_invalid_contract_payload(store, prov, make_attack):
    bad = make_attack(1).model_dump(mode="json")
    bad["successes"] = bad["trials"] + 1
    with pytest.raises(ValidationError):
        store.append("attack", bad, provenance=prov)
    with pytest.raises(ValueError, match="unknown contract"):
        store.append("not_a_contract", {}, provenance=prov)


def test_get_detects_tampering(store, prov, make_attack):
    rec = store.append("attack", make_attack(1), provenance=prov, record_id="t1")
    path = store.results_dir / "t1.json"
    data = json.loads(path.read_text())
    data["payload"]["attack_method"] = "edited"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="hash mismatch"):
        store.get(rec.record_id)


def test_unsafe_record_id_rejected(store, prov, make_attack):
    with pytest.raises(ValueError, match="unsafe"):
        store.append("attack", make_attack(1), provenance=prov, record_id="../escape")


def test_seed_derivation_is_stable():
    from qmint.core.config import derive_seed, make_rng

    assert derive_seed(42, "attacks") == derive_seed(42, "attacks") != derive_seed(42, "proofs")
    assert make_rng(42, "x").integers(0, 10**9) == make_rng(42, "x").integers(0, 10**9)
    random.seed(0)  # unrelated global state must not influence derived seeds
    assert derive_seed(42, "attacks") == derive_seed(42, "attacks")


def test_current_provenance_pins_this_checkout():
    from qmint.core.config import load_config
    from qmint.core.records import current_provenance
    from qmint.core.serialization import file_sha256

    cfg = load_config(env={})
    p = current_provenance(cfg, command="pytest", seed=42)
    assert p.environment_lock == file_sha256(cfg.lock_file)
    assert len(p.git_sha.removesuffix("-dirty")) == 40
