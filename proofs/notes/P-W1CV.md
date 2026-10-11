# P-W1CV: Wiesner classical-verification variant (game W1_CV)

**Source.** MVW 2012 (arXiv:1202.4010v1), **Theorem 2** (p. 3).

**Statement with quantifiers.** In the variant where the bank verifies a note by sending a uniformly random challenge c in {0,1}^n and checking the returned outcomes at the positions where c matches the preparation basis: for every n >= 1 and **for every** quantum strategy that holds one valid note and answers two independent challenges,

    Pr[ both verifications accept ] <= (3/4 + sqrt(2)/8)^n  (~0.9268^n),

and this is tight.

**Hypotheses -> code.** `uniform_bb84_product_state`, `single_note_no_oracle`, `uniform_classical_challenge`, `exact_classical_verifier` must be declared; no noise/loss parameters.

**Reproduced.** n_min(1e-9) = 273.

**Warning.** The base is larger than 3/4, so using (3/4)^n here would be optimistic. A test (`test_mutated_w1cv_using_w1_base_is_caught`) shows the independent checker rejects that mutation.
