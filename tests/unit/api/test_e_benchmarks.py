"""Agent E: GET /benchmarks wired to lanes H (classical), G (latency) and E (photon QBER)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from qmint.api.app import app
from qmint.api.routes.benchmarks import H_RECORDS


@pytest.fixture(scope="module")
def data() -> dict:
    body = TestClient(app).get("/api/v1/benchmarks").json()
    assert body["status"] == "OK" and body["provenance"]["git_sha"]
    return body["data"]


def test_every_lane_h_record_is_a_row_with_its_record_id(data: dict) -> None:
    ids = {json.loads(line)["record_id"] for line in H_RECORDS.read_text().splitlines() if line.strip()}
    rows = {r["id"]: r for r in data["protocols"] if r["family"] == "classical"}
    assert set(rows) == ids
    for r in rows.values():
        assert r["evidence_kind"] == "MODELLED_LATENCY" and r["record_git_sha"] and r["environment_lock"]
        assert r["local_validation"]["evidence_kind"] == "MODELLED_LATENCY"


def test_double_spend_outcomes_follow_lane_h(data: dict) -> None:
    by = {(r["protocol_id"], r["variant"]): r["double_spend"]["outcome"] for r in data["protocols"]}
    assert by[("classical_h0_bearer", "negative_control")] == "SUCCEEDS"
    assert by[("classical_h1_online_ledger", "coordinator")] == "PREVENTED"
    assert by[("classical_h6_anonymous_ecash", "cfn88_sec1_k16")] == "DETECTED_NOT_PREVENTED"
    assert by[("classical_h5_secure_hardware", "assumption_violated_clone")] == "OUT_OF_MODEL"
    assert by[("s_money_kent_2022_ideal_2site", "ideal")] == "BOUNDED_BY_THEOREM"


def test_comparability_never_collapses_to_a_score(data: dict) -> None:
    statuses = {p["status"] for p in data["comparability"]}
    assert "COMPARABLE" not in statuses and {"QUALIFIED", "INCOMPARABLE"} <= statuses
    for r in data["protocols"]:
        assert "score" not in r
        if r["family"] == "classical" and r["comparability_pair"]:
            assert r["comparability_status"] in ("QUALIFIED", "INCOMPARABLE")
    h0 = next(p for p in data["comparability"] if p["pair_id"] == "X11-H0")
    assert h0["status"] == "INCOMPARABLE" and all(c["left"] and c["right"] for c in h0["columns"])


def test_quantum_latency_on_matched_topology_is_not_available(data: dict) -> None:
    s1 = next(r for r in data["protocols"] if r["family"] == "quantum")
    assert s1["local_validation"] is None and "GH" in s1["latency_unavailable_reason"]
    assert data["matched_topology"]["status"] == "NOT_AVAILABLE"


def test_h3_late_commit_reports_pre_presentation_commit(data: dict) -> None:
    rows = [r for r in data["protocols"] if r["variant"] == "late_commit_ot_private"]
    assert rows and all(r["pre_presentation_commit"]["value"] > 0 for r in rows)


def test_latency_cases_jiang_and_ripe(data: dict) -> None:
    cases = {c["id"]: {q["id"]: q for q in c["quantities"]} for c in data["latency_cases"]}
    intra = cases["jiang2024-intracity"]
    assert abs(intra["smoney_modelled"]["value"] - 15_340.0) <= 10.0
    assert intra["smoney_published"]["evidence_kind"] == "PUBLISHED_AGGREGATE"
    ripe = cases["ripe-prb6330-prb6251"]
    assert ripe["one_way_p50"]["evidence_kind"] == "MEASURED_LATENCY" and "RTT/2" in ripe["one_way_p50"]["note"]
    assert ripe["one_way_p50"]["value"] > ripe["lightcone_bound"]["value"]


def test_photon_runs_have_cis_and_published_reference(data: dict) -> None:
    ph = data["photon"]
    assert len(ph["runs"]) == 22
    for r in ph["runs"]:
        assert r["ci_lo"] <= r["qber"] <= r["ci_hi"] and r["n_errors"] < r["n_sifted"]
    bases = {b["basis"]: b for b in ph["bases"]}
    assert bases["Z"]["published"]["value"] == pytest.approx(0.0145)
    assert bases["X"]["published"]["value"] == pytest.approx(0.0328)
    assert abs(bases["Z"]["state_averaged"]["value"] - 0.0145) < 1e-4
    assert bases["Z"]["pooled"]["evidence_kind"] == "PHOTON_EXPERIMENT"
    assert "multiphoton probability" in ph["not_observable"]
