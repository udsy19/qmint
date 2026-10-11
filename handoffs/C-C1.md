# Lane C / C1 — attacks and W1 Choi SDP

- Branch `feat/C-attacks`; evidence `handoffs/C-C1-evidence.json` (regenerate with
  `python -m qmint.attacks.report --out handoffs/C-C1-evidence.json [--clarabel-n2]`, ~110 s).
- Derivation and certification: `audits/SDP_DERIVATION.md`.
- W1 SDP (NUMERICAL_SDP): n=1 = 0.75 (SCS and Clarabel), n=2 = 0.5625 (SCS 0.2 s; Clarabel 24 s, 6.5 GB, primal optimal_inaccurate). n=3 refused by the size guard.
- CERTIFIED_NUMERIC (exact rational LDL^T on shifted dual): 3/4 <= OPT_1 <= 0.750000000003638; 9/16 <= OPT_2 <= 0.562500000007276. W1_CV n=1 <= 0.9267766955417756 (theorem 0.92677669529664).
- Controls: transpose-omission and factor-order bugs are invisible on BB84 n=1. They are caught on the six-state ensemble (0.5 vs 2/3) and at n=2 without W_pi (0.375). Bit-order swap gives the same SDP value but honest acceptance drops to 0.375. Per-note threshold gives 1.0. Secret basis gives 1.0 (OUT_OF_MODEL).
- Heuristics (MC lower bounds, exact per-qubit both-pass values): measure-resend 5/8, Bayes resend 0.6545, Buzek-Hillery 2/3, phase-covariant x-z 0.7286, MVW 3/4. A01 does NOT reach 3/4.
- A06 split-and-report-loss on the toy W2 gives success 1.0 at a 50% loss allowance (NO_THEOREM). A08 leaky oracle at n=8 gives 0.996 using 84 queries (OUT_OF_MODEL).
- Tests: 65 passed (incl. slow), 64 passed without slow; ruff clean. No paid jobs.
