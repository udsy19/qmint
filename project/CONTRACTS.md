# Frozen integration contracts C0–C7 (schema 1.0.0)

Code of record: `qmint/core/contracts.py` (Pydantic v2), `qmint/core/serialization.py`,
`qmint/core/interfaces.py`. JSON Schemas: `schemas/v1/*.json`; frozen hashes:
`schemas/v1/SCHEMA_HASHES.json` (enforced by `tests/contracts/test_contracts.py::test_schema_hashes_frozen`).

| Contract | Models | Key invariants |
|---|---|---|
| C0 | `ProtocolSpec` | `protocol_id` must be registered in `PROTOCOL_GAMES`; game must be one of that protocol's games |
| C1 | `TokenRecord` (public), `IssuerSecret` (private) | token metadata rejects secret-like keys; `IssuerSecret` refuses `model_dump`, JSON, pickle, canonical serialization; repr redacted; `reveal_for_testing_only()` tags TEST_ONLY |
| C2 | `MeasurementEvent`, `PhotonEvent`, `CalibrationRecord` | `PHOTON_EXPERIMENT` calibration requires dataset SHA-256; intervals have units; fractions in [0,1]; `experiment_family` must match consumer protocol |
| C3 | `AttackResult` | successes ≤ trials; Monte Carlo requires CI; SDP evidence requires primal, dual and dual residual |
| C4 | `SpacetimeNetwork`, `Site`, `Link`, `TransactionTrace`, `TraceEvent` | links reference known sites; no retrocausal DAG edges; distinct event kinds for local validation vs settlement vs irrevocability |
| C5 | `SecurityCertificate`, `BoundRequest`, `BoundResult` | default `UNCERTIFIED` with null bounds; `CERTIFIED` only with assumptions met, proof ref, checker id, evidence hashes, PUBLISHED_THEOREM/CERTIFIED_NUMERIC evidence, and every target bounded; a `BoundResult` value requires a theorem id and cannot coexist with UNSUPPORTED/out-of-domain/failed assumptions |
| C6 | `BenchmarkRecord`, `EvidenceManifest` | quantum/classical flag consistent with protocol id; every record carries evidence kind, git sha, environment lock |
| C7 | enums + `Interval`/`Unit` | `Basis` Z/X; BB84 `(Z,0)=|0>,(Z,1)=|1>,(X,0)=|+>,(X,1)=|->`; no implicit Qiskit little-endian decoding; time in ns; ε is a max adversary win probability, never an error bar |

Games: `W1` (MVW 2012 simple counterfeiting, (3/4)^n), `W1_CV` (MVW classical-verification variant,
(3/4+√2/8)^n), `W2` (noisy/threshold Wiesner — no closed form assumed), `S1` (Kent et al. 2022 ideal 2-site,
(1/2+1/(2√2))^N), `S2` (Kent et al. 2022 realistic), `D1` (Schiansky et al. 2023), `A1` (Gavinsky et al. 2025),
`C1` (classical double-spend systems game).

Cross-lane interfaces (`qmint/core/interfaces.py`): `ProofEvaluator` (D→I), `IndependentChecker` (D, separate
code path), `Challenger`/`TokenHandle` (B), `AttackSimulator` (C), `CalibrationProvider` (E).

Migration policy: changes go in `schemas/v2/` via a lead-approved migration; v1 stays frozen.
