# Lane H: classical comparators (H0–H6) vs S-money S1

Regenerate with `python -m qmint.classical.run_baselines --pqc-reps 5`. All H scenarios now run on lane G's
discrete-event engine through `qmint/classical/engine_adapter.py`. Every number in `benchmark_records.jsonl` is
`MODELLED_LATENCY` on SYNTHETIC lightcone networks: link `propagation_lower_bound_ns` plus declared processing
(site 10 µs, coordinator/replica 50 µs). These are lower bounds. They favour coordination-based designs and are
not measurements. `pqc_timings.json` holds wall-clock CPU timings of a pure-Python reference ML-DSA on an Apple M4 Pro.
Those timings are not representative of optimized implementations.

## Lane-M red-team fixes (lane FGH)

| id | fix | regression |
|---|---|---|
| M-H1 | H3-OT secrets are `HMAC-SHA256(issuer_key, …)` with an issuer-private 256-bit key from `secrets.token_bytes`. Public data (seed, token id, site index) no longer determines them. Simulations pass an explicit key for reproducibility; no customer-side agent receives it. | `tests/adversarial/test_m_classical.py::test_h3_ot_secrets_unpredictable` (xfail removed) |
| M-H2 | Stage II is one-shot per token in both late-commit modes. The issuer latches the first `Commit`/`CommitC` before relaying it and refuses (does not relay) any later one. A site ignores a second `Activate`/`RelayC`. A presentation held by `hold_until_active` is decided by the first commit only. | `…::test_h3_{disclosed,ot}_second_commit_refused`, `tests/unit/classical/test_classical_h3.py` |
| M-H3 | H1/H2 idempotency keys are random 128-bit values per presentation, persisted with the pending request. They are no longer `sha256(merchant, token, local counter)`. A `replayed=True` ACCEPT is honoured only for a key the terminal has pending, and the flag is forwarded in `Result` (so H1 `classical_bytes` grows by 17 B and H2 by 34 B). A second till of the same merchant, or a restarted till, gets `REJECT_DOUBLE_SPEND`. | `…::test_h1_second_terminal_same_merchant_does_not_release_goods_twice`, `test_classical_h1.py` |
| M-H4 | A **strong** double-spend adversary has been added next to the weak `replay` one. See the matched-topology section. In `benchmark_records.jsonl`, `double_spends_successful` is now the worst case over both adversaries, and `configuration.double_spends_by_adversary` lists each one. | `tests/integration/test_gh_matched.py::test_strong_adversary_*`, `test_classical_records.py` |
| M-G1 | `run_s_money` draws z uniformly by default (seeded). Bob's pre-presentation view is identical for b = 0 and b = 1. | `tests/adversarial/test_m_networks.py::test_default_run_hides_choice_from_bank`, `tests/unit/networks/test_networks_s_money.py` |

**Changed result:**
- H6's `double_spends_successful` goes from 1 to 2, because the strong adversary also re-presents the coin after
  the race and the offline merchant accepts it a third time.
- No other double-spend outcome changes. Every preventing design (H1, H2, H3 ×3, H4+H1, H4+H3, and H5 with its
  assumption holding) still has 0 double spends, now against the strong adversary as well.
- Against the code *before* these fixes, the strong adversary gets 1 extra accept on H1, H2, H4+H1 and both H3
  late-commit modes. This was checked by re-introducing the three bugs in-process.
- So the earlier "prevented" entries were valid only against the replay adversary, as M-H4 said.

## What the strongest classical construction is, per scenario

| Scenario requirement | Best classical construction found | What it gives up versus S1 (ideal) |
|---|---|---|
| Late site choice and online infra OK | H1 (or H2 if replicated) | validation waits ≥ coordinator RTT; coordinator learns site; unavailable under partition |
| Instant local acceptance, site known at issuance | H3-preassigned or **H4+H3** (signed site binding, needs no per-token provisioning) | late-choice flexibility; issuer learns site at issuance |
| Late choice + local acceptance + issuer must not learn site | **H3 `late_commit_ot_private`** (classical mirror of IQT1 bit-masking via 1-of-M OT) | unforgeability and privacy are **computational** (any real classical OT needs hardness assumptions or trusted setup); OT instantiation NOT_IMPLEMENTED (ideal functionality) |
| Late choice, local acceptance, no Stage-II message at all | H5 secure hardware (trust model) | requires tamper-resistant hardware assumption H5-TR; broken assumption ⇒ double spend (tested, OUT_OF_MODEL) |
| Offline + payer privacy | H6 (Chaum–Fiat–Naor 1988 §1) | **detection, not prevention**: both offline merchants accept; spender identified at deposit |

Skeptic's key point: S1 is not coordination-free. In Kent et al. 2022 Table I, steps 7–9 (arXiv:2104.11717v4), Alice
sends `c = b ⊕ z` to Bob, and Bob relays it to both B_i in the causal past of Q_i. H3-late-commit has the same Stage-II
causal requirement (`stage_ii_commit_to_activation_ns` in the records). Once the OT variant is added, the remaining
difference from S1 is the adversary model: S1's Lemma 1 bound is information-theoretic in the ideal model, while the
classical constructions are computational or trust-based. So S1's advantage over the best classical construction is
in what it assumes, not in latency. Any claim that it is faster needs a scenario where the classical constructions'
extra trust or hardness assumptions are disallowed.

## Comparability (comparability_matrix.csv; columns exactly as master plan §8)

- QUALIFIED: H1, H2, H3-preassigned, H3-late-disclosed, H3-late-OT, H4+H1, H4+H3. They are comparable only once
  the listed concessions are priced: adversary model, coordinator trust, privacy loss and flexibility loss.
- INCOMPARABLE:
  - H0 and H4-alone fail the C1 goal.
  - H5 relies on trusted tamper-resistant hardware, a different trust model.
  - H6 detects double spends instead of preventing them.
- No pair is marked COMPARABLE.

## Sources
- FIPS 204, Table 2 p.16 (key/signature sizes; verified against dilithium_py output):
  https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.204.pdf (sha256 57239b9f…6b6b).
- Kent, Lowndes, Pitalúa-García, Rarity, arXiv:2104.11717v4: Table I, Lemma 1 eq.(1), definitions p.3–4.
- Chaum, Fiat, Naor, CRYPTO'88, LNCS 403 pp.319–327, §1, doi:10.1007/0-387-34799-2_25. The copy read was the Wayback
  archive of blog.koehntopp.de/uploads/chaum_fiat_naor_ecash.pdf (sha256 07e6544a…5637). The Springer original was not
  accessed.

## Matched topology: S-money vs H0–H6 on one engine (lane GH)

Regenerate with `python -m qmint.classical.matched_topology` (about 3 min). Outputs:
- `matched_topology_results.csv`: 528 rows = 6 topologies × 11 protocols × 4 processing models × b ∈ {1, 0}.
  RIPE rows are medians over 20 seeds.
  - `race_accepted_sites` is the outcome of the weak replay adversary.
  - `strong_accepted_presentations` and `strong_double_spends` are the outcomes of the strong adversary
    (maximum over seeds).
- `matched_topology_records.jsonl`: one C6 record per (topology, protocol, processing model), b = 1.
- `matched_topology_traces.jsonl`: C4 traces, seed 0, b = 1, Jiang processing. It holds the honest runs plus the
  replay and strong double-spend runs.
- `figure6_trace_data.json`: spacetime-diagram data (S1 vs H1 race vs H3 late commit, plain and OT) for Jinan,
  Yiyuan–Mazhan, 100 km and RIPE.

Every protocol runs on the same lane-G `TopologyCase`, with the same seed and the same choreography:
- Alice chooses b at L0.
- Any Stage-II message starts at the choice.
- Both sites see a presentation at the same nominal time.
- The issuer, ledger and HQ sit at L0.

All values are `MODELLED_LATENCY`. RIPE link delays are measured inputs (RTT/2).

Processing time is **one matched parameter**. Each model applies the same per-step time to every node of every
protocol, S-money's B_i included. Relays cost 0, both for S-money's B0→B1 and for the H3 issuer. The models are:
- `zero_processing`: communication only.
- `jiang_dTproc_1507ns`: 1.507 µs per step (Jiang 2024 SI).
- `h_site_10us`: 10 µs per step, lane H's declared terminal time, applied to everything.
- `h_coord_50us`: 50 µs per step, lane H's declared coordinator time, applied to everything.

Every trace passes G's causality check.

Choice → local accept at the remote site (b = 1, Jiang processing; µs):

| protocol | Jinan 2.766 km | Yiyuan–Mazhan 60.54 km | 10 km | 100 km | 1000 km | RIPE HEL–TMP (median) |
|---|---|---|---|---|---|---|
| S1 S-money (G model) | 15.34 | 304.21 | 51.54 | 501.85 | 5004.97 | 1979.62 |
| H3 late-commit (disclosed / ideal-OT) | 15.34 | 304.21 | 51.54 | 501.85 | 5004.97 | 1979.62 |
| H3 preassigned, H4+H3 (site fixed at issuance) | 15.34 | 304.21 | 51.54 | 501.85 | 5004.97 | 1928.7–1933.8 |
| H0 (negative control, double spend accepted) | 15.34 | 304.21 | 51.54 | 501.85 | 5004.97 | 1928.67 |
| H5 (trusted hardware), H6 (detection only) | 16.84 | 305.71 | 53.05 | 503.36 | 5006.48 | 1930.18 |
| H1, H4+H1 (ledger at L0) | 46.01 | 912.62 | 154.62 | 1505.56 | 15014.91 | 6022.74 |
| H2 (3 replicas, 2 at L0) | 49.02 | 915.64 | 157.64 | 1508.57 | 15017.92 | 6083.53 |

Local validation is 1.507 µs for S1, H0, H3 and H4+H3, and 3.014 µs for H5 and H6 (a challenge round). For
H1/H4+H1 at Jinan it is 32.18 µs, which is 2L/c_fibre = 27.66 µs plus 3 processing steps.

Issuer awareness and settlement on the same topology: S1 29.17 µs at Jinan, because B_b's outcome still has to
reach L0. That is the same as H0/H3/H4+H3 and within one processing step of H1 (30.67 µs).

What the numbers say:
- **Where S-money has no latency edge:**
  - Over H3 late-commit, with or without the ideal-OT privacy, choice → accept and the pre-presentation commit
    (13.83 µs at Jinan, 302.70 µs at Yiyuan–Mazhan) are identical on every topology. The Stage-II relay of c and
    H3's relay are the same message pattern.
  - Over H3/H4+H3 preassigned, H0, H5 and H6: equal, or within one processing step.
  - Over issuer awareness and settlement: no protocol has an edge.
  - On RIPE, S1 and H3-late are about 51 µs (median) slower than protocols that need only Alice's signal. Validation
    waits for whichever arrives later, the presentation or the relayed c. In 7 of 20 seeds c reached B1 after the
    presentation.
- **Where it has one:** against online-ledger designs (H1, H2, H4+H1) whose ledger is not at the presentation site,
  the edge is exactly one synchronous round trip. At Jinan with zero processing that is 2L/c_fibre = 27.66 µs,
  Jiang's classical reference. That edge buys late choice without a trusted relay that learns b, which only
  H3-OT matches. H3-OT matches it computationally, with an ideal OT that is NOT_IMPLEMENTED.
- The comparability statuses in `comparability_matrix.csv` are unchanged by these results.

### Double-spend adversaries (M-H4)
- **`replay` (weak; the adversary of the earlier H/GH runs):** the genuine presentation is made at both sites at
  the same nominal time.
- **`strong`:** `replay` plus an adaptive second wave, made after the first outcome is in the customer's causal
  past. It uses only what a customer legitimately holds:
  - a second Stage-II commit to the other site (H3 late-commit modes);
  - re-presentation at the other site;
  - OT secrets derived from public data (H3-OT, the pre-fix M-H1 derivation);
  - for the ledger designs, presentations at a second till of the same merchant at the other site and at a fresh
    (restarted) till at L_b (the M-H3 deployment).
- Outcomes are the same on all 6 topologies, all 4 processing models, b ∈ {0, 1} and all RIPE seeds:
  - 0 double spends for H1, H2, H3 ×3, H4+H1, H4+H3 and H5;
  - 1 for H0;
  - 2 for H6 (detection only).
- S-money double spending is **not simulated**, because token validity is symbolic in G's model. Its security
  comes from Kent 2022 Lemma 1 in the ideal model, not from these runs.

### Processing-time sensitivity (lane-M re-audit of M-H5)
- **The unmatched comparison M-H5 warned about.** Lane H's scenarios use 10 µs per site and 50 µs per
  coordinator, and G's S-money uses 1.507 µs. Put side by side, those would give H1 ≈ 111.5 µs against S1 ≈ 15.3 µs
  at Jinan. About 68.5 µs of that 96 µs gap is the processing mismatch alone.
- **The matched comparison.** With processing matched (S1 − protocol, choice → accept at L1, µs, b = 1):

| topology | protocol | zero | 1.507 µs | 10 µs | 50 µs |
|---|---|---|---|---|---|
| Jinan 2.766 km | H3 late-commit (both), H3-pre, H4+H3, H0 | 0 | 0 | 0 | 0 |
| Jinan 2.766 km | H5, H6 (challenge round) | 0 | −1.51 | −10 | −50 |
| Jinan 2.766 km | H1, H4+H1 | −27.66 | −30.67 | −47.66 | −127.66 |
| Jinan 2.766 km | H2 (2 of 3 replicas at L0) | −27.66 | −33.69 | −67.66 | −227.66 |
| Yiyuan–Mazhan 60.54 km | H1, H4+H1 | −605.4 | −608.41 | −625.4 | −705.4 |
| RIPE HEL–TMP (median) | H3 late-commit (both) | 0 | 0 | 0 | 0 |
| RIPE HEL–TMP (median) | H0, H4+H3 | +50.95 | +50.95 | +50.95 | +50.95 |
| RIPE HEL–TMP (median) | H1, H4+H1 | −4040.1 | −4043.1 | −4060.1 | −4140.1 |

- **What the sensitivity shows:**
  - S1's edge over a remote ledger is 2 one-way delays plus 2 processing steps. It grows by 2p, because the ledger
    path has 3 steps against S1's 1.
  - S1's equality with H3 late-commit does not depend on p.
  - On RIPE, signal-only designs keep their roughly 51 µs lead over S1 at every p.
- **What does not change:** no qualitative conclusion above depends on the processing model.
