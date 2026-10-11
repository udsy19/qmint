# Lane G — G1 handoff (relativistic networking, causal event simulator, RIPE data)

Branch `feat/G-networks`. Started at `ece05ef`. Code commit `389804d`; the handoff commit follows it.

## What it does
- **Engine** (`events.py`, `simulator.py`): a seeded discrete-event engine. The heap is ordered by `(time, insertion seq)`. It hosts `Actor`s that follow `on_message` / `on_local_request`, which return `Send | Record | SetTimer` effects. Every cross-site delivery has to satisfy `recv >= send + max(link bound, light cone)`. If a latency model breaks that, the engine raises `CausalityViolation` instead of clamping. Latency models: `Lightcone`, `Fiber` (2/3 c by default), and `Empirical` (resampled RIPE RTT/2). The engine also supports FIFO queueing, loss with retransmission, timed partitions, and per-site clock offsets kept within `clock_error_bound_ns`; actors see their local clock. Results export to a C4 `TransactionTrace`.
- **Causality** (`causality.py`): checks for retrocausal edges, for messages faster than the bound, and for information that reaches a site faster than light along any path in the DAG. Also provides a spacelike/timelike/AMBIGUOUS classifier that accounts for clock error, ordering under uncertainty, and a detector for synchronous cross-site round trips.
- **Topologies** (`topology.py`): PAPER cases from Jiang et al. 2024 (Jinan: 2.766 km fibre, 426 m straight line; Yiyuan–Mazhan: 60.54 km fibre, 51.60 km straight line), plus SYNTHETIC cases at 1, 10, 100 and 1000 km. In every case the C4 lower bound is the straight-line light cone. The fibre delay is modelled separately at runtime.
- **RIPE** (`ripe.py`): an adapter for the public REST API. The committed fixture covers anchor-mesh pings: msm 7714918 (Helsinki prb6330 → Tampere prb6251, Frankfurt prb6979 → Tampere) and msm 10683825 (Tampere → Helsinki). One-way delay is taken as RTT/2, and that assumption is flagged. Endpoint coordinates that contradict the measured RTT are refused.
- **S-money** (`s_money_sites.py`): the two-site S-token event flow. Alice's choice → commitment c → one-way forward → local validation → issuer awareness → settlement. A `query_home` negative control exists to check that the round-trip detector works.
- **Classical race TEST FIXTURES** (`classical_race_fixtures.py`): minimal H0, H1 and H3 actors. Lead: replace these with lane H's versions at integration, then delete the module.

## Results
| case | S-money (modelled) | published | H1 fixture, remote merchant |
|---|---|---|---|
| Jinan 2.766 km | 15.337 µs | 15.34 ± 0.01 µs | 27.66 µs (= paper's 2L/c_f) |
| Yiyuan–Mazhan 60.54 km | 304.207 µs | 304.20 ± 0.01 µs | 605.4 µs |
| RIPE HEL–TMP (median of 20 seeds) | 1.98 ms | — | 4.13 ms |

For the RIPE HEL→TMP link, the RTT/2 p50 is 1.948 ms, against a 0.517 ms light-cone bound (MEASURED_LATENCY).

The RIPE numbers are not a matched benchmark: trust model, privacy and processing differ between the S-money model and the H1 fixture.

## Verification notes
- The haversine distance between the paper's published coordinates is about 49.55 km, not the stated 51.60 km. The stated value is used and the gap is recorded.
- The paper gives the Jinan straight-line distance as 426 m in the main text and 425 m in the caption and SI.

## Tests
`$PY -m pytest tests/contracts tests/unit/networks -q -o addopts=''` → exit 0, 71 passed. That includes 53 network-lane tests and 1 live `@pytest.mark.network` test. `ruff check` passes.

## Limitations and proposals
See the JSON file. Key points:
- The S-money model covers timing only; it says nothing about security.
- The S-money traces use the registered protocol id `s_money_kent_2022_ideal_2site`, because no id exists for Jiang's practical S-tokens. A v2 proposal is included.
- Figure 6 is not plotted yet.
