# FDE-1: proofs + photonics fixes (M-D1..D5, M-E1, KE basis_bias, Q proposals)

Branch `feat/FDE-fixes`, starting at main `02aeab1`. The code, data and tests are in commit `5a91930`; this handoff is the commit after it. No paid jobs were run and nothing used the network: the real data came from the shared cache.

## Fixed (each M strict-xfail is now a passing test)
| id | fix | where |
|---|---|---|
| M-D1 | The noise check is now a per-game **allowlist**: W1/W1_CV accept `n`, S1 accepts `N` and `M` (M must be 1). The only other keys accepted are `declared_assumptions`, `verifier` (must be exact) and `verification_oracle_queries` (must be 0). Any other key, under any spelling and at any value (including 0), is OUT_OF_MODEL in the evaluator and refused by the checker. The checker keeps its own independent copy of the list. The length key is now game-specific: W1 no longer accepts `N`. | `assumption_check.check_noise_free`, `checker._ideal_gate`, `ideal_bounds` |
| M-D2 | The SDP (CERTIFIED_NUMERIC) path now runs the same `_model_gates` as the published path: allowlist (+`sdp_certificate`), required declarations of P-W1/P-W1CV, and an exact proof reference ∈ {own claim, `P-W2/sdp`}. `parameters.n` must also equal `sdp_certificate.n`. | `checker._model_gates`, `_check_sdp` |
| M-D3 | The proof reference must match exactly: the claim id or one of its registered bound ids. `P-W1CV` and `P-W1/` are refused for W1. | `checker._model_gates` |
| M-D4 | A calibration is admitted only if: confidence ≥ 0.95; any `dataset_sha256` is registered in `datasets/manifests/*.yaml` under the **same** `experiment_family`; a PHOTON_EXPERIMENT record has `n_events` ≥ 1000; the basis bias is within [0, ½). The family must also be in the claim's list, as before. | `assumption_check.check_calibration`, `zenodo.registered_datasets` |
| M-D5 | The Fig. 5 β_max check is now a two-sided band, \|ours/paper − 1\| ≤ rel. Before, any overestimate passed. | `reproduce.digitized_agrees` |
| M-E1 | `summary.json` `split.p_value` is now a run-level Welch test: p = 0.334 (D/A), 0.587 (H/V). The pooled iid test is kept as `pooled_iid_p_value` (0.0034) and labelled invalid. A new `interpretation` field reads: "overdispersed / heterogeneous across runs (χ²/dof≈10) … no evidence of monotone drift". The widened hull intervals are unchanged. The wording is updated in the calibration docstring, `interval_method` and `datasets/README.md`. | `calibration.summarize`, `confidence.welch_t` |
| KE | `basis_bias_interval` now holds \|p_Z − ½\| (Z record 0.0031 [0.0020, 0.0042]; X record 0.0021 [0, 0.0050]) instead of p_Z ≈ 0.497. On the D side it is documented as β_PB, and anything not within [0, ½) is refused. | `calibration.bias_interval`, `_CALIBRATION_MAP` |
| Q | The synthetic generator moved to `qmint/photonics/synthetic.py`, and `entrypoints.py` imports it directly (the file-path loader is gone). Archives whose README carries `SYNTHETIC_TAG` give `SYNTHETIC` CalibrationRecords. | `calibration.analyze_archive/calibration_record` |
| Q | Added `datasets/manifests/zenodo_7979319.json`, a C6 EvidenceManifest. It holds one input, `datasets/cache/zenodo_7979319/Archive.zip` (sha256 + md5), and no env-lock pin, so the lock does not drift. It is generated from the YAML, and a test keeps the two in sync. A realdata test shows `realdata_preflight` returns `[]` when `datasets/cache` points at the shared cache. | `zenodo.dataset_evidence_manifest` |

## Tests
`$PY -m pytest tests -q -m "not network and not slow" -o addopts=""` exits 0: **1074 passed, 15 xfailed**, 2 deselected. The baseline was 983 passed and 26 xfailed. The realdata tests ran against the cache. `ruff check qmint tests` is clean.

## Needs other lanes (not my files)
- **N (urgent claim wording).** The fig04 caption (`qmint/evaluation/experiments.py:262-265`) is now false. It still says "Non-stationarity: … differ … (two-proportion p = …)" but prints the Welch p = 0.334. Proposed text: `"Runs are overdispersed / heterogeneous (chi2/dof = {d:.1f}); no evidence of monotone drift: run-level Welch test, holdout runs {h} vs calibration runs {c}, p = {split['p_value']:.2f} (a pooled iid two-proportion test, p = {split['pooled_iid_p_value']:.3f}, is invalid under this dispersion)."` The N11 ledger row in `tables.py:133-135` needs the same fix.
- **KB/KD (web).** Two places still state non-stationarity: `limitations.tsx:54` and `benchmarks/_components/sections.tsx:271` ("split differs, p = …"). `holdout_p_value` in `api/routes/benchmarks.py` now returns the Welch p.
- **Figures.** I regenerated `figures/fig02-05` caption and manifest JSON. The staleness test pins proofs/photonics source hashes, so this was required to keep the suite green. The images are byte-identical. N should re-run `make_figures` after the caption fix.
- **I (compiler).** Add the M-D1/M-D2 inputs to T7. The checker now refuses them.
- **Lead.** Point `datasets/cache` at the shared cache (for example, symlink the whole directory) so that run_all's preflight passes.

## Limitations
- Interval methods are not whitelisted.
- The PUBLISHED_AGGREGATE Schiansky record (1σ, 0.6827) is refused as a calibration by the floor. It only matters for D1, which is never certified.
- The `git_sha` in `reports/data_working/.../manifest.json` is the starting commit.
