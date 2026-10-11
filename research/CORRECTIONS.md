# Corrections, version changes and source discrepancies (lane A, A1)

Snapshot 2026-10-11. This file separates **published corrections** (issued by authors or publishers) from **discrepancies observed by lane A** (internal inconsistencies or recomputation mismatches). Discrepancies aren't errata. They're flags for lanes C/D/E to resolve against the primary source.

## 1. Published corrections

### P04 — Schiansky et al., "Demonstration of quantum-digital payments", Nat. Commun. 14, 3849 (2023)

* **Correction:** Author Correction, published **21 August 2023**, https://doi.org/10.1038/s41467-023-40866-x (Nat. Commun. 14:5059). Read in full (HTML and 1-page PDF, sha256 `5018ada3…6a223`).
* **Scope (verbatim from the correction):** the original Discussion section, 4th paragraph, 6th sentence, read:
  > "Remarkably, we can amend our protocol such that the number of purchases is not bounded by the MAC function: the Client simply encrypts a new random key R with C, and forwards the result along with the cryptogram to the TTP."

  It was corrected to:
  > "We can amend our protocol such that the number of purchases is not bounded by the MAC function, by growing C during the payment process: when the Client receives a new quantum token |P〉, we append additional quantum states for QKD, and use the cryptogram κ for authentication."
* **Lane A reading of significance (limited to what the text says):** the correction replaces a proposed key-refresh mechanism (encrypting a fresh key R under C) with a different one (growing C with extra QKD states, authenticated by κ). It changes **no equation, figure, table, measured value or security number**. The article page's change history lists only this correction. The corrected sentence is present in the current HTML (checked).
* **Impact on QMint:** if QMint models multi-purchase use of the same client key C, it must follow the corrected mechanism, or treat unbounded purchases as out of model and use the n-time-secure MAC bound. The single-payment D1 game is unaffected.

### Other papers

* P01 (arXiv 1202.4010): single arXiv version. No erratum found on arXiv. The conference version wasn't checked.
* P03 (npj QI 8:28): no correction listed on the article page. arXiv 2104.11717 has 4 versions (v4 2022-04-07, after journal publication). **Differences v1–v4 vs journal weren't diffed** (NOT_VERIFIED).
* P04 arXiv preprint 2305.14504 has v2 dated 2024-01-08, after publication and after the correction. Not diffed.
* P05 (2408.13063): v1 → v2 (2024-09-19). Not diffed. v2 used.
* P08 (2307.12120) v1–v5, P12 (2503.18890) v1–v4, P18 v1–v4, P22 v1–v3: revisions exist. Not diffed (out of scope for A1).

## 2. Dataset/code version changes

* **Zenodo data, concept 10.5281/zenodo.7979318:** the paper cites **v1 = 7979319** (153,143,236 B, md5 `fd708578…bf94`). A **newer version 7997998** (2023-06-02, 290,067,249 B, md5 `544ed5cf…72be`) exists. Its 44 chunk TSVs are byte-for-byte identical in name, size and CRC32. It adds `tagfile_example/SG.txt`, `tagfile_example/BG.txt` and an updated README.
* **Zenodo code, concept 10.5281/zenodo.7985330:** three versions (7985331 → 7997961 → 8020667). The paper cites the latest, 8020667.
* **Cross-reference error:** the code README says example tag files are under `10.5281/zenodo.7979319` in subfolder `tagfile_example`. They're only in 7997998.
* **Licence inconsistency:** the code record's Zenodo metadata says CC BY 4.0, but the archive contains `LICENSE_AGPLv3` (see LICENSE_AND_PATENT_RISKS.md).

## 3. Discrepancies observed by lane A (not errata; to be resolved)

| # | Source | Observation | Lane A check | Who resolves |
|---|---|---|---|---|
| D-1 | P04 main text vs SI Table 2 | Multiphoton probability 6.76±0.12 % (main) vs p_m = 6.02±0.28 % (SI) | Plugging each into SI eq.(16) at l=0.224 gives 3.795 % (main text reports 3.79 %) and 3.822 % (SI reports 3.82 %). The two documents use different p_m values. | E, D |
| D-2 | P04 main/Fig.4 vs SI Table 2 | Sub-token length N = 4.2×10⁶ (Fig. 4b) vs 4 482 440 ± 1600 (SI Table 2) | p_d = exp(−(δ_d²/2)·½(1−p_m/2)·N) = 5.91×10⁻⁴⁵ only with N = 4.2×10⁶ and p_m=0.0602 (exponent 101.84). N = 4 482 440 gives 6.3×10⁻⁴⁸. | D |
| D-3 | P04 SI eq.(6) | Choi operator defined with 1/d prefactor but TP condition written as Tr_out J = 1 (should be (1/d)·1 under that normalisation) | Visual check of SI p.2 | C |
| D-4 | P04 SI eq.(15) | Dual variable X1 called "Hermitian 2×2", while the TP constraint lives on 7-dim H_P | Visual/text check SI p.6 | C |
| D-5 | P04 SI Note 1C | Chernoff bounds stated for sums of independent {0,1} variables (with μ used both as per-trial mean and total). Then applied to the weighted combination M(e,l) = (4+2√2)e + l, whose per-trial values exceed 1. | Not a claim of error. Applicability needs a formal check. | D |
| D-6 | P04 SI Note 3B | Reduction from coherent to i.i.d. attacks is a qualitative de Finetti argument with no finite-N correction term | — | D, M |
| D-7 | P04 SI vs main text | SDP states written as X/Y eigenstates (|±〉, |±i〉) in SI. Main text uses H/V and D/A. | Relabeling of an MUB pair. Lanes B/C must fix convention C7 (Z/X). | B, C |
| D-8 | P05 eqs.(27),(29) | Reported ε′_cor = 2.1×10⁻¹¹, ε′_unf = 5.52×10⁻⁹ | Recomputing with the stated formula, K and P_wrong gives 1.82×10⁻¹¹ and 5.507×10⁻⁹. The reported values are *larger* (conservative). Likely rounding or different K. | D |
| D-9 | P03 Fig.5 example | γ_err and ν_cor per plotted point aren't published | ν_unf = 3.9×10⁻³ is consistent (recomputed 3.89×10⁻³ for first term = 5×10⁻¹⁰). Exact Fig.5 reproduction needs a parameter search. | D, I |
| D-10 | P04 code release | Missing `find_start_alt` module and `requirements.txt`. No security-analysis code. | Archive listing | E |
| D-11 | arXiv journal-ref for P04 | arXiv lists "Nature Communications 14, 3849 (2023)". Nature `citation_firstpage` is 3849, so they agree. The master plan doesn't give the article number. | consistent | — |

## 4. Reconciliation with the master-plan literature snapshot (§2, §16)

* §2 P04 says the dataset is "approximately 153 MB on the observed v1 record": **confirmed** (153,143,236 B). It doesn't mention v2 (290 MB). **Flag:** lane E must choose and record the version.
* §2 says "The code endpoint was not accessible in our initial browser check": it **is accessible now** via the Zenodo API (2026-10-11). See DATASOURCE_REGISTER.
* §2 P05 says "reports experimentally compared transactions over 2.77-km and 60.54-km links": **confirmed** from the abstract.
* §2 P07 "Kukharchyk et al., 2026": confirmed, now published as Quantum Sci. Technol. 11, 040501 (2026) per arXiv journal-ref.
* §2 P08 "Zhandry 2023/2025": published in TheoretiCS vol. 4 (2025-08-19), DOI 10.46298/theoretics.25.18.
* §2 P11 "Yuen": published in Quantum 9, 1691 (2025).
* §3.1 W1_CV "(3/4 + sqrt(2)/8)^n": **confirmed** (P01 Thm 2). The game is two independent classical challenges answered from one ticket, with the counterfeiter's POVM depending on both challenges.
* §3.1 S1 "(1/2+1/(2√2))^N": **confirmed** (P03 Lemma 1, eq.(1)). Proof in SI Note IV.
