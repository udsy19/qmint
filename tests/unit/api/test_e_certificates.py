"""Agent E: Security Certificate Studio API (lane D ProofEngine + IndependentProofChecker gating)."""

from __future__ import annotations

import json
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from qmint.api.app import app
from qmint.api.routes import certificates as route
from qmint.core.contracts import CertificateStatus
from qmint.core.serialization import sha256_hex
from qmint.proofs.registry import default_registry


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def presets(client: TestClient) -> dict[str, dict]:
    body = client.get("/api/v1/certificates/catalog").json()
    assert body["status"] == "OK"
    return {p["id"]: p["request"] for p in body["data"]["presets"]}


def _post(client: TestClient, req: dict) -> dict:
    r = client.post("/api/v1/certificates", json=req)
    assert r.status_code == 200, r.text
    return r.json()["data"]


def test_w1_certified_only_by_checker(client: TestClient, presets: dict) -> None:
    d = _post(client, presets["w1-n73"])
    assert d["draft_certificate"]["proof_check_status"] == "UNCERTIFIED"  # engine never certifies
    assert d["checked_certificate"]["proof_check_status"] == "CERTIFIED"
    assert d["checker"]["checker_id"] == "qmint.proofs.checker/decimal-v1"
    assert d["classification"]["verdict"] == "CERTIFIED"


def test_checker_gating_rejection_is_never_overridden(client: TestClient, presets: dict) -> None:
    """If the independent checker refuses, the studio must not report CERTIFIED anywhere."""

    def refuse(self, cert):  # noqa: ANN001
        return self._verdict(cert, ["forced refusal for test"])

    with mock.patch.object(route.IndependentProofChecker, "check", refuse):
        body = client.post("/api/v1/certificates", json=presets["w1-n73"]).json()
    d = body["data"]
    assert d["checked_certificate"]["proof_check_status"] == "UNCERTIFIED"
    assert d["classification"]["verdict"] != "CERTIFIED"
    assert body["evidence_kind"] == "UNCERTIFIED"
    assert '"proof_check_status":"UNCERTIFIED"' in d["export"]["canonical_json"]


def test_d1_never_certified(client: TestClient, presets: dict) -> None:
    for pid in ("d1-schiansky", "d1-photon"):
        d = _post(client, presets[pid])
        unf = next(a for a in d["axes"] if a["axis"] == "epsilon_unf")
        assert unf["result"]["log10_value"] < -40  # the bound reproduces ...
        assert d["checked_certificate"]["proof_check_status"] != CertificateStatus.CERTIFIED.value  # ... but is not certified
        assert any("never certified" in r for r in d["checker"]["reasons"])
        assert d["classification"]["verdict"] != "CERTIFIED"


def test_missing_privacy_theorem_is_null_not_zero(client: TestClient, presets: dict) -> None:
    d = _post(client, presets["w1-privacy"])
    priv = next(a for a in d["axes"] if a["axis"] == "epsilon_priv")
    assert priv["result"]["value"] is None and priv["result"]["log10_value"] is None
    assert priv["applicable"] is False and priv["meets_target"] is None
    assert d["checked_certificate"]["upper_bounds"]["epsilon_priv"] is None
    assert d["checked_certificate"]["proof_check_status"] == "UNCERTIFIED"


def test_calibration_family_mismatch_is_out_of_model(client: TestClient, presets: dict) -> None:
    d = _post(client, presets["s2-photon-mismatch"])
    assert d["calibration"]["family_matches"] is False
    assert d["classification"]["verdict"] == "OUT_OF_MODEL"
    assert all(a["result"]["log10_value"] is None for a in d["axes"])


def test_ideal_game_with_error_tolerance_is_out_of_model(client: TestClient, presets: dict) -> None:
    d = _post(client, presets["w1-noisy"])
    assert d["classification"]["verdict"] == "OUT_OF_MODEL"
    assert d["checked_certificate"]["proof_check_status"] == "UNCERTIFIED"


def test_infeasible_when_bound_exceeds_target(client: TestClient, presets: dict) -> None:
    req = dict(presets["w1-n73"], parameters={"n": 10})
    d = _post(client, req)
    assert d["classification"]["verdict"] == "INFEASIBLE"
    sizing = {q["id"]: q for q in d["sizing"]["quantities"]}
    assert sizing["n_min"]["value"] == 73 and sizing["n_min"]["evidence_kind"] == "PUBLISHED_THEOREM"


def test_s2_interval_propagates_to_worst_endpoint(client: TestClient, presets: dict) -> None:
    req = json.loads(json.dumps(presets["s2-fig5"]))
    req["parameters"]["P_noqub"] = {"lo": 0.0037, "hi": 0.00382}
    d = _post(client, req)
    unf = next(a for a in d["axes"] if a["axis"] == "epsilon_unf")
    step = next(s for s in unf["uncertainty"] if s["parameter"] == "P_noqub")
    assert step["direction"] == "increasing" and step["endpoint_used"].startswith("hi")
    assert d["optimization"]["status"] == "NOT_AVAILABLE" and "lane I" in d["optimization"]["reason"]


def test_no_theorem_game(client: TestClient, presets: dict) -> None:
    d = _post(client, presets["w2"])
    assert d["theorem"] is None and d["no_theorem_reason"]
    assert d["classification"]["verdict"] == "UNCERTIFIED"


def test_export_is_canonical_and_hashed(client: TestClient, presets: dict) -> None:
    d = _post(client, presets["s2-fig5"])
    exp = d["export"]
    assert sha256_hex(exp["canonical_json"]) == exp["sha256"]
    cert = json.loads(exp["canonical_json"])
    assert cert["proof_check_status"] == "CERTIFIED" and exp["obligations_sha256"] in cert["evidence_hashes"]


def test_catalog_declarations_cover_kent_table6(client: TestClient) -> None:
    games = {g["game"]: g for g in client.get("/api/v1/certificates/catalog").json()["data"]["games"]}
    s2 = games["S2"]
    names = {d["name"] for d in s2["declarations"]}
    assert names == set(default_registry().claim("P-S2").required_declarations)
    assert all(d["description"].startswith("Table 6") for d in s2["declarations"] if d["name"].startswith("table6_"))
    assert games["A1"]["theorem"] is None and games["A1"]["no_theorem_reason"]


def test_bad_requests_are_422(client: TestClient) -> None:
    assert client.post("/api/v1/certificates", json={"game": "W1", "protocol_id": "wiesner_noisy"}).status_code == 422
    assert client.post("/api/v1/certificates", json={"game": "S2", "parameters": {"N": {"lo": 2, "hi": 1}}}).status_code == 422
    assert client.post("/api/v1/certificates", json={"targets": {"epsilon_unf": 0}}).status_code == 422
