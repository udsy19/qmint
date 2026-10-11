# P-W1: Wiesner simple counterfeiting (game W1)

**Source.** Molina, Vidick, Watrous, *Optimal counterfeiting attacks and generalizations for Wiesner's quantum money*, TQC 2012, arXiv:1202.4010v1, **Theorem 1** (p. 2). Proof: semidefinite programming, Sections 2-3.

**Statement with quantifiers.** For every n >= 1, and **for every** quantum channel Phi (any dimension of ancilla, unbounded computation) that maps one n-qubit bank note to two n-qubit registers:

    Pr[ both registers pass the bank's exact test ] <= (3/4)^n,

where the probability is over the bank's uniformly random secret choice of each qubit from {|0>,|1>,|+>,|->}. The bound is achieved by some channel, so it is tight.

**Hypotheses, in plain English, and their code counterparts** (`required_declarations` in `proofs/OBLIGATIONS.yaml`):

| Hypothesis | Code |
|---|---|
| Each qubit is an independent uniform BB84 state, secret from the adversary | declared `uniform_bb84_product_state` |
| The adversary holds exactly one note and never talks to a verifier (no oracle, no re-tries, no leaked post-measurement states; MVW p. 2 names these as *not covered*) | declared `single_note_no_oracle`; `verification_oracle_queries` must be 0/absent |
| The bank's test is the exact projective test: every qubit must be right; no error tolerance, no loss | declared `exact_projective_verifier`; `error_threshold`, `loss_tolerance`, `gamma_err`, `E`, `P_noqub` must be absent/0; any calibration with non-zero QBER/loss/multiphoton is refused |

**Code.** `qmint/proofs/ideal_bounds.py` (`IdealBoundEvaluator`, `log10_bound`, `min_length_for_target`), log space; checker `qmint/proofs/checker.py` re-derives `n ln(3/4)` in 60-digit Decimal.

**Reproduced.** n_min(eps = 1e-9) = 73 (same as the superseded bootstrap). log10 bound at n = 10^6 is -124938.7366 (no underflow; the linear value is reported as `None`, never 0).

**Not covered (refused, tested).** W1_CV (different, larger base), W2 (noisy/threshold), S1/S2/D1, any oracle access, any noise. The (3/4)^n formula is not a bound for a bank API.
