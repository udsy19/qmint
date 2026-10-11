"""Standalone BB84 prepare/verify circuit (self-contained; depends only on qiskit, optionally qiskit-aer).

Copy this single file to any Qiskit environment (e.g. a Qollab project, which requires the Qiskit
framework). It does not import QMint and never contacts a cloud provider.

Conventions (identical to QMint C7):
  (Z,0)=|0>, (Z,1)=|1>, (X,0)=|+>, (X,1)=|->.  X-basis measurement = H then Z measurement.
  Qubit i is measured into classical bit i. Qiskit count keys put classical bit 0 RIGHTMOST;
  decode_key() reverses them so result[i] is the outcome of qubit i. (IonQ's raw OpenQASM 3
  results instead put q[0] LEFTMOST: pass ionq_raw=True for those.)

Usage:
  python bb84_standalone.py --bits 0110 --bases ZXXZ --shots 1000 --seed 7
"""

from __future__ import annotations

import argparse
import json

from qiskit import QuantumCircuit


def build(bits: str, bases: str, verify_bases: str | None = None) -> QuantumCircuit:
    vb = verify_bases or bases
    if not (1 <= len(bits) <= 8 and len(bits) == len(bases) == len(vb)):
        raise ValueError("need 1..8 qubits with matching bits/bases lengths")
    qc = QuantumCircuit(len(bits), len(bits), name="bb84_prepare_verify")
    for i, (b, basis) in enumerate(zip(bits, bases, strict=True)):
        if basis not in "ZX" or b not in "01":
            raise ValueError("bits in {0,1}, bases in {Z,X}")
        if b == "1":
            qc.x(i)
        if basis == "X":
            qc.h(i)
    qc.barrier()
    for i, basis in enumerate(vb):
        if basis == "X":
            qc.h(i)
        qc.measure(i, i)
    return qc


def decode_key(key: str, ionq_raw: bool = False) -> str:
    """Return outcomes ordered by qubit index (character i = qubit i)."""
    key = key.replace(" ", "")
    return key if ionq_raw else key[::-1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bits", required=True)
    ap.add_argument("--bases", required=True)
    ap.add_argument("--shots", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--qasm3", action="store_true", help="print OpenQASM 3 and exit")
    a = ap.parse_args()
    qc = build(a.bits, a.bases)
    if a.qasm3:
        from qiskit import qasm3

        print(qasm3.dumps(qc))
        return
    from qiskit_aer import AerSimulator

    counts = AerSimulator(seed_simulator=a.seed).run(qc, shots=a.shots).result().get_counts()
    by_qubit = {decode_key(k): v for k, v in counts.items()}
    print(
        json.dumps(
            {
                "backend": "local_aer_simulator (ideal)",
                "shots": a.shots,
                "seed": a.seed,
                "prepared_bits_qubit_order": a.bits,
                "counts_qubit_order": by_qubit,
                "verify_pass_fraction": by_qubit.get(a.bits, 0) / a.shots,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
