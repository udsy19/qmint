"""Lab routes (agent KD): /lab/mint and /lab/attack over lanes B, C, D and F.

Covers the information boundary (no issuer secret outside the explicit TEST_ONLY teaching
reveal), exact values against lane C/D, Monte Carlo intervals, the SDP bracket, validation
limits and the compute deadline.
"""

from __future__ import annotations

import json
import math

import pytest
from fastapi.testclient import TestClient

from qmint.api.app import app
from qmint.api.routes import lab

SECRET_KEYS = {
    "basis", "bases", "bit", "bits", "secret", "state_label", "bloch", "qasm2", "circuit_sha256",
    "resources", "expected_outcome", "outcome_distribution", "outcome", "teaching_qubits",
}


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _keys(obj, path=()):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k, path
            yield from _keys(v, (*path, k))
    elif isinstance(obj, list):
        for v in obj:
            yield from _keys(v, path)


def _strings(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)
    elif isinstance(obj, str):
        yield obj


def _quantities(obj):
    if isinstance(obj, dict):
        if {"value", "unit", "evidence_kind", "method", "source"} <= set(obj):
            yield obj
        for v in obj.values():
            yield from _quantities(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _quantities(v)


def _post(client: TestClient, path: str, body: dict) -> dict:
    r = client.post(f"/api/v1/lab/{path}", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "OK" and out["provenance"]["git_sha"]
    return out


# --------------------------------------------------------------------------- mint


@pytest.mark.parametrize("noise", [None, {"channel": "amplitude_damping", "strength": 0.3}])
def test_mint_never_returns_secret_outside_teaching(client: TestClient, noise: dict | None) -> None:
    body = {"n_qubits": 8, "seed": 11, "shots": 300, "trials": 50}
    if noise:
        body["noise"] = noise
    pub = _post(client, "mint", body)
    taught = _post(client, "mint", {**body, "teaching_reveal": True})

    d = pub["data"]
    assert d["teaching"] is None
    leaked = [(k, p) for k, p in _keys(d) if k in SECRET_KEYS]
    assert leaked == [], leaked
    assert d["circuit"]["redacted"] is True
    assert all(q["prepare"] == ["secret"] and q["verify"] == ["secret"] for q in d["circuit"]["qubits"])
    assert set(d["token"]["public_metadata"]) == {"serial"}

    t = taught["data"]["teaching"]
    assert t["domain"] == "TEST_ONLY_TEACHING_REVEAL" and t["proof_applicability"] == "OUT_OF_MODEL"
    secret_bits = t["expected_outcome"]
    assert secret_bits == "".join(str(q["bit"]) for q in t["qubits"]) and len(secret_bits) == 8
    # the public response carries none of the teaching-only material, not even as a substring
    for s in _strings(d):
        if "SN-" in s:  # serial / token id: random hex, unrelated to the secret
            continue
        assert secret_bits not in s
        assert t["circuit_sha256"] not in s
    assert t["qasm2"] and t["qasm2"] not in json.dumps(d)
    # identical public data apart from the teaching block and timings
    for k in ("token", "flow", "statistics", "circuit", "theorem"):
        assert taught["data"][k] == d[k]


def test_mint_flow_lifecycle_and_crosschecks(client: TestClient) -> None:
    d = _post(client, "mint", {"protocol_id": "wiesner_noisy", "n_qubits": 6, "threshold": 1, "seed": 3,
                               "noise": {"channel": "depolarizing", "strength": 0.1}, "shots": 4000, "trials": 1500})
    assert d["evidence_kind"] == "SIMULATOR_NOISY"
    data = d["data"]
    assert data["protocol"]["game_id"] == "W2" and data["token"]["protocol_id"] == "wiesner_noisy"
    flow = {s["id"]: s for s in data["flow"]}
    assert flow["verify"]["result"] in ("accepted", "rejected")
    assert flow["replay"]["result"] == "refused"
    assert flow["verify"]["serial"] == data["token"]["public_metadata"]["serial"]
    assert (flow["remint"]["result"] == "done") == (flow["verify"]["result"] == "accepted")
    acc = {q["id"]: q for q in data["statistics"]["acceptance"]}
    # depolarizing is basis-independent: this note == any note == 1 - Bin tail
    exact = acc["honest_accept_note_exact"]["value"]
    assert math.isclose(exact, acc["honest_accept_mean"]["value"], rel_tol=1e-9)
    assert math.isclose(exact, 0.95**6 + 6 * 0.05 * 0.95**5, rel_tol=1e-9)
    for qid in ("honest_accept_note_aer", "honest_accept_mc"):
        iv = acc[qid]["interval"]
        assert iv["confidence"] == 0.95 and iv["lo"] <= exact <= iv["hi"]
    assert acc["honest_accept_mc"]["method"] == "monte_carlo"
    rows = data["statistics"]["error_counts"]
    assert math.isclose(sum(r["exact_probability"] for r in rows), 1.0) and len(rows) == 7
    assert sum(r["sampled_count"] for r in rows) == 4000
    assert [r["accepted"] for r in rows] == [True, True] + [False] * 5
    assert data["theorem"]["value"] is None  # W2: no closed form, never 0
    assert data["hardware"]["evidence_kind"] == "QPU" and data["hardware"]["value"] is None


def test_mint_ideal_theorem_and_determinism(client: TestClient) -> None:
    body = {"n_qubits": 5, "seed": 7, "shots": 500, "trials": 100}
    a, b = _post(client, "mint", body), _post(client, "mint", body)
    for k in ("token", "flow", "statistics"):
        assert a["data"][k] == b["data"][k]
    th = a["data"]["theorem"]
    assert th["evidence_kind"] == "PUBLISHED_THEOREM" and math.isclose(th["value"], 0.75**5)
    assert "Theorem 1" in th["source"] and "1202.4010" in th["source"]
    acc = {q["id"]: q for q in a["data"]["statistics"]["acceptance"]}
    assert acc["honest_accept_note_aer"]["value"] == 1.0


@pytest.mark.parametrize(
    "body",
    [
        {"n_qubits": 9},
        {"threshold": 1},
        {"protocol_id": "wiesner_noisy", "threshold": 0},
        {"protocol_id": "wiesner_noisy", "n_qubits": 3, "threshold": 3},
        {"shots": 20001},
        {"trials": 5001},
        {"noise": {"channel": "none", "strength": 0.1}},
        {"noise": {"channel": "bit_flip", "strength": 0.1}},
        {"unknown": 1},
    ],
)
def test_mint_validation(client: TestClient, body: dict) -> None:
    r = client.post("/api/v1/lab/mint", json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


# --------------------------------------------------------------------------- attack

W1_PER_QUBIT = {
    "A01_basis_guess_resend": 5 / 8,
    "A01b_basis_guess_bayes_resend": 0.6545084971874737,
    "A02_breidbart_resend": 5 / 8,
    "A02b_breidbart_bayes_resend": 0.6545084971874737,
    "A03_universal_buzek_hillery": 2 / 3,
    "A03b_phase_covariant_xz": (3 + 2 * math.sqrt(2)) / 8,
    "A04_mvw_optimal_channel": 3 / 4,
}


@pytest.mark.parametrize("attack", sorted(W1_PER_QUBIT))
def test_w1_attacks_exact_mc_and_theorem(client: TestClient, attack: str) -> None:
    n = 3
    d = _post(client, "attack", {"attack": attack, "n": n, "trials": 1500, "seed": 5, "include_sdp": False})["data"]
    assert d["game_id"] == "W1" and d["proof_applicability"] == "IN_MODEL"
    cs = {q["id"]: q for q in d["counterfeit_success"]}
    exact = W1_PER_QUBIT[attack] ** n
    assert math.isclose(cs["counterfeit_exact"]["value"], exact, rel_tol=1e-9)
    assert "LOWER bound" in cs["counterfeit_exact"]["note"]
    mc = cs["counterfeit_mc"]
    assert mc["evidence_kind"] == "MONTE_CARLO" and mc["interval"]["lo"] <= exact <= mc["interval"]["hi"]
    th = d["theorem_bound"]
    assert th["evidence_kind"] == "PUBLISHED_THEOREM" and math.isclose(th["value"], 0.75**n)
    assert exact <= th["value"] + 1e-12
    assert d["single_copy_pass"]["value"] >= exact
    assert d["attack_result"]["game_id"] == "W1" and d["attack_result"]["trials"] == 1500
    assert d["sdp"] is None


def test_measure_resend_single_copy_is_three_quarters(client: TestClient) -> None:
    d = _post(client, "attack", {"attack": "A01_basis_guess_resend", "n": 1, "trials": 0})["data"]
    assert math.isclose(d["single_copy_pass"]["value"], 0.75)
    assert math.isclose(d["counterfeit_success"][0]["value"], 0.625)
    assert [q["id"] for q in d["counterfeit_success"]] == ["counterfeit_exact"] and d["attack_result"] is None


@pytest.mark.parametrize(
    ("attack", "applicability", "game"),
    [
        ("A06_split_and_report_loss", "NO_THEOREM", "W2"),
        ("A08_adaptive_oracle_probe", "OUT_OF_MODEL", "W1"),
        ("CTRL_secret_leak", "OUT_OF_MODEL", "W1"),
    ],
)
def test_out_of_model_attacks_have_no_theorem(client: TestClient, attack: str, applicability: str, game: str) -> None:
    d = _post(client, "attack", {"attack": attack, "n": 4, "trials": 200, "seed": 2})["data"]
    assert d["proof_applicability"] == applicability and d["game_id"] == game
    assert d["theorem_bound"]["value"] is None and d["theorem_bound"]["evidence_kind"] == "UNCERTIFIED"
    assert d["sdp"] is None
    cs = {q["id"]: q for q in d["counterfeit_success"]}
    assert cs["counterfeit_exact"]["value"] > 0.75**4  # beats the W1 number -- because the game differs
    iv = cs["counterfeit_mc"]["interval"]
    assert iv["lo"] - 1e-9 <= cs["counterfeit_exact"]["value"] <= iv["hi"] + 1e-9
    assert d["attack_result"]["proof_applicability"] == applicability


def test_sdp_bracket(client: TestClient) -> None:
    for n in (1, 2):
        s = _post(client, "attack", {"attack": "A04_mvw_optimal_channel", "n": n, "trials": 0})["data"]["sdp"]
        assert s["status"] == "OK"
        lo, up, ind = s["lower"]["value"], s["upper_certified"]["value"], s["upper_independent"]["value"]
        assert lo == 0.75**n == ind and lo <= up <= lo + 1e-9
        assert s["upper_certified"]["evidence_kind"] == "CERTIFIED_NUMERIC"
        assert s["numerical"]["evidence_kind"] == "NUMERICAL_SDP" and s["numerical"]["method"] == "numerical_sdp"
    s3 = _post(client, "attack", {"attack": "A04_mvw_optimal_channel", "n": 3, "trials": 0})["data"]["sdp"]
    assert s3["status"] == "UNSUPPORTED" and "64" in s3["reason"] and s3["upper_certified"] is None


def test_attack_quantities_well_formed(client: TestClient) -> None:
    body = _post(client, "attack", {"attack": "A03b_phase_covariant_xz", "n": 2, "trials": 300,
                                    "noise": {"channel": "dephasing", "strength": 0.2}})
    for q in _quantities(body["data"]):
        assert q["value"] is None or 0.0 <= q["value"] <= 1.0 + 1e-12
        if q["method"] == "monte_carlo":
            assert q["interval"] is not None
    hw = body["data"]["hardware"]
    assert hw["evidence_kind"] == "QPU" and hw["value"] is None and "not run" in hw["note"]
    assert any("honest holder only" in n for n in body["data"]["notes"])
    honest = body["data"]["honest_acceptance"][0]["value"]
    assert math.isclose(honest, (1 - 0.1) ** 2)  # dephasing p: X-basis error p, Z none -> mean error p/2


@pytest.mark.parametrize(
    "body",
    [
        {"n": 0},
        {"n": 9},
        {"trials": 5001},
        {"attack": "A08_adaptive_oracle_probe", "trials": 401},
        {"attack": "A05_unknown"},
        {"probes": 17},
        {"max_error_fraction": 0.6},
    ],
)
def test_attack_validation(client: TestClient, body: dict) -> None:
    r = client.post("/api/v1/lab/attack", json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_deadline_returns_504(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lab, "REQUEST_DEADLINE_S", 0.0)
    r = client.post("/api/v1/lab/attack", json={"attack": "A01_basis_guess_resend", "n": 8, "trials": 5000})
    assert r.status_code == 504
    assert r.json()["error"]["code"] == "timeout"
