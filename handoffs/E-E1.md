# Lane E, task E1: Schiansky 2023 photonic data (X07) and calibration

**Result (PHOTON_EXPERIMENT):** reproduced both error rates published in Nat. Commun. 14, 3849
(2023) from the raw Zenodo 7979319 archive. I used the paper's own estimator, which is the mean over the two
TTP states of P(error | state):

| | This work | Paper |
|---|---|---|
| H/V | 1.4491% ± 0.0081 | 1.45 ± 0.01% |
| D/A | 3.2787% ± 0.0117 | 3.28 ± 0.01% |

Pooled errors/sifted gives 1.4301% (Z) and 3.2866% (X).

Main findings:
- The archive is ASCII TSV, not binary. The TTP and client files are row-paired, so each row pair is one coincidence.
- The "3 ns window" is a rounded 3-ns bin rule. It holds for all 8,964,878 pairs, and my matcher reproduces the pairing exactly in all 22 runs.
- Raw TTM8000 tags (v2 record 7997998) turned out to be the raw source of `linear/chunk00`. My independent offset, drift and matching pipeline finds a drift of −2.98 ns/s, recovers 94.7% of the archived pairs, gets QBER 1.458% (archived 1.463%) and estimates 1.8% accidental coincidences.
- Runs are overdispersed (chi²/dof ≈ 10), so the record intervals are a conservative hull rather than Clopper-Pearson alone.
- The two halves of the run sequence differ: the D/A holdout differs significantly (p = 0.003).
- Loss, efficiency and multiphoton probability can't be observed from this archive, so they are left null. The paper's values are kept separately as PUBLISHED_AGGREGATE.
- The authors' code (8020667) ships with an AGPL-3.0 license file although its metadata says CC-BY-4.0. I read it but copied nothing. It also can't run as published: it is missing `find_start_alt` and its requirements file.

Records go in `reports/data_working/schiansky2023/calibration_records.json` and carry `experiment_family=schiansky_2023`. `check_consumer` rejects them for S-money and Wiesner.

Tests: `$PY -m pytest tests/contracts tests/unit/photonics -q` exits 0 with 54 passed, 3 of them realdata.

Details, blockers and the migration proposals are in `E-E1.json`.
