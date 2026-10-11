# N-N1: figure/table harness from merged evidence (lane N phase 1)

Branch `feat/N-paper` from `9a4e8a9`. No paid jobs; no network used.

**Entry:** `python -m qmint.evaluation.make_figures --out figures [--tables-out reports/paper] [--check|--force|--only figNN]`.
Proposed wrapper for lane L: `scripts/make_figures.py` -> `qmint.evaluation.make_figures.main`.

**Modules (`qmint/evaluation/`):** `statistics` (CP/Wilson via `qmint.attacks.stats`, zero-success upper bound),
`experiments` (evidence loaders + figure registry; reads RecordStore for 6-9), `plots` (renderers, evidence styles,
fixture guard), `tables` (T1 from seed+registry; T4/T5 anchored ledgers), `make_figures` (C6 manifests via
`qmint.core.manifest`, stale-cache rejection, CLI), `entrypoints` (lane-L convention).

| Fig | Status | Evidence |
|---|---|---|
| 2 W1 oracle | READY | THEOREM, MC, CERTIFIED_NUMERIC, SIM-IDEAL; W1_CV drawn as a different game |
| 3 attacker zoo | READY | exact closed forms asserted vs re-executed Kraus values; A06/A08/CTRL in red, OUT_OF_MODEL/NO_THEOREM |
| 4 Zenodo photons | READY | PHOTON_EXPERIMENT vs PUBLISHED_AGGREGATE; DOI + archive sha256 in caption |
| 5 Kent secure region | READY | Kent 2022 Thm 1 only; paper values DIGITIZED; experimental tuple UNCERTIFIED |
| 6 spacetime | PENDING | renderer done; needs GH trace records |
| 7 latency | PENDING | renderer done; needs matched quantum+classical benchmark records |
| 8 Pareto / 9 ablations | PENDING | renderers done; needs lane I formats |
| 10 hardware | READY | SYNTHETIC + SIM-IDEAL/NOISY; QPU NOT RUN; verbatim caption |

Every figure: SVG+PNG+CSV, caption JSON (status, evidence kinds/tags, legend, manifest id+sha), C6 manifest pinning
inputs, executed modules, outputs, git sha, env lock. Builds are byte-deterministic. PENDING renders no axes/numbers,
CSV `status/PENDING`. Fixture/SYNTHETIC records raise `FixtureDataError` unless `fixture_ok=True` (watermarked).

Tables (`reports/paper/`): T1 theorem families (15 seed theorems + 5 registry-only obligations; flags seed id
`P-W1-CV` vs registry `P-W1CV`), T4 24 negative results, T5 12 scope constraints. Drafts:
`NEGATIVE_RESULTS_draft.md`, `REPRODUCE_draft.md`.

**Tests:** `pytest tests/contracts tests/unit/evaluation` -> 43 passed (15 lane N), exit 0; full non-slow suite
810 passed; ruff clean; `make_figures --check` exit 0; `verify_manifest.py figures` OK.

**Proposals:** C6 `evidence_kinds` list; G/H/I write records into `experiments/` (fig 6/7 then build automatically);
C5<->C6 pairing key for fig 8. Details/limitations in `N-N1.json`.
