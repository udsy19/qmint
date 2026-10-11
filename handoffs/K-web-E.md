# K-web-E: benchmarks explorer and Security Certificate Studio

Branch `feat/KE-web`. It started at `6a8053e`. The API commit is `81fcbc3` and the web commit is `1c32918`; the handoff commit comes after them. The machine-readable record is `K-web-E.json`.

## API (`qmint/api/routes/{benchmarks,certificates}.py`): every DEMO_ADAPTER is gone

### `GET /benchmarks`
Returns `status: OK`. Everything comes from the committed evidence of merged lanes.

- **Lane H:** 23 `BenchmarkRecord`s from `benchmark_records.jsonl`, each validated against the C6 contract. Each becomes a row with:
  - the double-spend outcome: PREVENTED, SUCCEEDS, DETECTED_NOT_PREVENTED (H6) or OUT_OF_MODEL (H5 with the assumption violated);
  - local validation, network cross-check and pre-presentation (Stage-II) commit latencies (MODELLED);
  - trust, hardware and adversary;
  - flexibility and privacy;
  - the X11 pair id and its status;
  - the record id, git sha, environment lock and the regeneration command.
- **X11 matrix:** `comparability_matrix.csv` is split into per-column concessions (classical vs S1).
- **S1 row:** an ideal-model reference with outcome BOUNDED_BY_THEOREM. Its matched-topology latency is null, and the row gives the lane GH reason.
- **Lane G:** the Jiang 2024 intracity and intercity rows (modelled vs published vs light cone), and RIPE HEL→TMP and FRA→TMP (measured RTT/2 p05–p95, plus a modelled S-money min–max over 20 seeds).
- **Lane E:** 22 runs, each with a Clopper–Pearson 95% interval. Per basis it also gives the pooled hull from the CalibrationRecord, the paper's estimator ±1.96 SE, the published ±, the overdispersion and the holdout p-value.
- **Matched-topology slot:** `NOT_AVAILABLE`, because lane GH is in flight.
- **Reproducibility block:** commands, lane-H git sha, environment lock and evidence files.

### `GET /certificates/catalog`
For each game it returns:
- the registry theorem from OBLIGATIONS.yaml: claim, citation and URL, quantifier, axes with anchors, formulas, domains and monotonicity, caveats, parameters and accepted calibration families;
- the required declarations, with Kent Table 6 A–G texts matched from the claim's assumptions.

It also lists the calibration sources (lane E Z/X photon records and the published aggregate) and 9 presets. Four presets are lane D's committed example certificates. The other five demonstrate failure states:
- S2 with a photon calibration, which gives a family mismatch;
- D1 with a photon calibration;
- W1 with an honest-error tolerance, which is out of model;
- W1 with a privacy target, which has no theorem;
- W2, which has no bound.

### `POST /certificates`
- Calls `ProofEngine.evaluate` once per axis, as a `BoundRequest` with declared assumptions, noise source and calibration, all passed straight through.
- Builds a draft with `draft_certificate`, then runs `IndependentProofChecker.check`. **Only the checker sets CERTIFIED.**
- Adds a studio classification (OUT_OF_MODEL, INFEASIBLE or UNCERTIFIED) derived from the evaluator and checker reasons. The response labels it as derived, and it never alters the exported status.
- Gives per-axis uncertainty propagation: worst endpoint according to the registry's monotonicity, `domain_only`, or "undocumented, refused".
- THEOREM sizing (W1, W1_CV, S1 only) uses `min_length_for_target` and `log10_bound` from lane D, plus a bound-vs-n curve.
- The resource-optimisation slot is `NOT_AVAILABLE` (lane I).
- Export is the checker's canonical JSON (`canonical_json`) together with its sha256 and the OBLIGATIONS.yaml sha256.

**Preset outcomes (verified):**

| Preset | Result |
|---|---|
| W1 n=73 | CERTIFIED |
| S2 Fig.5 hypothetical | CERTIFIED (all 4 axes) |
| S2 Kent experimental tuple | UNCERTIFIED (Theorem 1 domain, ε_cor > target) |
| D1 published | UNCERTIFIED (p_d = 5.91e−45 shown, never certified) |
| S2 + photon calibration | OUT_OF_MODEL (CALIBRATION_FAMILY_MISMATCH) |
| W1 + tolerance | OUT_OF_MODEL |
| W1 + privacy target | UNCERTIFIED (privacy bound null) |
| W2 | UNCERTIFIED (no theorem) |
| W1 n=10 | INFEASIBLE |

## Web
- **`/benchmarks`** (`app/(platform)/benchmarks/**`):
  - summary readouts and a "read before comparing" note;
  - a filterable explorer: network segmented control (default 2 sites · 10 km), family, outcome, comparability and search;
  - a sortable table with `aria-sort`; outcomes sort by meaning and nulls always go last;
  - expandable rows with the concessions, record id, sha and command;
  - a log-scale classical latency chart. S1 is explicitly absent from it.
- **Further sections on `/benchmarks`:**
  - the GH "not available" state;
  - an X11 concessions browser (a list on desktop, a select on mobile);
  - latency case studies (one log chart plus per-case readouts with an evidence label on every number);
  - photon QBER per run for Z and X, against a published band and pooled-hull lines;
  - a reproducibility panel with copy buttons.
- **`/certificates`** (`components/certificates/**`):
  - preset strip;
  - form: game, the four ε targets (empty means none), honest-error tolerance with game-specific semantics, theorem parameters (point or interval for non-integers), a declared-hypotheses checklist with Table 6 texts, noise source, and calibration radios that preview the family check;
  - Run is the accent button, also bound to ⌘↵. Requests are abortable. States: loading, stale-input notice, error with the 422 detail.
- **Studio results:**
  - verdict callout with a 2px bar, plus the checker's status and id;
  - per-axis table that switches to a stacked list below 640px. A missing bound always reads "no applicable bound";
  - uncertainty propagation grouped by parameter;
  - theorem panel (statement, quantifier, source link, anchors and caveats in disclosures);
  - hypotheses (declared and machine-checked, failed shown in red);
  - THEOREM sizing readouts and a log₁₀-bound-vs-n chart, with the lane I optimisation shown as unavailable;
  - calibration panel;
  - export (Copy, Download, sha, preview).
- **`components/charts/**`** holds the generic primitives for D:
  - `ChartFrame` (title, legend, `role=img` summary, data-table toggle), `ChartLegend`, `SERIES`, `useReducedMotion` and `useNarrow`;
  - `IntervalPlot` (dot plus error bars on a linear or log axis, reference bands and lines);
  - `LineBandChart` (lines with CI bands, horizontal target and bound lines, vertical markers, log or linear axes);
  - `ScatterPareto` (scatter with a Pareto frontier);
  - `scale.ts` (log and linear ticks and domains, `formatNs`, `formatLog10Bound` (never 0), `paretoFrontier`, `middleTruncate`).
  - All are built on recharts 3 with design tokens, and animation is off under reduced motion.

## Tests and results
- `pnpm typecheck` 0, `pnpm lint` 0, `pnpm test` 37/37 (21 of them new: scale, explorer model, form model, results with real API fixtures), `pnpm build` 0.
- Python: `tests/unit/api/test_e_benchmarks.py` (7) and `test_e_certificates.py` (12) all pass. They cover:
  - checker gating, including a mocked checker refusal: never CERTIFIED anywhere and the export stays UNCERTIFIED;
  - D1 never certified;
  - a missing privacy theorem is null, not 0;
  - family mismatch gives OUT_OF_MODEL;
  - INFEASIBLE;
  - worst-endpoint propagation;
  - canonical export and its hash;
  - Table 6 declarations;
  - 422s.
- `ruff` is clean.
- Overall: `pytest tests/unit/api tests/contracts` gives 76 passed and 3 failed. **All 3 are `test_api.py` assertions on the replaced demo adapter (not edited, per the preamble):**
  - `test_certificates_never_certified`: it posts the old body `{game, epsilon_unf_target, n}` and expects `DEMO_ADAPTER` with demo_bounds. Replace it with `test_e_certificates.py::test_w1_certified_only_by_checker`, `test_checker_gating_rejection_is_never_overridden` and `test_d1_never_certified`.
  - `test_certificate_min_size_and_failed_assumption`: superseded by `test_infeasible_when_bound_exceeds_target` (n_min = 73) and `test_ideal_game_with_error_tolerance_is_out_of_model`.
  - `test_benchmarks_rows`: `data.rows` is now `data.latency_cases` and `data.protocols`. The same Jiang and RIPE assertions are in `test_e_benchmarks.py::test_latency_cases_jiang_and_ripe`, and classical rows are now OK instead of NOT_AVAILABLE.
  - **Proposed lead change:** delete these three tests from `test_api.py`.

## Visual QA
Screenshots were taken with the Playwright 1.62 chromium against `next dev -p 3004` and the API on :8784. There is no horizontal overflow at 390, 768, 1440 or 1920, and no console errors. Files are in `/private/tmp/claude-501/ke-shots/`:
- `bench-{390,768,1440,1920}.png`
- `cert-{390,768,1440,1920}.png`
- `cert-{mismatch,kentexp,d1}-1440.png`

**Iterations made after reviewing the screenshots:**
- category rows switched to an index axis so input order equals visual order;
- log domains pushed off exact decades so points don't sit on the frame;
- nice 1-2-5 linear ticks;
- grid readouts instead of wrapping flex;
- ms units for RIPE;
- fixed a 37px overflow at 390 (grid `min-w-0`);
- stacked axis list on mobile;
- deduplicated checker reasons;
- uncertainty grouped by parameter;
- a rejected calibration is no longer shown as propagated.

The narrow-viewport label gutter (`useNarrow`) was added after the last 390 benchmarks capture; F should recapture.

**Mobbin (targeted):** 2 searches.
- Gumloop Tasks (https://mobbin.com/screens/2d6d329b-0b8e-4162-834b-d9d0db79cff5): filter segment and status column, used for the explorer filter bar.
- DoorDash Merchant Product mix (https://mobbin.com/screens/0fce9fb1-1e7c-41c4-a2da-01535d9324e5): sortable header affordance.
- Browserbase schema builder (https://mobbin.com/screens/be114db0-9519-4275-831b-5836d3570baf) and Customer.io Tester (https://mobbin.com/screens/d9fa0bc2-767a-4563-82fc-eb983668bbd3): request on the left and live response on the right, with a warning callout. Used for the studio layout and the stale-input notice.
- Devin test run (https://mobbin.com/screens/2c590764-5b6a-48cc-b979-310c18a1bdd8): pass/fail check list. Used for the hypotheses panel.

## Findings and blockers
1. **D↔E semantic mismatch, flagged and not fixed (not my files).** `qmint/proofs/assumption_check._CALIBRATION_MAP` maps `basis_bias_interval` to Kent's `beta_PB`, a bias in [0, ½). Lane E's `basis_bias_interval` is instead the fraction of coincidences in TTP basis Z (≈0.497). It is only reached for kent_2022-family records, so today it is masked by the family check. Proposal: lane E renames the field, or lane D maps it as |p − ½|.
2. **D1 calibration mapping:** with the photon record, lane D merges the measured QBER hull into `e_h`, which is domain-only for P-D1/unf. The bound is unchanged and D1 stays uncertified.
3. **No GH/I data:** the matched-topology and optimisation slots are designed NOT_AVAILABLE states, and both name the lane they wait for.
4. **No pushes, no paid jobs.** Servers were stopped.
