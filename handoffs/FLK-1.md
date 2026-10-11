# FLK-1: core records, old workbench retirement, API evidence gate

Branch `feat/FLK-fixes`, from `02aeab1`. The code is in commit `d2ab1ff`. The JSON record is `FLK-1.json`.

## Delivered
- **M-L1 (`qmint/core/records.py`).** `RecordStore.get()` now refuses a record unless:
  - its file `record_id` equals the id requested;
  - it has exactly one `run_registry.jsonl` line, and that line matches `record_sha256`, `payload_sha256`, contract, evidence kind and `result_path`;
  - the envelope `evidence_kind` equals the payload's own evidence field.
  Both M-L1 strict xfails (an injected file, and a SYNTHETIC record relabelled MONTE_CARLO) now pass, and their markers are removed. The registry hash chain (optional in the audit) was not added.
- **M-K1 and supersession.**
  - `qmint/ui/evidence_badges.py` was moved (git rename) to `qmint/api/evidence_labels.py`, and `/api/v1/evidence/labels` uses it. `evidence-labels.json` is byte-identical after regeneration.
  - Deleted: all of `qmint/ui/` (app, build, claims, records, svg, views), `app/site/`, and `tests/unit/ui/` (the workbench tests and fixtures).
  - `claims.py` (`fmt_number`/`Cited`) was not kept, because no Python code outside `qmint/ui` used it.
  - The badge-rule tests were ported to `tests/unit/api/test_evidence_labels.py`.
- **API provenance gate (`qmint/api/routes/evidence.py`).** Every `/evidence` record goes through `RecordStore.get`. It must also have a hex git sha and no "fixture" marker in its provenance or payload. Otherwise it is served with `evidence_kind=SYNTHETIC`, `provenance_verified=false` and `provenance_problems`. New fields: `recorded_evidence_kind`, `provenance_verified`, `provenance_problems`.
  - The M-K1 regression in `tests/adversarial/test_m_records.py` now tests this gate.
  - It loads the three lane-K fixture payloads (MONTE_CARLO, NUMERICAL_SDP, MODELLED_LATENCY) inline into a real store, and none of them is served as non-SYNTHETIC.
  - A relabelled record is served as SYNTHETIC, and a genuine MONTE_CARLO control is served as MONTE_CARLO.
- **Lane A probe (`qmint/api/common.py`).** Lane A is now detected by its files: `research/PRIOR_ART_MATRIX.csv`, `THEOREM_REGISTRY_SEED.yaml` and `DATASOURCE_REGISTER.yaml`. `/meta` reports A as merged, and `test_meta_lanes_detected` now asserts it.
- **`schemas.Method`** gains `monte_carlo` and `numerical_sdp`.
  - KD's route-local widening (`LabMethod` and the `method` override) is gone.
  - `class LabQuantity(Quantity)` is kept as a body-less subclass. Its only job is to keep the OpenAPI component name `LabQuantity`, which `web/components/lab/{quantity.tsx,comparison.ts,lab-api.ts}` import. Not trivial to drop, because those files belong to another agent.
  - **For KD:** switch those imports to `Schemas["Quantity"]`, then delete the subclass and rename to `Quantity` in `lab.py`.
- **`GET /api/v1/evidence/highlights`** (new file `qmint/api/routes/highlights.py`, requested by KB). Values are read live, and every source carries its path, sha256 and field:
  - **W1 SDP bracket (CERTIFIED_NUMERIC).** Read from `handoffs/C-C1-evidence.json` `w1_sdp.n{1,2}_SCS.certified`: 3/4 ≤ OPT₁ ≤ 0.750000000003638 and 9/16 ≤ OPT₂ ≤ 0.562500000007276. It is cross-checked against `proofs/certificates/reproduction_v1.json` rows (lane D exact dual 3/4 and 9/16, agrees=true). If D disagrees, the highlight is withheld.
  - **Schiansky QBER (PHOTON_EXPERIMENT).** Z is 1.4491% and X is 3.2787%, state-averaged, from `reports/data_working/schiansky2023/summary.json`. The published 1.45% and 3.28% are shown as separate PUBLISHED_AGGREGATE quantities.
  - **Matched topology, Jinan 2.766 km (MODELLED_LATENCY).** Choice→accept times with Jiang processing and b=1 are S1 15 337 ns, H3 late-commit OT 15 337 ns and H1 46 011 ns. Comparability counts are 0 comparable, 7 qualified and 4 incomparable. Sources are `matched_topology_results.csv` and `comparability_matrix.csv`.
  - If an artefact is missing, that highlight goes under `data.unavailable` with the reason. It is never invented.
  - **For KB:** `web/components/marketing/research-values.ts` (the SDP_W1 and ZENODO_QBER constants) can now read this endpoint and be deleted.
- **Q/L manifests.** `qmint.core.manifest.load_manifest` accepts `.yaml`/`.yml` as well as JSON. `realdata_preflight` reads `*.json` and also any YAML that declares `manifest_id`. YAML without it (lane E's existing dataset descriptors `zenodo_*.yaml`) is ignored, and the refusal message says so. A new integration test covers a YAML manifest passing, a descriptor being ignored, and a tamper giving MISMATCH. `run_all` stays REFUSED until lane FDE commits real EvidenceManifests.
- **API client.** Regenerated with `pnpm gen:api` (`openapi.json` and `schema.d.ts`).

## Checks
- `$PY -m pytest tests -q -m "not network and not slow" -o addopts=""`: exit 0, **974 passed**, 2 deselected, 21 xfailed. That is 26 − 5 xfails fixed: 2 for M-L1 and 3 parametrised for M-K1.
- `$PY -m ruff check qmint scripts tests`: clean.
- Repo-wide `ruff check .` reports 2 findings in `qollab/main.py` (B023 at lines 69 and 187). I did not touch that file, and it is not owned by FLK.
- `cd web && pnpm typecheck`: 46 errors after vs 49 before. All of them are in `components/marketing/hero/*`, which another agent is fixing. There are no new errors.
- `pnpm test`: 93/93 pass.
- `pnpm install --frozen-lockfile --prefer-offline` was run because the worktree had no `node_modules`.

## Stale references left (not owned by FLK; for the lead)
No code imports `qmint.ui` any more. Prose and comments still name the old paths in:
- `web/lib/format.ts:2` and `web/lib/evidence/index.ts:2` (frozen `web/lib`);
- `web/components/docs/content/methodology.tsx:63` (KC);
- `docs/design/{DESIGN_SYSTEM,DESIGN_DIRECTION,WEBSITE_BRIEF,WEB_OWNERSHIP}.md`;
- `project/{DECISIONS.md,TRACKER.yaml,merge_lane.sh}`, `AGENT_WORK_PACKAGES.md` and `QMINT_MASTER_RESEARCH_PLAN.md`.

They should now point to `qmint/api/evidence_labels.py`. The `fmt_number` mirror comment has no Python counterpart left: `web/lib/format.ts` is now the only implementation.

## Limitations
- Fixture detection in the gate uses markers: it looks for a "fixture" substring and a non-hex git sha, and it fails toward SYNTHETIC.
  - The gate does not consult an EvidenceManifest.
  - Someone who can rewrite both a result file and its registry line consistently can still forge a record. Closing that needs the registry hash chain or signing.
- The comparability counts are labelled MODELLED_LATENCY because the contract has no "classification" evidence kind. Their note says they are a count of matrix rows, not a measurement.
- No paid jobs and no network.
