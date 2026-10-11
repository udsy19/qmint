# P-D1: quantum-digital payment cryptogram (game D1)

**Source.** Schiansky et al., *Demonstration of quantum-digital payments*, Nat. Commun. 14, 3849 (2023), Supplementary Note 3. **Author Correction** doi:10.1038/s41467-023-40866-x was read: it changes only the Discussion text on growing the MAC key C and does not affect any bound or number used here.

**What the paper states.**
1. N = 1 SDP (SI Eqs. 14-15): minimise the error e a cheater must declare when declaring loss <= l, over all CPTP maps from the token state (vacuum, qubit and 4-outcome multiphoton subspace with populations p0, p1, pm) to two classical cryptograms.
2. Secure-region boundary (SI Eqs. 16-18), described by the authors as an analytic expression that **fits** the numerical optimum: M(e, l) = (4 + 2 sqrt 2) e + l <= (1/2)(1 - p_m/2).
3. N -> infinity: an informal appeal to exponential de Finetti (SI Note 3B), with no finite-N correction term.
4. Finite N (SI Eqs. 19-23): honest abort 1 - p_h <= exp(-(delta_h^2/3) M(e_h, l_h) N); dishonest success p_d <= exp(-(delta_d^2/2)(1/2)(1 - p_m/2) N), admissible iff (1/2)(1 - p_m/2)(1 - delta_d) >= M(e_h, l_h)(1 + delta_h).

**Quantifiers.** "For every CPTP cheating map" holds only at N = 1 inside the SDP. For N > 1 the statement relies on the de Finetti reduction plus Chernoff tails.

**Code.** `finite_size.py`: `schiansky_ln_pd` -> axis epsilon_unf (`P-D1/unf`), `schiansky_ln_fail_honest` -> epsilon_cor (`P-D1/cor`; this mapping of "honest abort" to correctness is QMint's interpretation). Required declarations: `two_merchants_one_bit, honest_ttp, it_secure_mac, fock_diagonal_spdc_source, permutation_symmetric_iid_reduction`. Calibration family must be `schiansky_2023` (qber -> e_h, loss -> l_h, multiphoton -> p_m). Worst endpoints: p_m -> hi for p_d; e_h, l_h -> **lo** for the honest-abort bound, because that formula, as written, improves with a larger design mishap rate. This is a documented monotonicity, tested.

**Reproduced.** p_d = 5.911e-45 at N = 4.2e6, p_m = 0.0602, delta_d = 0.01 (SI Table 2: 5.911 +- 0.088 e-45). M(e_m^{+-}, l_m) = 0.448. e_d(l_m) = 3.82 %. Eq. (23) holds at delta_h = 0.031.

**Main text vs SI discrepancies** (also found independently by lane A, `research/THEOREM_REGISTRY_SEED.yaml` T-SCH23-ASYMPTOTIC/FINITE; our numbers agree with theirs):
- multiphoton probability: 6.76 +- 0.12 % in the main text (reproduces the main-text e_d = 3.79 %) vs p_m = 6.02 +- 0.28 % in SI Table 2 (reproduces e_d = 3.82 % and "allowed mishaps" 0.4849 = (1/2)(1 - p_m/2));
- sub-token length: N = 4.2e6 (Fig. 4b) vs 4,482,440 (SI Table 2).
The published p_d = 5.911e-45 recomputes ONLY with N = 4.2e6 and p_m = 6.02 %. N = 4,482,440 gives 6.3e-48 and p_m = 6.76 % gives 8.7e-45.

**Open question: Chernoff applied to a weighted sum (QMint assessment, not a claim of error).** SI Eqs. (7)-(8) are the multiplicative Chernoff bounds for a sum of independent variables taking values in {0,1}. Per token state the mishap contribution is w * err + loss with w = 4 + 2 sqrt 2 ~ 6.83, so it takes values in {0, 1, w}. That is outside the stated hypothesis, because the MGF step e^{tx} <= 1 + x(e^t - 1) needs x in [0,1]. Rescaling by 1/w puts it in [0,1], and the textbook bound then gives an exponent smaller by a factor w:
p_d <= exp(-(delta_d^2/2) (1/2)(1 - p_m/2) N / w) ~ 3.3e-7 at the published tuple (vs 5.9e-45). The honest bound (Eq. 19) has the same issue. The authors may have a justification we have not found. QMint records the published formula (NUMERICALLY_SUPPORTED, never certified) and exposes the rescaled value only as reproduction evidence (`schiansky_ln_pd_rescaled_assessment`). It needs lane M review. Independence across states is a further unverified hypothesis (collective-attack / de Finetti).

**Why never CERTIFIED.** (a) The boundary is a fit, not a proven closed form. (b) The de Finetti step is informal and has no finite-N term. (c) Chernoff is applied to a weighted combination of error and loss rather than to a single Bernoulli count. (d) The MAC forgery probability p_t = 1/sqrt|C| is not composed into any stated epsilon. Results carry `PUBLISHED_AGGREGATE` / `NUMERICALLY_SUPPORTED`, and the independent checker always returns UNCERTIFIED for D1. Privacy: no theorem, so no value.
