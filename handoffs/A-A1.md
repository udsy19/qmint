# Handoff A-A1: literature, novelty, licensing

Branch `feat/A-research`, starting from `ece05ef`, research commit `8d9c138`. Tests: `pytest tests/contracts tests/unit/research` gives exit 0, 24 passed (6 research). Ruff is clean. No paid jobs were run.

## Deliverables
- `research/PRIOR_ART_MATRIX.csv`: 24 rows (P01–P12 plus P13–P24 found in this audit). Each row has an access status.
- `research/THEOREM_REGISTRY_SEED.yaml`: 15 theorem entries for MVW W1/W1_CV/Sec 3.5, Kent 2022 Lemmas 1–5 and Thm 1–2, Schiansky SDP/asymptotic/finite-N, Jiang Thm 1 and Gavinsky. Each entry has per-field VERIFIED_FROM_SOURCE / NOT_VERIFIED status and URL plus page/equation anchors.
- `research/DATASOURCE_REGISTER.yaml`: Zenodo records (API metadata, md5 checksums, sizes, archive listings), RIPE Atlas, and licences for 17 software repos.
- `research/NOVELTY_HYPOTHESES.md` (7 conflicts, 11 disallowed statements), `research/CORRECTIONS.md`, `research/LICENSE_AND_PATENT_RISKS.md`, `licenses/REFERENCE_AUDIT.md`.

## Key findings for other lanes
- **B/C/D:** the bases are W1 = (3/4)^n, W1_CV = (3/4+√2/8)^n and S1 = (1/2+1/(2√2))^N. These are three different games, verified against the primary sources. MVW Sec 3.5's binomial tail is a *joint*-success threshold game and doesn't cover W2.
- **E:** the paper cites Zenodo 7979319 (v1), but a newer v2 (7997998) exists with identical chunks plus raw `tagfile_example`. The code (8020667) ships `LICENSE_AGPLv3` against CC BY metadata, so don't copy it. It also has no SDP or security code.
- **D:** Schiansky's main text and SI disagree on p_m (6.76 vs 6.02 %) and N (4.2e6 vs 4.48e6). p_d = 5.91e-45 recomputes only with N = 4.2e6. The SI Choi normalisation and the "2×2 dual" are inconsistent. The applicability of the Chernoff bound to the weighted M(e,l) is an open question. The 2023 correction only changes one Discussion sentence.
- **I/N:** the closest prior art to the compiler is Kent 2022 (device-parameter ε maps and secure region), Jiang 2024 (7σ confidence propagation and measured time advantage), Schiansky/Bozzio (loss-error SDP) and the QKD tools (openQKDsecurity, numerical_qkd). The defensible claim is a reproducible, game-typed certificate and benchmark platform, plus any *measured* resource gain over published tuples.

## Proposed interface changes (not applied)
- Add GameIds `W1_THRESH_JOINT` and `S2_JIANG24`.
- Add an optional `dataset_version_doi` field for provenance.

## Blockers and limitations
- The EP 23168897.9 status is unverified.
- Several references (P13–P16, P19–P22) were checked at metadata level only, and P17 at abstract level only.
- The SI proofs were transcribed but not audited.
