"""Agent C (KC) route tests: research library, tracker gates, game anchors, evidence index."""

from __future__ import annotations

import csv
import math

import pytest
import yaml
from fastapi.testclient import TestClient

from qmint.api.app import app
from qmint.api.routes.protocols import GAMES
from qmint.core.config import REPO_ROOT
from qmint.core.contracts import GameId
from qmint.proofs.registry import default_registry


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def library(client: TestClient) -> dict:
    r = client.get("/api/v1/research/sources")
    assert r.status_code == 200, r.text
    return r.json()


def test_library_is_real_lane_a_files(library: dict) -> None:
    assert library["status"] == "OK" and library["evidence_kind"] is None
    entries = {e["id"]: e for e in library["data"]["sources"]}
    with open(REPO_ROOT / "research/PRIOR_ART_MATRIX.csv", newline="", encoding="utf-8") as f:
        papers = list(csv.DictReader(f))
    seed = yaml.safe_load((REPO_ROOT / "research/THEOREM_REGISTRY_SEED.yaml").read_text(encoding="utf-8"))
    obl = yaml.safe_load((REPO_ROOT / "proofs/OBLIGATIONS.yaml").read_text(encoding="utf-8"))
    assert {p["id"] for p in papers} <= set(entries)
    assert {t["theorem_id"] for t in seed["theorems"]} <= set(entries)
    assert {c["claim_id"] for c in obl["claims"]} <= set(entries)
    kinds = {e["kind"] for e in entries.values()}
    assert kinds == {"paper", "theorem", "obligation", "correction", "novelty", "dataset"}
    # the plan-derived "unverified" label is gone; statuses are the files' own
    assert not [e for e in entries.values() if e["verification"] == "from plan, unverified"]


def test_statuses_verbatim_from_files(library: dict) -> None:
    entries = {e["id"]: e for e in library["data"]["sources"]}
    assert entries["T-MVW12-THM1"]["status"] == "VERIFIED_FROM_SOURCE"
    assert entries["T-GAV25-CONSTR10"]["status"] == "NOT_VERIFIED"
    assert entries["P-W1"]["status"] == "PUBLISHED_REPRODUCED"
    assert entries["P-D1"]["status"] == "NUMERICALLY_SUPPORTED"  # never upgraded to certified
    assert entries["P01"]["status"] == "FULL_TEXT_READ" and entries["P13"]["status"] == "METADATA_ONLY"
    assert entries["CORR-D-1"]["status"] == "OPEN_DISCREPANCY" and entries["CORR-D-11"]["status"] == "RESOLVED"
    assert entries["NOV-H1"]["status"] == "HYPOTHESIS" and entries["NOV-C3"]["status"] == "CONFLICT"
    glossary = {g["status"] for g in library["data"]["glossary"]}
    assert {e["status"] for e in entries.values()} <= glossary, "every status shown needs a definition"


def test_citations_and_title_provenance(library: dict) -> None:
    entries = {e["id"]: e for e in library["data"]["sources"]}
    p01 = entries["P01"]
    assert any("1202.4010" in u for u in p01["urls"])
    assert p01["title_source"] and "section 16" in p01["title_source"]
    assert "10.1038/s41534-022-00524-4" in entries["P03"]["dois"]
    assert entries["P13"]["title_source"] is None  # no invented titles
    assert "10.5281/zenodo.7979319" in entries["DS-SCH23-TIMETAGS-V1"]["dois"]
    assert "T-MVW12-THM1" in p01["related"]  # back-link from theorem to paper


def test_files_hashed(library: dict) -> None:
    files = {f["path"]: f for f in library["data"]["files"]}
    assert files["research/PRIOR_ART_MATRIX.csv"]["entries"] == 24
    assert all(f["sha256"] and len(f["sha256"]) == 64 for f in files.values())


def test_entry_detail_and_404(client: TestClient) -> None:
    body = client.get("/api/v1/research/sources/T-MVW12-THM1").json()
    assert body["status"] == "OK"
    fields = {f["key"]: f for f in body["data"]["fields"]}
    assert fields["bound_latex"]["kind"] == "latex"
    assert fields["assumptions"]["kind"] == "list"
    assert "(3/4)^n" in fields["statement_verbatim"]["text"]
    assert {r["id"] for r in body["data"]["related"]} >= {"P01", "P-W1"}
    r = client.get("/api/v1/research/sources/NOPE")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_tracker_gates_verbatim(client: TestClient) -> None:
    body = client.get("/api/v1/meta/tracker").json()
    assert body["status"] == "OK"
    doc = yaml.safe_load((REPO_ROOT / "project/TRACKER.yaml").read_text(encoding="utf-8"))
    gates = {g["gate_id"]: g["status"] for g in body["data"]["gates"]}
    assert gates == {k: v["status"] for k, v in doc["gates"].items()}
    tasks = {t["task_id"]: t for t in body["data"]["tasks"]}
    assert set(tasks) == set(doc["tasks"])
    assert all(t["status"] in body["data"]["status_values"] for t in tasks.values())


def test_game_anchors_never_cross_games(client: TestClient) -> None:
    games = {g["game_id"]: g for g in client.get("/api/v1/games").json()["data"]}
    seed = yaml.safe_load((REPO_ROOT / "research/THEOREM_REGISTRY_SEED.yaml").read_text(encoding="utf-8"))
    by_id = {t["theorem_id"]: t["game"] for t in seed["theorems"]}
    reg = default_registry()
    for gid, g in games.items():
        for a in g["anchors"]:
            if a["kind"] == "theorem":
                assert by_id[a["ref_id"]] == gid
            else:
                assert reg.claim(a["ref_id"]).game == gid
    assert {a["ref_id"] for a in games["W1"]["anchors"]} == {"T-MVW12-THM1", "P-W1"}


@pytest.mark.parametrize("game", [GameId.W1, GameId.W1_CV, GameId.S1])
def test_transcribed_bases_match_lane_d(game: GameId) -> None:
    """The per-unit bases transcribed in protocols.GAMES equal lane D's reproduced bound at size 1."""
    from qmint.proofs.ideal_bounds import log10_bound

    claim, _ = default_registry().bound_for(game, "epsilon_unf")
    assert claim.status.value == "PUBLISHED_REPRODUCED"
    per = GAMES[game].per_unit
    assert per is not None and math.isclose(10 ** log10_bound(game, 1), per, rel_tol=1e-12)


def test_evidence_index_sorted_or_empty(client: TestClient) -> None:
    body = client.get("/api/v1/evidence").json()
    assert body["status"] == "OK"
    times = [r["created_utc"] for r in body["data"]["records"]]
    assert times == sorted(times, reverse=True)
