"""Lane K API contract tests (FastAPI TestClient; small shot counts, deterministic seeds)."""

from __future__ import annotations

import json
import math

import pytest
from fastapi.testclient import TestClient

from qmint.api.app import app
from qmint.api.export import DEFAULT_OUT, dumps, labels_doc, openapi_doc
from qmint.api.routes.lab import cloner_single_copy_pass, measure_resend_per_qubit
from qmint.core.contracts import CertificateStatus, EvidenceKind
from qmint.quantum.cloner import BRUSS_BOTH_PASS_ANALYTIC

FORBIDDEN = {"basis", "bases", "bits", "secret", "secret_bases", "secret_bits", "outcomes", "key", "verifier_key"}


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _envelope(body: dict) -> None:
    assert body["status"] in ("OK", "DEMO_ADAPTER", "NOT_AVAILABLE")
    assert set(body) >= {"status", "evidence_kind", "provenance", "reason", "data"}
    if body["status"] != "OK":
        assert body["reason"]
    assert body["provenance"]["git_sha"]


def _quantities(obj):
    if isinstance(obj, dict):
        if {"value", "unit", "evidence_kind", "method", "source"} <= set(obj):
            yield obj
        for v in obj.values():
            yield from _quantities(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _quantities(v)


@pytest.mark.parametrize(
    "path", ["/meta", "/games", "/protocols", "/benchmarks", "/research/sources", "/evidence", "/evidence/labels"]
)
def test_get_endpoints_envelope(client: TestClient, path: str) -> None:
    r = client.get("/api/v1" + path)
    assert r.status_code == 200, r.text
    _envelope(r.json())
    for q in _quantities(r.json()):
        EvidenceKind(q["evidence_kind"])


def test_health(client: TestClient) -> None:
    assert client.get("/api/v1/health").json() == {"ok": True}


def test_meta_lanes_detected(client: TestClient) -> None:
    lanes = {x["lane"]: x["merged"] for x in client.get("/api/v1/meta").json()["data"]["lanes"]}
    assert lanes["F"] and lanes["G"] and lanes["L"] and lanes["J"]
    assert set(lanes) >= set("ABCDEFGHIJL")


def test_games_bounds(client: TestClient) -> None:
    games = {g["game_id"]: g for g in client.get("/api/v1/games").json()["data"]}
    assert games["W1"]["per_unit_value"] == 0.75 and games["W1"]["bound_evidence_kind"] == "PUBLISHED_THEOREM"
    assert math.isclose(games["S1"]["per_unit_value"], 0.5 + 1 / (2 * math.sqrt(2)))
    for g in ("W2", "S2", "D1", "A1", "C1"):
        assert games[g]["closed_form"] is False and games[g]["per_unit_value"] is None


def _mint(client: TestClient, **kw) -> dict:
    r = client.post("/api/v1/lab/mint", json=kw)
    assert r.status_code == 200, r.text
    return r.json()


def test_mint_deterministic_and_secret_separated(client: TestClient) -> None:
    a = _mint(client, n_qubits=5, seed=7, backend="aer", shots=500)
    b = _mint(client, n_qubits=5, seed=7, backend="aer", shots=500)
    _envelope(a)
    assert a["data"] == b["data"]
    token = a["data"]["token"]
    assert not {k.lower() for k in token["public_metadata"]} & FORBIDDEN
    assert not [k for k in FORBIDDEN if f"\"{k}\":" in json.dumps(token)]
    iv = a["data"]["issuer_view"]
    assert iv["domain"] == "ISSUER_PRIVATE_DEMO" and len(iv["qubits"]) == 5
    expected = "".join(str(q["bit"]) for q in iv["qubits"])
    assert a["data"]["statistics"]["expected_outcome"] == expected
    assert a["evidence_kind"] == "SIMULATOR_IDEAL"
    # ideal: the only outcome is the secret bit string, and every shot accepts
    assert a["data"]["statistics"]["analytic_distribution"] == [{"outcome": expected, "probability": 1.0}]
    aer = [q for q in a["data"]["statistics"]["acceptance"] if q["method"] == "aer_sampling"][0]
    assert aer["value"] == 1.0 and aer["interval"]["confidence"] == 0.99


def test_mint_noisy_labels_and_ci(client: TestClient) -> None:
    body = _mint(client, n_qubits=3, seed=1, backend="aer", shots=4000,
                 noise={"channel": "depolarizing", "param": 0.1, "readout_p01": 0.01, "readout_p10": 0.02})
    assert body["evidence_kind"] == "SIMULATOR_NOISY"
    assert body["data"]["token"]["state_kind"] == "noisy_simulated"
    acc = {q["id"]: q for q in body["data"]["statistics"]["acceptance"]}
    exact, ci = acc["honest_accept_note_analytic"]["value"], acc["honest_accept_note_aer"]["interval"]
    assert ci["lo"] <= exact <= ci["hi"]


def test_mint_rejects_too_many_qubits(client: TestClient) -> None:
    r = client.post("/api/v1/lab/mint", json={"n_qubits": 9})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_measure_resend_exact_values() -> None:
    single, both = measure_resend_per_qubit()
    assert math.isclose(single, 3 / 4) and math.isclose(both, 5 / 8)
    assert math.isclose(cloner_single_copy_pass("bruss2000"), 0.5 + math.sqrt(1 / 8))


@pytest.mark.parametrize("attack", ["honest", "measure_resend", "bruss_cloner", "mvw_channel"])
@pytest.mark.parametrize("n", [1, 3])
def test_attack_quantities(client: TestClient, attack: str, n: int) -> None:
    r = client.post("/api/v1/lab/attack", json={"attack": attack, "n": n, "backend": "aer", "shots": 800, "seed": 3})
    assert r.status_code == 200, r.text
    body = r.json()
    _envelope(body)
    assert body["status"] == "DEMO_ADAPTER" and "lane C" in body["reason"]
    d = body["data"]
    assert d["theorem_bound"]["value"] == pytest.approx(0.75**n)
    assert d["theorem_bound"]["evidence_kind"] == "PUBLISHED_THEOREM"
    for q in _quantities(d):
        assert q["value"] is None or 0.0 <= q["value"] <= 1.0
    exact = {q["id"]: q for q in d["double_verification_success"]}
    if attack == "honest":
        assert exact["double_verification_success"]["value"] is None
        return
    base = {"measure_resend": 5 / 8, "bruss_cloner": BRUSS_BOTH_PASS_ANALYTIC, "mvw_channel": 3 / 4}[attack]
    assert exact["double_verification_success"]["value"] == pytest.approx(base**n)
    assert exact["double_verification_success"]["value"] <= d["theorem_bound"]["value"] + 1e-12
    mc = exact.get("double_verification_success_aer")
    if attack in ("bruss_cloner", "mvw_channel") and n == 1:
        assert mc is not None and mc["evidence_kind"] in ("MONTE_CARLO", "SIMULATOR_IDEAL")
        assert "LOWER bound" in mc["note"]
        assert mc["interval"]["lo"] - 0.02 <= base <= mc["interval"]["hi"] + 0.02
        assert d["attack_result"]["game_id"] == "W1"
    else:
        assert mc is None


def test_certificate_protocol_game_mismatch_is_422(client: TestClient) -> None:
    r = client.post("/api/v1/certificates", json={"game": "W1", "protocol_id": "wiesner_noisy"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_labels_cover_enums(client: TestClient) -> None:
    labels = client.get("/api/v1/evidence/labels").json()["data"]
    keys = {lab["key"] for lab in labels}
    assert {k.value for k in EvidenceKind} <= keys and {s.value for s in CertificateStatus} <= keys
    assert {"DEMO_ADAPTER", "NOT_AVAILABLE"} <= keys
    assert [lab for lab in labels if lab["tone"] == "ok"] == [lab for lab in labels if lab["key"] == "CERTIFIED"]
    assert labels == labels_doc()["labels"]


def test_unknown_route_error_shape(client: TestClient) -> None:
    r = client.get("/api/v1/does-not-exist")
    assert r.status_code == 404 and set(r.json()["error"]) == {"code", "message", "detail"}


def test_cors_localhost_3000_only(client: TestClient) -> None:
    ok = client.options("/api/v1/meta", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    bad = client.options("/api/v1/meta", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in bad.headers


def test_generated_files_in_sync() -> None:
    assert (DEFAULT_OUT / "openapi.json").read_text(encoding="utf-8") == dumps(openapi_doc()), (
        "run: python -m qmint.api.export"
    )
    assert (DEFAULT_OUT / "evidence-labels.json").read_text(encoding="utf-8") == dumps(labels_doc())


def test_openapi_component_names_are_clean() -> None:
    names = set(openapi_doc()["components"]["schemas"])
    assert {"Quantity", "ApiError", "MintResponse", "AttackResponse", "CertificateResponse"} <= names
    assert not [n for n in names if "__" in n or n.endswith(("-Input", "-Output")) or "[" in n]
