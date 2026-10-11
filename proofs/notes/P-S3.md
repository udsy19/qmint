# P-S3: S-money spacetime / instant-validation invariant

**Status: UNSUPPORTED (pending lane G).** This is not an epsilon bound. Kent et al. 2022 (Tables 1-3, Fig. 1) require stage I and Alice's commitment to happen in the intersection of the causal pasts of all presentation points Q_i, and validation at Q_b to finish without waiting for any signal from points spacelike-separated from Q_b.

**Obligation.** For every simulated event DAG: (i) no event is caused by an event outside its past light cone (C4 already forbids retrocausal edges); (ii) the validation event at Q_b has no causal parent at any Q_{b'} spacelike-separated from it; (iii) Alice's commitment c lies in the causal past of every Q_i.

**Note.** The paper's discussion says the *security* of the schemes does not rely on spacetime constraints. The invariant is only needed for the claimed instant-validation advantage.
