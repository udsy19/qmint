# J-J1: optional IonQ/Qollab backend adapter and provenance

**Paid jobs run: none.** No job was submitted to IonQ (QPU or cloud simulator). Submission is hard-disabled
(`SUBMISSION_ENABLED_IN_THIS_BUILD = False`). No credentials were read or logged.

## Result
- `qmint/quantum/ionq.py`
  - `probe_backend()`: versions, provider installed, key present (bool), `.env` files that qiskit-ionq would read, public backend list, documented limits with citations.
  - BB84 builder (1–8 qubits, C7 map), explicit bit-order decoding (`qiskit_clbit0_rightmost` / `ionq_q0_leftmost`).
  - `BackendRunRecord`: provenance with no silent fallback.
  - Local Aer ideal/noisy runs.
  - `build_dry_run()`: cost estimate plus approval gate. It requires `QMINT_ALLOW_PAID_HARDWARE=1` **and** `QMINT_PAID_RUN_APPROVAL_TOKEN` equal to a plan-bound token. Even with both set, it returns `REFUSED`.
  - CLI: `python -m qmint.quantum.ionq --out DIR`.
- `qmint/quantum/qollab.py` + `qollab/`: portable bundle made of OpenQASM 3, a standalone Qiskit script and a JSON manifest (C6 `EvidenceManifest`). Qollab integration is **BLOCKED**.
- Install: `qiskit-ionq 1.1.1` installed. Qiskit stays at 2.5.2 (no downgrade).

## Probe facts (2026-10-11, cited in `qollab/evidence/sources.json`)
- **Backends:** forte-1 is available (36q). forte-enterprise-1/-3 are unavailable. Aria and Harmony are retired. The simulator has 29q and noise models aria-1/2, forte-1 and forte-enterprise-1.
- **Shots:** 1..1,000,000 through the API. qiskit-ionq caps QPU jobs at 10,000.
- **Mid-circuit measurement:** supported on the simulator; target-dependent on QPUs. Dynamic circuits are not supported anywhere.
- **Bit order:** IonQ raw results put q[0] leftmost. Qiskit counts put clbit0 rightmost.
- **Pricing:** IonQ does not publish a direct rate card. Reseller prices:
  - Azure Forte 1: $0.0001645 per 1q gate-shot, $0.001121 per 2q gate-shot, minimum $25.79 (error mitigation off) or $168.195 (on).
  - Braket Forte: $0.30 per task + $0.08 per shot.
- **Hazard:** qiskit-ionq reads keys from a `.env` file before `os.environ`. Keep `.env` files out of the repo tree.

## Numbers
| what | value | evidence |
|---|---|---|
| 8q honest verify, Aer ideal, 1000 shots | 1000/1000, Wilson95 [0.9962, 1] | SIMULATOR_IDEAL |
| 8q honest verify, Aer noisy (hypothetical, not IonQ-calibrated) | 929/1000, Wilson95 [0.911, 0.943] | SIMULATOR_NOISY |
| 8q dry-run, 1000 shots, EM off | 12 1q gates, 0 2q; Azure $25.79–27.76; Braket $80.30; IonQ-direct unknown (null) | PUBLISHED_AGGREGATE prices |

## How a human would run it
See `HUMAN_RUN_PROCEDURE` in `ionq.py`:
1. Review the dry-run JSON.
2. Export your own key.
3. Get a binding quote via `dry_run=True` + `/jobs/{id}/cost`.
4. Set the flag and the token.
5. Make a lead-reviewed code change that enables submission. Record the result as a `BackendRunRecord(evidence_kind=QPU)`.

## For the lead at merge
- Deduplicate the BB84 builder: make `ionq.build_bb84_prepare_verify` import lane F's `qmint/quantum/circuits.py` builder. Keep `qollab/bb84_standalone.py` as the self-contained copy; the equality test guards it against drift.
- Contract proposals (v2): `BackendRunRecord`, and a C7 `bit_order` enum. Details are in the JSON.

## Tests
`$PY -m pytest tests/contracts tests/unit/ionq -q` exited 0 with 57 passed. `ruff check` exited 0.

The tests cover:
- an autouse fixture that blocks the network and the provider constructor
- secret-not-in-output
- SKIPPED/REFUSED instead of fake success
- the token being bound to the plan
- billing rules
- both bit orders
- rejection of silent fallback
- drift between the standalone script and the package
- export manifest hashes
