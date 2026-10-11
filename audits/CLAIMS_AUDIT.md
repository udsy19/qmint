# Claims audit (lane M, master plan T10)

- **Review SHA:** `9a4e8a9368e75d3e8e329231020e1992bc7f04ea`.
- **Method:** every key number in `handoffs/*.md` was re-executed by me at that SHA, or re-derived without lane code where marked **indep.** Scratch outputs went to the session scratchpad and are not committed.
- **Interpreter:** `PY=/Users/udsy/PycharmProjects/Qollab-QMint/.venv/bin/python`.
- **Status vocabulary:**
  - REPRODUCED: same value from the lane's own code at the review SHA.
  - INDEP-REPRODUCED: same value from my own derivation or parser.
  - CONFIRMED-SOURCE: checked against the primary source by me.
  - QUALIFIED: the number reproduces but the interpretation needs a caveat.
  - NOT-REPRODUCED.
  - NOT-RUN.

## Reproduced numbers

| lane | claim (handoff) | my re-execution | status |
|---|---|---|---|
| C | W1 SDP n=1 = 0.75 (SCS, Clarabel), n=2 = 0.5625; certified 3/4 ≤ OPT₁ ≤ 0.750000000003638, 9/16 ≤ OPT₂ ≤ 0.562500000007276; W1_CV n=1 ≤ 0.9267766955417756 | `$PY -m qmint.attacks.report --out <tmp>` (90.8 s, exit 0). All values identical to `handoffs/C-C1-evidence.json` except timing/RSS; the optional Clarabel n=2 block was not requested | REPRODUCED |
| D | exact duals: W1 3/4, 9/16; W1_CV 0.9267766953053069 | `$PY -m qmint.proofs.reproduce --out <tmp>` exit 0, every row `[ok]` | REPRODUCED |
| B/F/C | MVW channel gives 3/4ⁿ; Z measure-resend gives 5/8ⁿ (both copies), 3/4 single copy | **indep.** analytic derivation (`test_measure_resend_both_copies_is_5_8_single_copy_is_3_4`). **New cross-lane check:** F's MVW Kraus and C's A01 Kraus against **B's** challenger give 0.75ⁿ and 0.625ⁿ exactly, n=1..3 | INDEP-REPRODUCED |
| B/C | correction of the work order: measure-resend W1 = (5/8)ⁿ, not (3/4)ⁿ | Correct. MVW 2012 (arXiv:1202.4010) never states (5/8)ⁿ (full-text search). It gives (3/4)ⁿ as the optimum via an explicit non-measure channel (Thm 1, Sec. 3.2). The work-order figure confused single-copy pass (3/4) with the joint event | CONFIRMED-SOURCE |
| E | QBER H/V 1.4491 %, D/A 3.2787 % (state-averaged); pooled 1.4301 % / 3.2866 %; Z 31 231/2 183 822, X 75 417/2 294 692 | **indep.** pandas parser on raw Zenodo 7979319 (`Archive.zip` md5 `fd708578…bf94` matches the Zenodo record; sha256 `ef73667f…0130` matches E's `dataset_sha256`). Per-state rates: Z 0.92503 % / 1.97311 % → 1.44907 %; X 2.82656 % / 3.73088 % → 3.27872 %. Counts identical. All row pairs satisfy \|Δt\| < 2.99 ns. E's own realdata tests: 3 passed | INDEP-REPRODUCED |
| E | runs overdispersed, χ²/dof ≈ 10 | indep.: 10.48 (Z), 9.88 (X) | INDEP-REPRODUCED |
| E | "the two halves differ: D/A holdout p = 0.003" (non-stationarity) | p = 0.0034 reproduces only with a pooled binomial 2×2 test (runs 0–5 vs 6–10), which assumes iid counts. E's own χ²/dof ≈ 10 says they are not iid. Welch test on per-run rates: p = 0.33 (X), 0.59 (Z). The first-5 vs last-5 split: pooled p = 0.38 / 0.27. The X "difference" is driven by one outlier run (chunk 05: 3.638 %), and Z has its own outlier (chunk 06: 1.698 %) | QUALIFIED (M-E1) |
| D | Kent: P_det^theo 0.01863, β_PB 2.4e-3, β_PS 3.6e-3, E 0.058, ν_unf 3.9e-3; Fig. 5 β_max 6.9e-6 / 2.25e-4 / 5.9e-4 | reproduce.py identical | REPRODUCED; see M-D5 on the tolerance |
| D | Kent experimental tuple is outside Theorem 1 | reproduce.py `paper=False qmint=False`. Source: "In order to guarantee unforgeability using Theorem 1, we need to improve some experimental parameters (see Fig. 5)" (Results), and Discussion "Experiments with our relatively low precision devices do not guarantee unforgeability" | REPRODUCED + CONFIRMED-SOURCE |
| A/D | Schiansky p_d = 5.911e-45 recomputes only with N = 4.2e6 (Fig. 4b), not SI Table 2 N = 4 482 440 ± 1600 | indep. 6.27e-48 at the Table N. The Table 2 p_d (5.911 ± 0.088e-45) uses the Fig. 4b N. Since the Table N gives a *smaller* p_d, the published value is the conservative of the two. No explanation in either document | CONFIRMED-SOURCE |
| A/D | p_m: main text 6.76 ± 0.12 % vs SI Table 2 6.02 ± 0.28 % | Confirmed. Also: 6.02 % = 2·g2(0) with g2(0) = 0.03010 (SI Table 2); arXiv v2 writes "≤ 6.02 ± 0.28 %"; allowed mishaps 0.4849 needs 6.02 %. Reading: SI p_m is a g2-based upper estimate, main text p_m a correlation measurement. With 6.76 %, p_d = 8.7e-45 (D) | CONFIRMED-SOURCE |
| D | Chernoff applied to the weighted mishap sum is outside the {0,1} hypothesis; rescaled p_d = 3.3e-7 | Confirmed from SI Note 1C Eqs. (7)–(8) ("value 1 with probability p_i and 0 with probability 1 − p_i") and Eqs. (18)–(22): no per-state variables defined, no rescaling. **Stronger than D's note:** an iid cheater on the fitted boundary at l = 0 has exact tail 6.96e-9 (≫ 5.9e-45, ≤ 3.3e-7). See M-S1 | CONFIRMED-SOURCE; D's position upheld |
| B | SI Table 2: M = 0.448, allowed 0.4849, Eq. (23) holds at δ_h = 0.031 | reproduce.py and indep. arithmetic: 0.4849·0.99 = 0.480 ≥ 0.448·1.031 = 0.462 | REPRODUCED |
| G | Jinan 15.337 µs, Yiyuan–Mazhan 304.207 µs (published 15.34 ± 0.01, 304.20 ± 0.01) | `run_s_money(jiang2024_*(), b=1).transaction_time_ns` gives 15337.0 / 304207.0 | REPRODUCED (model reproduces the paper's timing equation, not a measurement) |
| H | double-spend matrix (H0, H4-alone, H5-violated, H6 succeed; others prevented); comparability matrix | `$PY -m qmint.classical.run_baselines --out <tmp> --pqc-reps 1`. The decisions and matrix CSV are identical. Only PQC wall-clock timings differ, and `environment_lock` (records pin `8ba38ce4…`, current `requirements.lock` is `5a34f779…`) | REPRODUCED; QUALIFIED by M-H4 (weak adversary) |
| F | X03 Qiskit/NumPy/QuTiP agreement; Aer noisy 9/9 inside CI; Bruß 0.7286, MVW 0.75 | `$PY -m qmint.quantum.evidence <tmp> x`: every numeric field identical to `handoffs/F-F1_evidence.json` (diffs only in git sha/provenance) | REPRODUCED |
| J | no paid jobs; submission hard-disabled | `SUBMISSION_ENABLED_IN_THIS_BUILD = False` (`qmint/quantum/ionq.py:47`). No IonQ calls made by me | CONFIRMED (code) |
| L | `canonical_json` leaks a nested IssuerSecret (L's critical finding) | No longer reproduces: nested secrets are refused by `canonical_json`, `model_dump(_json)`, pickle and deepcopy at the review SHA (fixed by lead commit bae86d6; copy/deepcopy refusal added in 9a4e8a9) | FIXED |
| K | "FIXTURE label forced by SYNTHETIC" | true as stated, but insufficient: fixtures labelled MONTE_CARLO/NUMERICAL_SDP/MODELLED_LATENCY pass as real (M-K1) | QUALIFIED |
| all | test suite | `$PY -m pytest tests -m "not network and not realdata"`: 796 passed before my changes; with `tests/adversarial`: +30 passed, 26 xfailed (strict) | REPRODUCED |

## Findings from the claims audit

### M-E1 (LOW): "non-stationarity" is overdispersion
- **What E reported.** E-E1 states that the two halves of the run sequence differ significantly (D/A p = 0.003), and that the holdout falls outside the calibration CP interval in both bases.
- **Why the test is wrong.** The p-value comes from a two-proportion test that treats ~2.3 M sifted pairs as iid, while E's own heterogeneity statistic is χ²/dof ≈ 10.
- **With a run-level test.** Neither basis rejects stationarity (Welch p = 0.33 / 0.59), and the alternative 5/5 split is not significant even pooled.
- **The supportable statement.** Run-to-run heterogeneity exceeds binomial noise by ~10× (single outlier runs: linear chunk 06, diagonal chunk 05). Clopper–Pearson intervals under-cover, which E's hull already accounts for. There is no evidence of drift between halves.
- **Repro:** `$PY -m pytest tests/adversarial/test_m_claims.py -k overdispersion -q` (realdata; passes; it documents the finding).
- **Remedy (E):** reword `summary.json`/E-E1, and use an overdispersion-aware test (run-level Welch or quasi-binomial) for the holdout check.

### M-D5 (LOW): one-sided reproduction tolerance
- **The bug.** `qmint/proofs/reproduce.py` marks Fig. 5 β_max rows `[ok]` when `ours >= paper*(1-rel)`. Any overestimate passes, and β_max is the *permissive* direction: a larger admissible bias means a weaker requirement.
- **Current values are fine.** 6.92e-6 vs a digitized 6e-6 (+15 %), 2.25e-4 vs 2.3e-4, 5.9e-4 vs 6e-4. But the check would also print `[ok]` for 10× the paper value.
- **Remedy (D):** a two-sided band (DIGITIZED_FIGURE tolerance stated a priori).

### M-S1: see CRYPTOGRAPHIC_REVIEW
- Any manuscript sentence quoting Schiansky's 5.9e-45 must carry the caveat that it is unsupported by the paper's stated Chernoff hypothesis. An iid cheater reaches 7e-9 if the fitted boundary is attainable at l→0, and the generic valid bound is 3.3e-7.

### Stale environment pin (LOW, H/E/N)
- **What is stale.** H's committed `benchmark_records.jsonl` pins `environment_lock = 8ba38ce4…`, while the repository's `requirements.lock` now hashes to `5a34f779…` (J's `qiskit-ionq` install changed it).
- **Effect.** The numbers reproduce, but the manifests no longer verify against the current lock.
- **Remedy (N, during regeneration):** regenerate on the frozen lock before the manuscript, and fail `verify_manifest` on lock drift.

## Not reproduced / not run
- **C's slow Clarabel n=2 (6.5 GB)** was not re-run. SCS n=2 and D's exact 9/16 cover the value.
- **E's raw-tag pipeline** (v2 record 7997998: drift −2.98 ns/s, 94.7 % pair recovery, 1.8 % accidentals) was **NOT-RUN** by me. Its archive is in the cache (sha256 `f4eb1c34…d707`), so it should be re-audited.
- **G's RIPE HEL–TMP 1.98 ms / 4.13 ms** was **NOT-RUN**. It needs network access, or the fixture path is subject to lane G's committed fixture.
- **J's Azure/Braket price quotes** are PUBLISHED_AGGREGATE. I did not re-fetch them.
- **A's 24-row prior-art matrix** was not re-audited beyond the three sources I read (Schiansky 2023 + SI, Kent 2022, MVW 2012).

## Re-audit list (lanes in flight at review time)
- **Q (protocols/attacks/proofs dedupe):** re-run this whole table plus `tests/adversarial` and update the imports. A dedupe must not change any reproduced value.
- **I (compiler):** every compiled certificate must re-check through `IndependentProofChecker`. Add M-D1/M-D2 mutation inputs to the compiler's T7 suite.
- **GH (merged on main 7130c1f after the review SHA):**
  - matched-topology numbers (`reports/classical_baseline_notes`, figure-6 data);
  - processing-time matching (S-money 1.507 µs vs H 10/50 µs);
  - the strong double-spend adversary.
- **K-web (merged on main 7130c1f):** the API evidence routes must enforce the M-K1 provenance gate, and the lab demo must never emit IN_MODEL evidence.
- **N:** every manuscript number must map to a row above, or to a record ID with a provenance-checked envelope (M-L1).
