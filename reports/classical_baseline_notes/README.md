# Lane H: classical comparators (H0–H6) vs S-money S1

Regenerate with `python -m qmint.classical.run_baselines --pqc-reps 5`. All H scenarios now run on lane G's
discrete-event engine through `qmint/classical/engine_adapter.py`. Every number in `benchmark_records.jsonl` is
`MODELLED_LATENCY` on SYNTHETIC lightcone networks: link `propagation_lower_bound_ns` plus declared processing
(site 10 µs, coordinator/replica 50 µs). These are lower bounds. They favour coordination-based designs and are
not measurements. `pqc_timings.json` holds wall-clock CPU timings of a pure-Python reference ML-DSA on an Apple M4 Pro.
Those timings are not representative of optimized implementations.

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

Regenerate with `python -m qmint.classical.matched_topology` (about 1 min). Outputs:
- `matched_topology_results.csv`: 264 rows = 6 topologies × 11 protocols × 2 processing models × b ∈ {1, 0}.
  RIPE rows are medians over 20 seeds.
- `matched_topology_records.jsonl`: one C6 record per (topology, protocol, processing model), b = 1.
- `matched_topology_traces.jsonl`: C4 traces, seed 0, b = 1, Jiang processing, honest runs plus double-spend races.
- `figure6_trace_data.json`: spacetime-diagram data (S1 vs H1 race vs H3 late commit, plain and OT) for Jinan,
  Yiyuan–Mazhan, 100 km and RIPE.

Every protocol runs on the same lane-G `TopologyCase`, with the same seed and the same choreography:
- Alice chooses b at L0.
- Any Stage-II message starts at the choice.
- Both sites see a presentation at the same nominal time.
- The issuer, ledger and HQ sit at L0.

All values are `MODELLED_LATENCY`. RIPE link delays are measured inputs (RTT/2). The processing models are:
- `jiang_dTproc_1507ns`: every node step costs 1.507 µs (Jiang 2024 SI). Relays cost 0, as in G's S-money B0→B1.
- `zero_processing`: communication only.

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
