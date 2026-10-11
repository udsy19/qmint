# QMint web — ownership map for phase-2 agents

Phase 1 (Agent A) delivered: tokens, primitives, `/design-system`, typed API client, FastAPI API, stub routes.
Read first: `WEBSITE_BRIEF.md` (incl. Lead notes), `DESIGN_DIRECTION.md`, `DESIGN_SYSTEM.md`, `MOBBIN_RESEARCH.md`.

## Frozen (change only via the lead)

| Path | Why |
|---|---|
| `web/app/globals.css` | design tokens |
| `web/components/ui/**` | shared primitives |
| `web/lib/utils.ts`, `web/lib/format.ts`, `web/lib/fonts.ts`, `web/lib/evidence/**` | shared helpers |
| `web/lib/api/client.ts` | typed fetch wrapper |
| `web/lib/api/openapi.json`, `schema.d.ts`, `evidence-labels.json` | **generated** — run `pnpm gen:api`, never hand-edit |
| `web/app/layout.tsx`, `web/app/design-system/**` | root layout (fonts, skip link, providers) + QA specimen |
| `web/package.json`, `pnpm-lock.yaml`, configs (`next.config.ts`, `tsconfig.json`, `eslint.config.mjs`, `vitest.config.ts`, `playwright.config.ts`, `postcss.config.mjs`) | toolchain; new dependencies need lead approval |
| `qmint/api/**`, `tests/unit/api/**` | API contract. Need a field/endpoint? Propose it to the lead (or the lead assigns one agent); then `pnpm gen:api` |

If a primitive is missing, build it locally in your own directory first and propose promotion in your handoff.

## Route and directory ownership

| Agent | Owns (create/edit) | Routes | API used |
|---|---|---|---|
| **B — Landing & brand** | `web/app/(marketing)/**` (incl. its `layout.tsx`: marketing nav + footer), `web/components/marketing/**`, `web/public/brand/**` | `/` | `/api/v1/games`, `/api/v1/lab/attack` (hero instrument, analytic backend), `/api/v1/meta` |
| **C — Shell, research, docs** | `web/app/(platform)/layout.tsx` (sidebar, 48px header, breadcrumbs, mobile sheet, global ⌘K), `web/app/(platform)/app/**`, `web/app/(platform)/research/**`, `web/app/(platform)/docs/**`, `web/components/shell/**`, `web/components/research/**`, `web/components/docs/**` | `/app`, `/research`, `/docs` | `/meta`, `/protocols`, `/games`, `/evidence`, `/research/sources` |
| **D — Quantum lab** | `web/app/(platform)/lab/**`, `web/components/lab/**` | `/lab/mint`, `/lab/attack` | `POST /lab/mint`, `POST /lab/attack` |
| **E — Benchmarks & certificates** | `web/app/(platform)/benchmarks/**`, `web/app/(platform)/certificates/**`, `web/components/charts/**`, `web/components/certificates/**` | `/benchmarks`, `/certificates` | `/benchmarks`, `POST /certificates`, `/games` |
| **F — Integration & QA** | `web/e2e/**`, `docs/design/VISUAL_QA.md`, `docs/design/screenshots/**`, deletion of `web/components/route-stub.tsx` once unused | all (read-only review; file fix requests to owners) | all |

Shared expectations: D and E may import `web/components/charts/**` (owned by E; D requests additions from E or keeps
chart-like lab visuals in `components/lab/`). C's shell wraps D's and E's routes automatically via
`(platform)/layout.tsx` — page files must not render their own sidebar/header. Every page: one `<main id="main">`,
one `<h1>`, metadata `title`. Data fetching: use `apiGet`/`apiPost` only; server components may call the API
(server-side origin `QMINT_API_ORIGIN`, default `http://127.0.0.1:8787`), client components go through `/api` rewrites.

## Commands (run from `web/`, pnpm only)

```bash
pnpm install                 # pnpm only — never npm/yarn (disk budget; pnpm hard-links)
pnpm dev                     # http://localhost:3000 ; /api/* → :8787
pnpm typecheck               # tsc --noEmit (strict)
pnpm lint                    # eslint (next core-web-vitals + typescript)
pnpm test                    # vitest + Testing Library (co-locate *.test.tsx with components)
pnpm build                   # next build — must pass before handoff
pnpm e2e                     # playwright (chromium only; desktop-1440 + mobile-390 projects)
pnpm gen:api                 # regenerate openapi.json, evidence-labels.json, schema.d.ts from qmint/api
```

API (from repo root): `PY=/Users/udsy/PycharmProjects/Qollab-QMint/.venv/bin/python`
`$PY -m uvicorn qmint.api.app:app --port 8787` · tests `$PY -m pytest tests/unit/api tests/contracts -q` ·
`$PY -m ruff check qmint/api tests/unit/api`.

Playwright browser: `@playwright/test` is pinned to **1.62.0**, which uses the chromium-1234 build already in
`~/Library/Caches/ms-playwright`. Do not upgrade it or run `playwright install` (disk ~8 GB free).

## Supersession of the wave-1 static workbench

`qmint/ui/` (static HTML renderer) and `app/site/` are superseded by `web/`. Kept in phase 1 because
`qmint/ui/evidence_badges.py` is the source of the evidence-label table (served by `/api/v1/evidence/labels`) and its
views are not yet covered. Plan: once C/D/E pages cover protocol/game cards, attacks, spacetime, certificates and
the evidence ledger, the lead (or F) moves `evidence_badges.py` (+ the `fmt_number`/`Cited` rules from `claims.py`
if still used) into `qmint/api/`, then deletes `qmint/ui/{app,build,views,svg,records}.py`, `app/site/`, and the
corresponding `tests/unit/ui` cases in the same change, and greps for zero remaining references.
