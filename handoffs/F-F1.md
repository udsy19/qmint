# Lane F — F1–F4 handoff (branch feat/F-quantum)

**Scope:** BB84 1–8 qubit circuits, independent references (analytic / NumPy / QuTiP), CPTP qubit noise,
separate photonic model, W1 cloner circuits, resources + provenance. Local simulation only; no paid jobs.

## Modules (`qmint/quantum/`)
- `bb84.py` — C7 states, Bloch overlaps, exact analytic distributions, 8-qubit dense cap, seeded `IssuerSecret` notes.
- `circuits.py` — prep/verify circuits (H before Z-measure for X), **`decode_bitstring`** (Qiskit little-endian → C7 tuple), exact `quantum_info` path, Aer runner, `MeasurementEvent` builder (SIMULATOR_IDEAL/NOISY).
- `references.py` — NumPy density matrices (kron order, q0 most significant) and QuTiP; no Qiskit import.
- `channels.py` — depolarizing / dephasing / amplitude damping Kraus + CPTP check, readout confusion, Aer conversion, closed-form acceptance.
- `photonic_model.py` — Poisson / heralded SPDC source, η link, detector efficiency, dark counts, two threshold detectors, multiphoton fraction, seeded event MC. Separate from `channels.py` (AST test). Label SYNTHETIC.
- `cloner.py` — Bruß et al. 2000 phase-covariant cloner (`heuristic_circuit_attack`, W1 both-pass (3+2√2)/8 ≈ 0.7286) and MVW 2012 §3.2 channel via Stinespring (exact rational 3/4 → `mvw2012_optimal_channel_circuit`).
- `records.py` — resource counts (width/depth/gates + generic transpile, explicitly not hardware-native), `BackendProvenance`, Clopper–Pearson.
- `evidence.py` — writes `handoffs/F-F1_evidence.json`.

## Results
- X03: Qiskit vs NumPy max deviation 7e-15, QuTiP vs NumPy 1.7e-15 (64 cases, n=1..8, ideal and noisy).
- Aer noisy acceptance: analytic value inside 99.9% CI in 9/9 cases (SIMULATOR_NOISY).
- W1 cloners (SIMULATOR_IDEAL): Bruß 0.7286 (Aer 0.7294 [0.7237, 0.7351]); MVW 0.75 exactly (Aer 0.7511 [0.7454, 0.7566]). Both ≤ 3/4.
- Honest exact-match acceptance is fragile (SYNTHETIC): readout 1%/2% alone → 0.886 at n=8, 0.144 at n=128.

## Tests
`$PY -m pytest tests/contracts tests/unit/quantum -q` → exit 0, 164 passed. `ruff check` clean.

## Limitations
See `known_limitations` in F-F1.json. Main ones: hypothetical noise parameters, no hardware calibration,
phenomenological photonic model not yet compared to measured data, cloner circuits not resource-optimal,
and simulation does not demonstrate no-cloning.
