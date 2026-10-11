# Lane H: classical comparators (H0–H6) vs S-money S1

Regenerate with `python -m qmint.classical.run_baselines --pqc-reps 5`. Every number in `benchmark_records.jsonl` is
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
