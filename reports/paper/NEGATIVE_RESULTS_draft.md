# Negative results and unsupported claims (DRAFT, lane N phase 1)

Status: draft for the lead. The root `NEGATIVE_RESULTS.md` is finalised at gate G7.
Every item below points at a row of `reports/paper/table4_negative_results.md` (N01-N24) or
`table5_scope_constraints.md` (S01-S12). Those tables are generated, and every row is pinned to a
verbatim excerpt of its source file, so the exact numbers live there and nowhere else. This draft
paraphrases them and adds no new numbers.

## 1. Corrections to our own plan and to folklore

- **Measure-resend is not 3/4 in W1** (N01, N02). The work order assumed measure-resend reaches the
  W1 optimum. It doesn't. For a single copy it's 3/4 per qubit, but the W1 event needs both copies to
  pass, and that comes to 5/8. Lanes B and C found this independently, and Fig. 3 re-derives it from
  the Kraus operators.
- **MVW Sec. 3.5 does not cover the noisy game W2** (N17). Its binomial tail is a joint-success
  threshold game. No theorem in the registry bounds W2 (N16), so W2 certificates are refused.

## 2. Published results that QMint cannot certify

- **Schiansky et al. 2023 (game D1) is never certified** (N03). The finite-size argument applies
  a Chernoff bound to a weighted mishap sum that isn't a {0,1} variable. If you rescale it the way
  the textbook bound requires, the bound gets many orders of magnitude weaker (N04). This is flagged
  as an open question, not as a refutation.
- The published p_d reproduces only with the main-text N and the SI p_m, a mixed parameter set (N06).
  The SI Choi normalisation and the "2x2 dual" are inconsistent (N07).
- **Kent et al. 2022's own experimental tuple lies outside the Theorem 1 domain** (N05). The paper
  says this too ("we need to improve some experimental parameters"). Fig. 5 draws the tuple as
  UNCERTIFIED, above every certified curve.

## 3. Weaker distinctions than a quick reading suggests

- **S1 is not coordination-free** (N08). The Stage-II bit has to be relayed to both sites before
  presentation.
- **A classical escrow with ideal OT reproduces the operational properties** (N09): late choice,
  local acceptance and an issuer-blind commit. What remains is the security model: computational
  for the classical scheme, information-theoretic for ideal S1.
- RIPE-based latency comparisons are not trust-matched (N22). Fig. 7 stays PENDING until matched
  quantum and classical records exist.

## 4. Physical and experimental limits

- **The exact (zero-tolerance) verifier collapses under small noise** (N10, Fig. 10). Honest
  acceptance falls quickly with note length, even at percent-level readout error. A noise-tolerant
  verifier is game W2, which has no bound (N16).
- **The 2023 photon runs are overdispersed** (N11, Fig. 4): run-to-run heterogeneity (χ²/dof ≈ 10,
  driven by a few outlier runs), not temporal drift. A run-level Welch test of contiguous halves finds no
  difference (p = 0.334 D/A, 0.587 H/V). An earlier pooled-iid test (p = 0.003) wrongly suggested
  non-stationarity and was corrected after red-team review. Per-run Clopper-Pearson intervals understate
  the spread, so calibration intervals are widened.
- Loss, detector efficiency and multiphoton probability can't be observed from the archive (N12).
- **The authors' code can't be reused** (N13). The licence is inconsistent (AGPL file vs CC-BY
  metadata) and the code is non-runnable as published. Nothing was copied.

## 5. Attacks outside the model (not counterexamples)

- Split-and-report-loss wins the toy lossy threshold verifier (N14), and a leaky accept/reject
  oracle is fatal (N15). Both break a W1 hypothesis. Fig. 3 draws them in red, labelled
  OUT_OF_MODEL / NO_THEOREM.

## 6. Method and infrastructure limits

- Some SDP implementation bugs are invisible on BB84 at n=1, so complex-ensemble controls are
  required (N18). The SDP is refused at n=3 and is costly at n=2 with one solver (N19). Lane C's
  rational dual matrices were not exported (N24).
- No QPU job was run and Qollab integration is BLOCKED (N20). Fig. 10 says "QPU: NOT RUN".
- The frozen serializer can emit issuer-secret material when it is nested in an `Any` field
  (N23). It is worked around, and a contract fix is proposed by lane L.
- Jiang et al.'s stated inter-city distance disagrees with their coordinates (N21).

## 7. Scope constraints (Table 5)

The following are out of scope, with no claims made: public-key money (S01); transferability
(S02, no registered game); quantum-memory money (S03); equating trapped-ion noise with optical loss
(S04); W1 outside its hypotheses (S05); more than two S1 sites (S06); privacy epsilons, which are
never reported as 0 (S07); cross-protocol calibration reuse (S08); simulation as a security
argument (S09, S10); the ideal-model-only S1 bound (S11); and an unvalidated photonic model (S12).

## Open before G7
- Add lane GH/I negative results once those lanes report: compiler savings vs published tuples,
  and the matched latency comparison.
- Novelty matrix from lane A and review SHA from lane M (required by the N work order).
