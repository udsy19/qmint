# K-web-A — website phase 1 (design research, design system, foundations, API)

Branch `feat/K-web`, code commit `89b6535`. Phase-2 agents start from `docs/design/WEB_OWNERSHIP.md`.

## Delivered
- **Research:** `docs/design/MOBBIN_RESEARCH.md`. 32 real Mobbin queries (screens, flows and sections; web; output `code`) produced 47 references across all 10 brief tasks, plus anti-patterns, a synthesis and originality guardrails. No `ai_usage_notice` came back.
- **Direction:** `DESIGN_DIRECTION.md` covers the repo audit (merged F, G, J, L; not merged B, C, D, E, H, I, A), the principles and the reference map.
- **System:** `DESIGN_SYSTEM.md` covers tokens, the Geist Sans/Mono/Pixel (Square + Grid) scale, the evidence-label grammar (glyph shape for origin, glyph colour for tone, only CERTIFIED in mint), components, charts (recharts, with the reason), motion with reduced-motion handling, and a11y.
- **Web:** `web/` runs Next 16.4 App Router, React 19.3, TS 5.9 strict and Tailwind 4.3.
  - Tokens live in `app/globals.css`. Primitives are in `components/ui/` (Radix/cmdk/sonner).
  - Evidence labels are generated from Python.
  - The typed client (`lib/api/client.ts`, generated `schema.d.ts`) handles timeouts, aborts and typed `ApiError`.
  - `/design-system` is the specimen page. The 8 routes are stubs.
  - `/api/*` is rewritten to :8787.
  - Playwright is pinned to 1.62.0, which uses the cached chromium-1234.
- **API:** `qmint/api` (FastAPI) serves 11 endpoints under `/api/v1`.
  - Every response carries `status` (OK, DEMO_ADAPTER or NOT_AVAILABLE), `evidence_kind`, `provenance` and `reason`.
  - Every number is a `Quantity` with a unit, evidence kind, method, source and an optional CI.
  - Errors use the `ApiError` envelope.

## Results
- web: typecheck 0, lint 0, vitest 16/16, build 0, Playwright e2e 22/22 (1440 + 390).
- python: `pytest tests/unit/api tests/unit/ui tests/contracts` gives 84 passed, and ruff is clean.
- Screenshots are in `docs/design/screenshots/phase1/`. The first capture showed a 13px overflow at 390px from the readout grid and table track, which is now fixed. The e2e overflow check was also loosened by `isMobile`, and that is fixed too.

## Findings
- **Measure-resend:** the W1 counterfeit (both-pass) rate is **(5/8)^n**. The work order's (3/4)^n is the single-copy pass rate.
- **Qiskit threading:** qiskit 2.5 segfaults when circuits are built on several threads at once, so the API serialises quantum work.

Limitations and the v2 proposal (EvidenceKind ANALYTIC) are in the JSON. No paid jobs were run.
