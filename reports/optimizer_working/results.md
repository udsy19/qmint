# Lane I: certificate compiler experiments X12 / X13 (generated)

Pre-registration commit `0268feed3b37bc0c6f6b544ccfc6eb882f134e91`; frozen_experiments.yaml sha256 `dc306b78bb14add4...`; software revision `ad36dbbf7ec271c9860bf1c085b22f585fff89da`; runtime 181.41 s.

Evidence: bounds = PUBLISHED_THEOREM re-derived by lane D's independent checker (S2/W1/S1); D1 = PUBLISHED_AGGREGATE, never certified. Kent Fig. 5 devices are DIGITIZED_FIGURE; half-beta devices and all interval boxes are HYPOTHETICAL. Issuance seconds use a HYPOTHETICAL 1e8 Hz rate (MODELLED). These are bounds under declared Table 6 idealisations, not experimental security evidence for any device.

## G5 verdict

**POSITIVE (pre-registered improvement rule met)**. Rule: G5 passes with a POSITIVE result iff the improvement rule holds on at least one frozen S2 device scenario at (epsilon_unf=1e-9, honest=1e-3, M=1) in BOTH point and interval versions; otherwise the negative result is reported. All other cells are secondary/exploratory (no multiple-testing correction is needed for the deterministic primary cell; secondary cells are labelled exploratory).

Released certificates: 320; independent-checker rejections among emitted candidates: 3.

Primary cell (eps_unf <= 1e-9, honest failure <= 1e-3, M = 1). N = prepared pulses per token; only CERTIFIED results get a number.

| device | uncertainty | published N | naive N | compiler N | naive/compiler | published/compiler |
|---|---|---|---|---|---|---|
| K22-F5a | point | 40,000,000 | 18,836,491 | 10,592,537 | 1.78 | 3.78 |
| K22-F5a | interval | INFEASIBLE | INFEASIBLE | INFEASIBLE | - | - |
| K22-F5b | point | INFEASIBLE | 35,481,339 | 8,413,951 | 4.22 | - |
| K22-F5b | interval | INFEASIBLE | INFEASIBLE | INFEASIBLE | - | - |
| K22-F5c | point | INFEASIBLE | 66,834,392 | 6,309,573 | 10.6 | - |
| K22-F5c | interval | INFEASIBLE | INFEASIBLE | INFEASIBLE | - | - |
| K22-F5a-half | point | 40,000,000 | 7,943,282 | 7,079,458 | 1.12 | 5.65 |
| K22-F5a-half | interval | INFEASIBLE | 749,894,209 | 105,925,373 | 7.08 | - |
| K22-F5b-half | point | 40,000,000 | 595,662 | 562,341 | 1.06 | 71.1 |
| K22-F5b-half | interval | INFEASIBLE | 2,371,374 | 1,496,236 | 1.58 | - |
| K22-F5c-half | point | 40,000,000 | 446,684 | 421,697 | 1.06 | 94.9 |
| K22-F5c-half | interval | INFEASIBLE | 473,151 | 421,697 | 1.12 | - |

## X12: S2 target sweep (honest failure <= 1e-3, M = 1, certified N)

| device | unc | eps_unf | published | naive | compiler |
|---|---|---|---|---|---|
| K22-F5a | point | 0.001 | 40,000,000 | 11,885,022 | 9,440,609 |
| K22-F5a | point | 1e-06 | 40,000,000 | 18,836,491 | 10,592,537 |
| K22-F5a | point | 1e-09 | 40,000,000 | 18,836,491 | 10,592,537 |
| K22-F5a | point | 1e-12 | INFEASIBLE | 18,836,491 | 13,335,214 |
| K22-F5a | interval | 0.001 | INFEASIBLE | INFEASIBLE | INFEASIBLE |
| K22-F5a | interval | 1e-06 | INFEASIBLE | INFEASIBLE | INFEASIBLE |
| K22-F5a | interval | 1e-09 | INFEASIBLE | INFEASIBLE | INFEASIBLE |
| K22-F5a | interval | 1e-12 | INFEASIBLE | INFEASIBLE | INFEASIBLE |
| K22-F5a-half | point | 0.001 | 40,000,000 | 6,683,439 | 4,466,836 |
| K22-F5a-half | point | 1e-06 | 40,000,000 | 7,498,942 | 6,683,439 |
| K22-F5a-half | point | 1e-09 | 40,000,000 | 7,943,282 | 7,079,458 |
| K22-F5a-half | point | 1e-12 | INFEASIBLE | 10,592,537 | 7,079,458 |
| K22-F5a-half | interval | 0.001 | INFEASIBLE | 749,894,209 | 84,139,514 |
| K22-F5a-half | interval | 1e-06 | INFEASIBLE | 749,894,209 | 105,925,373 |
| K22-F5a-half | interval | 1e-09 | INFEASIBLE | 749,894,209 | 105,925,373 |
| K22-F5a-half | interval | 1e-12 | INFEASIBLE | FEASIBLE | 105,925,373 |
| K22-F5b | point | 0.001 | INFEASIBLE | 35,481,339 | 8,413,951 |
| K22-F5b | point | 1e-06 | INFEASIBLE | 35,481,339 | 8,413,951 |
| K22-F5b | point | 1e-09 | INFEASIBLE | 35,481,339 | 8,413,951 |
| K22-F5b | point | 1e-12 | INFEASIBLE | 35,481,339 | 11,220,185 |
| K22-F5b | interval | 0.001 | INFEASIBLE | INFEASIBLE | INFEASIBLE |
| K22-F5b | interval | 1e-06 | INFEASIBLE | INFEASIBLE | INFEASIBLE |
| K22-F5b | interval | 1e-09 | INFEASIBLE | INFEASIBLE | INFEASIBLE |
| K22-F5b | interval | 1e-12 | INFEASIBLE | INFEASIBLE | INFEASIBLE |
| K22-F5b-half | point | 0.001 | 40,000,000 | 398,107 | 398,107 |
| K22-F5b-half | point | 1e-06 | 40,000,000 | 595,662 | 562,341 |
| K22-F5b-half | point | 1e-09 | 40,000,000 | 595,662 | 562,341 |
| K22-F5b-half | point | 1e-12 | INFEASIBLE | 794,328 | 707,946 |
| K22-F5b-half | interval | 0.001 | INFEASIBLE | 1,496,236 | 1,333,521 |
| K22-F5b-half | interval | 1e-06 | INFEASIBLE | 1,678,804 | 1,333,521 |
| K22-F5b-half | interval | 1e-09 | INFEASIBLE | 2,371,374 | 1,496,236 |
| K22-F5b-half | interval | 1e-12 | INFEASIBLE | 2,371,374 | 1,995,262 |
| K22-F5c | point | 0.001 | INFEASIBLE | 63,095,734 | 3,981,072 |
| K22-F5c | point | 1e-06 | INFEASIBLE | 66,834,392 | 5,308,844 |
| K22-F5c | point | 1e-09 | INFEASIBLE | 66,834,392 | 6,309,573 |
| K22-F5c | point | 1e-12 | INFEASIBLE | 66,834,392 | 6,309,573 |
| K22-F5c | interval | 0.001 | INFEASIBLE | INFEASIBLE | INFEASIBLE |
| K22-F5c | interval | 1e-06 | INFEASIBLE | INFEASIBLE | INFEASIBLE |
| K22-F5c | interval | 1e-09 | INFEASIBLE | INFEASIBLE | INFEASIBLE |
| K22-F5c | interval | 1e-12 | INFEASIBLE | INFEASIBLE | INFEASIBLE |
| K22-F5c-half | point | 0.001 | 40,000,000 | 446,684 | 421,697 |
| K22-F5c-half | point | 1e-06 | 40,000,000 | 446,684 | 421,697 |
| K22-F5c-half | point | 1e-09 | 40,000,000 | 446,684 | 421,697 |
| K22-F5c-half | point | 1e-12 | INFEASIBLE | 446,684 | 421,697 |
| K22-F5c-half | interval | 0.001 | INFEASIBLE | 473,151 | 421,697 |
| K22-F5c-half | interval | 1e-06 | INFEASIBLE | 473,151 | 421,697 |
| K22-F5c-half | interval | 1e-09 | INFEASIBLE | 473,151 | 421,697 |
| K22-F5c-half | interval | 1e-12 | INFEASIBLE | 473,151 | 421,697 |

## X12: ideal games (all four selectors, CERTIFIED)

| game | eps_unf | selector | N | closed form | checker |
|---|---|---|---|---|---|
| W1 | 0.001 | naive_analytic | 25 | 25 | CERTIFIED |
| W1 | 0.001 | exhaustive_oracle | 25 | 25 | CERTIFIED |
| W1 | 0.001 | compiler | 25 | 25 | CERTIFIED |
| W1 | 1e-06 | naive_analytic | 49 | 49 | CERTIFIED |
| W1 | 1e-06 | exhaustive_oracle | 49 | 49 | CERTIFIED |
| W1 | 1e-06 | compiler | 49 | 49 | CERTIFIED |
| W1 | 1e-09 | naive_analytic | 73 | 73 | CERTIFIED |
| W1 | 1e-09 | exhaustive_oracle | 73 | 73 | CERTIFIED |
| W1 | 1e-09 | compiler | 73 | 73 | CERTIFIED |
| W1 | 1e-12 | naive_analytic | 97 | 97 | CERTIFIED |
| W1 | 1e-12 | exhaustive_oracle | 97 | 97 | CERTIFIED |
| W1 | 1e-12 | compiler | 97 | 97 | CERTIFIED |
| S1 | 0.001 | naive_analytic | 44 | 44 | CERTIFIED |
| S1 | 0.001 | exhaustive_oracle | 44 | 44 | CERTIFIED |
| S1 | 0.001 | compiler | 44 | 44 | CERTIFIED |
| S1 | 1e-06 | naive_analytic | 88 | 88 | CERTIFIED |
| S1 | 1e-06 | exhaustive_oracle | 88 | 88 | CERTIFIED |
| S1 | 1e-06 | compiler | 88 | 88 | CERTIFIED |
| S1 | 1e-09 | naive_analytic | 131 | 131 | CERTIFIED |
| S1 | 1e-09 | exhaustive_oracle | 131 | 131 | CERTIFIED |
| S1 | 1e-09 | compiler | 131 | 131 | CERTIFIED |
| S1 | 1e-12 | naive_analytic | 175 | 175 | CERTIFIED |
| S1 | 1e-12 | exhaustive_oracle | 175 | 175 | CERTIFIED |
| S1 | 1e-12 | compiler | 175 | 175 | CERTIFIED |

## X12: compiler vs exhaustive oracle on the small grids

| scenario | grid pts | oracle N | compiler N | identical | oracle calls | compiler calls | oracle s | compiler s | oracle peak B | compiler peak B |
|---|---|---|---|---|---|---|---|---|---|---|
| S2/K22-F5a/point/M1/unf1e-06/h0.001 | 129,024 | 39,810,717 | 39,810,717 | yes | 387,072 | 353 | 6.49 | 0.0116 | 1,049,385 | 164,729 |
| S2/K22-F5a/point/M1/unf1e-09/h0.001 | 129,024 | 39,810,717 | 39,810,717 | yes | 387,072 | 354 | 6.43 | 0.0114 | - | - |
| S2/K22-F5a/interval/M1/unf1e-06/h0.001 | 129,024 | INFEASIBLE | INFEASIBLE | yes | 387,072 | 28 | 9.65 | 0.0014 | - | - |
| S2/K22-F5a/interval/M1/unf1e-09/h0.001 | 129,024 | INFEASIBLE | INFEASIBLE | yes | 387,072 | 28 | 9.88 | 0.0015 | - | - |
| S2/K22-F5b/point/M1/unf1e-06/h0.001 | 129,024 | 15,848,932 | 15,848,932 | yes | 387,072 | 323 | 6.65 | 0.0108 | - | - |
| S2/K22-F5b/point/M1/unf1e-09/h0.001 | 129,024 | 15,848,932 | 15,848,932 | yes | 387,072 | 323 | 6.64 | 0.011 | - | - |
| S2/K22-F5b/interval/M1/unf1e-06/h0.001 | 129,024 | INFEASIBLE | INFEASIBLE | yes | 387,072 | 27 | 10.3 | 0.0016 | - | - |
| S2/K22-F5b/interval/M1/unf1e-09/h0.001 | 129,024 | INFEASIBLE | INFEASIBLE | yes | 387,072 | 27 | 10.1 | 0.0015 | - | - |
| S2/K22-F5c/point/M1/unf1e-06/h0.001 | 129,024 | 15,848,932 | 15,848,932 | yes | 387,072 | 296 | 6.78 | 0.011 | - | - |
| S2/K22-F5c/point/M1/unf1e-09/h0.001 | 129,024 | 15,848,932 | 15,848,932 | yes | 387,072 | 296 | 6.92 | 0.0111 | - | - |
| S2/K22-F5c/interval/M1/unf1e-06/h0.001 | 129,024 | INFEASIBLE | INFEASIBLE | yes | 387,072 | 28 | 10.2 | 0.0016 | - | - |
| S2/K22-F5c/interval/M1/unf1e-09/h0.001 | 129,024 | INFEASIBLE | INFEASIBLE | yes | 387,072 | 28 | 10.1 | 0.0017 | - | - |
| D1/D1-PUB-SI/unf1e-06/h0.001 | 18,081 | 63,096 | 63,096 | yes | 36,162 | 389 | 0.554 | 0.0113 | 540,358 | 205,813 |
| D1/D1-PUB-SI/unf1e-09/h0.001 | 18,081 | 63,096 | 63,096 | yes | 36,162 | 389 | 0.554 | 0.0112 | - | - |
| D1/D1-ZEN-IID/unf1e-06/h0.001 | 18,081 | 398,107 | 398,107 | yes | 36,162 | 247 | 0.77 | 0.0138 | - | - |
| D1/D1-ZEN-IID/unf1e-09/h0.001 | 18,081 | 398,107 | 398,107 | yes | 36,162 | 246 | 0.778 | 0.0131 | - | - |

## X12: published recipes at matched security

| scenario | match | published N | compiler N | published/compiler | note |
|---|---|---|---|---|---|
| S2/K22-F5a/point/M1/strict-matched | strict | 40,000,000 | 33,496,544 | 1.19 | published eps_rob is below float range; matched only to 1e-300 (weaker than published on eps_rob) |
| S2/K22-F5a/interval/M1/unf1e-09/h0.001 | strict | - | - | - | NO_APPLICABLE_BOUND_AT_DEVICE |
| S2/K22-F5b/point/M1/unf1e-09/h0.001 | strict | - | - | - | NO_APPLICABLE_BOUND_AT_DEVICE |
| S2/K22-F5b/interval/M1/unf1e-09/h0.001 | strict | - | - | - | NO_APPLICABLE_BOUND_AT_DEVICE |
| S2/K22-F5c/point/M1/unf1e-09/h0.001 | strict | - | - | - | NO_APPLICABLE_BOUND_AT_DEVICE |
| S2/K22-F5c/interval/M1/unf1e-09/h0.001 | strict | - | - | - | NO_APPLICABLE_BOUND_AT_DEVICE |
| S2/K22-F5a-half/point/M1/strict-matched | strict | 40,000,000 | 18,836,491 | 2.12 | published eps_rob is below float range; matched only to 1e-300 (weaker than published on eps_rob) |
| S2/K22-F5a-half/interval/M1/unf1e-09/h0.001 | strict | - | - | - | NO_APPLICABLE_BOUND_AT_DEVICE |
| S2/K22-F5b-half/point/M1/strict-matched | strict | 40,000,000 | 2,985,383 | 13.4 | published eps_rob is below float range; matched only to 1e-300 (weaker than published on eps_rob) |
| S2/K22-F5b-half/interval/M1/unf1e-09/h0.001 | strict | - | - | - | NO_APPLICABLE_BOUND_AT_DEVICE |
| S2/K22-F5c-half/point/M1/strict-matched | strict | 40,000,000 | 1,188,502 | 33.7 | published eps_rob is below float range; matched only to 1e-300 (weaker than published on eps_rob) |
| S2/K22-F5c-half/interval/M1/unf1e-09/h0.001 | strict | - | - | - | NO_APPLICABLE_BOUND_AT_DEVICE |
| D1/D1-PUB-SI/strict-matched | strict | 4,200,000 | 1,188,502 | 3.53 | UNCERTIFIED by construction (D1) |
| D1/D1-PUB-SI/design-matched | design | 4,200,000 | 133,352 | - | UNCERTIFIED by construction (D1) |

## X12: rejections and infeasibility certificates

| request | outcome | reason |
|---|---|---|
| game W2 | REJECTED | game W2: no published theorem / certified bound registered (lane D); the compiler refuses it |
| game A1 | REJECTED | game A1: no published theorem / certified bound registered (lane D); the compiler refuses it |
| game C1 | REJECTED | game C1: no published theorem / certified bound registered (lane D); the compiler refuses it |
| S2 reporting strategy 'report_with_basis' | REJECTED | reporting strategy 'report_with_basis' unsupported: only ['QT1', 'QT2'] satisfy KLPR2022 Table 6 C/D (Lemma 5) |
| W1 with noise parameter E | REJECTED | ideal: parameters ['E'] are not part of the W1 theorem |
| S2 with Schiansky 2023 calibration | REJECTED | calibration family 'schiansky_2023' cannot be used in the S2 proof model (needs 'kent_2022'; no cross-protocol calibration transfer) |
| D1 with three merchants | REJECTED | D1 analysis covers exactly two merchants (SI Note 3A) |
| Jiang 2024 published tuple (S2_JIANG24) | REJECTED | REJECTED: theorem T-JIANG24-THM1 is not a registered game (S2_JIANG24 not in GameId); never scored under KLPR2022 S2 |
| W1 with privacy target 1e-2 | INFEASIBLE | epsilon_priv: no applicable bound meets the target | unmet axes at N=512: ['epsilon_priv'] |
| D1 with privacy target 1e-2 | OUT_OF_MODEL | epsilon_priv: no D1 theorem for this axis (never reported as 0) | unmet axes at N=10000000000: ['epsilon_priv'] |
| S2 K22-F5a privacy target 0.01 (beta_E=0.001, HYPOTHETICAL) | FEASIBLE | all bounds re-derived independently (qmint.proofs.checker/decimal-v1) and every target met |
| S2 K22-F5a privacy target 0.0001 (beta_E=0.001, HYPOTHETICAL) | INFEASIBLE | epsilon_priv: Lemma 4 bound (beta_E, fixed by the device) exceeds the target | unmet axes at N=10000000000: ['epsilon_priv'] |
| S2 missing declaration table6_E_no_side_channels | OUT_OF_MODEL | no feasible configuration at the largest grid N (see infeasibility certificate) | unmet axes at N=10000000000: ['epsilon_unf', 'epsilon_cor', 'epsilon_rob'] |
| S2 K22-EXP (paper's experimental tuple) | INFEASIBLE | no feasible configuration at the largest grid N (see infeasibility certificate) | unmet axes at N=10000000000: ['epsilon_unf'] |

## X12: D1 (Schiansky 2023) -- UNCERTIFIED by construction

Lane D's checker never certifies D1 (fitted SDP boundary, informal de Finetti, open Chernoff question). Numbers below are numerical support only and are excluded from every certified comparison and Pareto front.

| device | eps_unf | published | naive | compiler |
|---|---|---|---|---|
| D1-PUB-SI | 1e-06 | 4,200,000 | 595,662 | 37,584 |
| D1-PUB-SI | 1e-09 | 4,200,000 | 891,251 | 44,668 |
| D1-PUB-SI | 1e-12 | 4,200,000 | 1,188,502 | 53,088 |
| D1-PUB-INT | 1e-06 | INFEASIBLE | INFEASIBLE | 141,254 |
| D1-PUB-INT | 1e-09 | INFEASIBLE | INFEASIBLE | 177,828 |
| D1-PUB-INT | 1e-12 | INFEASIBLE | INFEASIBLE | 211,349 |
| D1-ZEN-IID | 1e-06 | INFEASIBLE | INFEASIBLE | 237,137 |
| D1-ZEN-IID | 1e-09 | INFEASIBLE | INFEASIBLE | 281,838 |
| D1-ZEN-IID | 1e-12 | INFEASIBLE | INFEASIBLE | 334,965 |
| D1-ZEN-DRIFT | 1e-06 | INFEASIBLE | INFEASIBLE | INFEASIBLE |
| D1-ZEN-DRIFT | 1e-09 | INFEASIBLE | INFEASIBLE | INFEASIBLE |
| D1-ZEN-DRIFT | 1e-12 | INFEASIBLE | INFEASIBLE | INFEASIBLE |

## X13: uncertainty ablation (S2, honest <= 1e-3)

| device | eps_unf | selector | N point | N interval | point selection re-scored on interval box |
|---|---|---|---|---|---|
| K22-F5a | 0.001 | compiler | 9,440,609 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5a | 0.001 | naive_analytic | 11,885,022 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5a | 0.001 | published_fixed | 40,000,000 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5a | 1e-06 | compiler | 10,592,537 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5a | 1e-06 | naive_analytic | 18,836,491 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5a | 1e-06 | published_fixed | 40,000,000 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5a | 1e-09 | compiler | 10,592,537 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5a | 1e-09 | naive_analytic | 18,836,491 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5a | 1e-09 | published_fixed | 40,000,000 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5a | 1e-12 | compiler | 13,335,214 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5a | 1e-12 | naive_analytic | 18,836,491 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5a | 1e-12 | published_fixed | INFEASIBLE | INFEASIBLE | - |
| K22-F5b | 0.001 | compiler | 8,413,951 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5b | 0.001 | naive_analytic | 35,481,339 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5b | 0.001 | published_fixed | INFEASIBLE | INFEASIBLE | - |
| K22-F5b | 1e-06 | compiler | 8,413,951 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5b | 1e-06 | naive_analytic | 35,481,339 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5b | 1e-06 | published_fixed | INFEASIBLE | INFEASIBLE | - |
| K22-F5b | 1e-09 | compiler | 8,413,951 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5b | 1e-09 | naive_analytic | 35,481,339 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5b | 1e-09 | published_fixed | INFEASIBLE | INFEASIBLE | - |
| K22-F5b | 1e-12 | compiler | 11,220,185 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5b | 1e-12 | naive_analytic | 35,481,339 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5b | 1e-12 | published_fixed | INFEASIBLE | INFEASIBLE | - |
| K22-F5c | 0.001 | compiler | 3,981,072 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5c | 0.001 | naive_analytic | 63,095,734 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5c | 0.001 | published_fixed | INFEASIBLE | INFEASIBLE | - |
| K22-F5c | 1e-06 | compiler | 5,308,844 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5c | 1e-06 | naive_analytic | 66,834,392 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5c | 1e-06 | published_fixed | INFEASIBLE | INFEASIBLE | - |
| K22-F5c | 1e-09 | compiler | 6,309,573 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5c | 1e-09 | naive_analytic | 66,834,392 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5c | 1e-09 | published_fixed | INFEASIBLE | INFEASIBLE | - |
| K22-F5c | 1e-12 | compiler | 6,309,573 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5c | 1e-12 | naive_analytic | 66,834,392 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5c | 1e-12 | published_fixed | INFEASIBLE | INFEASIBLE | - |
| K22-F5a-half | 0.001 | compiler | 4,466,836 | 84,139,514 | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5a-half | 0.001 | naive_analytic | 6,683,439 | 749,894,209 | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5a-half | 0.001 | published_fixed | 40,000,000 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5a-half | 1e-06 | compiler | 6,683,439 | 105,925,373 | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5a-half | 1e-06 | naive_analytic | 7,498,942 | 749,894,209 | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5a-half | 1e-06 | published_fixed | 40,000,000 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5a-half | 1e-09 | compiler | 7,079,458 | 105,925,373 | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5a-half | 1e-09 | naive_analytic | 7,943,282 | 749,894,209 | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5a-half | 1e-09 | published_fixed | 40,000,000 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5a-half | 1e-12 | compiler | 7,079,458 | 105,925,373 | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5a-half | 1e-12 | naive_analytic | 10,592,537 | 749,894,209 | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5a-half | 1e-12 | published_fixed | INFEASIBLE | INFEASIBLE | - |
| K22-F5b-half | 0.001 | compiler | 398,107 | 1,333,521 | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5b-half | 0.001 | naive_analytic | 398,107 | 1,496,236 | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5b-half | 0.001 | published_fixed | 40,000,000 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5b-half | 1e-06 | compiler | 562,341 | 1,333,521 | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5b-half | 1e-06 | naive_analytic | 595,662 | 1,678,804 | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5b-half | 1e-06 | published_fixed | 40,000,000 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5b-half | 1e-09 | compiler | 562,341 | 1,496,236 | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5b-half | 1e-09 | naive_analytic | 595,662 | 2,371,374 | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5b-half | 1e-09 | published_fixed | 40,000,000 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5b-half | 1e-12 | compiler | 707,946 | 1,995,262 | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5b-half | 1e-12 | naive_analytic | 794,328 | 2,371,374 | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5b-half | 1e-12 | published_fixed | INFEASIBLE | INFEASIBLE | - |
| K22-F5c-half | 0.001 | compiler | 421,697 | 421,697 | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5c-half | 0.001 | naive_analytic | 446,684 | 473,151 | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5c-half | 0.001 | published_fixed | 40,000,000 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5c-half | 1e-06 | compiler | 421,697 | 421,697 | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5c-half | 1e-06 | naive_analytic | 446,684 | 473,151 | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5c-half | 1e-06 | published_fixed | 40,000,000 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5c-half | 1e-09 | compiler | 421,697 | 421,697 | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5c-half | 1e-09 | naive_analytic | 446,684 | 473,151 | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5c-half | 1e-09 | published_fixed | 40,000,000 | INFEASIBLE | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5c-half | 1e-12 | compiler | 421,697 | 421,697 | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5c-half | 1e-12 | naive_analytic | 446,684 | 473,151 | NOT certified under interval (point selection unsafe under uncertainty) |
| K22-F5c-half | 1e-12 | published_fixed | INFEASIBLE | INFEASIBLE | - |

## X13: IID vs drift-aware calibration, frozen selection, holdout runs 6-10 (D1, UNCERTIFIED)

Frozen selection sha256 `965dcd2ceaeaf7ed...`. Calibration e_h intervals: IID 0.03287-0.0335, drift-aware 0.02894-0.0377. Holdout coverage: IID 0%, drift-aware 100%.

| run | QBER (X) | in IID | in drift | IID-selected config | drift-selected config |
|---|---|---|---|---|---|
| 6 | 0.0323 | no | yes | targets met | NO_FROZEN_CONFIG (selection infeasible) |
| 7 | 0.0318 | no | yes | targets met | NO_FROZEN_CONFIG (selection infeasible) |
| 8 | 0.0324 | no | yes | targets met | NO_FROZEN_CONFIG (selection infeasible) |
| 9 | 0.032 | no | yes | targets met | NO_FROZEN_CONFIG (selection infeasible) |
| 10 | 0.0342 | no | yes | INADMISSIBLE (SI Eq. 23 fails on holdout interval) | NO_FROZEN_CONFIG (selection infeasible) |

## X13: fixed N vs joint thresholds (S2, primary cell)

| device | unc | log10 eps_unf published @4e7 | log10 eps_unf thresholds optimised @4e7 | N naive | N joint |
|---|---|---|---|---|---|
| K22-F5a | point | -11 | -87.9 | 18,836,491 | 10,592,537 |
| K22-F5a | interval | - | - | - | - |
| K22-F5b | point | - | -221 | 35,481,339 | 8,413,951 |
| K22-F5b | interval | - | - | - | - |
| K22-F5c | point | - | -350 | 66,834,392 | 6,309,573 |
| K22-F5c | interval | - | - | - | - |
| K22-F5a-half | point | -11 | -150 | 7,943,282 | 7,079,458 |
| K22-F5a-half | interval | - | - | 749,894,209 | 105,925,373 |
| K22-F5b-half | point | -11 | -2.31e+03 | 595,662 | 562,341 |
| K22-F5b-half | interval | - | -1.08e+03 | 2,371,374 | 1,496,236 |
| K22-F5c-half | point | -11 | -5.55e+03 | 446,684 | 421,697 |
| K22-F5c-half | interval | - | -3.43e+03 | 473,151 | 421,697 |

## X13: presentation points (Theorem 2, C = L(L-1)/2)

| device | unc | points 2^M | C | compiler N |
|---|---|---|---|---|
| K22-F5a | point | 2 | 1 | 10,592,537 |
| K22-F5a | point | 4 | 6 | 11,885,022 |
| K22-F5a | point | 8 | 28 | 12,589,254 |
| K22-F5a | interval | 2 | 1 | INFEASIBLE |
| K22-F5a | interval | 4 | 6 | INFEASIBLE |
| K22-F5a | interval | 8 | 28 | INFEASIBLE |
| K22-F5b | point | 2 | 1 | 8,413,951 |
| K22-F5b | point | 4 | 6 | 9,440,609 |
| K22-F5b | point | 8 | 28 | 10,000,000 |
| K22-F5b | interval | 2 | 1 | INFEASIBLE |
| K22-F5b | interval | 4 | 6 | INFEASIBLE |
| K22-F5b | interval | 8 | 28 | INFEASIBLE |
| K22-F5c | point | 2 | 1 | 6,309,573 |
| K22-F5c | point | 4 | 6 | 7,079,458 |
| K22-F5c | point | 8 | 28 | 7,079,458 |
| K22-F5c | interval | 2 | 1 | INFEASIBLE |
| K22-F5c | interval | 4 | 6 | INFEASIBLE |
| K22-F5c | interval | 8 | 28 | INFEASIBLE |
| K22-F5a-half | point | 2 | 1 | 7,079,458 |
| K22-F5a-half | point | 4 | 6 | 7,498,942 |
| K22-F5a-half | point | 8 | 28 | 7,943,282 |
| K22-F5a-half | interval | 2 | 1 | 105,925,373 |
| K22-F5a-half | interval | 4 | 6 | 118,850,223 |
| K22-F5a-half | interval | 8 | 28 | 118,850,223 |
| K22-F5b-half | point | 2 | 1 | 562,341 |
| K22-F5b-half | point | 4 | 6 | 595,662 |
| K22-F5b-half | point | 8 | 28 | 630,957 |
| K22-F5b-half | interval | 2 | 1 | 1,496,236 |
| K22-F5b-half | interval | 4 | 6 | 1,678,804 |
| K22-F5b-half | interval | 8 | 28 | 1,778,279 |
| K22-F5c-half | point | 2 | 1 | 421,697 |
| K22-F5c-half | point | 4 | 6 | 473,151 |
| K22-F5c-half | point | 8 | 28 | 501,187 |
| K22-F5c-half | interval | 2 | 1 | 421,697 |
| K22-F5c-half | interval | 4 | 6 | 473,151 |
| K22-F5c-half | interval | 8 | 28 | 473,151 |

## Checker accounting

Released (CERTIFIED by lane D's independent checker): 320. Rejected by the checker: 3. D1 certificates UNCERTIFIED by construction: 71.

