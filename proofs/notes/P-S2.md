# P-S2: realistic S-money QT1/QT2 (game S2)

**Source.** Kent et al. 2022 (doi:10.1038/s41534-022-00524-4) and its Supplementary Information. Equations transcribed from the article HTML LaTeX and cross-read against the PDF/SI.

| Axis | Result | Anchor | Domain (refused outside) |
|---|---|---|---|
| robustness | eps_rob = exp(-(P_det N/2)(1 - gamma_det/P_det)^2) | Lemma 2, Eq. (3); SI Eqs. (58)-(59) | Eq. (2): 0 < gamma_det < P_det |
| correctness | eps_cor = exp(-(A N/4)(1 - 2 nu_cor/A)^2) + exp(-(E nu_cor N/3)(gamma_err/E - 1)^2), A = P_det(1 - 2 beta_PB) | Lemma 3, Eq. (5) | Eq. (4): gamma_err/2 < E < gamma_err; 0 < nu_cor < A/2 |
| privacy | eps_priv = beta_E (Bob guesses b with prob <= 1/2 + eps_priv) | Lemma 4, Eq. (6) | 0 < beta_E < 1/2 |
| unforgeability | eps_unf = exp(-(P_noqub N/3)(nu_unf/P_noqub - 1)^2) + exp(-N f) | Theorem 1, Eqs. (7)-(10); SI Eqs. (99)-(102) | Eq. (7) and f > 0; theta in (0, pi/4) |
| 2^M points | rob*M, cor*M, priv^M = 2^-M[(1+2 priv)^M - 1], unf*C, C = L(L-1)/2 spacelike pairs | Theorem 2, Eq. (11); SI Theorem 3 (194)-(198) | M >= 1; C required if M > 1 |

with f = (gamma_det - nu_unf)[lambda/2 (1 - delta/lambda)^2 - ln(1 + 2 beta_PS)] - (1 - (gamma_det - nu_unf)) ln(1 + h) (Eq. 8), h = 2 beta_PS sqrt(1/2 + 2 beta_PB^2 + (1/2 - 2 beta_PB^2) sin 2 theta), delta = gamma_det gamma_err/(gamma_det - nu_unf) (Eq. 9), lambda = (1/2)(1 - sqrt(1 - [1 - O(theta)^2](1 - 4 beta_PB^2))), O(theta) = (cos theta + sin theta)/sqrt 2 (Table 5 items 2-3).

**Quantifiers.** Unforgeability: Bob honest; **for every** strategy of Alice with arbitrary quantum technology (only restricted indirectly by Table 6 G). Robustness/correctness: both honest; the probability is over the experiment's randomness. Privacy: Alice honest; **for every** strategy of Bob, *given* Table 6 C-F.

**Hypotheses -> code.** Table 6 A, B, C/D, E, F, G and the independence that the SI Proposition 1 Chernoff bounds need are physical idealisations that cannot be checked from counts, so each must be declared (`table6_A_two_bases`, ..., `independent_rounds`); missing ones give `ASSUMPTION_MISSING:<name>`. The parameter source must be known: a `CalibrationRecord` with `experiment_family = kent_2022` and experimental/published origin, or `noise_source` in {calibration, published_kent_2022, hypothetical}; anything else is refused. `P_noqub` (a multiphoton bound) is required for unforgeability.

**Calibration mapping (documented choice).** qber -> E, multiphoton -> P_noqub, basis_bias -> beta_PB, loss l -> P_det = 1 - l. If a parameter is also given as a scalar, the hull of the two is used.

**Interval propagation.** Worst endpoints (registry `monotonicity`): P_det -> lo; E, beta_PB, beta_PS, theta, P_noqub, beta_E -> hi. Each direction is unit-tested numerically. The domain must hold on every corner of the box; the independent checker re-derives the worst case by brute-force corner maximisation.

**Reproduced from the paper (proofs/certificates/reproduction_v1.json).** eps_rob = e^-1052.6 at N = 4e7, P_det = 0.019, gamma_det = 0.018. P_noqub(mu = 0.09) = 3.815e-3. P_det^theo = 0.01863 (Eq. 17). beta_PB = 2.37e-3, beta_PS = 3.59e-3, E = 0.0585 from the published counts. Minimal nu_unf = 3.88e-3 (paper: 3.9e-3). Fig. 5 beta_max: theta = 10 deg, E = 0.058 -> 6.9e-6 (paper: 6e-6); theta = 5 deg, E = 0.03 -> 2.25e-4 (paper: approximately 2.3e-4, our value is 2.3 % lower, unexplained, possibly rounding); theta -> 0, E = 0.01 -> 5.9e-4 (paper: ~6e-4). The paper's experimental tuple (beta_PB = 2.4e-3, beta_PS = 3.6e-3, theta = 10 deg) fails Theorem 1 for every gamma_err tried, matching the paper's statement that the experiment does not yet give unforgeability.

**Caveats.** nu_cor, nu_unf, gamma_err are free analysis/protocol choices; any admissible choice gives a valid bound, but QMint does not claim an optimal choice. The paper's Fig. 5 construction makes eps_cor exactly 1e-9; with float rounding that equality can fail the checker, which is why the example certificate nudges gamma_err up by 0.1 %. These bounds are conditional on Table 6 and are not an experimental security certificate for any device.
