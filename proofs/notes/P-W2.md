# P-W2: noisy / threshold Wiesner (game W2) and the SDP-support obligation

**Status of the W2 game: no bound.** No closed-form published bound is assumed. The (3/4)^n theorem does **not** transfer: with an error threshold the honest-acceptance event and the adversary's winning event both change.

**Path to support.** Lane C's n = 1 Choi-matrix SDP for the exact threshold verifier. A floating-point SDP optimum is evidence `NUMERICAL_SDP` only. The independent checker accepts a `CERTIFIED_NUMERIC` certificate only with residual accounting: given the dual Y with computed lambda_min(Y (x) I - G) and a rigorous eigenvalue error bound err, the padded dual Y + r I with r = max(0, err - lambda_min) is feasible, so Tr(Y) + r * dim(Y) is a valid upper bound. Fields required: `solver, game_definition_sha256, primal_objective, dual_objective, dual_min_eigenvalue, eigenvalue_error_bound, dual_variable_dim, certified_bound`.

**ASSUMPTION_MISSING.** The checker cannot verify that the supplied G matrix encodes the W2 game; it relies on `game_definition_sha256`. That link must be audited by lane C/M.

**MVW 2012 Sec. 3.5 does not cover W2.** The "threshold results" there (binomial tail sum_{j>=t} C(n,j) alpha^j (1-alpha)^{n-j}) count repetitions in which BOTH copies succeed jointly. That is not a verifier applying its own threshold to each copy, and the formula says nothing about honest acceptance. This agrees with lane A's reading (T-MVW12-SEC35). Implementing it would need a new game id (lane A proposes `W1_THRESH_JOINT`), which is a contract migration and is not done here.

**SDP-support obligation: met at CERTIFIED_NUMERIC for W1/W1_CV (lane C), independently re-verified by lane D.**
Lane C (`qmint/attacks/certify.py`, `audits/SDP_DERIVATION.md`, `handoffs/C-C1-evidence.json`) reports exactly verified dual bounds:
- W1: 3/4 <= OPT_1 <= 0.750000000003638 and 9/16 <= OPT_2 <= 0.562500000007276;
- W1_CV: OPT_1 <= 0.9267766955417756.

Lane D re-checked these in `qmint/proofs/sdp_exact.py`, which is called only from `checker.py` and imports nothing from `qmint.attacks`:
1. **G_n.** We build G_n = 4^-n sum_s rho_s^T (x) rho_s (x) rho_s ourselves from rational BB84 projectors, using the (input, out1, out2) big-endian ordering.
2. **Exact PSD test.** Symmetric Gaussian elimination in Fractions. A zero pivot is allowed only when its whole row is zero, so the test is valid for singular matrices. Lane C's test is a positive-definite LDL^T without pivoting, so the two methods differ.
3. **W1.** The analytic MVW dual Y = (3/8)^n 1 passes Y (x) 1 - G_n >= 0 EXACTLY for n = 1 and 2. So OPT_1 <= 3/4 and OPT_2 <= 9/16 are rigorous, and lane C's larger certified values are confirmed. Lowering one diagonal entry by 1e-9 makes the check fail (negative control).
4. **W1_CV n=1.** Our own CVXPY dual is rounded to dyadic rationals and shifted until the exact test passes. That gives OPT <= 0.92677669530531, which is at most lane C's 0.9267766955417756, so C's claim is confirmed. The theorem value is 0.92677669529664.
5. **Residual accounting.** For every lane C record, certified >= dual objective + delta * dim, within the 2^-40 dyadic rounding.

**Limitation.** Lane C did not export its rational dual matrices. Lane D therefore confirms C's claimed bound values, not C's specific Y. The checker can verify an explicit `dual_matrix_rational` if one is provided.

**Checker policy.** A CERTIFIED_NUMERIC certificate is accepted only for W1 with n <= 2 or W1_CV with n = 1, and only after the exact re-verification above. W2 SDP certificates are refused until there is an independent construction of the W2 game operator.
