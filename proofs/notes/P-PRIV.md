# P-PRIV: user privacy

**Transcribed theorem.** Kent et al. 2022 **Lemma 4, Eq. (6)**: QT1 and QT2 are eps_priv-private with eps_priv = beta_E, where privacy means that, **for every** strategy of Bob, Pr[Bob guesses Alice's presentation choice b before she presents] <= 1/2^M + eps_priv, *given* Table 6 C-F (Alice's reporting strategy leaks nothing about her bases or z; no side channels; equal detectors). For 2^M points, Eq. (11) gives eps_priv^M = 2^-M[(1 + 2 beta_E)^M - 1]. Code: bound `P-S2/priv`.

**Status of the obligation: UNSUPPORTED.** The master-plan obligation is an empirical test of issuer location-inference advantage under the defined privacy game, with statistical intervals. That test has not been run.

**No theorem means no value.** W1, W1_CV, S1 (prose argument only), D1 (MAC hides merchant; no epsilon stated), A1 and C1 have no privacy theorem in the registry. The evaluators return `UNSUPPORTED` with `value = None`. The checker rejects any certificate that reports a privacy bound (including 0) without a theorem, and any privacy target that has no applicable bound (tested).
