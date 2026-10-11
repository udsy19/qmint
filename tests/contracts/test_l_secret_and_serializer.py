"""Lane L boundary regressions: strict serialization default and secret leakage.

Covers: canonical serializer refuses NaN/secrets by default; record store refuses
unknown fields, IssuerSecret, TEST_ONLY revelations and credential values; structured
logs redact secrets; `qmint doctor` reports credential presence as booleans only.
"""

import io
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from qmint.core.contracts import IssuerSecret, SecretBoundaryError
from qmint.core.logging import REDACTED, get_logger, log_event, redact
from qmint.core.records import Provenance, RecordStore
from qmint.core.serialization import canonical_json

ROOT = Path(__file__).resolve().parents[2]
SENTINEL = "sk-qmint-SENTINEL-0123456789"
FIX = ROOT / "tests" / "fixtures" / "contracts"


@pytest.fixture
def secret():
    return IssuerSecret(token_id="t1", protocol_id="wiesner_ideal", bases=["Z", "X"], bits=[0, 1])


@pytest.fixture
def store(tmp_path):
    return RecordStore(tmp_path / "experiments")


@pytest.fixture
def prov():
    return Provenance(git_sha="a" * 40, environment_lock="b" * 64, command="pytest", seed=1)


def _benchmark(**config):
    return {
        "record_id": "b1", "protocol_id": "classical_h1_online_ledger", "classical_or_quantum": "classical",
        "security_target": {}, "trust_model": "t", "pre_distribution": "none", "spending_flexibility": "none",
        "privacy_game": "none", "network_id": "n", "site_count": 1, "method": "m", "configuration": config,
        "evidence_kind": "SYNTHETIC", "git_sha": "a" * 40, "environment_lock": "b" * 64,
    }


# ----------------------------------------------------------- strict serializer default


def test_canonical_json_strict_by_default(secret):
    assert canonical_json({"b": 1, "a": [2, 1]}) == '{"a":[2,1],"b":1}'
    with pytest.raises(ValueError):
        canonical_json({"x": math.nan})
    with pytest.raises(SecretBoundaryError):
        canonical_json({"nested": [secret]})


def test_store_rejects_unknown_fields_and_nan(store, prov):
    with pytest.raises(ValidationError):
        store.append("benchmark", {**_benchmark(), "unexpected": 1}, provenance=prov)
    with pytest.raises(ValueError):
        store.append("benchmark", _benchmark(x=math.inf), provenance=prov)
    assert not store.results_dir.exists() or not any(store.results_dir.iterdir())


# ----------------------------------------------------------- secret leakage


def test_issuer_secret_never_written_to_records(store, prov, secret):
    with pytest.raises(SecretBoundaryError):
        store.append("benchmark", _benchmark(leak=secret), provenance=prov)
    with pytest.raises(SecretBoundaryError):
        store.append("benchmark", _benchmark(leak=secret.reveal_for_testing_only()), provenance=prov)
    assert not store.registry.exists()
    assert not store.results_dir.exists() or not any(store.results_dir.iterdir())


def test_credential_env_value_never_written_to_records(store, prov, monkeypatch):
    monkeypatch.setenv("IONQ_API_KEY", SENTINEL)
    with pytest.raises(SecretBoundaryError):
        store.append("benchmark", _benchmark(note=f"key={SENTINEL}"), provenance=prov)
    assert not store.registry.exists()


def test_log_redaction(monkeypatch, secret):
    monkeypatch.setenv("IONQ_API_KEY", SENTINEL)
    buf = io.StringIO()
    log = get_logger("qmint.test", stream=buf)
    log_event(log, f"calling backend with {SENTINEL}", api_key="plain", bases=["Z"], bits=[1], password="pw",
              token_id="tok-public", issuer=secret, header=f"Authorization: Bearer {SENTINEL}xyz",
              nested={"verifier_key": "k", "ok": [SENTINEL]})
    out = buf.getvalue()
    assert SENTINEL not in out and "plain" not in out and '"pw"' not in out
    rec = json.loads(out)
    f = rec["fields"]
    assert f["api_key"] == f["bases"] == f["bits"] == f["password"] == REDACTED
    assert f["token_id"] == "tok-public"  # public identifiers survive
    assert f["issuer"] == "<IssuerSecret REDACTED>"
    assert f["nested"] == {"verifier_key": REDACTED, "ok": [REDACTED]}
    assert REDACTED in rec["event"]


def test_redact_handles_exception_text(monkeypatch):
    monkeypatch.setenv("MY_SERVICE_TOKEN", SENTINEL)
    assert SENTINEL not in redact(RuntimeError(f"auth failed for {SENTINEL}"))


def test_doctor_reports_secret_presence_as_boolean_only():
    env = {**__import__("os").environ, "IONQ_API_KEY": SENTINEL}
    r = subprocess.run([sys.executable, "-m", "qmint.cli", "doctor", "--json"], cwd=ROOT, capture_output=True,
                       text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert SENTINEL not in r.stdout + r.stderr
    assert json.loads(r.stdout)["secrets_present"]["IONQ_API_KEY"] is True


def test_nested_issuer_secret_in_contract_model_refused(store, prov, secret):
    """Regression: frozen canonical_json leaks a secret nested in an Any field (see handoff L-L1);
    the record store must refuse it independently."""
    from qmint.core.contracts import SecurityCertificate
    from qmint.core.records import contains_issuer_secret

    cert = SecurityCertificate(protocol_id="wiesner_ideal", game_id="W1", security_model_id="m", reason="r",
                               parameters={"leak": secret})
    assert contains_issuer_secret(cert)
    with pytest.raises(SecretBoundaryError):
        store.append("certificate", cert, provenance=prov)
    assert not store.registry.exists()


def test_frozen_canonical_json_refuses_nested_secret(secret):
    from qmint.core.contracts import SecurityCertificate

    cert = SecurityCertificate(protocol_id="wiesner_ideal", game_id="W1", security_model_id="m", reason="r",
                               parameters={"leak": secret})
    with pytest.raises(SecretBoundaryError):
        canonical_json(cert)


def test_log_redaction_walks_models(secret):
    from qmint.core.contracts import SecurityCertificate

    cert = SecurityCertificate(protocol_id="wiesner_ideal", game_id="W1", security_model_id="m", reason="r",
                               parameters={"leak": secret, "bases": ["X"], "n": 3})
    out = redact({"cert": cert})["cert"]
    assert out["parameters"] == {"leak": "<IssuerSecret REDACTED>", "bases": REDACTED, "n": 3}
