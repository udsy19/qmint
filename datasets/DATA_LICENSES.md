# Data and third-party code licenses

| Item | Zenodo metadata | License file shipped in the archive | QMint handling |
|---|---|---|---|
| Data, 7979319 (v1) | CC-BY-4.0 | `LICENSE_CC_BY`: CC Attribution **3.0** Unported | Not redistributed. Derived aggregates are published with attribution (below). |
| Data, 7997998 (v2) | CC-BY-4.0 | same CC BY 3.0 text | Same as v1 |
| Code, 7985331 (v0) | CC-BY-4.0 | none | Read only |
| Code, 7997961 (v1) | CC-BY-4.0 | CC BY 3.0 text | Read only |
| Code, 8020667 (v2, cited by the paper) | CC-BY-4.0 | **GNU AGPL v3** | Read only. **No code copied.** `qmint/photonics` is an independent reconstruction (Apache-2.0). |

The metadata and the shipped license files disagree for both the data (4.0 vs 3.0) and the code
(CC-BY vs AGPL). Both CC BY versions allow redistributing derived numbers with attribution, so
the small CSV/JSON outputs in `reports/data_working/` are fine. For the code, QMint assumes the
most restrictive reading (AGPL-3.0) and keeps clear of it.

Attribution: P. Schiansky, J. Kalb, E. Sztatecsny, M.-C. Roehsner, T. Guggemos, A. Trenti,
M. Bozzio, P. Walther, "Data for Demonstration of quantum-digital payments", Zenodo (2023),
doi:10.5281/zenodo.7979319. Paper: Nat. Commun. 14, 3849 (2023), doi:10.1038/s41467-023-39519-w.
Correction: doi:10.1038/s41467-023-40866-x.
