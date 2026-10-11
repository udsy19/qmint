"""Lane K API contract tests (FastAPI TestClient; small shot counts, deterministic seeds)."""

from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient

from qmint.api.app import app
from qmint.api.export import DEFAULT_OUT, dumps, labels_doc, openapi_doc
from qmint.core.contracts import CertificateStatus, EvidenceKind

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
    assert lanes["A"] and lanes["F"] and lanes["G"] and lanes["L"] and lanes["J"]
    assert set(lanes) >= set("ABCDEFGHIJL")


def test_games_bounds(client: TestClient) -> None:
    games = {g["game_id"]: g for g in client.get("/api/v1/games").json()["data"]}
    assert games["W1"]["per_unit_value"] == 0.75 and games["W1"]["bound_evidence_kind"] == "PUBLISHED_THEOREM"
    assert math.isclose(games["S1"]["per_unit_value"], 0.5 + 1 / (2 * math.sqrt(2)))
    for g in ("W2", "S2", "D1", "A1", "C1"):
        assert games[g]["closed_form"] is False and games[g]["per_unit_value"] is None




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
