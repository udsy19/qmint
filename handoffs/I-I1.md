# Lane I handoff (I-I1): resource-optimal, independently checked certificate compiler

Branch `feat/I-compiler`, starting at `9a4e8a9`.
- **Pre-registration:** commit `0268fee`, made before any optimisation was run. It contains `benchmarks/{frozen_experiments,holdouts,baseline_matrix}.yaml`, and their hashes are pinned by `tests/unit/compiler/test_preregistration.py`.
- **Code:** commits `7c55f24` and `ad36dbb`. The results were generated at `ad36dbb`, which is the revision recorded in `results.json`.

## What exists
- **`qmint/compiler/constraints.py`**: a parameter-space DSL covering:
  - W1, W1_CV and S1 with N only.
  - Kent 2022 S2: N, γ_det, γ_err, ν_cor and ν_unf on worst-case-relative grids. The device inputs are P_det, E, β_PB, β_PS, θ, P_noqub(μ), β_E, M and C. The reporting strategy must be QT1 or QT2.
  - Schiansky D1: N, δ_d, δ_h, with exactly 2 merchants.
- **Rejected requests:** W2, A1 and C1; noise parameters in ideal games; cross-protocol calibration; any reporting strategy other than QT1/QT2; ≠2 merchants; θ outside (0, π/4); M>1 without C; missing declarations.
- **`selectors.py`**: four selectors that share one grid:
  - the published fixed recipe;
  - naive analytic sizing (Kent's "each term = target/2" rule plus binary search);
  - an exhaustive oracle, the only selector labelled `global_optimum_on_grid`;
  - the compiler, labelled `best_found`. It prunes using monotonicity conditions M1–M3, which are documented in the frozen YAML and tested numerically through the engine. It also does exact tie-break enumeration at N*.
- **`scoring.py`**: every candidate is scored only through `ProofEngine.evaluate`. The cache key is canonical over game, axis, device, params, calibration and proof version (the engine id plus SHA-256 of OBLIGATIONS.yaml and the D source files).
- **`certify.py`**: every emitted candidate is re-checked through `IndependentProofChecker`, and only CERTIFIED ones are released. It also produces `InfeasibilityCertificate`s that give, per axis, the best bound found, the engine's domain reasons with counts, and any `ASSUMPTION_MISSING`.
- **`pareto.py`**: dominance checks and duplicate collapse.
- **`calibration.py`**: D1 e_h intervals from lane E's per-run table, IID (Clopper-Pearson) or drift-aware (hull with a Student-t prediction interval). Holdout runs 6–10 can only be read after a selection is frozen with a SHA lock.
- **`experiments.py` and `report.py`**: the X12/X13 runner and figures.
- **`entrypoints.py`**: `qmint compiler optimize|verify|experiments`, `run_core_stage`.

## Results (`reports/optimizer_working/`)
- **Compiler vs exhaustive oracle:** identical on 16 of 16 small-grid problems (12 S2 point/interval and 4 D1). On S2 small grids the compiler used about 1/1100 of the engine calls (353 vs 387,072) and ran about 560× faster (0.012 s vs 6.5 s). Peak memory was 165 KB against 1.05 MB.
- **Ideal games:** all selectors reproduce the closed form. W1 n_min = 25/49/73/97 and S1 N_min = 44/88/131/175 for ε = 1e-3/1e-6/1e-9/1e-12, and all are CERTIFIED.
- **S2 primary cell** (ε_unf ≤ 1e-9, honest ≤ 1e-3, M=1). N is prepared pulses. Bounds are PUBLISHED_THEOREM and every number is CERTIFIED.

| device | published | naive | compiler | naive/compiler |
|---|---|---|---|---|
| F5a (DIGITIZED) point | 4.0e7 | 1.88e7 | 1.06e7 | 1.78 |
| F5b point | INFEASIBLE | 3.55e7 | 8.41e6 | 4.22 |
| F5c point | INFEASIBLE | 6.68e7 | 6.31e6 | 10.6 |
| F5a/b/c interval | all INFEASIBLE (f ≤ 0 on the HYPOTHETICAL box) | | | |
| F5a-half (HYP) point / interval | 4.0e7 / INF | 7.94e6 / 7.50e8 | 7.08e6 / 1.06e8 | 1.12 / 7.08 |
| F5b-half point / interval | 4.0e7 / INF | 5.96e5 / 2.37e6 | 5.62e5 / 1.50e6 | 1.06 / 1.58 |
| F5c-half point / interval | 4.0e7 / INF | 4.47e5 / 4.73e5 | 4.22e5 / 4.22e5 | 1.06 / 1.12 |

- **Published recipe, strict-matched** (the compiler must meet every published achieved bound, with ε_rob capped at 1e-300 because 1e-457 underflows a float): published/compiler is 1.19 at F5a, 2.12 at F5a-half, 13.4 at F5b-half and 33.7 at F5c-half.
- **Published tuple at Kent's Fig. 5 F5b/F5c points:** outside Theorem 1 under our transcription. This is consistent with lane D's β_max being 2% lower than the paper's.
- **Why the compiler gains (A3):** at the published N = 4e7, optimising the thresholds moves log10 ε_unf from −10.96 to −87.9 at F5a. γ_det = 0.018 leaves ε_rob ≈ 1e-457, so robustness is heavily over-provisioned. Almost all of the gain comes from choosing γ_det jointly.
- **Uncertainty (A1):** none of the point-selected configurations stays certified when re-scored on its interval box. The uncertainty boxes themselves are HYPOTHETICAL.
- **Sites (A4):** Theorem 2 with C = L(L−1)/2 costs only about 6–19% more N from 2 to 8 presentation points.
- **Checker:** 320 certificates released, all CERTIFIED. 3 candidates were rejected by the checker, all from the *naive* selector: the float engine came out about 2e-8 dex below the 60-digit re-derivation near f ≈ 5e-8 at N ≈ 5e8. These are double-precision cancellation errors, not a monotonicity bug, since the engine's worst corner equals the float maximum over all corners. The compiler had 0 rejections.
- **D1 (UNCERTIFIED by construction, PUBLISHED_AGGREGATE / PHOTON_EXPERIMENT):**
  - The published tuple is inadmissible (SI Eq. 23) on the published-aggregate interval box.
  - With the IID calibration (runs 0–5) the configuration is feasible at N = 2.8e5 for 1e-9/1e-3.
  - With the drift-aware calibration (e_h up to 3.77%), no admissible configuration exists for any N.
  - Holdout: the IID interval covers 0 of 5 holdout runs and the drift-aware interval covers 5 of 5. The IID-frozen configuration met its targets on runs 6–9 but is INADMISSIBLE on run 10.

## G5 verdict (honest)
The pre-registered rule is met, so the verdict is **POSITIVE**, but it rests on one device: F5a-half, which is HYPOTHETICAL (β halved). There the gain is 2 grid steps (1.12×) for the point device and 7.1× for the interval device. F5b-half and F5c-half pass only at exactly one grid step (1.0593), which is the resolution limit.
- The large gains (1.8–10.6× vs naive, 3.8× vs published) appear only for the paper's own Fig. 5 points used as point devices.
- Under the uncertainty box those devices are infeasible for every selector.
- The gain comes from a mechanism Kent et al. themselves flag ("probably does not optimize"): they over-provision robustness.
- This is at most an L2 *candidate*: a measured resource improvement under an explicit published bound, conditional on declared Table 6 idealisations and on HYPOTHETICAL device and interval inputs. It is not physical security, and it is methodologically a domain transfer of QKD parameter optimisation (NOVELTY C1/C4). No real S2 calibration exists. The 2023 data stays in D1, which is never certified.

## Tests
`$PY -m pytest tests/contracts tests/unit/compiler -q` passes with exit 0: 94 passed (76 lane I and 18 contracts). `tests/unit/proofs tests/integration` give 261 passed. Ruff is clean.

## Limitations / proposals
- **For lane D (proposal, not applied):** add an outward rounding margin to float engine bounds, or a condition-aware guard near f → 0, so that drafts are never optimistic relative to the checker.
- **For lane D:** offer a log10-valued target in `Targets`. Alternatively, accept that strict matching below 1e-308 cannot be expressed.
- **YAML quirk:** PyYAML reads `1.0e8` as a string. It is coerced in code, and the frozen file is unchanged.
- **D1 design-matched comparison:** the published p_d of 5.91108e-45 exceeds the quoted 5.911e-45 by 1.3e-5, so the design-matched comparison is infeasible for the published recipe. Use the strict-matched ratio instead: 3.53×, UNCERTIFIED.
- **Holdout disclosure:** lane E's holdout statistics were visible before pre-registration; this is disclosed in holdouts.yaml.
- **Resource model:** issuance time uses a HYPOTHETICAL 1e8 Hz rate, and both it and the classical-bit proxy are monotone in N.
- **Not done:** no realdata stage was implemented, and no surrogate or ML was used.
