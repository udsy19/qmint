# Changelog

## 0.1.0 — 2026-10-11 (Qollab × IonQ hackathon release)

- Frozen data contracts C0–C7 with canonical serialization and a secret boundary for issuer data.
- Protocols: Wiesner money; Kent et al. 2022 S-money (IQT1/IQT2/QT1/QT2); Schiansky et al. 2023 quantum-digital payments.
- Attacks: counterfeiting SDP with certified dual bounds (n = 1, 2), heuristic attacks with confidence intervals,
  negative controls; cross-run against the independent protocol implementation.
- Proofs: theorem registry, ideal and Kent 2022 finite-size bounds, independent checker.
- Real photon data: Zenodo 7979319 decoded; published QBERs reproduced.
- Classical baselines H0–H6 on a causal discrete-event simulator; matched-topology comparison with S-money.
- Pre-registered certificate compiler (negative: savings do not survive calibration uncertainty).
- FastAPI research API, Next.js website, static GitHub Pages snapshot, Qollab one-circuit `main.py`.
- Independent red-team audit; all five high-severity findings fixed with regression tests.
- Integrity pass: photon overdispersion (not drift); 2023 bound as an unresolved reproducibility finding;
  (5/8)ⁿ labelled attack-specific; no S-money latency advantage over classical late-commit escrow.
