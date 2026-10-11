# B-B3 Schiansky et al. 2023 quantum-digital payments (D1) -- lane B handoff

- Code: `qmint/protocols/schiansky_payment_2023.py`; tests `tests/unit/protocols/test_protocols_schiansky.py`.
- The TTP, client and merchant flow follows P04 steps 2-5. One MAC tag bit sets the basis of each sub-token of N states. The basis-bit mapping comes from the paper's (0101, 0011) example. Two TTP rules exist: the ideal step-5 rule, and the SI Note 3C mishap rule M(e,l) = (4+2 sqrt2) e + l. A payment ledger records accepted payments, `check()` is the stateless D1 predicate, and the module emits C4 events.
- Reproduced SI Table 2 aggregates: M = 0.448, allowed = 0.4849, and eq. (23) holds.
- Finding (MONTE_CARLO, depends on an interpretation): at the paper's operating point with delta_h = 0.031, the honest pass rate per sub-token is 0.63 at N=2e3 and 0.9989 at N=2e5.
- The source leaves some things unspecified, so the following are interpretations, not facts:
  - the concrete MAC family (a GF(2^ell) strongly-universal instance is used);
  - the e/l estimators and the granularity of the threshold test.
- The 2023 correction only changes the Discussion's unbounded-purchase extension, which is not implemented.
