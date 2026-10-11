# B-B2 Kent et al. 2022 S-money (IQT1/IQT2 ideal, QT1/QT2 realistic) -- lane B handoff

- Code: `qmint/protocols/kent_smoney_2022.py`; tests `tests/unit/protocols/test_protocols_kent_smoney.py`.
- Each step of P03 Tables 1-3 is a session method. Bob's agents B, B0 and B1 hold the secret. Alice-side entry points (`bank_send_quantum`, `alice_report_detections`, `alice_send_d`, `alice_send_c`, `present`) serve both honest and dishonest Alice. Events are C4 `TraceEvent`s with caller-supplied times and arrivals.
- Overlines (complements) in Table 1 were read from the HTML table page, because the PDF text drops them.
- Findings, all MONTE_CARLO or exact checks and no bounds:
  - Bob's view before the reveal is independent of b (exact enumeration, all four schemes).
  - A biased z gives Bob exactly a beta_E advantage.
  - In the S1 dual-presentation game, Breidbart measurement reaches (1/2+1/(2 sqrt2))^N, the Lemma 1 value.
  - Random-basis-then-guess reaches (3/4)^N.
  - QT honest acceptance matches the exact mixture formula for the simulated channel.
- Not implemented:
  - 2^M presentation points.
  - Photonic multi-photon effects and reporting strategies.
  - The preparation biases beta_PS and beta_PB, and the misalignment theta.
- Lemma and Theorem formulas are left to lane D.
