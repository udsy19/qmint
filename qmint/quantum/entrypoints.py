"""Lane F (+ J) run_core stage (see ``qmint.core.lanes``): BB84 three-way agreement and local Aer runs.

Offline and seeded. Simulator job ids / completion times (random per run) are dropped from the
stage outputs so they are byte-deterministic; everything is SIMULATOR_* evidence, no hardware.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from qmint.core.lanes import StageSkipped, write_stage_json
from qmint.core.serialization import file_sha256

VOLATILE_KEYS = frozenset({"job_id", "completed_utc"})
AGREEMENT_TOL = 1e-12


def _stable(obj: Any) -> Any:
    """Drop per-run random identifiers (Aer job UUIDs, wall-clock times) recursively."""
    if isinstance(obj, dict):
        return {k: _stable(v) for k, v in obj.items() if k not in VOLATILE_KEYS}
    if isinstance(obj, list):
        return [_stable(v) for v in obj]
    return obj


def run_core_stage(*, seed: int, out_dir: Path) -> dict[str, Any]:
    missing = [m for m in ("qiskit", "qiskit_aer", "qutip") if importlib.util.find_spec(m) is None]
    if missing:
        raise StageSkipped(f"optional quantum dependencies not installed: {missing} (extra [quantum])")
    from qmint.quantum import cloner, ionq
    from qmint.quantum.evidence import aer_noisy_points, three_way_agreement

    tw = three_way_agreement(seed)
    worst = max(max(r["max_abs_diff_qiskit_numpy"], r["max_abs_diff_qutip_numpy"],
                    r.get("max_abs_diff_analytic_numpy", 0.0)) for r in tw)
    if worst > AGREEMENT_TOL:
        raise RuntimeError(f"BB84 analytic/NumPy/QuTiP/Qiskit disagreement {worst:.3e} > {AGREEMENT_TOL}")
    aer = aer_noisy_points(seed, shots=2000)
    if not all(r["analytic_inside_ci"] for r in aer):
        raise RuntimeError("Aer noisy acceptance outside its 99.9% CI around the analytic value")
    src = file_sha256(Path(cloner.__file__))
    cloners = [cloner.simulate_attack(name, 1, 4, 500, seed, source_code_sha=src).model_dump(mode="json")
               for name in ("bruss2000", "mvw2012")]
    bits, bases = [1, 0, 1, 1, 0, 0, 1, 0], "ZXZXXZXZ"
    qc = ionq.build_bb84_prepare_verify(bits, bases)
    j_runs = {}
    for noisy in (False, True):
        rec = ionq.run_local_aer(qc, shots=500, seed=seed, noisy=noisy)
        k, n = ionq.verify_pass_count(rec.counts, bits, rec.bit_order)  # type: ignore[arg-type]
        j_runs["noisy" if noisy else "ideal"] = {"record": rec.model_dump(mode="json"), "verify_pass": [k, n]}
    if j_runs["ideal"]["verify_pass"][0] != j_runs["ideal"]["verify_pass"][1]:
        raise RuntimeError("ideal Aer honest verification rejected a shot")
    res = {
        "x03_three_way_agreement": {"cases": len(tw), "max_abs_diff": worst, "rows": tw},
        "aer_noisy_points": aer,
        "w1_cloner_circuits_aer": cloners,
        "ionq_adapter_local_aer_8q": j_runs,
        "paid_jobs_run": False,
    }
    return {"outputs": [write_stage_json(out_dir, "quantum_core.json", _stable(res))]}
