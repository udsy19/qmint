# Handoff FGH-1: fix lane for networks + classical (lane-M findings)

- **Branch:** `feat/FGH-fixes`, from `02aeab1`.
- **Commits:** code and reports in `8a8c529`; this handoff in the commit after it.
- **Tests:** `pytest tests -m "not network and not slow"` gives 1001 passed, 21 xfailed, exit 0. Before: 983 passed, 26 xfailed. `ruff check qmint tests` is clean.

## Fixed (each strict-xfail M test now passes; marker removed, assertion unchanged)

| id | fix |
|---|---|
| M-H1 | **H3-OT secrets.** They are now `HMAC-SHA256(issuer_key, label)`. `issuer_key` is issuer-private, from `secrets.token_bytes(32)`. Seed and token id are public labels only. |
| M-H2 | **One-shot Stage II.** The issuer latches the first `Commit`/`CommitC` before the relay leaves, and refuses later ones without relaying them (`refused_commits`). Sites ignore a second `Activate`/`RelayC`. A unit test checks that `hold_until_active` cannot be released by a second commit. |
| M-H3 | **Idempotency keys.** H1/H2 keys are random 128-bit values per presentation. `replayed=True` is honoured only for a key the terminal has pending, and the flag is forwarded. A second till or a restarted till of the same merchant gets `REJECT_DOUBLE_SPEND`. |
| M-H4 | **Strong adversary.** Added to the matched runner and to the double-spend matrix. It does the race, then re-commits to the other site, re-presents there, presents forged public-data OT secrets, and presents at a second till and at a restarted till of the same merchant. Every report has been regenerated. |
| M-G1 | **Default z.** `run_s_money` now draws z uniformly (seeded, coupled through c), so Bob's view is independent of b. |
| M-H5 re-audit | **Processing.** Processing is one matched per-step parameter for every protocol, S-money included. The sweep covers 0, 1.507, 10 and 50 µs, and the README reports the sensitivity. |

## Changed headline results
- **H6 `double_spends_successful`: 1 → 2.** The strong adversary re-presents the coin, and the offline merchant accepts it again.
- **Everything else is unchanged:**
  - Every preventing design still has 0 double spends against the strong adversary. This holds on all 6 topologies, all 4 processing models, both b, and all RIPE seeds.
  - Without the fixes, the strong adversary gets 1 extra accept on H1, H2, H4+H1 and both H3 late modes (checked in-process).
  - The latency columns are bit-identical for the two existing processing models.
- **Processing sensitivity (Jinan, S1 − H1, µs):** −27.66 at zero, −30.67 at 1.507, −47.66 at 10 and −127.66 at 50. In general the gap is 2 one-way delays + 2p.
  - S1 equals H3-late at every processing time.
  - The unmatched comparison (H at 10/50 µs vs S at 1.507 µs) would have put the Jinan gap at about 96 µs.
- **Wire bytes:** H1 grows by 17 B and H2 by 34 B, because of the `replayed` flag.

## Limitations, follow-ups and interface changes
See the JSON. In short:
- Simulations use an explicit issuer key and seeded idempotency RNGs for reproducibility.
- S-money double spending is still not simulated.
- `audits/*` statuses still say OPEN. That path is not owned, so the lead or lane M needs to flip them.
- The `run_matched` keyword is now `adversary=` instead of `adversarial=`.
