# P-W2: noisy / threshold Wiesner (game W2)

**Status: UNSUPPORTED.** No closed-form published bound is assumed. The (3/4)^n theorem does **not** transfer: with an error threshold the honest-acceptance event and the adversary's winning event both change.

**Path to support.** Lane C's n = 1 Choi-matrix SDP for the exact threshold verifier. A floating-point SDP optimum is evidence `NUMERICAL_SDP` only. The independent checker accepts a `CERTIFIED_NUMERIC` certificate only with residual accounting: given the dual Y with computed lambda_min(Y (x) I - G) and a rigorous eigenvalue error bound err, the padded dual Y + r I with r = max(0, err - lambda_min) is feasible, so Tr(Y) + r * dim(Y) is a valid upper bound. Fields required: `solver, game_definition_sha256, primal_objective, dual_objective, dual_min_eigenvalue, eigenvalue_error_bound, dual_variable_dim, certified_bound`.

**ASSUMPTION_MISSING.** The checker cannot verify that the supplied G matrix encodes the W2 game; it relies on `game_definition_sha256`. That link must be audited by lane C/M.

**MVW 2012 Sec. 3.5 does not cover W2.** The "threshold results" there (binomial tail sum_{j>=t} C(n,j) alpha^j (1-alpha)^{n-j}) count repetitions in which BOTH copies succeed jointly. That is not a verifier applying its own threshold to each copy, and the formula says nothing about honest acceptance. This agrees with lane A's reading (T-MVW12-SEC35). Implementing it would need a new game id (lane A proposes `W1_THRESH_JOINT`), which is a contract migration and is not done here.
