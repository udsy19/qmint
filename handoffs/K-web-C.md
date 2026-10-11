# K-web-C — platform shell, overview, research library, docs (agent KC)

Branch `feat/KC-web`, start `6a8053e`, code commit `2a70399`.

## Delivered
- **Shell** (`web/app/(platform)/layout.tsx`, `web/components/shell/`): 240px sidebar (Overview · Lab: Mint, Attack · Analysis: Benchmarks, Certificates · Library: Research, Docs) collapsing to a 48px rail (button or `[`, persisted in localStorage); 48px header with breadcrumbs (/lab is a non-link group); mobile sheet (Radix dialog); global ⌘K/Ctrl+K palette over every route, every docs page + section, and every research entry (lazy-loaded once, retried after failure); focus moves to `<main id="main">` after client navigation; footer on every platform page with **"This effort is supported by Qollab & IonQ."** (exact, `components/shell/support.ts`) plus MIT LICENSE and DISCLOSURE.md links (GitHub main).
- **/app**: real data only — git sha / API / schema / tracker phase, gates G0–G7 verbatim from TRACKER (G3 PASSED, G6 SKIPPED…), games with formula + evidence label + theorem/obligation anchors linking into /research, record store (explicit empty state: `experiments/run_registry.jsonl` absent in this checkout), lanes/tasks table, package probe (disclosure), protocol registry, tool links.
- **/research** + **/research/[id]**: 81 entries (24 papers, 15 theorems, 10 obligations, 6 datasets, 12 corrections, 14 novelty items) parsed from the lane A/D/E files; search (`/` focuses), kind/game/verification filters synced to the URL, grouped dense rows; detail page with status + definition, game, anchor, source file, lead statement, citations/DOIs, every field of the source record (LaTeX shown as labelled source), related entries with back-links; glossary of all statuses and source-file sha256s.
- **/docs** + 8 pages (getting started incl. support/license/disclosure section, architecture, examples, API reference generated from openapi.json, CLI, reproducibility, methodology & evidence labels, limitations): docs nav, on-this-page scroll-spy, anchors, copy-able code blocks.
- **API** (my route files): `GET /research/sources` now OK from real files (was plan §16 DEMO_ADAPTER), `GET /research/sources/{entry_id}` (404 envelope), `GET /meta/tracker`, `GameInfo.anchors`, evidence newest-first, endpoint docstrings. `pnpm gen:api` regenerated.

## Tests / checks
- web: typecheck 0, lint 0, vitest 34/34 (new: shell/nav/palette/support-line, docs registry↔content↔openapi tags, research filters), build 0.
- python: `pytest tests/unit/api tests/contracts` → 70 passed, **1 expected failure**: `test_api.py::test_research_sources_unverified` asserts the old "from plan, unverified" label. **Needed test_api.py change (lead):** delete that test (replacement coverage in `tests/unit/api/test_c_routes.py`, 12 tests). ruff clean.
- Example commands in /docs/examples were run on this checkout (exit 0): `qmint.cli doctor`, `sources list`, `qmint.proofs.reproduce` (~1 s), `qmint.attacks.report --trials 2000` (~20 s), `qmint.classical.run_baselines`, `scripts/run_core.py` (PASS=2 SKIPPED=9), curl to /meta/tracker, /research/sources/T-MVW12-THM1, /lab/attack ((3/4)^4, (5/8)^4 verified).

## Visual QA
Screenshots 390/768/1440/1920 of /app, /research, /research/T-KLPR22-THM1, /docs, /docs/getting-started, /docs/api, /lab/mint (shell around KD stub): `/private/tmp/claude-501/-Users-udsy-PycharmProjects-Qollab-QMint/634384d6-a062-4a24-8650-bcd5800df2da/scratchpad/kc/shots/`. No horizontal overflow at any width. Fixed after review: focus ring on <main> from StrictMode double effect, mobile tools grid, mobile breadcrumb chevron, detail-grid wrapping.

## Mobbin (targeted, recorded here per preamble)
- Delphi Knowledge list — https://mobbin.com/screens/6b40a2e7-0df3-480c-93d0-0f0f1c1684ec — status filter chips above a dense table → research filters.
- Gemini Notebook table — https://mobbin.com/screens/854709da-8018-4e45-9a1d-fceb951c545a — calm single-line rows with right-aligned meta → research rows.
- Square item library + filter sheet — https://mobbin.com/screens/7afc764b-3005-4676-a578-4c2a08200601 — filters as a side column that collapses on small screens.
- AirOps REST API page — https://mobbin.com/screens/a160611c-6fec-46bc-88c1-4aff9898cd36 — method + path line with copy, params as hairline list → API reference.
- fal API docs TOC — https://mobbin.com/screens/d7cd6f6e-809b-47ba-9bf4-9c8465771271 — sectioned TOC, code with copy.
- Customer.io API example — https://mobbin.com/screens/8d8c4bd1-ddf9-4fb3-b4a7-2bdb39bb3376 — code block with corner copy icon.
(No ai_usage_notice returned.)

## Blockers / notes for lead
- `qmint/api/common.py` (frozen) probes lane A as package `qmint.research`, so /meta reports A "absent" although A merged as files; the overview labels the probe accordingly and uses the tracker.
- Lane A data: T-MVW12-THM2.proof_obligation is `P-W1-CV` but the obligation id is `P-W1CV` (link not formed).
- `pyproject.toml` says license Apache-2.0 while LICENSE on main is MIT.
- Worktree TRACKER.yaml is the branch snapshot; overview shows whatever the served checkout has.
- No new dependencies. Servers on 8782/3002 stopped. No paid jobs.
