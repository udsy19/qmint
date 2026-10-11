# P-OPT: compiler outputs respect certified constraints

**Status: UNSUPPORTED (pending lane I).** Obligation: every configuration the compiler reports as feasible carries a `SecurityCertificate` that `qmint.proofs.checker.IndependentProofChecker` has marked CERTIFIED. Any configuration with a missing or UNSUPPORTED bound is excluded from certified Pareto fronts, and a requested privacy constraint without a theorem makes the request infeasible rather than being dropped. "Optimal" may be claimed only with an exact algorithm or certificate; otherwise the label is `best_found`.

Lane D provides: `ProofEngine.evaluate` (ProofEvaluator), `ProofEngine.draft_certificate` (always UNCERTIFIED), and `IndependentProofChecker.check` (the only path to CERTIFIED).
