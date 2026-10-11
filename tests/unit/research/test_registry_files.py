"""Structural checks for lane A research registers (no network, deterministic)."""
import csv
import math
import re
from pathlib import Path

import pytest
import yaml

from qmint.core.contracts import GameId

ROOT = Path(__file__).resolve().parents[3]
RESEARCH = ROOT / "research"

MATRIX_COLUMNS = [
    "id", "canonical_link", "authors", "publication_date", "version", "correction_status",
    "precise_theorem", "input_model", "verifier_model", "adversary_capabilities", "tested_parameters",
    "proof_dependencies", "datasets", "code", "license", "limitations", "what_QMint_adds", "access_status",
]
STATUSES = {"VERIFIED_FROM_SOURCE", "NOT_VERIFIED", "RECOMPUTED_BY_LANE_A"}
# Games used in the seed but not (yet) in the frozen GameId enum; proposed in the A1 handoff.
PROPOSED_GAMES = {"W1_THRESH_JOINT", "S2_JIANG24"}
URL_RE = re.compile(r"^https://\S+$")


@pytest.fixture(scope="module")
def matrix():
    with open(RESEARCH / "PRIOR_ART_MATRIX.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


@pytest.fixture(scope="module")
def registry():
    return yaml.safe_load((RESEARCH / "THEOREM_REGISTRY_SEED.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def datasources():
    return yaml.safe_load((RESEARCH / "DATASOURCE_REGISTER.yaml").read_text(encoding="utf-8"))


def test_matrix_has_required_columns_and_core_ids(matrix):
    header, rows = matrix
    assert [c for c in MATRIX_COLUMNS if c not in header] == []
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate paper ids"
    assert {f"P{i:02d}" for i in range(1, 13)} <= set(ids)
    for r in rows:
        assert re.fullmatch(r"P\d{2}", r["id"])
        for col in MATRIX_COLUMNS:
            assert r[col].strip(), f"{r['id']}: empty {col}"
        assert "http" in r["canonical_link"], r["id"]


def test_theorem_ids_unique_and_games_known(registry):
    ids = [t["theorem_id"] for t in registry["theorems"]]
    assert len(ids) == len(set(ids))
    known = {g.value for g in GameId} | PROPOSED_GAMES
    for t in registry["theorems"]:
        assert t["game"] in known, t["theorem_id"]
        assert t["source_paper_id"] in registry["sources"], t["theorem_id"]


def test_verified_theorems_have_url_and_anchor(registry):
    for t in registry["theorems"]:
        assert t["status"] in STATUSES - {"RECOMPUTED_BY_LANE_A"}
        if t["status"] == "VERIFIED_FROM_SOURCE":
            assert URL_RE.match(t.get("source_url", "")), t["theorem_id"]
            assert len(str(t.get("anchor", "")).strip()) >= 8, t["theorem_id"]


def test_field_statuses_valid_and_not_verified_has_reason(registry):
    for t in registry["theorems"]:
        ver = t["verification"]
        assert ver, t["theorem_id"]
        reasons = t.get("not_verified_reasons", {}) or {}
        for field, status in ver.items():
            assert status in STATUSES, (t["theorem_id"], field)
            if status == "NOT_VERIFIED":
                assert str(reasons.get(field, "")).strip(), (t["theorem_id"], field)


def test_core_games_carry_distinct_published_bounds(registry):
    by_id = {t["theorem_id"]: t for t in registry["theorems"]}
    assert by_id["T-MVW12-THM1"]["game"] == "W1"
    assert by_id["T-MVW12-THM2"]["game"] == "W1_CV"
    assert by_id["T-KLPR22-LEMMA1"]["game"] == "S1"
    assert by_id["T-SCH23-FINITE"]["game"] == "D1"
    w1_base, w1cv_base, s1_base = 3 / 4, 3 / 4 + math.sqrt(2) / 8, 1 / 2 + 1 / (2 * math.sqrt(2))
    assert len({round(w1_base, 12), round(w1cv_base, 12), round(s1_base, 12)}) == 3
    assert "\\tfrac34" in by_id["T-MVW12-THM1"]["bound_latex"]
    assert "sqrt2" in by_id["T-MVW12-THM2"]["bound_latex"]
    assert "2\\sqrt{2}" in by_id["T-KLPR22-LEMMA1"]["bound_latex"]


def test_datasource_register_zenodo_records(datasources):
    ds = {d["id"]: d for d in datasources["datasets"]}
    v1 = ds["DS-SCH23-TIMETAGS-V1"]
    assert v1["doi"] == "10.5281/zenodo.7979319"
    assert v1["files"][0]["size_bytes"] == 153143236
    assert re.fullmatch(r"md5:[0-9a-f]{32}", v1["files"][0]["checksum"])
    code = ds["DS-SCH23-CODE"]
    assert code["doi"] == "10.5281/zenodo.8020667"
    assert code["license_conflict"] is True
    for d in datasources["datasets"]:
        assert d["access_status"] in {"VERIFIED_API", "VERIFIED_LISTING", "VERIFIED_DOWNLOAD",
                                      "PARTIALLY_VERIFIED", "NOT_VERIFIED"}, d["id"]
