"""Optional IonQ backend adapter: probe, BB84 prepare/verify circuit, dry-run cost, provenance.

Lane J (master plan section 7 "J1", X15, G6). Hard guarantees of this module:

* It never submits a job to IonQ (QPU *or* cloud simulator). ``request_ionq_run`` always returns
  ``SKIPPED`` (no credentials / no provider) or ``REFUSED`` (credentials present but this build has
  submission disabled). Paid execution is a human-only step documented in ``HUMAN_RUN_PROCEDURE``.
* It never reads, returns or logs the value of an API key; only ``bool`` presence is exposed.
* It never falls back from a requested device to a simulator: a ``BackendRunRecord`` whose
  executed backend differs from the requested backend, or whose evidence kind does not match the
  backend class, fails validation.
* Counts are decoded with an explicit, named bit-order convention (C7: no implicit Qiskit
  little-endian decoding).

Sources for every documented limit/price are in ``qollab/evidence/sources.json`` (retrieved
2026-10-11) and repeated in ``DOCUMENTED_LIMITS`` / ``PRICE_TABLES`` below.
"""

from __future__ import annotations

import hmac
import importlib.metadata
import importlib.util
import json
import os
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from qmint.core.contracts import Basis, EvidenceKind, Interval, Unit, _Strict
from qmint.core.serialization import canonical_hash
from qmint.quantum.bb84 import state_label
from qmint.quantum.circuits import build_prepare_circuit

# --------------------------------------------------------------------------- #
# Configuration names (values are never read into logs or return values)
# --------------------------------------------------------------------------- #

# Same names, same precedence family as qiskit-ionq 1.1.1 helpers.resolve_credentials.
IONQ_KEY_ENV_VARS: tuple[str, ...] = ("IONQ_API_KEY", "QISKIT_IONQ_API_TOKEN", "IONQ_API_TOKEN")
PAID_HARDWARE_FLAG_ENV = "QMINT_ALLOW_PAID_HARDWARE"
APPROVAL_TOKEN_ENV = "QMINT_PAID_RUN_APPROVAL_TOKEN"

# Hard-coded off. Enabling paid submission is a lead-reviewed code change, not a runtime toggle.
SUBMISSION_ENABLED_IN_THIS_BUILD = False

EVIDENCE_DIR = Path(__file__).resolve().parents[2] / "qollab" / "evidence"
BACKENDS_SNAPSHOT = EVIDENCE_DIR / "ionq_backends_v0.4_snapshot.json"
SOURCES_RETRIEVED_UTC = "2026-10-11T21:12:02Z"


class RunStatus(str, Enum):
    COMPLETED = "COMPLETED"  # a job actually ran and returned counts
    SKIPPED = "SKIPPED"  # provider/credentials unavailable: nothing ran
    REFUSED = "REFUSED"  # preconditions present but submission refused by policy
    FAILED = "FAILED"  # a job was submitted and errored (job id known)


# --------------------------------------------------------------------------- #
# Documented limits and prices (cited; not measured by us)
# --------------------------------------------------------------------------- #

DOCUMENTED_LIMITS: dict[str, Any] = {
    "max_shots_per_job_api": {
        "value": 1_000_000,
        "source": "https://docs.ionq.com/api-reference/v0.4/jobs/create-job (shots: min 1, max 1000000)",
    },
    "max_shots_qiskit_ionq_qpu_backend": {
        "value": 10_000,
        "source": "qiskit-ionq 1.1.1 ionq_backend.IonQQPUBackend(max_shots=10_000)",
    },
    "qubits": {
        "value": {"qpu.forte-1": 36, "qpu.forte-enterprise-1": 36, "simulator": 29},
        "source": "https://api.ionq.co/v0.4/backends (snapshot qollab/evidence/ionq_backends_v0.4_snapshot.json)",
    },
    "mid_circuit_measurement": {
        "value": "simulator: supported; QPU: target-dependent (fails preflight with UnsupportedFeature, "
        "no execution charge); dynamic circuits (loops/branches): not supported on any target",
        "source": "https://docs.ionq.com/api-reference/v0.4/openqasm3",
    },
    "result_bit_order_ionq_openqasm3": {
        "value": "q[0] is the leftmost character of the bitstring",
        "source": "https://docs.ionq.com/api-reference/v0.4/openqasm3",
    },
    "debiasing_min_shots": {
        "value": 500,
        "source": "https://docs.ionq.com/api-reference/v0.4/jobs/create-job; default-on at >=500 shots per "
        "https://docs.ionq.com/guides/job-cost-and-usage",
    },
    "cloud_simulator_requires_api_key": {
        "value": True,
        "source": "job creation requires 'Authorization: apiKey <key>' "
        "(https://docs.ionq.com/api-reference/v0.4/jobs/create-job)",
    },
}

# Reseller price lists. IonQ-direct rates are NOT published (job-cost guide: rates vary by agreement).
PRICE_TABLES: dict[str, dict[str, Any]] = {
    "azure_quantum_forte_1": {
        "currency": "USD",
        "per_1q_gate_shot": 0.0001645,
        "per_2q_gate_shot": 0.001121,
        "min_per_program_error_mitigation_on": 168.195,
        "min_per_program_error_mitigation_off": 25.7899,
        "source": "https://learn.microsoft.com/azure/quantum/pricing (page updated_at 2026-04-23)",
    },
    "aws_braket_forte": {
        "currency": "USD",
        "per_task": 0.30,
        "per_shot": 0.08,
        "error_mitigation_min_shots": 2500,
        "source": "https://aws.amazon.com/braket/pricing/",
    },
    "ionq_direct": {
        "currency": "USD",
        "rate_card": None,
        "note": "not published; use POST /jobs/estimate or dry_run + GET /jobs/{id}/cost with an API key",
        "source": "https://docs.ionq.com/guides/job-cost-and-usage",
    },
}


# --------------------------------------------------------------------------- #
# Credential presence (boolean only)
# --------------------------------------------------------------------------- #


def api_key_present(env: Mapping[str, str] | None = None) -> bool:
    """True iff a non-empty IonQ key is in the process environment. Never returns the value."""
    env = os.environ if env is None else env
    return any(bool(env.get(name, "").strip()) for name in IONQ_KEY_ENV_VARS)


def _ionq_dotenv_files() -> list[str]:
    """`.env` files qiskit-ionq would read via python-dotenv (searched upward from its package dir).

    Returned as paths only; contents are never opened here.
    """
    spec = importlib.util.find_spec("qiskit_ionq")
    if spec is None or spec.origin is None:
        return []
    found = []
    for d in [Path(spec.origin).parent, *Path(spec.origin).parent.parents]:
        if (d / ".env").is_file():
            found.append(str(d / ".env"))
    return found


def _version(dist: str) -> str | None:
    try:
        return importlib.metadata.version(dist)
    except importlib.metadata.PackageNotFoundError:
        return None


# --------------------------------------------------------------------------- #
# Probe
# --------------------------------------------------------------------------- #


def load_backends_snapshot(path: Path = BACKENDS_SNAPSHOT) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def probe_backend(
    env: Mapping[str, str] | None = None,
    fetch_public_backends: Callable[[], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Describe what IonQ access is possible from here, without authenticating or submitting.

    ``fetch_public_backends`` may perform the unauthenticated GET https://api.ionq.co/v0.4/backends;
    by default the committed snapshot is used (no network). The IonQProvider is deliberately not
    constructed: its constructor issues HTTP requests and resolves credentials from `.env` files.
    """
    key = api_key_present(env)
    provider_installed = importlib.util.find_spec("qiskit_ionq") is not None
    if fetch_public_backends is None:
        backends, backends_source = load_backends_snapshot(), f"snapshot {SOURCES_RETRIEVED_UTC}"
    else:
        backends, backends_source = fetch_public_backends(), "live GET /v0.4/backends"
    cloud_ready = key and provider_installed
    skip_reason = (
        None if cloud_ready else ("no IonQ API key in environment" if not key else "qiskit-ionq missing")
    )
    return {
        "versions": {
            "qiskit": _version("qiskit"),
            "qiskit-aer": _version("qiskit-aer"),
            "qiskit-ionq": _version("qiskit-ionq"),
        },
        "provider_installed": provider_installed,
        "api_key_present": key,
        "dotenv_files_qiskit_ionq_would_read": _ionq_dotenv_files(),
        "public_backends": [
            {k: b.get(k) for k in ("backend", "status", "qubits", "supported_native_gates", "noise_models")}
            for b in backends
        ],
        "public_backends_source": backends_source,
        "ionq_cloud_simulator": RunStatus.SKIPPED.value if not cloud_ready else "AVAILABLE_NOT_USED",
        "ionq_qpu": RunStatus.SKIPPED.value if not cloud_ready else RunStatus.REFUSED.value,
        "skip_reason": skip_reason,
        "local_aer": importlib.util.find_spec("qiskit_aer") is not None,
        "documented_limits": DOCUMENTED_LIMITS,
        "submission_enabled_in_this_build": SUBMISSION_ENABLED_IN_THIS_BUILD,
    }


# --------------------------------------------------------------------------- #
# BB84 prepare/verify circuit and explicit bit-order decoding
# --------------------------------------------------------------------------- #

BitOrder = Literal["qiskit_clbit0_rightmost", "ionq_q0_leftmost"]


def build_bb84_prepare_verify(
    bits: Sequence[int],
    bases: Sequence[Basis | str],
    verify_bases: Sequence[Basis | str] | None = None,
):
    """n-qubit circuit: prepare BB84 states (C7 map) then measure each qubit in `verify_bases`.

    Qubit i is prepared in state_label(bases[i], bits[i]) (C7) and measured into clbit i.
    Measuring in X = H then Z-measure. Default verify basis = preparation basis (honest verify).
    No optimisation is applied, so the gate list is what would be submitted (and billed).
    """
    from qiskit import QuantumCircuit

    n = len(bits)
    if not 1 <= n <= 8 or len(bases) != n:
        raise ValueError("need 1..8 qubits and len(bases) == len(bits)")
    vb = list(bases) if verify_bases is None else list(verify_bases)
    if len(vb) != n:
        raise ValueError("len(verify_bases) != len(bits)")
    qc = QuantumCircuit(n, n, name="bb84_prepare_verify")
    # Preparation gates come from lane F's canonical builder (single source of the C7 map).
    qc.compose(build_prepare_circuit([Basis(b) for b in bases], [int(b) for b in bits]), inplace=True)
    qc.barrier()
    for i, basis in enumerate(vb):
        if Basis(basis) is Basis.X:
            qc.h(i)
        qc.measure(i, i)
    return qc


def decode_bitstring(key: str, n: int, order: BitOrder) -> tuple[int, ...]:
    """Return outcomes indexed by qubit/clbit number (index 0 = qubit 0) under a named convention."""
    s = key.replace(" ", "")
    if len(s) != n or set(s) - {"0", "1"}:
        raise ValueError(f"bitstring {key!r} is not {n} binary digits")
    if order == "qiskit_clbit0_rightmost":
        s = s[::-1]
    elif order != "ionq_q0_leftmost":
        raise ValueError(f"unknown bit order {order!r}")
    return tuple(int(c) for c in s)


def decode_counts(counts: Mapping[str, int], n: int, order: BitOrder) -> dict[tuple[int, ...], int]:
    out: dict[tuple[int, ...], int] = {}
    for k, v in counts.items():
        t = decode_bitstring(k, n, order)
        out[t] = out.get(t, 0) + int(v)
    return out


def verify_pass_count(counts: Mapping[str, int], bits: Sequence[int], order: BitOrder) -> tuple[int, int]:
    """(shots where every qubit returned its prepared bit, total shots). Meaningful for honest verify."""
    decoded = decode_counts(counts, len(bits), order)
    expected = tuple(int(b) for b in bits)
    return decoded.get(expected, 0), sum(decoded.values())


def wilson_interval(successes: int, trials: int, confidence: float = 0.95) -> Interval:
    from scipy.stats import binomtest

    ci = binomtest(successes, trials).proportion_ci(confidence_level=confidence, method="wilson")
    return Interval(lo=float(ci.low), hi=float(ci.high), unit=Unit.FRACTION, point=successes / trials)


# --------------------------------------------------------------------------- #
# Provenance
# --------------------------------------------------------------------------- #

_SIM_KINDS = {EvidenceKind.SIMULATOR_IDEAL, EvidenceKind.SIMULATOR_NOISY}


class BackendRunRecord(_Strict):
    """One backend run attempt. Lane-J local model (no frozen contract covers job-level provenance;
    see migration proposal in handoffs/J-J1.md).

    Invariants: job id / time / shots / counts only for runs that actually happened; SKIPPED and
    REFUSED carry none of them; a QPU record must report the same backend that was requested and
    cannot be a simulator; no silent fallback.
    """

    status: RunStatus
    requested_backend: str = Field(min_length=1)
    executed_backend: str | None = None
    backend_is_simulator: bool | None = None
    evidence_kind: EvidenceKind
    job_id: str | None = None
    completed_utc: str | None = None
    shots: int | None = Field(default=None, ge=1)
    counts: dict[str, int] | None = None
    bit_order: BitOrder | None = None
    noise_model: str | None = None
    native_gate_counts: dict[str, int] | None = None
    error: str | None = None
    reason: str | None = None
    circuit_sha256: str | None = None

    @model_validator(mode="after")
    def _consistent(self) -> BackendRunRecord:
        ran = (self.job_id, self.completed_utc, self.shots, self.counts, self.executed_backend)
        if self.status in (RunStatus.SKIPPED, RunStatus.REFUSED):
            if any(x is not None for x in ran):
                raise ValueError(f"{self.status.value} run must not carry job id/time/shots/counts/backend")
            if self.evidence_kind is not EvidenceKind.UNCERTIFIED:
                raise ValueError("a run that did not happen has evidence_kind UNCERTIFIED")
            if not self.reason:
                raise ValueError("SKIPPED/REFUSED requires a reason")
            return self
        if self.status is RunStatus.FAILED:
            if not (self.job_id and self.error):
                raise ValueError("FAILED requires job_id and error")
            if self.counts is not None:
                raise ValueError("FAILED run must not carry counts")
            return self
        # COMPLETED
        missing = [
            n
            for n, v in zip(
                ("job_id", "completed_utc", "shots", "counts", "executed_backend"), ran, strict=True
            )
            if v is None
        ]
        if missing or self.bit_order is None or self.backend_is_simulator is None:
            raise ValueError(f"COMPLETED run missing {missing or ['bit_order/backend_is_simulator']}")
        if self.executed_backend != self.requested_backend:
            raise ValueError("executed backend differs from requested backend (silent fallback forbidden)")
        if self.evidence_kind is EvidenceKind.QPU and self.backend_is_simulator:
            raise ValueError("QPU evidence from a simulator backend")
        if self.evidence_kind in _SIM_KINDS and not self.backend_is_simulator:
            raise ValueError("simulator evidence kind on a non-simulator backend")
        if self.evidence_kind not in _SIM_KINDS | {EvidenceKind.QPU}:
            raise ValueError("COMPLETED run must be QPU or SIMULATOR_* evidence")
        if self.evidence_kind is EvidenceKind.SIMULATOR_NOISY and not self.noise_model:
            raise ValueError("SIMULATOR_NOISY requires a declared noise_model")
        if sum(self.counts.values()) != self.shots:  # type: ignore[union-attr]
            raise ValueError("counts do not sum to shots")
        return self


# --------------------------------------------------------------------------- #
# Local Aer execution (free; the only execution this module performs)
# --------------------------------------------------------------------------- #

# Hypothetical, NOT calibrated to any IonQ device (F3 owns calibrated noise).
DEFAULT_NOISE = {"p1_depolarizing": 0.001, "readout_flip": 0.01}


def _aer_noise_model(p1: float, readout: float):
    from qiskit_aer.noise import NoiseModel, ReadoutError, depolarizing_error

    nm = NoiseModel()
    nm.add_all_qubit_quantum_error(depolarizing_error(p1, 1), ["x", "h"])
    nm.add_all_qubit_readout_error(ReadoutError([[1 - readout, readout], [readout, 1 - readout]]))
    return nm


def run_local_aer(
    qc, shots: int, seed: int, noisy: bool = False, noise: Mapping[str, float] = DEFAULT_NOISE
) -> BackendRunRecord:
    from qiskit_aer import AerSimulator

    nm = _aer_noise_model(noise["p1_depolarizing"], noise["readout_flip"]) if noisy else None
    sim = AerSimulator(noise_model=nm, seed_simulator=seed)
    job = sim.run(qc, shots=shots)
    counts = dict(job.result().get_counts())
    return BackendRunRecord(
        status=RunStatus.COMPLETED,
        requested_backend="local_aer_simulator",
        executed_backend="local_aer_simulator",
        backend_is_simulator=True,
        evidence_kind=EvidenceKind.SIMULATOR_NOISY if noisy else EvidenceKind.SIMULATOR_IDEAL,
        job_id=f"local-aer:{job.job_id()}",
        completed_utc=datetime.now(UTC).isoformat(),
        shots=shots,
        counts=counts,
        bit_order="qiskit_clbit0_rightmost",
        noise_model=(
            f"hypothetical depolarizing(p1={noise['p1_depolarizing']}) on x/h + "
            f"symmetric readout flip {noise['readout_flip']}; not IonQ-calibrated"
        )
        if noisy
        else None,
        circuit_sha256=circuit_sha256(qc),
    )


# --------------------------------------------------------------------------- #
# Dry-run cost estimate and approval gate
# --------------------------------------------------------------------------- #


def circuit_sha256(qc) -> str:
    from qiskit import qasm3

    return canonical_hash(qasm3.dumps(qc))


def gate_counts(qc) -> dict[str, int]:
    """Submitted (logical) gate counts. IonQ bills 1Q/2Q gates; gates on N>=3 qubits as 6(N-2) 2Q gates."""
    n1 = n2 = meas = 0
    for inst in qc.data:
        name, k = inst.operation.name, len(inst.qubits)
        if name in ("barrier", "delay"):
            continue
        if name == "measure":
            meas += 1
        elif k == 1:
            n1 += 1
        elif k == 2:
            n2 += 1
        else:
            n2 += 6 * (k - 2)
    return {"one_qubit": n1, "two_qubit": n2, "measurements": meas}


def estimate_costs(n1q: int, n2q: int, shots: int, error_mitigation: bool) -> dict[str, Any]:
    az = PRICE_TABLES["azure_quantum_forte_1"]
    m = az[
        "min_per_program_error_mitigation_on" if error_mitigation else "min_per_program_error_mitigation_off"
    ]
    gate_part = az["per_1q_gate_shot"] * n1q * shots + az["per_2q_gate_shot"] * n2q * shots
    aws = PRICE_TABLES["aws_braket_forte"]
    aws_shots = max(shots, aws["error_mitigation_min_shots"]) if error_mitigation else shots
    return {
        "azure_quantum_forte_1_usd": {
            "gate_shot_part": round(gate_part, 6),
            "formula_as_printed_additive_minimum": round(m + gate_part, 6),
            "rounded_up_to_minimum_interpretation": round(max(m, gate_part), 6),
            "note": "Azure prints AQT = m + rates*gate-shots; IonQ's guide says cost is rounded up to the "
            "minimum. Both shown; the true invoice is set by the provider.",
            "source": az["source"],
        },
        "aws_braket_forte_usd": {
            "total": round(aws["per_task"] + aws["per_shot"] * aws_shots, 6),
            "billed_shots": aws_shots,
            "source": aws["source"],
        },
        "ionq_direct_usd": {
            "total": None,
            "note": PRICE_TABLES["ionq_direct"]["note"],
            "source": PRICE_TABLES["ionq_direct"]["source"],
        },
    }


def approval_token(plan: Mapping[str, Any]) -> str:
    """Per-run approval token: binds approval to this exact circuit, backend and shots."""
    return (
        "qmint-approve-"
        + canonical_hash(
            {k: plan[k] for k in ("circuit_sha256", "target_backend", "shots", "error_mitigation")}
        )[:24]
    )


def approval_state(plan: Mapping[str, Any], env: Mapping[str, str] | None = None) -> dict[str, bool]:
    env = os.environ if env is None else env
    supplied = env.get(APPROVAL_TOKEN_ENV, "")
    return {
        "paid_hardware_flag_set": env.get(PAID_HARDWARE_FLAG_ENV) == "1",
        "approval_token_supplied": bool(supplied),
        "approval_token_matches_plan": bool(supplied) and hmac.compare_digest(supplied, approval_token(plan)),
    }


HUMAN_RUN_PROCEDURE = [
    "1. Review this dry-run JSON (circuit QASM hash, backend, shots, cost estimates) yourself.",
    "2. Obtain an IonQ API key from https://cloud.ionq.com and export it only in your own shell "
    "(export IONQ_API_KEY=...); never commit it or put it in a .env inside the repo tree.",
    "3. Get a binding quote: submit with dry_run=True (qiskit-ionq >= 1.0.3) and read GET /jobs/{id}/cost, "
    "or POST /jobs/estimate (https://docs.ionq.com/guides/job-cost-and-usage).",
    f"4. export {PAID_HARDWARE_FLAG_ENV}=1 and {APPROVAL_TOKEN_ENV}=<approval_token from this JSON>.",
    "5. A lead-reviewed change must flip SUBMISSION_ENABLED_IN_THIS_BUILD and implement submission via "
    "qiskit_ionq.IonQProvider().get_backend('qpu.forte-1').run(qc, shots=...); record job id, backend, "
    "timestamps, shots, counts (bit order 'qiskit_clbit0_rightmost' via qiskit-ionq) and native gate counts "
    "in a BackendRunRecord with evidence_kind=QPU. Agents must never perform steps 2-5.",
]


def build_dry_run(
    bits: Sequence[int],
    bases: Sequence[Basis | str],
    shots: int = 100,
    target_backend: str = "qpu.forte-1",
    error_mitigation: bool = False,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Dry-run plan for a 1-8 qubit BB84 prepare/verify job. Pure: no network, no submission."""
    if not 1 <= shots <= DOCUMENTED_LIMITS["max_shots_per_job_api"]["value"]:
        raise ValueError("shots outside documented API range")
    qc = build_bb84_prepare_verify(bits, bases)
    g = gate_counts(qc)
    plan: dict[str, Any] = {
        "kind": "qmint.ionq.dry_run",
        "evidence_kind": EvidenceKind.UNCERTIFIED.value,
        "target_backend": target_backend,
        "n_qubits": qc.num_qubits,
        "shots": shots,
        "error_mitigation": error_mitigation,
        "prepared_states": [
            state_label(b, x).value for x, b in zip(bits, bases, strict=True)
        ],
        "circuit_sha256": circuit_sha256(qc),
        "gate_counts_submitted": g,
        "gate_shots": {"one_qubit": g["one_qubit"] * shots, "two_qubit": g["two_qubit"] * shots},
        "cost_estimates": estimate_costs(g["one_qubit"], g["two_qubit"], shots, error_mitigation),
        "prices_retrieved_utc": SOURCES_RETRIEVED_UTC,
    }
    plan["approval_token"] = approval_token(plan)
    plan["approval_required"] = {
        "env_flag": f"{PAID_HARDWARE_FLAG_ENV}=1",
        "env_token": f"{APPROVAL_TOKEN_ENV}=<approval_token>",
        **approval_state(plan, env),
    }
    plan["submission"] = request_ionq_run(plan, env).model_dump(mode="json")
    plan["how_a_human_would_run_it"] = HUMAN_RUN_PROCEDURE
    return plan


def request_ionq_run(plan: Mapping[str, Any], env: Mapping[str, str] | None = None) -> BackendRunRecord:
    """Gatekeeper for IonQ cloud execution. Never submits in this build."""
    backend = str(plan["target_backend"])
    if importlib.util.find_spec("qiskit_ionq") is None:
        reason = "qiskit-ionq not installed"
    elif not api_key_present(env):
        reason = "no IonQ API key in environment"
    else:
        state = approval_state(plan, env)
        if not (state["paid_hardware_flag_set"] and state["approval_token_matches_plan"]):
            why = "missing human approval (flag and matching per-run token required)"
        else:
            why = "human approval present, but submission is disabled in this build/session"
        return BackendRunRecord(
            status=RunStatus.REFUSED,
            requested_backend=backend,
            evidence_kind=EvidenceKind.UNCERTIFIED,
            reason=why,
            circuit_sha256=plan.get("circuit_sha256"),
        )
    return BackendRunRecord(
        status=RunStatus.SKIPPED,
        requested_backend=backend,
        evidence_kind=EvidenceKind.UNCERTIFIED,
        reason=reason,
        circuit_sha256=plan.get("circuit_sha256"),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Write probe, dry-run and local Aer evidence JSON. Never submits to IonQ.

    python -m qmint.quantum.ionq --out qollab/evidence --bits 10110010 --bases ZXZXXZXZ --shots 1000 --seed 7
    """
    import argparse

    ap = argparse.ArgumentParser(prog="qmint.quantum.ionq")
    ap.add_argument("--out", required=True)
    ap.add_argument("--bits", default="10110010")
    ap.add_argument("--bases", default="ZXZXXZXZ")
    ap.add_argument("--shots", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    bits = [int(c) for c in a.bits]

    def dump(name: str, obj: Any) -> None:
        (out / name).write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    dump("probe.json", probe_backend())
    dump("dry_run_1q.json", build_dry_run(bits[:1], a.bases[:1], shots=a.shots))
    dump("dry_run_8q.json", build_dry_run(bits, a.bases, shots=a.shots))
    qc = build_bb84_prepare_verify(bits, a.bases)
    runs = {}
    for noisy in (False, True):
        rec = run_local_aer(qc, shots=a.shots, seed=a.seed, noisy=noisy)
        k, n = verify_pass_count(rec.counts, bits, rec.bit_order)  # type: ignore[arg-type]
        runs["noisy" if noisy else "ideal"] = {
            "record": rec.model_dump(mode="json"),
            "decoded_counts_qubit_order": {
                "".join(map(str, key)): v
                for key, v in sorted(decode_counts(rec.counts, len(bits), rec.bit_order).items())  # type: ignore[arg-type]
            },
            "verify_pass": {
                "successes": k,
                "trials": n,
                "wilson95": wilson_interval(k, n).model_dump(mode="json"),
            },
        }
    dump("local_aer_runs.json", {"bits": a.bits, "bases": a.bases, "seed": a.seed, **runs})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
