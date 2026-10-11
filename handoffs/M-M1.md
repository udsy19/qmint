# Handoff M-M1: independent adversarial audit (red team)

- **Branch:** `feat/M-redteam`.
- **Review SHA:** `9a4e8a9368e75d3e8e329231020e1992bc7f04ea`, the main state with lanes A–H, J and L merged. Its code is identical to main `4c04f53`.
- **Re-check on main `7130c1f`:** after GH/X and K-web phase 1 merged, all 26 strict-xfail findings still reproduce on a `git archive main` snapshot (34 passed, 26 xfailed).
- **Paid jobs:** none. No network calls apart from a sub-agent reading the three papers.

## Deliverables
- `audits/CRYPTOGRAPHIC_REVIEW.md`, `audits/DATA_LEAKAGE_REVIEW.md`, `audits/CLASSICAL_FAIRNESS_REVIEW.md`, `audits/CLAIMS_AUDIT.md`. Each finding has an id, severity, repro command, expected safe behaviour, owner, remedy, status and review SHA.
- `tests/adversarial/` (6 modules + `_reach.py`):
  - 34 passing checks: controls, cross-lane reproductions, independent real-data recomputation.
  - 26 `xfail(strict=True, reason="M-<id>: …")` regressions that assert the safe behaviour. `--runxfail` shows each live failure.

## Findings by severity

| sev | id | owner | one line |
|---|---|---|---|
| HIGH | M-D1 | D | Ideal W1/S1 certificates are CERTIFIED with noise/loss/threshold keys outside a 6-name denylist (`threshold`, `noise`, `qber`, `gamma_det`, `P_det`, `e_h`, `l_h`…) |
| HIGH | M-D2 | D | The SDP (CERTIFIED_NUMERIC) checker path skips the noise check, the declarations and the proof-ref/claim match |
| HIGH | M-B1 | B | `deepcopy`/`pickle` of a `RegisterHandle` is a perfect clone: W1 pair accepted with probability 1.0 |
| HIGH | M-H1 | H | H3-OT secrets are derivable from public (seed=0, token id), so a keyless double spend succeeds at both sites |
| HIGH | M-H2 | H | An H3 second Commit/CommitC re-activates another site after a spend, so double spend (both late-commit modes) |
| MEDIUM | M-B2 | B | Introspection: wallet handle → exact states; the Alice-facing Kent session holds Bob's IssuerSecret, t and u |
| MEDIUM | M-B3 | B | `redeem` does not bind the serial to the token id: victim's serial burned, attacker's note accepted |
| MEDIUM | M-D4 | D/E | Calibration gate: an unregistered dataset hash, n_events=1 and confidence 0.05 are all accepted |
| MEDIUM | M-H3 | H | Idempotency-key collision across tills or a restart: a second ACCEPT (replayed flag ignored) |
| MEDIUM | M-L1 | L | `RecordStore.get` accepts unregistered or relabelled result files (no registry hash check) |
| MEDIUM | M-K1 | K | `--real-data` drops the FIXTURE label for MONTE_CARLO/NUMERICAL_SDP/MODELLED_LATENCY fixtures |
| MEDIUM (claims) | M-S1 | D/N | Schiansky's 5.9e-45 is unsupported. An iid boundary cheater has tail 7.0e-9. D's never-certify stance is upheld |
| MEDIUM (claims) | M-H4 | H/N | The "prevented" entries in the double-spend matrix hold only for the weak replay adversary |
| LOW | M-D3 | D | `startswith` proof-ref check: W1 citing P-W1CV is accepted |
| LOW | M-D5 | D | One-sided reproduction tolerance (permissive direction) in reproduce.py |
| LOW | M-E1 | E | "Non-stationarity" p=0.003 is an artefact of a pooled iid test under χ²/dof≈10. Run-level Welch p=0.33 |
| LOW | M-G1 | G | `run_s_money` default z=0 makes c=b visible to B0 before presentation |
| LOW | M-B4 | B/G | The S1 harness does not enforce spacelike presentations. No beating strategy was found (uncertain) |
| LOW | M-H6 | H/GH | Metric mismatch (choice→accept vs presentation→accept). Addressed by GH on main |
| INFO | M-C0, M-G2, M-E2, M-H5 | — | No finding: SDP transpose/order tamper is harmless for real BB84 and lower claims are refused; timing metadata does not leak b; channel-swap blind spot fails pessimistic; Kent Table 1 confirms that S1 needs the c relay |

## Reproduced vs not reproduced
- **Reproduced:**
  - SDP 0.75 / 9/16 / W1_CV (C report regenerated, D exact).
  - D's `reproduce.py` (all rows).
  - Kent counts and the "experimental tuple outside Thm 1" result (source-confirmed).
  - Schiansky p_d at N=4.2e6 (and 6.27e-48 at the SI N).
  - B's SI Table 2 aggregates.
  - G's 15.337 / 304.207 µs.
  - H's double-spend and comparability matrices.
  - F's evidence file values.
  - L's nested-secret leak is fixed.
  - Suite: 826 passed + 26 xfailed.
- **Independently reproduced (own code):**
  - QBER 1.4491 % / 3.2787 % (state-averaged 1.44907 / 3.27872) with identical counts.
  - χ²/dof 10.5 / 9.9.
  - Measure-resend (5/8)ⁿ.
  - MVW 3/4ⁿ against B's challenger.
- **Qualified:**
  - E's non-stationarity (M-E1).
  - H's "prevented" (M-H4).
  - K's fixture labelling (M-K1).
  - D's Fig. 5 tolerance (M-D5).
- **Not run:**
  - E's raw-tag pipeline (7997998).
  - G's RIPE numbers.
  - C's Clarabel n=2.
  - J's prices.
  - A's matrix beyond three sources.

## Adjudication of the four open items, from my own reading of the sources
1. **Schiansky Chernoff (lane D's flag): upheld, and stronger than D's note.**
   - SI Note 1C (Eqs. 7–8): "N random variables X_i, which can each take the value 1 with probability p_i and 0 with probability 1 − p_i".
   - SI Eqs. (18)–(22) insert M(e,l) = (4+2√2)e + l as the mean, with no per-state variables and no rescaling. The Nature peer-review file does not discuss it.
   - An iid cheater at (e = 0.0710, l = 0) on the fitted boundary has an exact Binomial tail of 6.96e-9 at N = 4.2e6. That is far above the published 5.9e-45 and below the rescaled 3.3e-7.
   - Caveat: attainability of the l→0 end of the fitted boundary is unproven.
2. **N = 4.2e6 vs 4 482 440: confirmed.**
   - Fig. 4b: "λ = N = 4.2 × 10^6 … p_d = 5.9 × 10^−45".
   - SI Table 2: "Sub-token length N 4 482 440 ± 1600" next to "p_d 5.911 ± 0.088·10^−45".
   - The Table N would give 6.27e-48, so the published value is the conservative one.
   - p_m: 6.02 % = 2·g2(0) (arXiv v2 "≤ 6.02 %") vs 6.76 % in the main text. Not reconciled in either document.
3. **Measure-resend (5/8)ⁿ: correct.** Derived analytically and run against B. MVW 2012 never states 5/8. Its (3/4)ⁿ optimum (Thm 1) uses a non-measurement channel with dual Y = (3/8)·1.
4. **E non-stationarity: not supported as stated.** It is overdispersion. See M-E1.

## Source anchors read for this audit
- Schiansky SI PDF: https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41467-023-39519-w/MediaObjects/41467_2023_39519_MOESM1_ESM.pdf (Notes 1C, 3B–C, Table 2).
- Main text: https://www.nature.com/articles/s41467-023-39519-w and arXiv:2305.14504v2.
- Kent 2022: https://www.nature.com/articles/s41534-022-00524-4, Table 1 at `/tables/1`.
  - IQT1 step 7: "A computes the bit c = b ⊕ z and sends it to B"; step 8: "B sends c to B_i".
  - Caption: "Steps 1 to 8 in IQT_1, and 1 to 5 in IQT_2, take place within the intersection of the causal pasts of the presentation points".
  - Introduction: the advantage is "near-instant validation without time delays due to cross-checking, while satisfying unforgeability and user privacy with unconditional security".
- MVW 2012: arXiv:1202.4010, Thm 1, Sec. 3.2.

## Re-audit after in-flight merges
- **Q:** update imports and keep the strict xfails.
- **I:** compiler must use checker verdicts only; add M-D1/D2 to T7 mutation inputs.
- **GH (already on main 7130c1f):** strong adversary in `matched_topology`; `hold_until_active` + re-commit; processing-time matching.
- **K-web (already on main):** `qmint/api` evidence routes need the M-K1 provenance gate. The lab demo reveals seeded secrets by design and must never emit IN_MODEL evidence.

## Proposed interface changes (not applied)
- **C1 v2:** a `TokenHandle` contract clause that handles are non-copyable and non-picklable.
- **C2 v2:** `CalibrationRecord.dataset_sha256` must be in the DATASOURCE_REGISTER for its `experiment_family`, and `confidence_level ≥ 0.95`.
- **C5 v2:** a per-game parameter allowlist in OBLIGATIONS.yaml (`allowed_parameters`), enforced by the evaluator and the checker.
- **L envelope:** registry hash-chain and `get()` registry verification.
