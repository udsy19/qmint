"""Lane J tests: no paid calls, no secret logging, SKIPPED not fake success, explicit bit order."""

import importlib.util
import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from qmint.core.contracts import EvidenceKind
from qmint.quantum import ionq
from qmint.quantum.ionq import (
    APPROVAL_TOKEN_ENV,
    PAID_HARDWARE_FLAG_ENV,
    BackendRunRecord,
    RunStatus,
    api_key_present,
    build_bb84_prepare_verify,
    build_dry_run,
    decode_bitstring,
    decode_counts,
    estimate_costs,
    gate_counts,
    probe_backend,
    request_ionq_run,
    run_local_aer,
    verify_pass_count,
    wilson_interval,
)

ROOT = Path(__file__).resolve().parents[3]
FAKE_KEY = "sk-FAKE-do-not-log-0123456789abcdef"
NO_KEY: dict[str, str] = {}
WITH_KEY = {"IONQ_API_KEY": FAKE_KEY}

needs_aer = pytest.mark.skipif(importlib.util.find_spec("qiskit_aer") is None, reason="qiskit-aer absent")


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Any attempt to open a socket or construct the IonQ provider fails the test."""
    import socket

    def boom(*a, **k):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket.socket, "connect", boom)
    if importlib.util.find_spec("qiskit_ionq") is not None:
        import qiskit_ionq

        monkeypatch.setattr(qiskit_ionq.IonQProvider, "__init__", boom)


# ---------------------------------------------------------------- credentials


def test_key_presence_is_boolean_only():
    assert api_key_present(NO_KEY) is False
    assert api_key_present({"IONQ_API_KEY": "  "}) is False
    for name in ionq.IONQ_KEY_ENV_VARS:
        assert api_key_present({name: FAKE_KEY}) is True


def test_no_secret_in_probe_dry_run_or_logs(caplog):
    caplog.set_level(logging.DEBUG)
    env = {**WITH_KEY, PAID_HARDWARE_FLAG_ENV: "1"}
    blob = json.dumps(probe_backend(env)) + json.dumps(build_dry_run([0, 1], "ZX", env=env))
    assert FAKE_KEY not in blob
    assert FAKE_KEY not in caplog.text


# ---------------------------------------------------------------- probe


def test_probe_without_key_skips_everything_cloud():
    p = probe_backend(NO_KEY)
    assert p["api_key_present"] is False
    assert p["ionq_cloud_simulator"] == "SKIPPED"
    assert p["ionq_qpu"] == "SKIPPED"
    assert p["submission_enabled_in_this_build"] is False
    names = {b["backend"]: b for b in p["public_backends"]}
    assert names["qpu.forte-1"]["qubits"] == 36
    assert names["qpu.aria-1"]["status"] == "retired"
    assert p["documented_limits"]["max_shots_per_job_api"]["value"] == 1_000_000


def test_probe_with_key_still_refuses_qpu():
    p = probe_backend(WITH_KEY, fetch_public_backends=lambda: [{"backend": "simulator", "qubits": 29}])
    assert p["ionq_qpu"] == "REFUSED"
    assert p["public_backends_source"].startswith("live")


# ---------------------------------------------------------------- submission gate


def _plan(env):
    return build_dry_run([1, 0, 1], "XZZ", shots=200, env=env)


def test_no_key_gives_skipped_not_success():
    sub = _plan(NO_KEY)["submission"]
    assert sub["status"] == "SKIPPED"
    assert sub["job_id"] is None and sub["counts"] is None and sub["evidence_kind"] == "UNCERTIFIED"


def test_key_without_approval_refused():
    sub = _plan(WITH_KEY)["submission"]
    assert sub["status"] == "REFUSED" and "missing human approval" in sub["reason"]


def test_flag_without_token_refused():
    env = {**WITH_KEY, PAID_HARDWARE_FLAG_ENV: "1"}
    plan = _plan(env)
    assert plan["approval_required"]["paid_hardware_flag_set"] is True
    assert plan["approval_required"]["approval_token_matches_plan"] is False
    assert plan["submission"]["status"] == "REFUSED"


def test_full_approval_still_refused_in_this_build():
    plan = _plan(NO_KEY)
    env = {**WITH_KEY, PAID_HARDWARE_FLAG_ENV: "1", APPROVAL_TOKEN_ENV: plan["approval_token"]}
    rec = request_ionq_run(plan, env)
    assert rec.status is RunStatus.REFUSED and "disabled in this build" in rec.reason
    assert (
        build_dry_run([1, 0, 1], "XZZ", shots=200, env=env)["approval_required"][
            "approval_token_matches_plan"
        ]
        is True
    )


def test_token_bound_to_plan():
    a = build_dry_run([1, 0], "ZX", shots=100, env=NO_KEY)
    b = build_dry_run([1, 0], "ZX", shots=101, env=NO_KEY)
    c = build_dry_run([1, 1], "ZX", shots=100, env=NO_KEY)
    assert len({a["approval_token"], b["approval_token"], c["approval_token"]}) == 3


def test_dry_run_rejects_out_of_range_shots():
    with pytest.raises(ValueError):
        build_dry_run([0], "Z", shots=0, env=NO_KEY)
    with pytest.raises(ValueError):
        build_dry_run([0], "Z", shots=1_000_001, env=NO_KEY)


# ---------------------------------------------------------------- cost


def test_gate_counts_and_costs():
    qc = build_bb84_prepare_verify([1, 1, 0], "XZX")
    # prep: x,h (q0) + x (q1) + h (q2); verify: h (q0), h (q2) -> 6 one-qubit gates
    assert gate_counts(qc) == {"one_qubit": 6, "two_qubit": 0, "measurements": 3}
    c = estimate_costs(6, 0, 1000, error_mitigation=False)
    az = c["azure_quantum_forte_1_usd"]
    assert az["gate_shot_part"] == pytest.approx(6 * 1000 * 0.0001645)
    assert az["rounded_up_to_minimum_interpretation"] == pytest.approx(25.7899)
    assert az["formula_as_printed_additive_minimum"] == pytest.approx(25.7899 + 0.987)
    assert c["aws_braket_forte_usd"]["total"] == pytest.approx(0.30 + 80.0)
    assert c["aws_braket_forte_usd"]["billed_shots"] == 1000
    assert estimate_costs(6, 0, 1000, True)["aws_braket_forte_usd"]["billed_shots"] == 2500
    assert c["ionq_direct_usd"]["total"] is None  # unknown is None, never 0


def test_multiqubit_gate_billing_rule():
    from qiskit import QuantumCircuit

    qc = QuantumCircuit(4)
    qc.mcx([0, 1, 2], 3)  # N=4 qubits -> 6*(4-2)=12 2Q gates
    qc.cx(0, 1)
    assert gate_counts(qc)["two_qubit"] == 13


# ---------------------------------------------------------------- bit order


def test_decode_bitstring_conventions():
    # qubit0=1, qubit1=0, qubit2=0
    assert decode_bitstring("001", 3, "qiskit_clbit0_rightmost") == (1, 0, 0)
    assert decode_bitstring("100", 3, "ionq_q0_leftmost") == (1, 0, 0)
    assert decode_bitstring("0 01", 3, "qiskit_clbit0_rightmost") == (1, 0, 0)
    with pytest.raises(ValueError):
        decode_bitstring("01", 3, "ionq_q0_leftmost")
    with pytest.raises(ValueError):
        decode_bitstring("012", 3, "ionq_q0_leftmost")
    with pytest.raises(ValueError):
        decode_bitstring("010", 3, "big_endian")  # type: ignore[arg-type]


def test_decode_counts_merges_and_verify_pass():
    counts = {"001": 90, "000": 10}
    assert decode_counts(counts, 3, "qiskit_clbit0_rightmost") == {(1, 0, 0): 90, (0, 0, 0): 10}
    assert verify_pass_count(counts, [1, 0, 0], "qiskit_clbit0_rightmost") == (90, 100)
    # the same counts read with the wrong convention would score 10/100: order matters
    assert verify_pass_count(counts, [1, 0, 0], "ionq_q0_leftmost") == (0, 100)


@needs_aer
@pytest.mark.parametrize(
    "bits,bases", [([1, 0, 0, 1], "ZZXX"), ([0, 1, 1, 0, 1, 0, 0, 1], "XZXZXZXZ"), ([1], "X")]
)
def test_ideal_aer_honest_verify_is_deterministic(bits, bases):
    qc = build_bb84_prepare_verify(bits, bases)
    rec = run_local_aer(qc, shots=256, seed=11)
    assert rec.evidence_kind is EvidenceKind.SIMULATOR_IDEAL
    assert verify_pass_count(rec.counts, bits, rec.bit_order) == (256, 256)
    assert len(rec.counts) == 1


@needs_aer
def test_wrong_basis_gives_uniform_bit():
    qc = build_bb84_prepare_verify([0], "X", verify_bases="Z")
    rec = run_local_aer(qc, shots=4000, seed=3)
    p0 = rec.counts.get("0", 0) / 4000
    assert 0.45 < p0 < 0.55


@needs_aer
def test_noisy_aer_labelled_and_lower():
    bits = [1, 0, 1, 1, 0, 0, 1, 0]
    qc = build_bb84_prepare_verify(bits, "ZXZXZXZX")
    rec = run_local_aer(qc, shots=2000, seed=5, noisy=True)
    assert rec.evidence_kind is EvidenceKind.SIMULATOR_NOISY and "not IonQ-calibrated" in rec.noise_model
    k, n = verify_pass_count(rec.counts, bits, rec.bit_order)
    ci = wilson_interval(k, n)
    assert ci.hi < 1.0 and ci.lo > 0.8


# ---------------------------------------------------------------- provenance


def _done(**kw):
    base = dict(
        status=RunStatus.COMPLETED,
        requested_backend="qpu.forte-1",
        executed_backend="qpu.forte-1",
        backend_is_simulator=False,
        evidence_kind=EvidenceKind.QPU,
        job_id="j-1",
        completed_utc="2026-10-11T00:00:00+00:00",
        shots=10,
        counts={"0": 10},
        bit_order="qiskit_clbit0_rightmost",
    )
    base.update(kw)
    return BackendRunRecord(**base)


def test_completed_qpu_record_valid():
    assert _done().job_id == "j-1"


@pytest.mark.parametrize(
    "kw",
    [
        {"executed_backend": "simulator", "backend_is_simulator": True},  # silent fallback
        {"backend_is_simulator": True},  # QPU evidence from a simulator
        {"job_id": None},
        {"completed_utc": None},
        {"counts": {"0": 9}},  # counts must sum to shots
        {"bit_order": None},
        {"evidence_kind": EvidenceKind.SIMULATOR_IDEAL},  # sim kind on non-sim backend
        {"evidence_kind": EvidenceKind.MONTE_CARLO},
    ],
)
def test_completed_record_rejects_bad_provenance(kw):
    with pytest.raises(ValidationError):
        _done(**kw)


def test_noisy_sim_requires_noise_model():
    with pytest.raises(ValidationError):
        _done(
            requested_backend="s",
            executed_backend="s",
            backend_is_simulator=True,
            evidence_kind=EvidenceKind.SIMULATOR_NOISY,
        )


@pytest.mark.parametrize("status", [RunStatus.SKIPPED, RunStatus.REFUSED])
def test_skipped_cannot_carry_results(status):
    with pytest.raises(ValidationError):
        BackendRunRecord(
            status=status,
            requested_backend="qpu.forte-1",
            evidence_kind=EvidenceKind.UNCERTIFIED,
            reason="x",
            job_id="fake",
        )
    with pytest.raises(ValidationError):
        BackendRunRecord(
            status=status, requested_backend="qpu.forte-1", evidence_kind=EvidenceKind.QPU, reason="x"
        )
    with pytest.raises(ValidationError):
        BackendRunRecord(
            status=status,
            requested_backend="qpu.forte-1",
            evidence_kind=EvidenceKind.UNCERTIFIED,
            counts={"0": 1},
        )


def test_failed_requires_job_and_error_no_counts():
    with pytest.raises(ValidationError):
        BackendRunRecord(
            status=RunStatus.FAILED, requested_backend="q", evidence_kind=EvidenceKind.QPU, job_id="j"
        )
    with pytest.raises(ValidationError):
        BackendRunRecord(
            status=RunStatus.FAILED,
            requested_backend="q",
            evidence_kind=EvidenceKind.QPU,
            job_id="j",
            error="e",
            counts={"0": 1},
        )


# ---------------------------------------------------------------- standalone + qollab export


def _load_standalone():
    spec = importlib.util.spec_from_file_location("bb84_standalone", ROOT / "qollab" / "bb84_standalone.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("bits,bases", [("0110", "ZXXZ"), ("1", "X"), ("10110010", "XXZZXZXZ")])
def test_standalone_matches_package_circuit(bits, bases):
    """Intentional duplicate (self-contained export): guard against drift."""
    from qiskit import qasm3

    sa = _load_standalone().build(bits, bases)
    pk = build_bb84_prepare_verify([int(b) for b in bits], bases)
    assert qasm3.dumps(sa) == qasm3.dumps(pk)


def test_standalone_decode_key():
    sa = _load_standalone()
    assert sa.decode_key("001") == "100"
    assert sa.decode_key("100", ionq_raw=True) == "100"


@needs_aer
def test_standalone_cli_runs_locally():
    out = subprocess.run(
        [
            sys.executable,
            str(ROOT / "qollab" / "bb84_standalone.py"),
            "--bits",
            "011",
            "--bases",
            "ZXZ",
            "--shots",
            "64",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    doc = json.loads(out.stdout)
    assert doc["counts_qubit_order"] == {"011": 64} and doc["verify_pass_fraction"] == 1.0


def test_qollab_export_bundle(tmp_path):
    from qmint.core.contracts import EvidenceManifest
    from qmint.core.serialization import file_sha256
    from qmint.quantum.qollab import export_bundle

    doc = export_bundle([1, 0], "XZ", tmp_path)
    m = EvidenceManifest.model_validate(doc["evidence_manifest"])
    for e in m.entries:
        assert file_sha256(tmp_path / e.path_or_uri) == e.sha256
    assert doc["platform_integration"]["status"] == "BLOCKED"
    assert (tmp_path / "bb84_prepare_verify.qasm").read_text().startswith("OPENQASM 3")
    assert json.loads((tmp_path / "manifest.json").read_text())["circuit"]["n_qubits"] == 2


@needs_aer
def test_cli_writes_evidence_without_submitting(tmp_path, monkeypatch):
    for name in ionq.IONQ_KEY_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    assert ionq.main(["--out", str(tmp_path), "--shots", "100"]) == 0
    for f in ("probe.json", "dry_run_1q.json", "dry_run_8q.json", "local_aer_runs.json"):
        assert (tmp_path / f).is_file()
    runs = json.loads((tmp_path / "local_aer_runs.json").read_text())
    assert runs["ideal"]["verify_pass"]["successes"] == 100
    assert json.loads((tmp_path / "dry_run_8q.json").read_text())["submission"]["status"] == "SKIPPED"
