# QMint novelty hypotheses and conflicts (lane A, A1)

Snapshot 2026-10-11. Paper IDs refer to `research/PRIOR_ART_MATRIX.csv`. Theorem IDs refer to `research/THEOREM_REGISTRY_SEED.yaml`.

This audit doesn't claim QMint invented anything. Everything below is a *hypothesis* about what could still be new after a stronger search. Each hypothesis has to survive the conflicts listed here and an outside review before anyone writes it as a contribution.

## 1. What already exists (prior art, not QMint)

| Capability | Who did it first (as far as this audit found) | Evidence |
|---|---|---|
| Exact optimal 1→2 counterfeiting bound (3/4)^n for Wiesner, via SDP | Molina, Vidick, Watrous 2012 (P01) | Thm 1, p.2 |
| Classical-verification Wiesner variant, (3/4+√2/8)^n | P01 | Thm 2, p.3; Lemma 5 |
| Threshold binomial-tail bound (joint-success game) | P01 Sec 3.5 | eq.(4) |
| Noise-tolerant tokens with threshold verification | Pastawski et al. 2012 (P13) | PNAS 109:16079 (not read in full) |
| S-money / relativistic tokens, summoning-task semantics | Kent 2019 (P02) | Proc R Soc A 475:20190170 |
| Finite-size unforgeability/correctness/robustness/privacy bounds **as explicit functions of measured device parameters** (P_det, E, β_PB, β_PS, θ, P_noqub) | Kent, Lowndes, Pitalúa-García, Rarity 2022 (P03) | Lemmas 2–4, Thm 1, Thm 2 |
| A **security region** computed from experimental parameters (β_max curves at ε=10⁻⁹) | P03 Fig. 5 | Methods |
| Loss- and error-dependent double-spend SDP; secure region in (e,l); finite-N Chernoff choice of token length N | Schiansky et al. 2023 (P04); methodology traces to Bozzio, Diamanti, Grosshans 2019 (P15) | SI Note 3 |
| Real photon timetag data for a quantum payment experiment, CC BY 4.0 | P04 / Zenodo 7979319, 7997998 | DATASOURCE_REGISTER |
| Full S-token experiment with a **measured transaction-time advantage** over classical cross-checking (2.77 km, 60.54 km) | Jiang et al. 2024 (P05) | arXiv v2 |
| **Propagating confidence intervals (7σ) on measured device parameters into ε_unf / ε_cor** | P05 eqs.(26)–(29) | Methods p.18 |
| Quantum money with a quantum memory and a secure regime derived from measured memory efficiency/noise | Mamann et al. 2025 (P17) | Sci. Adv. 11:adx3223 (abstract only) |
| Anonymous tokens with classical verification and an issuer-tracking audit | Gavinsky et al. 2025 (P06) | Def 9, Claims 12–13 |
| Certified numerical security bounds (dual certificates, reliable lower bounds) and parameter optimisation over device parameters, open-source | Winick, Lütkenhaus, Coles 2018 + openQKDsecurity (P19); Bunandar et al. 2020 numerical_qkd (P20); Chung, Ng, Cai 2025 (P22) | QKD domain |
| ML prediction of optimal protocol parameters from device/channel parameters | Wang & Lo 2019 (P21) | QKD domain |

### Explicit search for "software that optimizes quantum-token / quantum-money security parameters from measured device data"

* Searches run 2026-10-11 (web search, arXiv metadata, GitHub API) found **no dedicated open-source tool** that takes measured optical data and returns optimized quantum-token (S-money / Wiesner / quantum-digital-payment) parameters with checked certificates. QMoney (SW-QMONEY) is a private-key simulator with no certified parameter optimiser in the README that was audited.
* The **closest prior art is in the papers themselves**: P03 hand-tunes (γ_det, ν_unf, γ_err, ν_cor) to hit ε=10⁻⁹ and says outright that its choice "probably does not optimize our results". P04 picks (δ_h, δ_d, N). P05 chooses (γ_err, ν_unf, ν_cor) and propagates 7σ parameter uncertainty. Each of these *is* a parameter selection from measured data. It just isn't packaged as a general tool.
* In QKD, parameter optimisation from device parameters is a mature topic with open-source code (P19–P22). Any QMint compiler is methodologically a port of that idea to token games.
* **Limitation of this search:** Google Scholar, patents beyond the two disclosed, and non-English literature weren't searched systematically. P13–P16 and P19–P22 were checked at metadata level only. This counts as a **negative search result, not proof of absence**.

## 2. What the QMint "certificate compiler" could legitimately claim (hypotheses H1–H6)

Each claim is conditional on the stated evidence existing. All of them are L1–L2 in the master-plan claims hierarchy (§4.6).

* **H1 – Cross-protocol, game-typed certificate format.** A machine-checkable certificate that ties every ε to a named game (W1, W1_CV, S1, S2, D1, …), a theorem ID with a source anchor, assumption flags (e.g. P03 Table 6 A–G), and an evidence kind. The certificate refuses out-of-domain parameter tuples (UNCERTIFIED/OUT_OF_MODEL). *New only as engineering/infrastructure.* Not found as an open tool for token protocols. Similar "theorem-preconditions-as-code" ideas exist in QKD tooling.
* **H2 – Systematic optimisation over published bounds.** Treat P03 Lemmas 2–3 + Thm 1 (and P04 eqs.(19)–(23), P05 Thm 1) as *fixed, cited* constraints and search the free parameters (γ_det, γ_err, ν_cor, ν_unf, N, δ_h, δ_d) to minimise resource cost at fixed ε. Report the gap against each paper's published tuple. *Possible measured increment:* e.g. smaller N at the same ε than P03's hand-tuned Fig.5 choices. This must be shown numerically and independently re-checked. If the gain is negligible, report that.
* **H3 – Uncertainty-aware calibration from public raw data.** Estimate (e, l, p_m) intervals from the Zenodo timetags with time-blocked holdouts and drift stress. Propagate them in the worst-case direction into the D1 bound. P05 already does confidence propagation for S-tokens, so the possible increment is only (a) for the D1 protocol, (b) from *public raw* data, (c) with holdout validation.
* **H4 – Independent reproduction and consistency audit.** Re-derive P04's N=1 SDP and P01's SDP with residual accounting. Document the discrepancies found in `CORRECTIONS.md` (p_m 6.76% vs 6.02%; N 4.2e6 vs 4.48e6; Choi normalisation). This is L1 reproduction value, not a new theorem.
* **H5 – Falsification harness.** Pair every certified configuration with the best known *attack* (Monte Carlo lower bounds, SDP optima at small n) so certificates can be shown to be non-vacuous and to fail when they should. This is engineering. It doesn't produce new bounds.
* **H6 – Trust-matched quantum vs classical systems benchmark.** Compare on matched topology/trust. P05 already measured a time advantage for one setting, so QMint can only add *breadth* (more topologies, explicit classical H0–H6 baselines, RIPE-measured RTTs) and must cite P05 as the origin of the measured advantage.

## 3. Highest-risk novelty conflicts (must be resolved before any novelty wording)

1. **C1 – P03 already gives device-parameter → ε maps and a computed secure region.** Kent et al. 2022 Thm 1/Lemmas 2–3 are exactly "measured device parameters → certified ε", and Fig. 5 is a security region. QMint can't claim "first noise/loss-aware certified quantum token parameters".
2. **C2 – P05 already propagates measurement confidence into ε and measured a time advantage.** Jiang et al. 2024 eqs.(26)–(29) and the 2.77/60.54 km transaction-time result. QMint can't claim "first uncertainty-aware security certificate for quantum tokens" or "first demonstrated quantum transaction-time advantage".
3. **C3 – P04/P15 already contain an SDP over noise *and* loss with a finite-N token-length selection.** QMint can't claim a novel "loss-dependent attack SDP" or "first finite-size quantum-payment security curve from real data".
4. **C4 – QKD numerical-security tooling (P19–P22: openQKDsecurity, numerical_qkd, Rényi finite-size frameworks, ML parameter prediction).** Generic "certified numerical bound + parameter optimisation from device data" is established in QKD. A QMint compiler is at best a domain transfer and must benchmark against or cite these.
5. **C5 – P01 Sec. 3.5 threshold result and P13 noise-tolerant tokens.** Any QMint "noise-tolerant Wiesner bound" risks duplicating (or misapplying) these. In particular, P01's binomial tail is for a *joint* per-repetition success count, not per-copy thresholds.
6. **C6 – P17 (Mamann et al. 2025) derives a secure regime from measured quantum-memory efficiency/noise for Wiesner money.** That conflicts with any "first experimental-data-driven Wiesner security region" claim. P17 was read at abstract level only, so a full read is required.
7. **C7 – Patents.** US 10,790,972 (Kent, S-money style tokens, assigned to CQC/Quantinuum per Google Patents) and EP 23168897.9 (Univ. Vienna, quantum payment token, P04 inventors). A compiler that *emits deployable protocol configurations* may sit near these claims (see LICENSE_AND_PATENT_RISKS.md).

## 4. Disallowed false statements (must never appear in code, docs, UI or paper)

1. "QMint proves Wiesner money is secure with (3/4)^n." **False framing.** (3/4)^n is Molina–Vidick–Watrous's theorem (P01 Thm 1), and it holds only for the simple 1→2 counterfeiting game W1 with an exact verifier and no verifier queries.
2. "The (3/4)^n bound applies to the noisy/threshold note (W2) or to S-money." **False.** W2 has no closed form in the sources read. S1 uses (1/2+1/(2√2))^N (P03 Lemma 1), a different game and value.
3. "(3/4+√2/8)^n and (1/2+1/(2√2))^N are the same classical-verification bound." **False.** They come from different games (P01 W1_CV vs P03 S1), with bases 0.9268 and 0.8536.
4. "QMint is the first to demonstrate a quantum transaction-time advantage / first experimental quantum token / first quantum payment." **False.** See P05, P03, P04, P14, P17.
5. "QMint is the first to compute quantum-token security from measured device parameters with confidence intervals." **False.** See P03 (device-parameter bounds) and P05 (7σ propagation).
6. "The 2023 Vienna experiment demonstrated offline/instant local validation like S-money." **False.** P04's TTP verifies online. P04 is a different protocol family (D1).
7. "The Schiansky et al. analysis code is CC BY and can be copied into QMint." **False/unsafe.** The code archive ships an AGPL-3.0 licence file that conflicts with the CC BY metadata, and it contains no security-analysis code anyway.
8. "The 21 Aug 2023 correction changed the security numbers." **False.** It replaced one Discussion sentence about growing the key C. No numbers changed (CORRECTIONS.md).
9. "QMoney / QMint implements public-key quantum cash." **False.** QMoney is private-key, quorum-verified, verify-and-remint (audited commit 017502e), and QMint's protocols are private-key or relativistic.
10. "A Monte Carlo attack success rate or an SCS/CVXPY objective value is a security proof." **False.** It's a lower bound on worst-case attack success, or a numerical value without residual accounting.
11. "Kent et al. 2022's experiment achieved guaranteed unforgeability." **False.** The authors state that their experimental parameters require improvement (β_PB, β_PS about 10–16× smaller) to guarantee it.

## 5. Recommendation

The defensible headline is **H1 + H2 + H4 as a reproducible benchmark and certificate-checking platform**. Add H3 only if the Zenodo data supports it, and H2's resource gain only if measured. Use the master plan's "Strong" or "Valuable negative" outcome wording until G5 evidence exists. Before any submission, a second agent (lane M or N) should do a full read of P13, P14, P15, P17, P19–P22 and a patent search.
