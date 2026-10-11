from __future__ import annotations

import copy

import pytest
import yaml

from qmint.core.contracts import GameId, ProofStatus, SecurityAxis
from qmint.proofs.registry import OBLIGATIONS_PATH, REQUIRED_CLAIM_IDS, Registry, default_registry

PLAN_3_6_FIELDS = (
    "claim_id", "protocol", "game", "source_and_theorem", "assumptions", "finite_n_or_asymptotic",
    "parameters", "quantifier_over_adversaries", "mathematical_bound", "numerical_method",
    "verification_script", "independent_crosscheck", "caveats", "status",
)


def test_all_mandatory_obligations_present():
    reg = default_registry()
    assert {c.claim_id for c in reg.claims} == set(REQUIRED_CLAIM_IDS)


def test_every_claim_has_all_master_plan_fields():
    raw = yaml.safe_load(OBLIGATIONS_PATH.read_text(encoding="utf-8"))
    for c in raw["claims"]:
        for f in PLAN_3_6_FIELDS:
            assert f in c and c[f] not in (None, "", []), (c["claim_id"], f)


def test_sources_have_url_and_hashes():
    for sid, s in default_registry().sources.items():
        assert s.url.startswith("https://"), sid
        assert all(len(f["sha256"]) == 64 for f in s.retrieved_files), sid


def test_bound_for_is_game_specific():
    reg = default_registry()
    assert reg.bound_for(GameId.W1, SecurityAxis.UNFORGEABILITY)[1].bound_id == "P-W1/unf"
    assert reg.bound_for(GameId.W1_CV, SecurityAxis.UNFORGEABILITY)[1].bound_id == "P-W1CV/unf"
    assert reg.bound_for(GameId.S1, SecurityAxis.UNFORGEABILITY)[1].bound_id == "P-S1/unf"
    for g in (GameId.W2, GameId.A1, GameId.C1):
        for a in SecurityAxis:
            assert reg.bound_for(g, a) is None
    for g in (GameId.W1, GameId.W1_CV, GameId.S1, GameId.D1):
        assert reg.bound_for(g, SecurityAxis.PRIVACY) is None  # no privacy theorem -> never 0


def test_status_vocabulary_and_honest_grades():
    reg = default_registry()
    assert reg.claim("P-D1").status == ProofStatus.NUMERICALLY_SUPPORTED
    for cid in ("P-W2", "P-S3", "P-C1", "P-OPT"):
        assert reg.claim(cid).status == ProofStatus.UNSUPPORTED
        assert reg.claim(cid).bounds == []


def test_registry_rejects_missing_or_duplicate_claims():
    raw = yaml.safe_load(OBLIGATIONS_PATH.read_text(encoding="utf-8"))
    broken = copy.deepcopy(raw)
    broken["claims"] = [c for c in broken["claims"] if c["claim_id"] != "P-PRIV"]
    with pytest.raises(ValueError):
        Registry.model_validate(broken)
    dup = copy.deepcopy(raw)
    dup["claims"].append(copy.deepcopy(dup["claims"][0]))
    with pytest.raises(ValueError):
        Registry.model_validate(dup)


def test_unsupported_claim_cannot_carry_bounds():
    raw = yaml.safe_load(OBLIGATIONS_PATH.read_text(encoding="utf-8"))
    bad = copy.deepcopy(raw)
    w2 = next(c for c in bad["claims"] if c["claim_id"] == "P-W2")
    w2["bounds"] = [{"bound_id": "P-W2/unf", "axis": "epsilon_unf", "anchor": "x", "formula": "(3/4)^n", "domain": "x"}]
    with pytest.raises(ValueError):
        Registry.model_validate(bad)


def test_monotonicity_directions_are_valid_words():
    for c in default_registry().claims:
        for b in c.bounds:
            assert set(b.monotonicity.values()) <= {"increasing", "decreasing"}
