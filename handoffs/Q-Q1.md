# Q-Q1: integration of protocols, attacks, quantum and proofs

Branch `feat/Q-integration`, starting from `9a4e8a9` (main with lanes A–L merged). The code is in commits `ff11b15` (interfaces and dedupe), `7552c7c` (G1 cross-run) and `054e1da` (entrypoints). The JSON record is in `Q-Q1.json`.

## 1. Interfaces (`qmint/core/interfaces.py`, lead-approved, Protocol additions only)
- Added `ChannelTokenHandle(TokenHandle, Protocol)` with `split(kraus, *, joint, copies)` and `measure(position, projector0, rng)`.
- Added `PairChallenger(Challenger, Protocol)` with `verify_pair(c1, c2)`.
- These are sub-Protocols, not edits to `TokenHandle` and `Challenger`. That keeps the change backward compatible: lane C's `NoteRegister` and `W1Challenger` still satisfy `TokenHandle` and `Challenger`. Adding the methods to the base Protocols directly would have broken them.
- `tests/contracts/test_interfaces.py` checks with runtime_checkable that B's `WiesnerChallenger` (EXACT and SHOTS) and `RegisterHandle` satisfy the new Protocols, and that the old implementers and a minimal handle still conform.

## 2. G1 cross-run (`qmint/attacks/crossrun.py`, `tests/integration/test_q_g1_crossrun.py`, `handoffs/Q-G1_evidence.json`)
Lane C's per-qubit Kraus channels were run on lane B's bank, using only `PairChallenger` / `ChannelTokenHandle`. Each row compares:
- B's exact `pair_acceptance_probability` for n = 1, 2, 3 over 3 different hidden secrets;
- C's own independent challenger analytics;
- the closed form;
- lane F's Qiskit cloner circuits, and F's Kraus operators run on B's register.

Max |diff| is 1.4e-15 across 21 rows. All 21 Monte Carlo runs (400 trials, using B's destructive `verify_pair`) have 95% CIs that cover the exact value. Exact values are labelled SIMULATOR_IDEAL; the Monte Carlo runs are MONTE_CARLO lower bounds.

| attack | per-qubit, closed form | B exact (n=1) | C exact | F circuit |
|---|---|---|---|---|
| A01 measure-resend | 5/8 | 0.6250 | 0.6250 | – |
| A01b / A02b Bayes resend | (3+√5)/8 | 0.654508 | 0.654508 | – |
| A02 Breidbart resend | 5/8 | 0.6250 | 0.6250 | – |
| A03 universal (Bužek–Hillery) | 2/3 | 0.666667 | 0.666667 | – |
| A03b phase-covariant x-z | (3+2√2)/8 | 0.728553 | 0.728553 | 0.728553 (bruss2000) |
| A04 MVW optimal | 3/4 | 0.7500 | 0.7500 | 0.7500 (mvw2012) |
| TEST_ONLY secret leak (n=4) | 1 | 1 (exact) | 50/50 (MC) | – |

The secret-leak row is OUT_OF_MODEL, with `theorem_upper_bound=None`. The other values match at n = 2 and 3 as p^n.

### G1 evidence (`Q-G1_evidence.json`, all_pass = true)
Every check below is recomputed live:
- **C:** SDP n=1 primal 0.7500000000000013, dual 0.7500000000000002. The certified upper bound is 0.750000000003638 (CERTIFIED_NUMERIC).
- **D:** an independent exact rational dual gives exactly 3/4.
- **F:** 64-case analytic/NumPy/QuTiP/Qiskit agreement, with max diff 3.3e-16.
- **B:** the challenger refuses copy, deepcopy and pickle, and neither the handle nor the record carries bases or bits.
- **Q:** cross-implementation agreement (the table above) and the leak control.

Regenerate with `qmint attacks g1-evidence --out handoffs/Q-G1_evidence.json` (about 5 s).

## 3. Dedupe (no-bloat)
No whole files were deleted. These duplicate definitions were removed:
- **`qmint/protocols/register.py`:** removed `_SQ2`, `_KETS` and `bb84_ket`. It now uses `qmint.quantum.bb84.state_vector`, and protocols plus their tests call `state_vector` directly.
- **`qmint/attacks/linalg.py`:** removed `_S2`, `_KET_OF_LABEL` and `bb84_ket`. `ket(label)` now looks up `bb84.STATE_VECTORS`, and `BB84_LABELS` is derived from `BB84State`.
- **`qmint/quantum/bb84.py`:** `state_label` and `state_vector` now accept `Basis | str`, because the callers relied on that coercion.
- **`qmint/attacks/games.py`:** removed `W1_BASE`, `W1_CV_BASE` and `GameMismatchError`.
  - `theorem_upper_bound` now reads `qmint.proofs.ideal_bounds.IDEAL_BASES` and raises D's `UnsupportedGameError`.
  - `MVW_SOURCE` now comes from D's registry citation.
- **`qmint/quantum/ionq.py`:** the BB84 preparation gates now come from F's `circuits.build_prepare_circuit`, and the label from `bb84.state_label`. The circuit hash is unchanged (`2124dfb4…`), and the qasm3 equality test against `qollab/bb84_standalone.py` (the intentional standalone copy) still passes.
- **Grep check:** no references remain to `bb84_ket`, `_KETS`, `_KET_OF_LABEL`, `W1_BASE` or `GameMismatchError`.
- **Kept on purpose, as independence evidence:**
  - C's `certify.py` and D's `sdp_exact.py` each have their own Fraction helpers. D is required to import nothing from attacks.
  - C's `phase_covariant_xz_kraus` / `mvw_optimal_kraus` and F's `cloner_kraus` are separate constructions that the cross-run checks against each other.
  - `ionq.decode_bitstring` (which accepts spaces and IonQ's order) and `ionq.wilson_interval` (which returns an `Interval`) differ from F's and C's versions.

## 4. Lane entrypoints
- **`qmint/protocols/entrypoints.py`** (`simulate wiesner|smoney|schiansky`): honest runs, plus an optional W1 attack on B's bank. W2 requires `--noise` together with `--threshold`.
- **`qmint/attacks/entrypoints.py`** (`attacks run --suite optimal-small|crossrun --game W1|W1_CV`, `attacks g1-evidence`): any other game exits 2.
- **`qmint/proofs/entrypoints.py`** (`proofs verify --game W1 --n 1 --method sdp --primal-dual`, `--method theorem`, `proofs reproduce`):
  - SDP is supported for W1 n=1,2 and W1_CV n=1. Larger n exits 2.
  - With no theorem the result is value=None and exit 1, never 0.
- **`qmint/quantum/entrypoints.py`:** three-way agreement, Aer noisy points, cloner circuits and the J adapter's local Aer runs. Aer job ids and completion times are dropped so the output is deterministic.
- **`qmint/quantum/qollab.py: cli_main`** (`qollab export --demo wiesner --out DIR`).
- **`qmint/photonics/entrypoints.py`** (`data fetch` and `data validate`):
  - The core stage uses SYNTHETIC fixtures and checks that the pipeline recovers the planted counts 8/400 and 6/400.
  - The realdata stage reproduces Zenodo 7979319: 1.45% and 3.28% in 7.8 s. It looks in `<cache_dir>` first, then the shared cache.
  - `data fetch` is REFUSED unless `QMINT_ALLOW_NETWORK=1`.
- **Shared helper:** `qmint.core.lanes.write_stage_json`, which writes canonical JSON.
- **Reuse:** `qmint/attacks/report.py` now exposes `sdp_section(timings=)`, `w1cv_section` and `w1_mc_section`, and `build()` uses them. The entrypoints reuse these instead of copying them.
- `cli.py` needed no change.

### run_core (`scripts/run_core.py --offline --seed 42`, exit 0, ~11 s; `--check-determinism` all true)
| stage | lane | status |
|---|---|---|
| doctor, contract_fixtures | L | PASS |
| protocols | B | PASS |
| quantum | F | PASS |
| attacks | C | PASS |
| proofs | D | PASS |
| photonics | E | PASS |
| networks / classical / compiler / evaluation | G/H/I/N | SKIPPED (no `entrypoints.py` merged; not owned by Q) |

## Tests
- `pytest tests -m "not network and not slow"`: exit 0, 846 passed, 2 deselected. The realdata tests ran because the cache is present.
- The slow tests in attacks and protocols pass.
- `ruff check .` is clean.

## Limitations / proposals
- **run_all is still refused.** `realdata_preflight` looks for `datasets/manifests/*.json`, but lane E committed YAML manifests. Lanes E and L need to agree on the format. The photonics realdata stage itself works.
- **Synthetic generator location.** The photonics core stage loads E's synthetic generator from `tests/unit/photonics/photonics_synth.py` by file path. The proposal to E is to move it to `qmint/photonics/synthetic.py`.
- **Mislabelled calibration records.** E's `calibration_record` hard-codes `data_origin=PHOTON_EXPERIMENT`, even for synthetic input. The proposal is to make `origin` a parameter. The Q stage emits no CalibrationRecord for synthetic data.
- **Stale source sha in C's evidence.** The `source_code_sha` in `handoffs/C-C1-evidence.json` predates the dedupe, because `attacks_source_sha` hashes all of `qmint/attacks/*.py`. Its numbers are unchanged; it was not regenerated.
- **`attacks run --out` writes plain JSON**, not through lane L's `RecordStore`. Wiring it in is a follow-up.
- **`simulate smoney` limits.** It accepts only `--sites 2` (the published two-site scheme), and there is no `--scenario` YAML support.
- No paid or hardware jobs were run and no network was used.
