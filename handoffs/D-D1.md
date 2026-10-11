# Lane D handoff: proofs (D-D1)

Branch `feat/D-proofs`, starting at `ece05ef`. The machine-readable record is `D-D1.json`.

**Delivered**
- Theorem registry: `proofs/OBLIGATIONS.yaml` and `qmint/proofs/registry.py`. It covers P-W1, P-W1CV, P-W2, P-S1, P-S2, P-S3, P-D1, P-C1, P-OPT and P-PRIV with every field from plan 3.6, plus source URLs, PDF hashes and equation anchors.
- Ideal bounds (`qmint/proofs/ideal_bounds.py`, log-space): W1, W1_CV and S1 are guarded by game ID. n_min at 1e-9 is 73, 273 and 131, the same as `bootstrap/`.
- Finite-size bounds (`qmint/proofs/finite_size.py`):
  - Kent 2022: Lemmas 2-4 and Theorems 1-2.
  - Schiansky 2023: SI Eqs. 16-23.
  - Any request outside a theorem's domain gets an UNSUPPORTED or out-of-domain result with no value.
- Assumption checks (`qmint/proofs/assumption_check.py`): declared-hypothesis predicates, noise-source and calibration-family checks, and interval propagation at the worst endpoint using documented, tested monotonicity directions.
- Independent checker (`qmint/proofs/checker.py`): uses 60-digit Decimal arithmetic, its own trig series and brute-force interval corners, and imports none of the evaluator modules. It also accepts CERTIFIED_NUMERIC SDP certificates, but only when residual padding is accounted for.
- Engine (`qmint/proofs/engine.py`): dispatches requests and builds draft certificates.
- Reproduction script: `qmint/proofs/reproduce.py`.
- Dossiers: `proofs/notes/*.md`.

**Tests:** 214 passed (`tests/contracts` plus `tests/unit/proofs`), and the smoke test passes. Ruff is clean.

**Key reproductions:** see `proofs/certificates/reproduction_v1.json`.
- Kent 2022:
  - eps_rob = e^-1052.6.
  - P_noqub, P_det^theo, beta_PB, beta_PS and E all match the counts in the paper.
  - Fig. 5 beta_max: 6.9e-6 (paper 6e-6), 2.25e-4 (paper ~2.3e-4) and 5.9e-4 (paper ~6e-4).
  - Kent's experimental tuple falls outside the Theorem 1 domain.
- Schiansky 2023: p_d = 5.911e-45 reproduces exactly, but only with N = 4.2e6 and p_m = 6.02%, not the SI Table N or the main-text p_m.

**Open question (flagged, not asserted):** Schiansky applies Chernoff to the weighted mishap sum (4+2√2)e + l. That variable takes values in {0, 1, 6.83}, outside the {0,1} hypothesis of the Chernoff bound. Rescaling it into [0,1], as the textbook bound requires, weakens p_d to 3.3e-7. D1 is therefore never certified.

**Pending other lanes:** P-W2 (lane C), P-S3 (lane G), P-C1 (lane H), P-OPT (lane I), and the empirical privacy-game test for P-PRIV.
