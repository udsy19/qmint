# Classical fairness review (lane M, red team)

- **Review SHA:** `9a4e8a9368e75d3e8e329231020e1992bc7f04ea` (lane H at the commit where H was merged).
- **Re-run on:** main `7130c1f` (GH re-hosted H on G's engine; `h3_escrow` gained `hold_until_active`). All three H findings still reproduce there.
- **Primary source:** Kent, Lowndes, Pitalúa-García, Rarity, npj Quantum Inf. 8, 28 (2022), https://www.nature.com/articles/s41534-022-00524-4, Table 1 (https://www.nature.com/articles/s41534-022-00524-4/tables/1) and the Introduction. I read it independently of lane H (quotes are in `handoffs/M-M1.md`).

## Summary

| id | sev | owner | finding | status |
|---|---|---|---|---|
| M-H1 | HIGH | H | The H3 `late_commit_ot_private` secrets are `sha256("h3-ot|0|token|i")` (seed defaults to 0 and is the scenario value), so a keyless customer derives every site's secret and is accepted at both sites | OPEN |
| M-H2 | HIGH | H | The H3 issuer relays a **second** `Commit`/`CommitC`. Spend at A, re-commit to B, and B accepts: a double spend in both late-commit modes | OPEN |
| M-H3 | MEDIUM | H | The H1/H2 idempotency key is `sha256(merchant|token|terminal-local counter)`, and the terminal ignores `replayed=True`. A second till of the same merchant, or a restarted till, accepts the same token again | OPEN |
| M-H4 | MEDIUM (claims) | H/N | The double-spend matrix's "prevented" entries for H1, H2 and H3 were obtained with a weak adversary (re-present the same secret at the other site). Under M-H1, M-H2 and M-H3 they hold only for that adversary | OPEN until fixed and re-run |
| M-H5 | INFO | H | Independently confirmed: S1 is not coordination-free. Kent Table 1 steps 7–9 require c = b⊕z to go A→B→B_i before Q_i, so H's central fairness argument stands | CONFIRMED |
| M-H6 | LOW | H/GH | Metric mismatch at the review SHA: G's "transaction time" runs from choice to accept, while H's `redemption_local_seconds` runs from presentation, with Stage II reported separately. GH's `matched_topology` (main 7130c1f) now reports these separately and says so | ADDRESSED on main (re-audit) |

## M-H1 (HIGH): predictable OT secrets in H3 `late_commit_ot_private`
- **The bug.** `EscrowIssuer.issue` derives `secrets[i] = sha256(f"h3-ot|{seed}|{token_id}|{i}")`. `seed` defaults to 0, `scenarios.run_h3` passes `seed=0`, and token ids are public.
- **The attack.** After any `CommitC`, the customer presents `secrets[(i-c) mod M]` at every site i and is accepted everywhere. `IdealOT` receiver-privacy is irrelevant, because the sender's secrets are public.
- **Repro:** `$PY -m pytest tests/adversarial/test_m_classical.py::test_h3_ot_secrets_unpredictable --runxfail -q`
- **Expected safe behaviour:** a keyless customer can open at most the one site whose secret it obtained through OT.
- **Remedy:** draw the secrets from a CSPRNG held only by the issuer (`secrets.token_bytes(32)`), keep them in the issuer's private store, and do not derive them from public data.
- **Why it matters for fairness.** H's README presents H3-OT as the classical construction that matches S1's late choice, local acceptance and issuer-blind commit. As implemented, it prevents nothing against a keyless adversary.

## M-H2 (HIGH): re-commit double spend
- **The bug.** `EscrowIssuer.handle` relays every `Commit`/`CommitC` it receives, and `EscrowSiteVerifier` overwrites `active`/`c`. `spent_local` is per-site.
- **The attack:**
  1. Commit A, then present at A: ACCEPT.
  2. Commit B, then present at B: ACCEPT.
- **Disclosed mode:** needs nothing extra.
- **OT mode:** the user's single `r_z` opens site b' after re-commit, with `c' = b' − z`.
- **Repro:** `$PY -m pytest tests/adversarial/test_m_classical.py -k second_commit --runxfail -q`
- **Expected safe behaviour:** the issuer accepts one Stage-II commit per token (a one-shot latch, recorded before relay), and sites ignore a second `Activate`/`RelayC`.
- **Remedy.** Note that S-money has the same structure: Bob must refuse a second c. Kent Table 1 step 7 has Alice send *the* bit c. Lane B's `alice_send_c` already refuses a second c (`_need("B", None, "c")`), so the classical mirror should too.

## M-H3 (MEDIUM): idempotency-key collision across tills
- **The bug.** `MerchantTerminal.handle(Present)` computes `idem_key = sha256(f"{merchant_id}|{token}|{self._counter}")[:32]`. The counter is per terminal instance and starts at 0.
- **What happens.** Two terminals sharing a `merchant_id` (two tills or two sites of one merchant, or a restarted terminal) produce the same key for the same token. The coordinator answers `ACCEPT, replayed=True` to the second, and `MerchantTerminal` forwards `decision` and ignores `replayed`.
- **Effect.** The goods are released twice and the merchant is credited once. The merchant loses, and the customer double-spends.
- **Repro:** `$PY -m pytest tests/adversarial/test_m_classical.py::test_h1_second_terminal_same_merchant_does_not_release_goods_twice --runxfail -q`
- **Control (passes):** two *different* merchants racing one token gives exactly one ACCEPT and one REJECT_DOUBLE_SPEND, so the coordinator's CAS is linearizable.
- **Remedy:**
  - Random 128-bit idempotency keys, persisted with the pending request.
  - A terminal treats `replayed=True` as ACCEPT only for a request it has pending.
  - The same rule in H2, which has no `replayed` flag at all.
- **Scope.** The H scenarios use one merchant per site (`m@{site}`), so the published matrix is unaffected *for that deployment*. The baseline is still not the strong ledger it is described as.

## M-H4 (claims): what the double-spend matrix supports
- **Reproduced.** I regenerated `python -m qmint.classical.run_baselines` and the double-spend decisions and comparability matrix match the committed `reports/classical_baseline_notes/` exactly:
  - successful double spends: H0, H4-alone, H5 with its assumption violated, and H6;
  - prevented: H1, H2, H3 (×3), H4+H1, H4+H3, and H5 with its assumption holding.
  - The only differences are PQC wall-clock timings and the stale `environment_lock`; see CLAIMS_AUDIT.
- **Limitation.** The scenario adversary "presents the same secret / same token at the other site" is the weakest double-spender. With the in-model adversaries above, H3 (late-commit, both modes) fails, and H1/H2 fail under a multi-till merchant.
- **Required qualifier.** Until H fixes M-H1/M-H2 and re-runs, the matrix must say "prevented against the replay-at-other-site adversary".

## M-H5: does classical preassignment beat S-money? (attack-list item)
- **Latency: yes, trivially, and lane H already says so.** H3-preassigned and H4+H3 accept locally with no Stage II at all. Presentation-to-accept is 10 µs of declared processing, with zero cross-site communication after the choice. S-money needs the Stage-II relay (15.337 µs choice→accept at Jinan, of which 13.83 µs is fibre).
- **The cost.** Late-choice flexibility, and the issuer learns the site at issuance. This is a *different requirement*, not an unfair win.
- **Is H's "S1 is not coordination-free" claim right?** I checked Kent 2022 Table 1 myself:
  - IQT1 step 7: "A computes the bit c = b ⊕ z and sends it to B."
  - Step 8: "B sends c to B_i, for i ∈ {0, 1}."
  - Step 9: "in the causal past of Q_i, B_i computes …"
  - The caption: steps 1–8 (IQT1) "take place within the intersection of the causal pasts of the presentation points."
  - IQT2 Stage II step 5 is "As steps 7 and 8 of IQT_1."
  - **So H's claim is correct.**
- **The paper's own framing of the advantage.** The Introduction says the advantage is "near-instant validation without time delays due to cross-checking, while satisfying unforgeability and user privacy with unconditional security". Instant validation is defined as "no communication between the verifiers and Bob for validation after Alice presents the token". This matches H's conclusion: the latency profile of S1 equals that of a late-commit classical escrow, and the distinction is information-theoretic versus computational/trusted security. **Confirmed.**
- **Fairness caveat in the other direction.** H's comparators run on synthetic light-cone networks with declared processing (10 µs site, 50 µs coordinator). G's S-money uses 1.507 µs measured processing (Jiang 2024). Comparing those numbers directly would favour S-money by about 8.5 µs per site. GH's matched-topology runner (main 7130c1f) puts both on one engine; re-audit that processing times are matched or explicitly reported.

## Re-audit after merges
- **GH (`qmint/classical/matched_topology.py`, `engine_adapter.py`):**
  - Re-run M-H1, M-H2 and M-H3 through the engine adapter. They still reproduce at the state-machine level on main.
  - Check that the matched runner's double-spend adversary is the strong one.
  - Check that `hold_until_active` cannot be used to queue a presentation that is later released by a *second* commit (M-H2 variant).
- **I (compiler):** must not treat any H "prevented" entry as a security property until M-H4 is resolved.
- **N (manuscript):** any quantum-vs-classical table needs (a) the M-H4 qualifier, (b) the trust-model column, and (c) a statement that the latency advantage over H3-late-commit is zero by construction (Kent Table 1).
