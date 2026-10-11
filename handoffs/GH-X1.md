# Handoff GH-X1: lane H classical machines on lane G's engine, matched-topology S-money comparison

Branch `feat/GH-integration`, starting at `6d83940`. Code commit `82b43a7`; reports commit `35ff288`. The handoff commit comes after these.

**Tests:** `$PY -m pytest tests -q -m "not network and not realdata"` gives 399 passed, 1 deselected, exit 0. `ruff check qmint tests` is clean.

## What was done
1. **One adapter** (`qmint/classical/engine_adapter.py`):
   - `NodeActor` hosts any H `ProtocolNode` as a G `Actor`. Outputs leave after `processing_ns`.
   - `PresentationPoint` is the user agent / till at a site. It records `verification_result_available_local`, answers H5/H6 challenges and can report to G's `IssuerHQ`.
   - The H1 timer hook needed no engine change. A node with `on_timeout` arms a G `SetTimer` per `idem_key` request.
2. **`_run_chain`, `deliver` and `path_delay_ns` are deleted.** `scenarios.py` runs every H0–H6 scenario on the engine, and the baseline numbers are unchanged.
3. **`qmint/networks/classical_race_fixtures.py` and its test are deleted.** The race tests now use H's real machines in `tests/integration/test_gh_engine_race.py`:
   - H0 double accept
   - hypothesis H1 linearizability: the coordinator's seq order equals engine arrival order
   - Jinan RTT
   - partition
   - lossy-link retry with the same idempotency key
   - H3 wrong-site reject
4. **Matched topology** (`qmint/classical/matched_topology.py`):
   - Runs S1 (G's `run_s_money`) and H0, H1, H2, H3 (all modes), H4+H1, H4+H3, H5 and H6.
   - Same `TopologyCase` for all: Jiang Jinan 2.766 km and Yiyuan–Mazhan 60.54 km; synthetic 10/100/1000 km; RIPE Helsinki→Tampere.
   - Same seed and choreography for all.
   - Two processing models.
   - Outputs: CSV, C6 records, C4 traces, and figure-6 JSON in `reports/classical_baseline_notes/`.

## Corrections
- **Stage-II relay in S-money (Kent 2022 Table I steps 7–9, checked in the arXiv v4 PDF p.5):**
  - G's scenario already modelled the relay's *timing*: c goes A0→B0, then B0→B1, and B_b waits for it.
  - G's engine did not put the relay in the trace's *causal DAG*. Effects were parented only on their trigger, so B1's accept did not descend from the relayed c whenever c arrived first.
  - Fix: the engine now adds per-actor process order (Lamport). The test `test_s_money_models_kent_table1_stage_ii_relay` checks it.
- **Frozen fixture `network_two_site.json` is 0.0095 ns superluminal** (33356.4 < 33356.4095). It was not edited because it is not owned. Proposal: change it to 33356.41.
- **H's `lightcone_network` rounded link bounds below the light cone.** It now uses G's exact `lightcone_links`.
- **H's old H3 late-commit scenario was time-inconsistent:** it decided the presentation before activation had arrived. Verifiers now hold the presentation until activation (`hold_until_active`).

## Results (MODELLED_LATENCY, b = 1, choice → local accept, µs, Jiang processing of 1.507 µs per step)
| protocol | Jinan | Yiyuan–Mazhan | 10 km | 100 km | 1000 km | RIPE (median of 20) |
|---|---|---|---|---|---|---|
| S1 | 15.34 | 304.21 | 51.54 | 501.85 | 5004.97 | 1979.62 |
| H3 late commit (disclosed / ideal OT) | 15.34 | 304.21 | 51.54 | 501.85 | 5004.97 | 1979.62 |
| H0 / H3-pre / H4+H3 | 15.34 | 304.21 | 51.54 | 501.85 | 5004.97 | 1928.7–1933.8 |
| H5 / H6 | 16.84 | 305.71 | 53.05 | 503.36 | 5006.48 | 1930.18 |
| H1 / H4+H1 | 46.01 | 912.62 | 154.62 | 1505.56 | 15014.91 | 6022.74 |
| H2 (2 of 3 replicas at L0) | 49.02 | 915.64 | 157.64 | 1508.57 | 15017.92 | 6083.53 |

- **Pre-presentation commit:** S1 and H3-late are both 13.83 µs at Jinan.
- **Settlement:** at Jinan it is 29.17 µs for S1, 30.67 µs for H1 and 29.17 µs for the H3 variants.
- **Double-spend races:** H0 and H6 accept twice. Every other classical design accepts once.
- **Where S-money has no edge (said plainly):**
  - It has no latency edge over H3 late commit (same relay pattern), H3-pre/H4+H3, H0, H5 or H6.
  - It has no edge in issuer awareness or settlement.
  - On RIPE it is about 51 µs slower than signal-only designs, because validation waits for the later of the presentation and c. In 7 of 20 seeds c reached B1 after the presentation.
- **Where it does have an edge:** against ledger designs whose ledger is not at the presentation site, it saves one synchronous round trip (27.66 µs at Jinan with zero processing). The comparability matrix statuses are unchanged.

## Limitations
These are listed in the JSON. In short:
- Security is not simulated for S1.
- H2 and the preassigned cases are best-case placements.
- RIPE results are medians, not paired samples.
- `project/TRACKER.yaml` still names the deleted fixtures; it is not an owned path.
