# P-S1: ideal two-site S-money (game S1)

**Source.** Kent, Lowndes, Pitalua-Garcia, Rarity, npj Quantum Information 8, 28 (2022), **Lemma 1, Eq. (1)** (main text p. 5); proof in **Supplementary Note IV** (via Lemma 6, SI Note III).

**Statement with quantifiers.** For the ideal schemes IQT1 and IQT2 (Table 1) with N transmitted qubits and two presentation points: if Bob follows the scheme honestly, then **for every** strategy of a dishonest Alice (unbounded quantum power),

    Pr[ Bob accepts tokens at both presentation points ] <= (1/2 + 1/(2 sqrt 2))^N  (~0.8536^N).

**Hypotheses -> code** (all must be declared): `ideal_no_loss_no_error` (exact BB84 qubits, no loss, no errors, no multiphoton), `two_presentation_points` (M = 1; `M != 1` is refused), `honest_bank_secure_agent_channels`, `uniform_bb84_states_and_bases`.

**Reproduced.** n_min(1e-9) = 131.

**Not covered.** Realistic QT1/QT2 (use P-S2). Theorem 2 (2^M points) is for QT^M, not for the ideal schemes. **Privacy:** the paper argues IQT privacy in prose only (p. 4, "Bob cannot obtain any information about b"); there is no numbered privacy result for IQT, so QMint reports no privacy value for S1 (never 0).
