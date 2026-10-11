# K-K1 — Evidence-first research workbench (wave 1, synthetic fixtures)

Branch `feat/K-ui`; code commit `33fbce0`. Contract SHA `ace5cbc`.

**Build:** `$PY -m qmint.ui.build --records tests/fixtures/contracts --records tests/unit/ui/fixtures --out app/site [--strict] [--real-data]`
-> `app/site/index.html` (self-contained, inline CSS/JS, no CDN), `figures/*.svg`, `site_manifest.json` (record hashes + file hashes).

**Modules:** `evidence_badges` (enum-only badges), `claims` (Cited numbers, ClaimPanel), `records` (load + validate C0–C6 JSON),
`svg` (spacetime diagram with light cones, Pareto scatter), `views` (protocol/game cards, attacks with CI and SDP primal/dual,
photon provenance, spacetime, certificates/Pareto, evidence ledger, hardware provenance), `app` (page assembly), `build` (CLI).

**Tests:** `$PY -m pytest tests/contracts tests/unit/ui -q` -> exit 0, 42 passed (24 UI). Ruff clean.
Covers: missing bound not zero; uncited number rejected from claim panel; simulated vs measured badges distinct;
UNCERTIFIED never green; failed assumptions -> red alert; FIXTURE label forced by SYNTHETIC; no external resources;
QPU "not run"; deterministic output hash; CLI entry.

**Limitations:** all data is SYNTHETIC fixture data (labelled FIXTURE DATA); theorem-card formulas come from the contract
comments, not re-verified; no browser/WCAG audit run; Pareto certified-ness uses a `configuration.certificate_ref` convention.

**Proposed v2 contract change:** `certificate_id` on SecurityCertificate, `certificate_ref` on BenchmarkRecord, `record_id` on ProtocolSpec.
No paid jobs run.
