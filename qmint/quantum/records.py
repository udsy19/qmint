"""Resource counts, backend provenance and binomial confidence intervals (lane F).

``BackendProvenance`` is a lane-internal record (not a frozen contract); it is
serialised with ``qmint.core.serialization.canonical_json``. Gate counts after the
generic transpile below are *not* hardware-native counts (lane J owns those).
"""

from __future__ import annotations

import platform
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from qmint.core.contracts import EvidenceKind, Interval, Unit
from qmint.core.serialization import sha256_hex

GENERIC_BASIS_GATES = ("rz", "sx", "x", "cx")


def clopper_pearson(successes: int, trials: int, confidence: float = 0.99) -> Interval:
    """Exact (Clopper-Pearson) binomial CI as a C7 ``Interval`` in probability units."""
    from scipy.stats import binomtest

    if trials <= 0 or not (0 <= successes <= trials):
        raise ValueError("need 0 <= successes <= trials, trials > 0")
    ci = binomtest(successes, trials).proportion_ci(confidence_level=confidence, method="exact")
    return Interval(lo=float(ci.low), hi=float(ci.high), unit=Unit.PROBABILITY, point=successes / trials)


def circuit_fingerprint(qc: Any) -> str:
    """Deterministic SHA-256 over (gate name, params, qubit indices, clbit indices)."""
    lines = []
    for inst in qc.data:
        op = inst.operation
        qs = [qc.find_bit(q).index for q in inst.qubits]
        cs = [qc.find_bit(c).index for c in inst.clbits]
        params = []
        for p in op.params:
            try:
                params.append(repr(round(float(p), 12)))
            except (TypeError, ValueError):
                params.append(sha256_hex(repr(p).encode()))
        lines.append(f"{op.name}|{','.join(params)}|{qs}|{cs}")
    return sha256_hex(f"{qc.num_qubits}/{qc.num_clbits}\n" + "\n".join(lines))


def resource_counts(qc: Any, transpile_generic: bool = True, seed_transpiler: int = 0) -> dict[str, Any]:
    """Width/depth/gate counts of the logical circuit and (optionally) a generic CX+1q transpile."""
    out: dict[str, Any] = {
        "width_qubits": qc.num_qubits,
        "clbits": qc.num_clbits,
        "depth": qc.depth(),
        "gate_counts": dict(sorted(qc.count_ops().items())),
        "two_qubit_gates": sum(
            1 for i in qc.data if i.operation.num_qubits == 2 and i.operation.name not in ("barrier", "measure")
        ),
    }
    if transpile_generic and not any(i.operation.name in ("kraus", "quantum_channel") for i in qc.data):
        from qiskit import transpile

        t = transpile(qc, basis_gates=list(GENERIC_BASIS_GATES), optimization_level=1, seed_transpiler=seed_transpiler)
        out["generic_transpile"] = {
            "basis_gates": list(GENERIC_BASIS_GATES),
            "optimization_level": 1,
            "note": "generic CX+1q basis, NOT hardware-native gate counts",
            "depth": t.depth(),
            "gate_counts": dict(sorted(t.count_ops().items())),
            "cx_count": int(t.count_ops().get("cx", 0)),
        }
    return out


def software_versions() -> dict[str, str]:
    import numpy
    import qiskit
    import qiskit_aer
    import qutip
    import scipy

    return {
        "python": platform.python_version(),
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
        "qiskit": qiskit.__version__,
        "qiskit_aer": qiskit_aer.__version__,
        "qutip": qutip.__version__,
    }


class BackendProvenance(BaseModel):
    """Who/what produced a number: local simulator identity, settings, circuit hash, resources."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    backend_name: str = Field(min_length=1)
    backend_kind: str = Field(min_length=1)  # "aer_simulator", "qiskit_statevector", "numpy", "qutip"
    evidence_kind: EvidenceKind
    simulator_method: str | None = None
    shots: int | None = None
    seed_simulator: int | None = None
    job_id: str | None = None
    noise_model: str | None = None
    circuit_sha256: str | None = None
    resources: dict[str, Any] = Field(default_factory=dict)
    software: dict[str, str] = Field(default_factory=dict)
    is_hardware: bool = False
    notes: str = ""
