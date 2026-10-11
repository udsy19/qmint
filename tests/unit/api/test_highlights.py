"""GET /evidence/highlights: headline numbers read from their artefacts, never typed in."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from qmint.api.app import app
from qmint.api.routes import highlights as hl
from qmint.core.config import REPO_ROOT
from qmint.core.serialization import file_sha256


@pytest.fixture(scope="module")
def body() -> dict:
    return TestClient(app).get("/api/v1/evidence/highlights").json()


def _q(body: dict, hid: str) -> dict[str, dict]:
    (h,) = [h for h in body["data"]["highlights"] if h["id"] == hid]
    return {q["id"]: q for q in h["quantities"]}


def test_all_highlights_served_with_hashed_sources(body):
    assert body["status"] == "OK" and body["data"]["unavailable"] == []
    assert {h["id"] for h in body["data"]["highlights"]} == set(hl.BUILDERS)
    for h in body["data"]["highlights"]:
        for s in h["sources"]:
            assert s["sha256"] == file_sha256(REPO_ROOT / s["path"])
        for q in h["quantities"]:
            assert q["value"] is not None and q["source"]


def test_sdp_bracket_matches_lane_c_artefact(body):
    q = _q(body, "w1_sdp_bracket")
    sdp = json.loads((REPO_ROOT / "handoffs/C-C1-evidence.json").read_text())["w1_sdp"]
    assert q["w1_opt_n1_lower"]["value"] == 0.75 and q["w1_opt_n2_lower"]["value"] == 0.5625
    assert q["w1_opt_n1_upper"]["value"] == sdp["n1_SCS"]["certified"]["upper_bound_float_up"]
    assert q["w1_opt_n2_upper"]["value"] == sdp["n2_SCS"]["certified"]["upper_bound_float_up"]
    assert {x["evidence_kind"] for x in q.values()} == {"CERTIFIED_NUMERIC"}


def test_qber_is_photon_experiment_and_published_is_separate(body):
    q = _q(body, "schiansky2023_qber")
    assert round(q["qber_Z_state_avg"]["value"] * 100, 4) == 1.4491
    assert round(q["qber_X_state_avg"]["value"] * 100, 4) == 3.2787
    assert q["qber_Z_state_avg"]["evidence_kind"] == "PHOTON_EXPERIMENT"
    assert q["qber_Z_published"]["evidence_kind"] == "PUBLISHED_AGGREGATE"


def test_matched_topology_is_modelled(body):
    q = _q(body, "matched_topology_jinan")
    assert q["choice_to_accept_S1_s_money"]["value"] == 15337.0
    assert q["choice_to_accept_H1"]["value"] > q["choice_to_accept_S1_s_money"]["value"]
    assert (q["comparability_comparable"]["value"], q["comparability_qualified"]["value"],
            q["comparability_incomparable"]["value"]) == (0, 7, 4)
    assert {x["evidence_kind"] for x in q.values()} == {"MODELLED_LATENCY"}


def test_missing_artefact_is_reported_not_invented(monkeypatch, tmp_path):
    monkeypatch.setattr(hl, "E_DIR", tmp_path)
    b = TestClient(app).get("/api/v1/evidence/highlights").json()
    assert [u["id"] for u in b["data"]["unavailable"]] == ["schiansky2023_qber"]
    assert "schiansky2023_qber" not in {h["id"] for h in b["data"]["highlights"]}
