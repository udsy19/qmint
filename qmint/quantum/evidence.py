"""Lane F evidence generator (X03 / X15-local / Figure 10 data). Deterministic seeds.

Usage:  python -m qmint.quantum.evidence <out.json> [git_sha]

Every number in the output carries an ``evidence_kind``:
  SYNTHETIC        analytic curves under hypothetical (uncalibrated) noise / photonic parameters
  SIMULATOR_IDEAL  noiseless Qiskit statevector / Aer sampling
  SIMULATOR_NOISY  Aer sampling under the declared NoiseSpec
No QPU jobs are run here (lane J owns hardware).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from qmint.core.contracts import Basis, EvidenceKind
from qmint.core.serialization import canonical_json
from qmint.quantum import cloner
from qmint.quantum.bb84 import MAX_STATEVECTOR_QUBITS, analytic_outcome_distribution, random_note_secret
from qmint.quantum.channels import (
    NoiseSpec,
    analytic_mean_accept_probability,
    analytic_note_accept_probability,
)
from qmint.quantum.circuits import accepted_shots, build_verify_circuit, qiskit_exact_distribution, run_aer
from qmint.quantum.photonic_model import (
    PhotonicLinkParams,
    click_statistics,
    multiphoton_fraction,
    simulate_pulses,
    transmission_from_loss_db,
)
from qmint.quantum.records import clopper_pearson, resource_counts, software_versions
from qmint.quantum.references import numpy_outcome_distribution, qutip_outcome_distribution

NOISE_GRID = {
    "depolarizing": [0.0, 0.01, 0.02, 0.05, 0.1],
    "dephasing": [0.0, 0.01, 0.02, 0.05, 0.1],
    "amplitude_damping": [0.0, 0.01, 0.02, 0.05, 0.1],
}
READOUT = (0.01, 0.02)  # hypothetical p01, p10


def _maxdiff(a: dict, b: dict) -> float:
    return max(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in set(a) | set(b))


def three_way_agreement(seed: int = 2026) -> list[dict[str, Any]]:
    rows = []
    specs = [NoiseSpec()] + [NoiseSpec(k, 0.05, *READOUT) for k in NOISE_GRID]
    for n in range(1, MAX_STATEVECTOR_QUBITS + 1):
        sec = random_note_secret(n, seed + n, token_id=f"x03_{n}")
        bases, bits = list(sec.bases), list(sec.bits)
        meas = [Basis.X if (i % 3 == 0) else b for i, b in enumerate(bases)]  # some wrong-basis checks
        for spec in specs:
            for mb in (bases, meas):
                q = qiskit_exact_distribution(bases, bits, mb, spec)
                npy = numpy_outcome_distribution(bases, bits, mb, spec)
                qt = qutip_outcome_distribution(bases, bits, mb, spec)
                row = {
                    "n": n,
                    "noise": spec.describe(),
                    "meas_is_secret_basis": mb is bases,
                    "max_abs_diff_qiskit_numpy": _maxdiff(q, npy),
                    "max_abs_diff_qutip_numpy": _maxdiff(qt, npy),
                    "evidence_kind": (EvidenceKind.SIMULATOR_IDEAL if spec.is_ideal else EvidenceKind.SIMULATOR_NOISY).value,
                }
                if spec.is_ideal:
                    row["max_abs_diff_analytic_numpy"] = _maxdiff(analytic_outcome_distribution(bases, bits, mb), npy)
                elif mb is bases:
                    row["accept_analytic"] = analytic_note_accept_probability(spec, bases, bits)
                    row["accept_numpy"] = npy.get(tuple(bits), 0.0)
                rows.append(row)
    return rows


def acceptance_curves() -> list[dict[str, Any]]:
    rows = []
    for kind, grid in NOISE_GRID.items():
        for p in grid:
            spec = NoiseSpec(kind, p, *READOUT)
            for n in (1, 2, 4, 8, 16, 32, 64, 128):
                rows.append(
                    {
                        "channel": kind,
                        "param": p,
                        "readout_p01_p10": list(READOUT),
                        "n": n,
                        "mean_accept_exact_verifier": analytic_mean_accept_probability(spec, n),
                        "mode": "analytic product formula (no statevector)",
                        "evidence_kind": EvidenceKind.SYNTHETIC.value,
                    }
                )
    return rows


def aer_noisy_points(seed: int = 7, shots: int = 20000) -> list[dict[str, Any]]:
    rows = []
    for kind in NOISE_GRID:
        spec = NoiseSpec(kind, 0.05, *READOUT)
        for n in (1, 4, 8):
            sec = random_note_secret(n, seed + n, token_id=f"aer_{kind}_{n}")
            bases, bits = list(sec.bases), list(sec.bits)
            counts, prov, _ = run_aer(build_verify_circuit(bases, bits, noise=spec), shots, seed + 100 * n, spec)
            k = accepted_shots(counts, bits)
            ci = clopper_pearson(k, shots, 0.999)
            exact = analytic_note_accept_probability(spec, bases, bits)
            rows.append(
                {
                    "channel": kind,
                    "param": 0.05,
                    "n": n,
                    "shots": shots,
                    "accepted": k,
                    "ci_0.999": ci.model_dump(mode="json"),
                    "analytic_exact": exact,
                    "analytic_inside_ci": ci.lo <= exact <= ci.hi,
                    "evidence_kind": prov.evidence_kind.value,
                    "provenance": prov.model_dump(mode="json"),
                }
            )
    return rows


def cloner_results(git_sha: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in ("bruss2000", "mvw2012"):
        per_state = {
            f"{b.value}{x}": {
                "circuit_statevector": cloner.circuit_both_pass_probability([b], [x], name),
                "numpy_kraus": cloner.numpy_both_pass_probability(b, x, name),
            }
            for b in (Basis.Z, Basis.X)
            for x in (0, 1)
        }
        attack = cloner.simulate_attack(name, n=1, n_notes=8, shots_per_note=5000, seed=11, source_code_sha=git_sha)
        out[name] = {
            "label": cloner.attack_label(name),
            "is_optimal_for_w1_exact_rational": cloner.is_optimal_for_w1(name),
            "analytic_both_pass_n1": cloner.analytic_both_pass(name, 1),
            "analytic_both_pass_n2": cloner.analytic_both_pass(name, 2),
            "circuit_both_pass_n2_example": cloner.circuit_both_pass_probability([Basis.X, Basis.Z], [1, 0], name),
            "per_state_n1": per_state,
            "w1_theorem_bound_n1": 0.75,
            "attack_result": attack.model_dump(mode="json"),
            "resources_n1": resource_counts(cloner.build_cloning_attack_circuit([Basis.Z], [0], name)),
            "evidence_kind": EvidenceKind.SIMULATOR_IDEAL.value,
        }
    out["mvw_exact_rational_value"] = str(cloner.mvw_both_pass_exact())
    return out


def photonic_curves() -> dict[str, Any]:
    rows = []
    for src, mu in (("poisson", 0.1), ("poisson", 0.5), ("heralded_spdc", 0.1)):
        for loss_db in (0, 3, 6, 10, 20, 30):
            p = PhotonicLinkParams(
                source=src, mu=mu, herald_efficiency=0.5, herald_dark_prob=1e-5,
                eta_link=transmission_from_loss_db(loss_db), eta_det=0.6, p_dark=1e-5, e_opt=0.01,
            )
            cs = click_statistics(p)
            rows.append(
                {
                    "source": src, "mu": mu, "loss_db": loss_db, **multiphoton_fraction(p), **cs,
                    "note_accept_n8_exact_no_loss_tolerance": cs["p_pass"] ** 8,
                    "evidence_kind": EvidenceKind.SYNTHETIC.value,
                }
            )
    p = PhotonicLinkParams(mu=0.5, eta_link=transmission_from_loss_db(3), eta_det=0.6, p_dark=1e-3, e_opt=0.02)
    ev = simulate_pulses(p, 200_000, seed=5).summary()
    ci = clopper_pearson(int(ev["detected_pulses"]), int(ev["pulses"]), 0.999)
    mc = {
        "params": "poisson mu=0.5, 3 dB, eta_det=0.6, p_dark=1e-3, e_opt=0.02",
        "summary": ev,
        "p_detect_ci_0.999": ci.model_dump(mode="json"),
        "p_detect_analytic": click_statistics(p)["p_detect"],
        "evidence_kind": EvidenceKind.SYNTHETIC.value,
        "note": "simulated photonic events; not PHOTON_EXPERIMENT data; separate from qubit gate noise",
    }
    return {"curves": rows, "monte_carlo_check": mc}


def verify_circuit_resources() -> list[dict[str, Any]]:
    rows = []
    for n in range(1, MAX_STATEVECTOR_QUBITS + 1):
        sec = random_note_secret(n, 99 + n, token_id=f"res_{n}")
        rows.append({"n": n, **resource_counts(build_verify_circuit(list(sec.bases), list(sec.bits)))})
    return rows


def generate(git_sha: str) -> dict[str, Any]:
    return {
        "lane": "F",
        "task": "F1",
        "git_sha": git_sha,
        "software": software_versions(),
        "caption": "Quantum-circuit primitive demonstration, not proof of a physically deployable quantum-cash system.",
        "x03_three_way_agreement": three_way_agreement(),
        "honest_acceptance_curves": acceptance_curves(),
        "aer_noisy_points": aer_noisy_points(),
        "w1_cloners": cloner_results(git_sha),
        "photonic_model": photonic_curves(),
        "verify_circuit_resources": verify_circuit_resources(),
        "paid_jobs_run": False,
    }


def main(argv: list[str]) -> int:
    out = Path(argv[1]) if len(argv) > 1 else Path("handoffs/F-F1_evidence.json")
    sha = argv[2] if len(argv) > 2 else "unknown"
    out.write_text(canonical_json(generate(sha)) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
