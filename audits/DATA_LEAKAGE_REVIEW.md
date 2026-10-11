# Data-leakage and provenance review (lane M, red team)

- **Review SHA:** `9a4e8a9368e75d3e8e329231020e1992bc7f04ea` (code-identical to main `4c04f53`).
- **Also re-run on:** main `7130c1f`. Every finding still reproduces there.
- **Repro prefix:** `PY=/Users/udsy/PycharmProjects/Qollab-QMint/.venv/bin/python`. Tests are in `tests/adversarial/`.

## Summary

| id | sev | owner | finding | status |
|---|---|---|---|---|
| M-B1 | HIGH | B | A token handle can be copied or pickled, and the copy is a perfect counterfeit | OPEN (see CRYPTOGRAPHIC_REVIEW) |
| M-B2 | MEDIUM | B | Exact BB84 states reachable from the wallet handle; Bob's secret reachable from the Alice-facing Kent session | OPEN (design) |
| M-L1 | MEDIUM | L | `RecordStore.get()` trusts any self-consistent `results/<id>.json`: no registry entry is needed, and the registry's `record_sha256` is never compared. A SYNTHETIC record can be relabelled MONTE_CARLO | OPEN |
| M-K1 | MEDIUM | K (+fixture authors) | Workbench `--real-data` drops the FIXTURE DATA label for fixture records labelled MONTE_CARLO, NUMERICAL_SDP or MODELLED_LATENCY | OPEN |
| M-G1 | LOW | G | `run_s_money` defaults to `z=0`, so commitment `c = b` reaches B0 before presentation. G's privacy test only checks that the key `"b"` is absent | OPEN |
| M-G2 | INFO | G | The timing-metadata attack failed: presentation arrival times and Bob's pre-presentation view are independent of b when z is uniform | NO FINDING |
| M-E2 | INFO | E | `detect_channel_swap` (threshold 0.25) misses a cross-basis TTP relabelling that yields a 23.4 % QBER. The error is pessimistic, not optimistic | NOTE |

## Token-object leakage (attack list item 1)

I probed lane B's `RegisterHandle` (Wiesner, Kent and Schiansky) and its challengers through each vector below.

| vector | IssuerSecret | RegisterHandle / register |
|---|---|---|
| `repr` / `str` / f-string / inside a list | redacted | the repr shows only the token id, n and consumed state |
| `model_dump`, `model_dump_json`, `canonical_json` (top level or nested in `SecurityCertificate.parameters`) | refused (`SecretBoundaryError` / `PydanticSerializationError`) | n/a |
| `pickle` | refused | **succeeds** and carries the density matrices (M-B1) |
| `copy.copy` / `deepcopy` (also of a certificate holding a secret) | refused | **succeeds**: the copy is a perfect clone (M-B1) |
| attribute access, `vars()`, the gc / closure walk | open (`secret.bits`): inherent in Python | `_register.reduced_state()` gives the exact states (M-B2) |
| challengers (`WiesnerChallenger`, `KentSMoneySession`, `SchianskyPaymentSystem`) | copy and pickle refused (`SecretHolder`) | the Kent session *is* the Alice-facing API (M-B2) |
| logs (`qmint.core.logging`) | redacted (lane L tests) | n/a |
| record store | refuses an `IssuerSecret` and the `TEST_ONLY` key (`test_store_refuses_test_only_revelation`) | n/a |

**Conclusion.** The serialization boundary that C1 promises holds. The in-memory capability boundary does not. Until challengers run out of process (remedy under M-B2), attack evidence depends on attack code honouring the API. As of the review SHA, lane C's code honours it (grep-verified: no `_register`, `_qubits`, `_peek` or `_secrets` access outside lane B).

## M-L1 (MEDIUM): record-store read path does not detect forgery
- **What `get()` checks.** `RecordStore.get(id)` validates the envelope and checks `canonical_hash(payload) == payload_sha256`. Both values live in the same file, so an attacker who can write `experiments/results/` can do either of the following:
  1. Drop a new `injected.json` with a self-consistent hash. `get("injected")` returns it even though `run_registry.jsonl` has no line for it.
  2. Rewrite a registered record, changing `payload.evidence_kind` and the envelope `evidence_kind` from SYNTHETIC to MONTE_CARLO, and recompute the hash. `get()` returns it, even though the registry's `record_sha256` no longer matches.
- **Repro:** `$PY -m pytest tests/adversarial/test_m_records.py -k "unregistered or relabelled" --runxfail -q`
- **What already works.** Tampering with the payload *without* rehashing is caught (`test_store_rejects_tampered_payload_without_rehash`).
- **Expected safe behaviour:** `get()` requires a registry line with matching `record_sha256` and `payload_sha256`, and requires the envelope `evidence_kind` to equal the payload's evidence field.
- **Remedy (lane L):**
  - Do the checks above in `get()`.
  - Optionally hash-chain the registry (each line includes the previous line's hash) so that registry lines are tamper-evident.

## M-K1 (MEDIUM): a figure can be forged from fixture records
- **Rule.** `qmint.ui.app.is_fixture` keeps the FIXTURE DATA label only if `real_data` is False or some record has evidence SYNTHETIC.
- **What slips through.** The lane-K fixtures `attack_mc_fixture.json` (MONTE_CARLO, `backend_kind="SYNTHETIC_FIXTURE"`, `source_code_sha="fixture"`), `attack_sdp_fixture.json` (NUMERICAL_SDP) and `bench_c_h1_fixture.json` (MODELLED_LATENCY) are not SYNTHETIC.
- **Effect.** `python -m qmint.ui.build --records <dir with only those> --real-data --strict` exits 0 and writes `"fixture_data": false`, with no FIXTURE banner. I reproduced this in a scratch directory.
- **The injected number is itself wrong.** The forged W1 "measure-resend" fixture value is 0.741, while the true value is 5/8.
- **Expected safe behaviour:** real-data mode accepts only records that come with provenance, i.e. records delivered through `RecordStore` envelopes (git sha, lock hash, registry match) or listed in an `EvidenceManifest` whose hashes verify. Anything else forces the FIXTURE label.
- **Remedy:**
  - K: implement that gate.
  - Fixture authors: label fixtures `evidence_kind=SYNTHETIC`, or keep them out of any directory that might be passed to `--real-data`.
- **Re-audit item.** K-web (`qmint/api/routes/evidence.py`, merged on main 7130c1f) is a second rendering path, and it needs the same gate.

## M-G1 (LOW): default `z=0` makes the commitment equal to the choice
- **What leaks.** `run_s_money(case, b)` uses `z=0` unless the caller passes one. B0's `message_receive` of the commitment therefore carries `c = b` at T_choice, i.e. before presentation.
- **Why the existing test misses it.** G's test `test_branch_hidden_from_bank_until_presentation` passes `z=1` and only checks that no event has a key named `"b"`.
- **Repro:** `$PY -m pytest tests/adversarial/test_m_networks.py::test_default_run_hides_choice_from_bank --runxfail -q`
- **Expected safe behaviour:** z is drawn from the seeded RNG, and the test compares Bob's view across b (distributionally over z).
- **Remedy:** lane G, a one-line default change plus the new test.

## M-G2 (INFO, no finding): timing metadata does not leak the choice
- **Presentation timing.** On Jinan 2.766 km and on synthetic 100 km, both bank agents receive a presentation at the identical coordinate time (1 013 830 ns at Jinan) whether b = 0 or 1. A0 waits the nominal one-way delay; A1 presents on arrival of Alice's branch message.
- **Bob's view.** With z uniform, the distribution of Bob's pre-presentation view (events, times and payloads) is identical across b.
- **Tests:** `test_presentation_timing_independent_of_choice` and `test_bob_view_distribution_independent_of_choice_when_z_uniform`.
- **Caveat.** With `Empirical` latency, A0 waits `max(samples)`. That is still b-independent, but it inflates A0-side presentation latency.
- **Clock skew.** Offsets beyond `clock_error_bound_ns` are refused, and a superluminal empirical sample raises `CausalityViolation` (both tested).
- **Drift.** Clock *drift* (offsets that change over time) is not modelled: offsets are constant per run, and no S-money or classical actor uses its local clock for a decision. A drift attack therefore has no surface today. It must be re-audited when any actor starts enforcing time windows (Kent's "in the causal past of Q_i" checks).

## M-E2 (INFO): channel-swap detector blind spot
- **The case.** In the linear folder, the raw contingency table (TTP channel → client channel; my own parser, no lane-E code) has TTP 2/3 as Z and 4/5 as X. Mislabelling TTP channel 4 as the Z "bit 1" channel gives (10 466 + 496 047)/2 163 356 = 23.4 % matched-basis errors. That is below `detect_channel_swap`'s 0.25 threshold, so the mislabel passes.
- **Why it is only INFO.** The error inflates QBER, so downstream bounds become pessimistic or INFEASIBLE rather than optimistic.
- **Remedy:** lane E could additionally require the inferred QBER to fall within a plausibility band of the published per-basis values, or check that both TTP channels of a basis have similar error rates.

## Re-audit list
- **K-web.** `qmint/api/*` (lab, evidence, certificates routes) on main 7130c1f: provenance gate (M-K1), and no handle or secret objects in responses. The lab demo intentionally reveals seeded secrets and must stay labelled.
- **Q dedupe.** M-B1 and M-B2 must survive the move: keep the strict xfails.
- **GH.** The matched-topology traces now carry H payloads in event `detail`. Re-run the Bob-view-independence test on H3 OT traces, and check that the issuer's observed `c` is b-independent under uniform z.
