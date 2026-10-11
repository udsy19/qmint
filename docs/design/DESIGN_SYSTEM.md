# QMint design system (v1, frozen after phase 1)

Code of record: `web/app/globals.css` (tokens), `web/components/ui/*` (primitives), `web/lib/evidence`,
`web/lib/format.ts`. Live specimen: **`/design-system`** (used by QA for visual regression).
Changes after phase 1 go through the lead (see `WEB_OWNERSHIP.md`). Direction and references: `DESIGN_DIRECTION.md`.

Dark only. There is no light theme in v1 (the brief is dark-first; a light token set would be a v2 migration).

## 1. Colour tokens

All colours are CSS variables on `:root`, mapped into Tailwind via `@theme inline`, so components write
`bg-surface`, `text-muted`, `border-border`, never hex.

| Token | Value | Role | Contrast on background |
|---|---|---|---|
| `--background` | `#08090B` | page field | — |
| `--surface` | `#0E0F12` | inputs, quiet panels | — |
| `--surface-raised` | `#15161A` | secondary buttons, selected rows | — |
| `--surface-overlay` | `#1B1C21` | popovers, dialogs, palette, toasts | — |
| `--surface-hover` | `#1F2026` | hover/highlight row | — |
| `--border` | `#23242A` | default hairline | — |
| `--border-strong` | `#34353D` | field outlines, emphasised rule | — |
| `--hairline` | white 5.5% | table row dividers on any surface | — |
| `--foreground` | `#F4F4F5` | primary text | 18.1:1 |
| `--muted` | `#9A9BA3` | secondary text | 7.2:1 |
| `--subtle` | `#80818A` | labels, column heads, captions, placeholders (≥ 4.5:1 on background and surface; 4.4:1 on overlay — avoid essential subtle text in overlays) | 5.1:1 |
| `--accent` | `#B6F3D1` | mint: the run/launch action, selected/active, decisive number, focus ring, CERTIFIED | 15.9:1 |
| `--accent-strong` | `#8EE8B8` | accent hover | — |
| `--accent-muted` | mint 10% | selection background | — |
| `--warn` | `#E6C27A` | UNCERTIFIED, SYNTHETIC, DEMO ADAPTER glyphs; unavailable icon | 11.7:1 |
| `--danger` | `#F0A3A3` | UNSAFE, OUT-OF-MODEL, errors | 9.9:1 |
| `--info` | `#AEC6EE` | theorem / measured glyphs | 11.5:1 |
| `--chart-1..4` | mint, blue-grey, amber, lilac | chart series (see §8) | — |
| `--chart-grid` / `--chart-axis` | `#1C1D22` / `#80818A` | chart scaffolding | — |

Accent budget: **one mint thing per view** (excluding focus ring). Mint is never decorative.

## 2. Typography

Official `geist` npm package **1.7.2**, wired in `web/lib/fonts.ts` via `next/font` (self-hosted, no CDN):

| Family | Import | CSS variable → Tailwind | Role |
|---|---|---|---|
| Geist Sans (variable) | `geist/font/sans` → `GeistSans` | `--font-geist-sans` → `font-sans` | all UI, prose, headlines |
| Geist Mono (variable) | `geist/font/mono` → `GeistMono` | `--font-geist-mono` → `font-mono` | numbers, units, ids, seeds, hashes, code, state notation, labels |
| Geist Pixel **Square** | `geist/font/pixel` → `GeistPixelSquare` | `--font-geist-pixel-square` → `font-pixel` | wordmark, two-digit section numerals ("01"), select display moments |
| Geist Pixel **Grid** | `geist/font/pixel` → `GeistPixelGrid` | `--font-geist-pixel-grid` → `font-pixel-grid` | token serials (`TKN-7F3A-0008`), loading/status motif |

Verified in `node_modules/geist/dist/pixel.js`: the package ships five Pixel cuts (Square, Grid, Circle, Triangle,
Line), each a single weight-500 woff2 loaded with `next/font/local`. We load **Square + Grid only**; Circle,
Triangle and Line are not loaded (saves bytes and keeps the system coherent).

Scale (Tailwind `text-*` utilities carry size, line-height, tracking, weight):

| Token | Size / line | Tracking | Weight | Use |
|---|---|---|---|---|
| `display-xl` | 72 / 72 | −4.5% | 560 | landing hero only (scale down to `display`/`h1` < 768px) |
| `display` | 56 / 58 | −4% | 560 | landing section openers, page heroes |
| `h1` | 40 / 44 | −3.2% | 560 | app page titles on wide pages, docs H1 |
| `h2` | 28 / 34 | −2.4% | 560 | section titles |
| `h3` | 20 / 27 | −1.6% | 560 | sub-sections, dialog hero numbers |
| `h4` | 16 / 24 | −0.8% | 560 | panel titles, app page titles in dense views |
| `body-lg` | 17 / 28 | 0 | 400 | marketing prose, lead paragraphs |
| `body` | 15 / 24 | 0 | 400 | default UI/prose |
| `sm` | 13 / 19.5 | 0 | 400 | dense UI, table cells, nav items |
| `xs` | 12 / 17 | 0 | 400 | captions, hints |
| `label` (`label-mono` utility) | 11 / 16 | +6%, uppercase, Mono 500 | | eyebrows, column heads, evidence labels |

Rules: headings Sans 560 (never 700+); max two weights per view (400 + 560/500). Every aligned number uses the
`tnum` utility (tabular + slashed zero). Units are Mono, `text-subtle`, separated by a space (`15.337 µs`).
Quantum notation in Mono: `|+⟩`, `|ψ⟩`, `(3/4)ⁿ`. Pixel never sets more than ~24 characters and never body copy.

## 3. Space, layout, grid

- 4px base; use Tailwind spacing (1 = 4px). Common steps: 4, 8, 12, 16, 24, 32, 48, 64, 96, 128.
- Gutter `--gutter`: 16px (< 768), 24px (≥ 768), 32px (≥ 1280).
- Containers (utilities include the gutter): `container-prose` 680px (reading), `container-content` 1080px
  (app pages), `container-wide` 1280px (marketing, dashboards). `max-w-prose` = 680px.
- 12-column grid on ≥ 1024px for marketing compositions; app pages use content + optional 280px right rail.
- App shell: header `--header-h` 48px; sidebar `--sidebar-w` 240px, rail 48px; marketing nav `--nav-h` 56px.
- Section rhythm: marketing 128–160px vertical between sections (96px mobile); app 32–48px between groups.
- Breakpoints: Tailwind defaults sm 640, md 768, lg 1024, xl 1280, 2xl 1536. QA widths: 390, 768, 1440, 1920.

## 4. Radius, borders, elevation, z-order

- Radius: `rounded-xs` 2px (tags, focus), `rounded-sm` 4px (buttons, inputs), `rounded-md` 6px (popovers,
  panels), `rounded-lg` 10px (dialogs, palette). Nothing larger; no pill buttons.
- Borders: 1px. `border-border` default, `border-border-strong` for fields, `border-hairline` for row dividers.
- Elevation: flat by default. `shadow-raised` (1px ring + soft drop) for floating controls; `shadow-overlay` for
  popovers/dialogs/palette/toasts. No glows, no backdrop blur.
- z-order utilities: `z-sticky` 10, `z-header` 20, `z-dropdown` 30, `z-overlay` 40, `z-modal` 50, `z-toast` 60,
  `z-tooltip` 70.

## 5. Motion

| Token | Duration | Use |
|---|---|---|
| `--duration-instant` | 80ms | hover colours, row highlight |
| `--duration-fast` | 140ms | buttons, tabs, chevrons, tooltips, dropdowns |
| `--duration-base` | 220ms | dialogs, tab content, panels |
| `--duration-slow` | 360ms | chart transitions, layout shifts |
| `--duration-deliberate` | 640ms | instrument/token state changes (hero, lab) only |

Easing: `ease-out` = `cubic-bezier(0.2,0,0,1)` (default, enter/feedback); `ease-in-out` `(0.4,0,0.2,1)` for
symmetric moves; `ease-emphasized` reserved for the hero instrument. Keyframes: `qm-fade-in` (opacity + 2px rise),
`qm-shimmer` (skeleton), `qm-pixel-blink` (PixelLoader).

Rules: CSS transitions first; `motion` library only if a phase-2 agent shows CSS cannot do it (lead approval,
not installed in phase 1). Animate opacity/transform only. Never loop motion except loaders. **Reduced motion**
(`prefers-reduced-motion: reduce`) collapses all animation/transition durations globally (globals.css); every
state change must also be expressed as text/icon change so nothing is lost without motion. Charts must render
final state immediately under reduced motion (`isAnimationActive={!reduced}` in recharts).

## 6. Evidence-label system

One component, `<EvidenceLabel kind group? />` (`web/components/ui/evidence-label.tsx`), driven by
`web/lib/api/evidence-labels.json`, which is **generated** from Python (`qmint/ui/evidence_badges.py` + API statuses)
by `pnpm gen:api`. Labels are never hand-written in TSX.

Visual grammar (restrained — no filled pills): Mono 11px uppercase text in `text-muted` + an 8px glyph.
- **Glyph shape = origin**: theory ■ · numeric ◩ · simulated □ · measured ● · none × · api ◇
- **Glyph colour = tone**: info (blue-grey), neutral (subtle), warn (amber), danger (red), ok (mint).
- Text is tinted only for `danger` (UNSAFE, OUT-OF-MODEL) and `ok` (CERTIFIED — the only mint label).
- Tooltip + screen-reader text carry the full definition (e.g. "a LOWER bound on worst-case attack success").

| Brief name | `group:key` | Visible label | Origin | Tone |
|---|---|---|---|---|
| THEOREM | `evidence_kind:PUBLISHED_THEOREM` | THEOREM | theory | info |
| NUMERICAL | `evidence_kind:NUMERICAL_SDP` | NUMERICAL | numeric | neutral |
| CERTIFIED-NUMERIC | `evidence_kind:CERTIFIED_NUMERIC` | CERTIFIED-NUMERIC | numeric | info |
| MONTE-CARLO lower bound | `evidence_kind:MONTE_CARLO` | MONTE-CARLO (lower bound) | simulated | neutral |
| SIMULATED | `evidence_kind:SIMULATOR_IDEAL` / `SIMULATOR_NOISY` | SIMULATOR-IDEAL / SIMULATOR-NOISY | simulated | neutral |
| SYNTHETIC | `evidence_kind:SYNTHETIC` | SYNTHETIC | simulated | warn |
| PHOTON-EXPERIMENT | `evidence_kind:PHOTON_EXPERIMENT` | PHOTON-EXPERIMENT | measured | info |
| QPU | `evidence_kind:QPU` | QPU | measured | info |
| MODELLED | `evidence_kind:MODELLED_LATENCY` | MODELLED-LATENCY | simulated | neutral |
| MEASURED | `evidence_kind:MEASURED_LATENCY` | MEASURED-LATENCY | measured | info |
| (published numbers) | `evidence_kind:PUBLISHED_AGGREGATE`, `DIGITIZED_FIGURE` | PUBLISHED-AGGREGATE, DIGITIZED-FIGURE | theory | neutral |
| UNCERTIFIED | `evidence_kind:UNCERTIFIED`, `certificate_status:UNCERTIFIED` | UNCERTIFIED | none | warn |
| (cert statuses) | `certificate_status:CERTIFIED / INFEASIBLE / UNSAFE / OUT_OF_MODEL` | CERTIFIED / INFEASIBLE / UNSAFE / OUT-OF-MODEL | | ok / warn / danger / danger |
| DEMO_ADAPTER | `api_status:DEMO_ADAPTER` | DEMO ADAPTER | api | warn |
| NOT_AVAILABLE | `api_status:NOT_AVAILABLE` | NOT AVAILABLE | api | neutral |

Usage rules (anti badge-soup):
1. A label sits **under or beside the number it qualifies**, never in a row of badges.
2. One label per number; when a whole panel shares one kind, label the panel header once.
3. The API also returns `Quantity.method` (`closed_form`, `exact_enumeration`, `aer_sampling`, `event_simulation`,
   `published_value`, `measured_dataset`, `not_available`). Show it as quiet Mono text in detail views ("exact",
   "sampled · 4 000 shots"); it disambiguates exact analytic values that the frozen contract labels SIMULATOR_IDEAL.
4. `DEMO ADAPTER` responses show a single page-level notice with the API `reason`, plus the label on each value.
5. Monte Carlo values always show their interval and the "lower bound" meaning; never present them as upper bounds.

## 7. Component inventory (`web/components/ui/`, frozen)

| File | Exports | Notes |
|---|---|---|
| `button.tsx` | `Button`, `buttonVariants` | variants accent (one per view: run/launch), primary (white), secondary, ghost, link, danger; sizes sm 28 / md 32 / lg 40 / icon; `asChild` for links |
| `input.tsx` | `Input`, `Label`, `Field`, `fieldBase` | `Field` wires label/hint/error ids; numeric inputs are Mono tnum; `aria-invalid` styles |
| `select.tsx` | `Select`, `SelectTrigger`, `SelectContent`, `SelectItem`, `SelectValue`, `SelectGroup`, `SelectLabel` | Radix; check in mint |
| `slider.tsx` | `Slider` | 3px track, mint range; always pair with a visible numeric value |
| `tabs.tsx` | `Tabs`, `TabsList`, `TabsTrigger`, `TabsContent` | underline tabs, no pills |
| `table.tsx` | `Table`, `THead`, `TBody`, `Tr`, `Th`, `Td`, `TableCaption` | `numeric` prop → right-aligned Mono tnum; hairline rows; no zebra |
| `tooltip.tsx` | `TooltipProvider` (in root layout), `Tooltip`, `TooltipTrigger`, `TooltipContent` | 300ms delay |
| `dialog.tsx` | `Dialog`, `DialogTrigger`, `DialogContent`, `DialogHeader`, `DialogTitle`, `DialogDescription`, `DialogBody`, `DialogFooter`, `DialogClose`, `DialogOverlay` | flat 60% scrim, no blur |
| `command.tsx` | `Command`, `CommandDialog`, `CommandInput`, `CommandList`, `CommandEmpty`, `CommandGroup`, `CommandItem`, `CommandSeparator`, `CommandFooter` | cmdk; 560px; mint 2px active bar; key-hint footer. Global ⌘K wiring is Agent C's |
| `disclosure.tsx` | `Disclosure`, `Collapsible*` | technical detail, derivations, provenance, raw JSON |
| `toast.tsx` | `Toaster` (in root layout), `toast` | sonner, bottom-right; run complete / copied / exported |
| `kbd.tsx` | `Kbd` | |
| `skeleton.tsx` | `Skeleton` | render real headers; skeleton only the cells |
| `pixel-loader.tsx` | `PixelLoader` | 3×3 Pixel motif; always with visible text |
| `evidence-label.tsx` | `EvidenceLabel` | §6 |
| `readout.tsx` | `Readout`, `ReadoutGroup` | label / Mono value / unit / interval + CI / evidence; `null` → missing text, never 0; `emphasis` = mint (one per group) |
| `state.tsx` | `StateMessage`, `EmptyState`, `ErrorState` (`timeout`), `UnavailableState` | role=status / alert; copy says what, why, next |
| `separator.tsx` | `Separator` | |

Helpers: `cn` (`lib/utils.ts`), `formatNumber/formatValue/formatInterval/NO_BOUND` (`lib/format.ts`, mirrors
`qmint/ui/claims.py::fmt_number`), `getEvidenceLabel/EVIDENCE_LABELS` (`lib/evidence`), typed API client
`apiGet/apiPost/ApiError` (`lib/api/client.ts`). Domain components (charts, lab panels, shell) live in the
phase-2 agents' own directories, built **from** these primitives.

## 8. Charts

Library: **recharts 3** (declarative React, composable `ErrorBar`/`ReferenceLine`/`ReferenceArea` cover error bars,
bound lines and confidence bands; adequate for the ≤ few-hundred-point datasets here; themable via props with our
CSS variables). visx was considered: more control, but every axis/tooltip/legend would be hand-built across
three agents, which is where inconsistency creeps in. Bespoke instruments (hero token visual, Bloch sphere,
circuit diagram, light-cone diagram) are hand-written SVG, not recharts.

Chart rules: greyscale scaffolding (`--chart-grid` lines, ≤ 3 horizontal gridlines, no vertical grid), axis text
Mono 11px `--chart-axis`; series 1 = mint (QMint/quantum), series 2 = `--chart-2` (comparison/classical),
bounds = `--chart-3` dashed 1px line labelled in Mono; CIs as error bars or 8%-alpha bands; log-scale when
values span > 2 decades (probabilities vs n). Legends as Mono text with 8px glyphs, not coloured boxes. Every
chart has a textual summary or a table toggle for accessibility. Charts must render a NOT_AVAILABLE state rather
than an empty axis.

## 9. Accessibility rules

- WCAG 2.2 AA. All text tokens (`foreground`, `muted`, `subtle`) are ≥ 4.5:1 on `background` and `surface`.
- Focus: visible 2px mint outline, 2px offset, on every interactive element (`:focus-visible` in base layer).
- Skip link to `#main` in root layout; each page has exactly one `<main id="main">` and one `<h1>`.
- Colour is never the only channel: evidence labels have text + glyph shape; status has a word.
- Keyboard: all controls reachable; ⌘K/Ctrl+K palette; Esc closes overlays (Radix); tabs arrow-key navigable.
- Forms: `Field` associates label/hint/error; errors use `role="alert"` and `aria-invalid`.
- Live results: wrap running regions in `aria-busy`, announce completion via `role="status"` text or toast.
- Charts: `role="img"` + `aria-label` summary, and a data table alternative.
- Touch targets ≥ 32px (≥ 40px for primary mobile actions). No horizontal page scroll at 390px.
- Reduced motion honoured globally (§5).

## 10. Content rules (from AGENT_RULES evidence discipline)

No "secure", "proven", "quantum advantage", "unforgeable" without matching evidence on the same screen. QMint is a
research platform: never imply banking services or deployable quantum currency. Probabilities are shown as
fractions (0.75), not percentages, unless labelled. ε is a maximum adversary win probability, never an error bar.
Never transfer a theorem across games (W1 ≠ W1_CV ≠ W2 ≠ S1 ≠ S2 ≠ D1 ≠ A1).
