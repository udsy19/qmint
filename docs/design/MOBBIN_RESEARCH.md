# QMint — Mobbin Design Research

- **Date:** 2026-10-11
- **Scope:** Visual and interaction references for the QMint Next.js site and app (`/`, `/app`, `/lab/mint`, `/lab/attack`, `/benchmarks`, `/certificates`, `/research`, `/docs`, `/design-system`, command palette, mobile nav).
- **Target aesthetic:** dark, technical, minimal, precise, quietly futuristic. Near-black surfaces, hairline borders, one mint accent (`#B6F3D1`), Geist Sans / Mono / Pixel.

## Tool availability

- The Mobbin MCP was available and authenticated. Every call returned results with inline preview images and `mobbin_url`s.
- **Tools used:** `mcp__mobbin__search_screens` (24 calls), `mcp__mobbin__search_flows` (2 calls), `mcp__mobbin__search_sections` (6 calls). That is **32 queries in total**.
- **Parameters:** `output_destination: "code"` on every call. `platform: "web"` on every screens/flows call except two `ios` fallbacks, which are marked in the log. They were used because Mobbin's web library has almost no true mobile-viewport captures (see query 24). Sections search has no platform parameter.
- **`ai_usage_notice`:** none of the 32 responses contained an `ai_usage_notice` field, so there is no notice text to quote.
- **Method:** each preview image was inspected visually. Every pattern below describes what the screenshots show, not what the metadata says.
- **Caveat:** many Mobbin captures of Vercel, Linear, Supabase and Stripe are in **light mode**. Where that applies, the layout, spacing and hierarchy carry over to our dark theme; the colours do not.

## Query log

| # | Tool | Query (abridged) | Filters | Results looked at | Useful? |
|---|---|---|---|---|---|
| 1 | search_screens | Vercel dashboard project overview with deployments list | web, limit 6 | 6 | Yes (Vercel overview) |
| 2 | search_screens | Linear issues list view with left sidebar | web, limit 6 | 6 | Yes (light-mode captures) |
| 3 | search_screens | Supabase project dashboard with table editor | web, limit 6 | 6 | Yes |
| 4 | search_sections | Dark hero for developer platform, two buttons + screenshot | limit 6 | 6 | Partly; mostly glow/gradient heroes, used as anti-patterns |
| 5 | search_screens | Linear marketing landing page hero | web, limit 5 | 1 | Yes |
| 6 | search_screens | Resend landing page with code snippet | web, limit 5 | 5 | Returned the Resend *app* (onboarding, API sheet), not marketing. Still useful |
| 7 | search_screens | Stripe homepage hero | web, limit 4 | 4 | Partly (hero = anti-pattern; dashboard useful) |
| 8 | search_sections | Feature grid with hairline dividers, mono labels | limit 6 | 6 | Yes (Linear, Attio) |
| 9 | search_screens | Raycast website landing page dark hero | web, limit 4 | 4 | **No Raycast results.** Returned Linear, Framer, Featurebase, Better Stack |
| 10 | search_screens | Command palette with grouped actions + shortcuts | web, limit 6 | 6 | Yes (Vapi, Juicebox) |
| 11 | search_screens | Vercel command menu with search + nav items | web, limit 4 | 4 | Yes |
| 12 | search_screens | AI playground with parameter sliders | web, limit 6 | 6 | Yes (Braintrust, Snowflake, FLORA, Cohere) |
| 13 | search_screens | Vercel project settings form sections + save footer | web, limit 4 | 4 | Yes |
| 14 | search_screens | Vercel web analytics, visitors chart + top pages | web, limit 4 | 4 | Yes (includes a dark-mode capture) |
| 15 | search_screens | Dark observability dashboard, latency percentiles, error rate | web, limit 6 | 6 | Yes (Supabase, Railway, Better Stack, LangSmith, Sentry) |
| 16 | search_screens | API reference, left nav + endpoint + code panel | web, limit 6 | 6 | Partly (GitBook schema rows) |
| 17 | search_screens | Docs article with sidebar + "On this page" TOC | web, limit 6 | 6 | Yes (Mintlify, Devin, Vercel) |
| 18 | search_flows | Deploying a project: import, configure, logs, success | web, limit 3 | 3 flows (19 screens) | Yes (Vercel, Cloudflare) |
| 19 | search_screens | Deployment build logs with collapsible steps + timestamps | web, limit 6 | 6 | Yes (Laravel Cloud, Railway, Emergent, Browserbase, Databricks) |
| 20 | search_screens | Incident detail with summary, timeline, components | web, limit 5 | 5 | Yes (incident.io, Better Stack, Stripe events) |
| 21 | search_screens | Vercel deployment details with build logs accordion | web, limit 4 | 4 | Yes (strongest task-8 reference) |
| 22 | search_screens | Empty state, small icon, one line, single action | web, limit 6 | 6 | Yes (v0, Copilot, Whop) |
| 23 | search_screens | Skeleton loading for table and charts | web, limit 5 | 5 | Yes (Neon, Unify) |
| 24 | search_screens | GitHub mobile web repository page, collapsed nav | web, limit 4 | 4 | **No.** All four were desktop-width GitHub captures. Logged as a gap |
| 25 | search_screens | Linear mobile issue list, bottom tab bar, dark | **ios**, limit 4 | 4 | Yes (fallback for task 10) |
| 26 | search_screens | Vercel mobile deployments list with status dots | **ios**, limit 4 | 4 | No Vercel results. GitHub iOS CI-run screen was useful |
| 27 | search_screens | PlanetScale overview with branches + query insights | web, limit 4 | 4 | Yes (dark mode, very relevant) |
| 28 | search_flows | Linear command menu + keyboard action | web, limit 2 | 2 flows (5 screens) | Partly; returned the shortcuts panel, not ⌘K |
| 29 | search_sections | Minimal dark footer with link columns + status indicator | limit 5 | 5 | Yes (Resend, Autosend, Midday) |
| 30 | search_sections | Mobile nav menu, full screen, developer site | limit 5 | 5 | **No.** No mobile-viewport menus returned |
| 31 | search_screens | Verification detail: signature hash, issuer, timestamps | web, limit 5 | 5 | Yes (Proton, Docusign) |
| 32 | search_sections | Benchmark comparison table, highlighted best result | limit 5 | 5 | Yes (Aside, Base) |

## References

Format for each entry: product, screen/flow, URL, research task, observed pattern, QMint application, and what we will **not** copy.

### R1. Vercel: Project Overview (Production Deployment card)
- **URL:** https://mobbin.com/screens/c7fc1aa9-5a08-4993-a979-66c3e729527c
- **Task:** 1
- **Pattern:**
  - Left sidebar is roughly 240px. It has 13px items with 16px line icons, and the active item gets a subtle filled row with no accent bar.
  - The global "Find…" input at the top shows an `F` keycap.
  - The main card pairs a screenshot thumbnail on the left with a stacked label/value grid on the right. Labels are 12px muted, values are 13–14px.
  - Status is a 6px green dot followed by "Ready" in plain text.
  - The commit hash is set in mono.
  - Below are three equal metric cards (Production Checklist / Observability / Analytics). Each has a 13px title plus a muted time window ("6h", "1w") and tiny sparklines.
- **QMint use:** `/app` overview.
  - Top card: "Latest mint run" with label/value grid (run id in mono, status dot + word, created, parameters hash).
  - Row of three equal panels below: recent attacks, verifier health, benchmark delta.
- **Not copying:**
  - The triangle logo and the black "Visit" split button.
  - The deployment screenshot thumbnail (we have no screenshots to show).
  - The blue-highlighted checklist rows.

### R2. Vercel: Overview, rollback state
- **URL:** https://mobbin.com/screens/d8e63884-5d43-4337-bf31-5667bc4ba5db
- **Task:** 8
- **Pattern:**
  - A full-width amber strip sits inside the card ("To undo the rollback…"), with an inline "Undo Rollback" secondary button aligned right.
  - The superseded deployment is shown with strikethrough text and a struck-out icon instead of being removed.
- **QMint use:** `/certificates`.
  - A revoked or superseded certificate keeps its row, struck through, with an inline notice strip and one corrective action.
- **Not copying:** the saturated yellow. Our warning is a muted amber text with a hairline amber border, not a filled band.

### R3. Linear: Issues list grouped by status
- **URL:** https://mobbin.com/screens/0ac97560-1aef-4907-a356-8c18c749437b
- **Task:** 1, 3
- **Pattern:**
  - Group headers ("In Progress 5", "Todo 7") are full-width bands one step lighter than the canvas, with a count and a `+` on the right.
  - Rows are about 36px tall, in this order: priority glyph, muted ID ("AS-11"), status icon, title in 13px medium, then labels and date right-aligned.
  - Sidebar sections ("Workspace", "Your teams") are 11px muted headers with collapsible carets.
- **QMint use:** `/app` runs list and `/lab/attack` attempts list.
  - Group by outcome (Accepted / Rejected / Pending).
  - Each row: mono run ID, then title, then right-aligned fidelity and timestamp.
- **Not copying:**
  - Linear's multicolour label chips. We will not have chips per row.
  - Linear's priority bar glyphs and circular status icons.

### R4. Linear: Project issues with Properties side panel
- **URL:** https://mobbin.com/screens/212fda35-366e-4dc0-a1d1-3b679659d6ab
- **Task:** 8
- **Pattern:**
  - Right column of about 280px holds a "Properties" key/value list (Status, Priority, Lead, Dates), then "Milestones", then a "Progress" mini chart.
  - Each section is collapsible with a caret and separated by a hairline.
  - "1 issue hidden by filters · Clear Filters" appears as inline muted text, not a banner.
- **QMint use:**
  - Detail pages (`/app/runs/[id]`, `/certificates/[id]`) with the main narrative on the left and a right metadata rail.
  - The "N hidden by filters" pattern for the benchmarks table.
- **Not copying:** the avatar-heavy lead/member rows and the brand-specific milestone diamond icons.

### R5. Linear: Display options popover
- **URL:** https://mobbin.com/screens/815793b1-5c75-43ac-94c7-93380781e337
- **Task:** 4
- **Pattern:**
  - Popover with a segmented List/Board toggle at the top.
  - Below that, label-left/control-right rows (Grouping ▾, Ordering ▾) and toggles.
  - Then a wrap of small toggle-chips for "Display properties".
  - Footer: "Reset" on the left, "Set default for everyone" on the right.
- **QMint use:** "View" popover for `/benchmarks` and `/app` tables (columns shown, grouping, ordering). Reset sits on the left.
- **Not copying:** the blue toggle colour. Ours uses the mint accent at low saturation, or plain white.

### R6. Supabase: Table Editor grid
- **URL:** https://mobbin.com/screens/86b8bccb-26bd-4502-b395-83c6dfc03c62
- **Task:** 1, 5
- **Pattern:**
  - 44px icon rail, then a secondary panel of about 200px, then the data grid.
  - Column headers show the name plus a muted type suffix (`id int8`, `created_at timestamptz`).
  - Cells are mono, rows about 28px, with full hairline grid lines.
  - Footer: "Page 1 of 1 · 100 rows · 21 records" on the left, a Data/Definition segmented control on the right.
- **QMint use:** `/benchmarks` raw-results view and `/lab/attack` measurement table.
  - Headers carry units/types (`fidelity  %`, `t_verify  ms`).
  - A mono numeric grid with a record count in the footer.
- **Not copying:**
  - The Supabase green "Connect" pill and the "PRODUCTION" orange badge.
  - The icon-rail plus secondary-panel double sidebar. One sidebar is enough for us.

### R7. Supabase: Add row side sheet
- **URL:** https://mobbin.com/screens/6e009d03-f48a-4093-bee4-2511b99cf707
- **Task:** 4
- **Pattern:**
  - Right sheet takes about 45% of the width.
  - Two-column form rows: the field name on the left with its type caption (`int4`) muted beneath it, and the input on the right.
  - Defaults are explained in small text ("Default: now()").
  - Sticky footer: "Cancel" then "Save ⌘↵", with the keycap inside the button.
- **QMint use:** `/lab/mint` advanced parameters sheet. Each parameter shows name, type/unit caption, input, and default note. The submit button carries a `⌘↵` hint.
- **Not copying:** Supabase's green primary button.

### R8. Linear: Marketing homepage hero
- **URL:** https://mobbin.com/screens/b7c17da1-eac4-4a8d-b7e9-2b8d6ef30f66
- **Task:** 2, 3
- **Pattern:**
  - Near-black page.
  - Nav: logo on the left; 12–13px links grouped right; a hairline vertical divider; then "Log in" text and a small white filled "Sign up".
  - Hero:
    - Left-aligned two-line headline at about 48–56px, tight tracking.
    - One muted subline.
    - On the right, aligned to the subline baseline, a quiet announcement link: dot, "Issue tracking is dead", URL, →.
  - A product UI frame with a hairline border and slightly lifted surface bleeds off the bottom of the fold. There is no glow.
- **QMint use:** `/` landing.
  - Left-aligned headline.
  - The quiet right-aligned "latest result" link (for example "• Attack benchmark v0.4 → /benchmarks").
  - A real `/lab/mint` UI frame below the fold line.
- **Not copying:**
  - Linear's exact headline phrasing style ("The X system for Y").
  - The diagonal gradient fade on the screenshot.
  - The specific product frame composition.

### R9. Linear: Numbered feature columns section
- **URL:** https://mobbin.com/sites/sections/11fa0cf7-8a9c-41f1-b38f-66918fac01f4
- **Task:** 2
- **Pattern:**
  - Four columns separated only by 1px vertical hairlines.
  - Each column has a tiny mono index label at the top ("1.0 Intake", "3.0 Build") and a 15–16px two-line statement anchored low.
  - "Learn more →" in muted 12px.
  - A large empty vertical space between label and statement.
- **QMint use:** `/` "How QMint works" strip: `01 Mint`, `02 Verify`, `03 Attack`, `04 Benchmark`, each linking to its route.
- **Not copying:** the "x.0" decimal numbering scheme. We use zero-padded `01–04` in Geist Mono.

### R10. Framer: Homepage hero
- **URL:** https://mobbin.com/screens/34f26fbd-c019-4744-8556-2b131e691ac0
- **Task:** 2
- **Pattern:**
  - Three short stacked sentence-lines as the headline.
  - Two compact buttons (white filled + dark grey filled) at about 28px height.
  - A changelog link ("Framer 3.0 Everything we shipped →") right-aligned on the same baseline as the buttons.
  - The app frame below has a dark surface and hairline border.
- **QMint use:** `/` CTA row: "Open the lab" (primary) and "Read the paper" (secondary), with a right-aligned "v0.x release notes →".
- **Not copying:** the three-sentence imperative headline cadence. It is now a cliché of AI-tool landing pages.

### R11. Stripe: Dashboard home ("Today")
- **URL:** https://mobbin.com/screens/9338307b-6a97-4399-869f-1e08827f4982
- **Task:** 5
- **Pattern:**
  - Section title "Today" at about 22px with a hairline rule under it.
  - KPI blocks: a label with dropdown caret ("Gross volume ▾"), a 16px value, a muted timestamp under the value, and a comparison column ("5 Dec 2024 ▾").
  - The chart sits on a faint vertical grid.
  - "Test mode" toggle in the top bar.
- **QMint use:**
  - `/app` KPI header: label ▾ (switch metric), value, as-of timestamp, comparison value.
  - "Simulation mode" toggle in the top bar so users always know whether a result is simulated.
- **Not copying:**
  - Stripe's diagonal gradient art and the purple/cyan decorative shapes.
  - The large "Get started with Stripe" promo panel.

### R12. Vapi: Command palette (dark)
- **URL:** https://mobbin.com/screens/593d7acd-2e16-4365-bcd6-02ce52f48f3b
- **Task:** 9
- **Pattern:**
  - Palette about 340px wide over a dimmed and blurred app.
  - 11px muted group labels: "Actions", "Recent", "All Pages".
  - Items show icon + name + a muted em-dash breadcrumb ("Metrics — Observe").
  - Right-aligned `⌘ O` keycap on actions.
  - Footer bar: "↑↓ to navigate · ↵ to select · ⌘O Switch Organizations" on the left, "14 results" on the right.
- **QMint use:** command palette (⌘K).
  - Groups: Actions (New mint run, Run attack, Verify certificate), Recent, Pages.
  - Breadcrumb suffix ("Fidelity sweep — Lab").
  - Key-hint footer and a result count.
- **Not copying:** Vapi's teal brand accents and its heavy background blur. We use a flat 60% black scrim instead.

### R13. Juicebox: Command palette with keyed footer
- **URL:** https://mobbin.com/screens/84169c57-5cd6-4495-bb71-93d37266f4c4
- **Task:** 9
- **Pattern:**
  - The active row has a 2px left accent bar plus a slightly lifted background.
  - Small-caps section headers ("ANALYTICS", "RESOURCES").
  - External items show a ↗ icon on the right.
  - Footer shows bordered keycaps: `↵` select, `↑↓` navigate, `Tab` jump sections, `⌘K` toggle.
- **QMint use:** command palette.
  - Active row uses a 2px mint left bar. This is one of the few places the accent appears.
  - ↗ marks external links (arXiv, GitHub).
  - `Tab` jumps between sections.
- **Not copying:** the serif small-caps section headers and the purple accent.

### R14. Vercel: Sidebar-anchored "Find…" menu
- **URL:** https://mobbin.com/screens/20b91aab-e548-47fd-88b9-b1cb2289e77d
- **Task:** 3, 9
- **Pattern:**
  - The sidebar search ("Find… F") opens a dropdown anchored to the sidebar rather than a centred modal.
  - Two-line results: name in 13px, type in 11px muted ("Project", "Navigation Assistant").
  - `Esc` keycap inside the input.
- **QMint use:** the `/docs` and `/research` sidebar filter opens an anchored result list. The global ⌘K stays centred.
- **Not copying:** the AI "Navigation Assistant" entry. QMint search is deterministic.

### R15. Vercel: Projects page empty panels
- **URL:** https://mobbin.com/screens/7be05ea5-e875-439d-bd1f-7aef97281d3b
- **Task:** 9
- **Pattern:**
  - Empty states inside panels: a 16px line icon, then one or two lines of 13px muted centred text ("Preview deployments that you have recently visited or created will appear here.").
  - No illustration and no CTA when nothing can be done.
  - The "Alerts" empty state has a single secondary button ("Upgrade to Pro").
- **QMint use:** all in-panel empty states.
  - Example: "No attack runs yet. Runs you start in the lab appear here."
  - Add a button only when a direct action exists.
- **Not copying:** the upsell framing. QMint has no paid tiers.

### R16. Braintrust: Playground model-parameters popover
- **URL:** https://mobbin.com/screens/3573d85b-70f0-4cce-bf0e-9bb2f1107654
- **Task:** 4
- **Pattern:**
  - Each parameter row: label on the left, current numeric value right-aligned ("0,7"), a small × reset button, and a full-width thin slider beneath.
  - Boolean params use a checkbox right-aligned.
  - Enum params use a compact select ("None ▾").
  - "Base task" header with an `● ` status dot.
  - Results grid below shows "This cell has not been run yet" as a muted placeholder.
- **QMint use:** `/lab/mint` parameter panel (qubits n, noise p, shots, seed).
  - Label on the left, mono value on the right, a per-param reset, then a 2px-track slider.
  - Unrun result cells say "Not run yet".
- **Not copying:** Braintrust's purple accents and the `{{input}}` template-variable chips.

### R17. Snowflake: Cortex Playground settings panel
- **URL:** https://mobbin.com/screens/8476874a-187a-48d0-99e2-90a4a56425d1
- **Task:** 4
- **Pattern:**
  - Right "Settings" panel of about 240px.
  - Each parameter is gated by a checkbox ("Set temperature"). When it is unchecked, the slider and number box are disabled grey.
  - A numeric input box sits left of the slider, with min/max endpoint labels ("0", "1") above the slider ends.
  - "View Code" pill buttons in the conversation reveal the equivalent API call.
- **QMint use:** `/lab/attack`.
  - Optional attack parameters are opt-in via checkbox and default to protocol values.
  - Number input + slider with min/max endpoint labels.
  - A "View code" toggle shows the equivalent Python/CLI invocation, which is key for reproducibility.
- **Not copying:** Snowflake's blue fill slider and brand iconography.

### R18. FLORA: Canvas with floating settings card
- **URL:** https://mobbin.com/screens/0b60e595-277a-4f03-965f-c62a5f798b4b
- **Task:** 4
- **Pattern:**
  - True-black canvas with a faint dot grid.
  - Floating top-right settings card with 11px uppercase letter-spaced labels (MODEL, QUALITY, SIZE, SEED) on the left and values on the right.
  - The SEED field shows a muted mono number.
  - A tiny "Tasks 0 active" status widget sits bottom-right.
- **QMint use:**
  - `/lab/mint` and `/lab/attack` visualisation area: a dot-grid background behind the qubit/state diagram.
  - Uppercase mono micro-labels for parameter names.
  - A persistent "Jobs · 0 running" corner indicator.
- **Not copying:**
  - FLORA's left floating pill toolbar and the circular "+" node affordances.
  - The image-generation framing.

### R19. Vercel: Project Settings (setting cards with footer strip)
- **URL:** https://mobbin.com/screens/a54fee2e-b776-42c2-bd7c-93f7e223c87c
- **Task:** 4
- **Pattern:**
  - Each setting is a bordered card: 16px semibold title, 13px muted one-sentence description, then the control.
  - A footer strip sits on a slightly different surface, separated by a hairline: "Learn more about Project ID ↗" on the left, a Save button on the right (disabled until dirty).
  - The read-only project ID is shown in mono with a copy icon.
  - The danger card (https://mobbin.com/screens/0654916b-7bfa-44f7-9854-bd8fc7bb1865) uses a red-tinted footer.
- **QMint use:**
  - `/app/settings` and `/lab/*` protocol configuration groups. Each group card has a "Learn more in /docs ↗" footer link and a local Save.
  - Mono IDs with a copy button.
- **Not copying:** the red-tinted danger fill. Ours is a hairline red border plus red text only.

### R20. Vercel: Web Analytics (dark)
- **URL:** https://mobbin.com/screens/900542f7-c157-4445-8f88-d79dca719c7a
- **Task:** 5
- **Pattern:**
  - KPI tabs (Visitors 13 / Page Views 24 / Bounce Rate 69%) double as the chart selector. The active tab has a 2px underline and the others are dimmed.
  - The chart has only three horizontal gridlines, no vertical grid, and a dashed segment for the incomplete current period.
  - The filled area is very low alpha.
  - Breakdown panels below: label on the left, count right-aligned, with a proportional bar drawn as a *row background fill*.
  - Uppercase muted "VISITORS" column header.
- **QMint use:** `/benchmarks`.
  - Metric tabs (Fidelity / Forgery success / Verify latency) select the chart.
  - Dashed line for in-progress runs.
  - Breakdown tables (by attack family) with background-fill bars instead of separate bar charts.
- **Not copying:** Vercel's blue series colour and its delta badge with red fill. Deltas are text-only (`+6.9%`) in muted or accent colour.

### R21. Vercel: Firewall Traffic top-N panels
- **URL:** https://mobbin.com/screens/1c61fe0f-bc04-4bd3-87b4-70f05357ad5a
- **Task:** 5
- **Pattern:**
  - A grid of "Top X" panels.
  - Values are mono (IPs, JA4 hashes, paths), truncated with an ellipsis.
  - Count right-aligned, followed by a tiny inline sparkline about 24px wide, then a `…` menu.
- **QMint use:**
  - `/lab/attack` "Top failing challenge bases" and "Top serials attempted": mono truncated hashes, count, inline micro-sparkline.
  - `/certificates` list: truncated hash with a copy affordance.
- **Not copying:** country flags and the three-column card mosaic. We use at most two columns.

### R22. PlanetScale: Database dashboard (dark)
- **URL:** https://mobbin.com/screens/3d61a34a-a436-4de5-a159-16ee70235a4c
- **Task:** 1, 5
- **Pattern:**
  - Topology diagram on a dot grid: VTGate → Primary → two Replicas as small cards with mono metrics ("PS-10 CPU: 2% Mem: 18%"), joined by dashed connectors.
  - Right rail: a 2×3 stats grid (label + large number), a storage list, and a "Recent activity" vertical timeline.
  - The latency chart legend uses mono chips ("● p50: 0.0 ms").
  - "ESTIMATED COSTS: $71.96" sits as uppercase mono in the top bar.
- **QMint use:**
  - `/app` and `/lab/mint` protocol diagram (Bank → Mint → Wallet → Verifier) drawn as small hairline node cards with dashed connectors on a dot grid. Each node shows mono stats.
  - Mono legend chips for chart series.
- **Not copying:** PlanetScale's logo, colourful avatar squares, and the exact node card styling (icon + coloured header).

### R23. PlanetScale: Query Insights
- **URL:** https://mobbin.com/screens/702e8da0-e1fd-4c42-90b5-699707785794
- **Task:** 5
- **Pattern:**
  - Metric tabs, each with a title plus a muted sub-value ("2 – 3ms p95").
  - Under that, a mini overview strip (brush) with day labels and a selected "Last 24 hours" window.
  - The main chart has vertical dotted event markers with numbered flags.
  - Footer: "Show events" toggle, refresh-interval select, Save and Copy.
  - Related screen with a query table and per-cell sparklines: https://mobbin.com/screens/9caa36e4-3e09-4565-aa6e-f59baea3f94e. The sorted column header is shaded.
- **QMint use:** `/benchmarks` time-series view.
  - A brush strip for selecting the run range.
  - Event markers for protocol version changes.
  - A "Copy data" action.
  - The sorted column in the results table is shaded.
- **Not copying:** the multi-hue cyan/green series palette. QMint charts are greyscale with one mint highlight series.

### R24. Supabase: Observability · Storage report
- **URL:** https://mobbin.com/screens/b6b4cc08-b64d-4543-a2d8-2501a2499237
- **Task:** 5, 8
- **Pattern:**
  - Each report card: a title, one big number ("762.81 ms"), a compact bar chart with start/end date labels only, and then a request table *inside the same card*.
  - Table rows are expandable (chevron), with a mono method/status ("POST 200 /storage/v1/…").
  - "Show more" in the card footer.
  - The time range control ("Last 24 hours", "Jun 1 → Jun 2") sits above all cards.
- **QMint use:** `/benchmarks` cards that pair a headline number, a small chart and an expandable list of the underlying runs (mono run id, outcome, ms).
- **Not copying:** the Supabase green bars and the left "Custom reports" sidebar section.

### R25. Mintlify: Docs page with "On this page"
- **URL:** https://mobbin.com/screens/731c0653-266e-4c03-aae6-df4d07631ebd
- **Task:** 6
- **Pattern:**
  - Three columns: left nav about 200px with group header "Getting Started"; a content column about 560px (~65ch); a right "On this page" TOC about 160px with nested indent and the active item in accent.
  - The title row has a "Copy page ▾" button on the right.
  - Callouts are a hairline box with an info icon, no fill.
  - Code blocks have a copy icon top-right.
- **QMint use:** `/docs` and `/research`.
  - Same three-column skeleton, prose at 65ch.
  - "Copy as Markdown" on each page.
  - Accent only on the active TOC item.
- **Not copying:** Mintlify's green branding, rounded pill nav highlight, and the generic "Card" component grid.

### R26. Devin (DeepWiki): Project Overview wiki
- **URL:** https://mobbin.com/screens/c3936cdb-13b2-4b54-b2a2-c7ccf723dd1b
- **Task:** 6
- **Pattern:**
  - A collapsible "Relevant source files ›" box at the top of each article lists file links in mono.
  - The left nav is a deep tree (section → page → sub-page) with tight 28px rows.
  - The right TOC is rendered as a "minimap" of short horizontal ticks rather than text.
  - "Last updated 3 days ago" and a branch selector sit in the top bar.
- **QMint use:** `/research` articles.
  - A collapsible "Sources" block at the top citing paper sections and repo files (for example `qmint/verify.py#L10-40`).
  - "Last updated" and version in the header.
- **Not copying:** the tick-minimap TOC (too clever for a research audience) and the floating "Ask Devin" input.

### R27. GitBook: API schema objects
- **URL:** https://mobbin.com/screens/a5dfcc72-e178-439b-9364-1f90162f8093
- **Task:** 6
- **Pattern:**
  - Schema objects are hairline-bordered rows with a mono name and "Show properties +" on the right; they expand inline.
  - Expanded rows show the type line in mono ("string · enum") plus "optional" in a warm colour.
  - Possible values appear as small mono tokens.
  - Response code "200" is green text followed by the description.
- **QMint use:** `/docs` API reference for the verifier/mint endpoints and data types (`Banknote`, `Certificate`, `AttackResult`).
- **Not copying:** GitBook's pink upgrade CTA and its emoji page icons.

### R28. Vercel: New Project / "Setting up a deployment" flow
- **URL:** https://mobbin.com/flows/edfece19-b9e5-482a-b867-ec0e47ff61ad
- **Task:** 7
- **Pattern:**
  - Single narrow column (~350px) "New Project" card.
  - A muted source box shows where the project imports from (repo + branch in mono).
  - Inputs follow, then collapsed accordions ("Build and Output Settings", "Environment Variables") that expand inline with mono placeholder commands.
  - A full-width primary "Deploy" button.
  - **Directly below** sits a dimmed "Deployment" card: "Once you're ready, start deploying to see the progress here…". The next stage is visible but inert.
- **QMint use:** `/lab/mint` as a staged workflow.
  - "Configure" card on top: protocol preset, n, noise, plus an advanced accordion.
  - Then a greyed "Run" card that comes alive on submit, then a "Verify" card.
  - Showing every stage up front makes the sequence learnable.
- **Not copying:**
  - The decorative arc illustration in the empty Deployment card.
  - The pastel gradient on the "Congratulations!" screen.

### R29. Cloudflare: "Setting up an application" flow
- **URL:** https://mobbin.com/flows/af56be7b-d807-4408-a749-e5e8f9573a6a
- **Task:** 7
- **Pattern:**
  - A horizontal numbered stepper at the top of the card: "① Select repository — ② Set up builds and deployments — ③ Deploy site". The current step is a filled circle; future steps are outlined circles joined by a hairline.
  - The footer has "← Change repository" as a text link on the left and the primary action on the right.
- **QMint use:** `/lab/attack` guided mode: ① Choose target note, ② Choose attack family, ③ Run and inspect. Back is a text link, not a button.
- **Not copying:** the Cloudflare orange/blue palette and its dense left nav with "Beta" badges.

### R30. Laravel Cloud: Deployment details
- **URL:** https://mobbin.com/screens/dd29535f-34aa-4279-82fc-76e11059f596
- **Task:** 7, 8
- **Pattern:**
  - Title "Deployment details · 2d300ac".
  - Metadata row: ✓ "Deployed" · hash · commit message · "Just now · 41s".
  - Grouped steps ("Build logs 21s", "Deployment logs 18s"). Each sub-step row shows the name on the left, a mono status word ("Finished", "Skipped") right-aligned, a duration ("20s") right-aligned, and a chevron to expand.
- **QMint use:** `/lab/mint` and `/lab/attack` run detail.
  - Groups "Preparation", "Quantum simulation", "Verification".
  - Each step shows a mono status word and duration.
  - This is the primary model for our step-status rows.
- **Not copying:** Laravel's red brand accents and the blue filled "Redeploy" button.

### R31. Emergent: Deployment in progress checklist
- **URL:** https://mobbin.com/screens/dff53201-0975-445f-b0e1-75aa0353d9ba
- **Task:** 7, 9
- **Pattern:**
  - Vertical step list in mono: ✓ done, a spinner plus a highlighted row with a live elapsed timer ("04:29") for the current step, and hollow circles for pending steps.
  - Above it, a reassuring line: "It takes around 5–7 mins. We'll notify you once done."
- **QMint use:** the `/lab/*` loading state for long simulations.
  - Mono step names, a live mm:ss timer on the current step, and an expected-duration line.
- **Not copying:** the light-blue filled current row. Ours is a hairline outline plus mint text.

### R32. Railway: Failed deployment, expanded diagnosis
- **URL:** https://mobbin.com/screens/411620e7-9ff6-4062-934b-9d0d31784174
- **Task:** 8
- **Pattern:**
  - Deployment history entries carry a "FAILED"/"COMPLETED" uppercase tag.
  - Expanding one shows a step tree with right-aligned mono durations "(00:06)". The failing step is red with the error message in red mono beneath.
  - A "Diagnosis" block follows with an explanation and action buttons.
  - A "Hide Skipped" toggle sits on the history header.
- **QMint use:** `/lab/attack` result detail.
  - A rejected forgery shows the exact failed verification step, the mono reason (for example `basis mismatch at qubit 17`), and a plain-language explanation.
  - "Hide passed steps" toggle.
- **Not copying:**
  - Railway's purple "Fix start command" AI action.
  - The pink-tinted full-row error backgrounds. We tint only the line, at about 8% alpha.

### R33. Vercel: Deployment Details (failed build)
- **URL:** https://mobbin.com/screens/ff81f1e9-25b1-46f9-8448-31fa40a77e4b
- **Task:** 8
- **Pattern:**
  - Top card: a "Build Failed" box with a 1px red border and the message on the left. On the right, a 4-column label/value grid: Created, Status ("● Error Latest"), Duration ("4s Just now"), Environment.
  - A "Build Logs" accordion below with a header showing line count ("16 lines"), error/warning counters (⊗ 1, ⚠ 1), a "Find in logs ⌘F" input, and duration with a status icon.
  - Log lines have a muted mono timestamp column. The warning line has an amber tint; error lines have a red tint.
  - Further collapsed accordions follow: Deployment Summary, Deployment Checks.
- **QMint use:** `/app/runs/[id]` and `/certificates/[id]`.
  - Summary card with an outcome box and a 4-column metadata grid.
  - A "Trace" accordion: line count, error/warn counters, find-in-trace, timestamped mono lines.
  - Then collapsed "Parameters", "Raw measurements", "Reproduce" sections.
- **Not copying:** Vercel's red "!" circle icon and the exact four-panel product-tile footer ("Runtime Logs / Observability / Speed Insights / Web Analytics").

### R34. Stripe: Workbench Events + detail pane
- **URL:** https://mobbin.com/screens/5423e185-8374-4b6c-a4a0-2d3ae9adc1d0
- **Task:** 8
- **Pattern:**
  - Left list grouped by day ("Today", "Yesterday"). Each row shows the event type in mono (`account.application.deauthorized`), a one-line description, and a right-aligned time.
  - "Updated today 09:32:55 · Refresh" at the top.
  - Right pane: an "Event details" key/value list (Event ID, Origin date, Source, API version); a dashed-border empty box ("No recent delivery attempts"); then a collapsible JSON viewer.
- **QMint use:** `/certificates` (and an audit log).
  - Mono event types (`note.minted`, `note.verified`, `attack.rejected`), split-pane detail with key/values and raw JSON.
  - "Updated hh:mm:ss · Refresh" freshness line.
- **Not copying:** Stripe's purple selection border and blurple links.

### R35. Better Stack: Incident timeline (dark)
- **URL:** https://mobbin.com/screens/4c651809-caad-4824-af3f-248d63e18c2a
- **Task:** 8
- **Pattern:**
  - Metadata table with a hairline grid (Affected Team, Owner, Region, Severity) and "+ Add" at the end.
  - Timeline: a 1px vertical line with small 16px event glyphs. Each event sentence inlines mono values ("added metadata `Region: EU and APAC`"), and the timestamp is right-aligned and muted.
- **QMint use:** the `/certificates/[id]` lifecycle timeline (issued → verified ×N → revoked), with mono inline values and right-aligned UTC timestamps.
- **Not copying:** Better Stack's navy-tinted dark palette. QMint uses neutral near-black, not blue-black.

### R36. Proton Drive: File details, "Digital signature verified"
- **URL:** https://mobbin.com/screens/d4a49f57-8d85-4b5c-ac63-05403b3c526a
- **Task:** 8
- **Pattern:**
  - Modal opening with a verification callout: a 2px left accent bar plus "Digital signature verified. This file was securely uploaded by …".
  - Then a plain two-column key/value list (Name, Uploaded by, Location, Modified, Type, MIME type, Size) with muted labels and bold values.
  - A single "Close" button.
- **QMint use:** `/certificates/[id]` verdict block.
  - "Verified: serial matches, k/n qubit tests passed" with a mint 2px left bar.
  - Then key/values (Serial, Issuer, Issued, Protocol, Parameters hash).
- **Not copying:** Proton's purple surround and the modal context. Ours is an inline page section.

### R37. Docusign: Envelope History / certificate
- **URL:** https://mobbin.com/screens/3b9577ec-b873-41e6-8a9b-82588f79da3b
- **Task:** 8
- **Pattern:**
  - Two-column metadata block (Subject, Envelope ID, Date Sent, Status, Holder…).
  - Then an "Activities" table (Time / User / Action / Activity / Status) with the IP shown under each user.
  - Footer: "Print" and "Download Certificate".
- **QMint use:** `/certificates/[id]` "Export" footer (Download JSON / Print / Copy verify command) and an activity table below the timeline.
- **Not copying:** Docusign's purple button and dense un-gridded metadata typography.

### R38. Aside: Benchmark bar comparison
- **URL:** https://mobbin.com/sites/sections/4f0a6897-50b7-4b01-a168-b355fb8421e3
- **Task:** 5
- **Pattern:**
  - Horizontal bars: system name on the left, bar in the middle, percent right-aligned.
  - **Only the featured row is coloured**; the others are light grey. Hairline row dividers.
  - Below it, a segmented control switches benchmark (Online-Mind2Web / BU Bench v1 / Odyssey).
- **QMint use:** `/benchmarks` and the `/` landing proof strip.
  - Bar list of schemes (QMint-Wiesner, baselines) with only the current protocol in mint.
  - A segmented control switches attack family.
- **Not copying:** the "SOTA / #1 ranked" marketing claim framing. Research results are stated neutrally, with CIs.

### R39. Base: Comparison table with highlighted column
- **URL:** https://mobbin.com/sites/sections/4b88c2aa-ffbd-44bf-b458-d2be6b40ba76
- **Task:** 5
- **Pattern:**
  - The featured column has a subtle background tint and accent-coloured values; the other columns are neutral.
  - Mono column headers with small glyphs.
  - Row labels are left-aligned in medium weight; values are centred.
- **QMint use:** `/benchmarks` protocol comparison (forgery bound, qubits/note, verify cost) with QMint's column tinted at about 4% mint.
- **Not copying:** Base's blue square brand mark and the crypto-chain comparison context. QMint must not read as a crypto product.

### R40. Neon: Skeleton table
- **URL:** https://mobbin.com/screens/9b5b1374-c015-495b-abcb-9cce659c741b
- **Task:** 9
- **Pattern:**
  - The real page title ("Computes") renders immediately. Only the data rows are skeleton bars, sized to their columns, with hairline row dividers kept.
  - The top bar shows "● All OK" as a status dot plus text.
- **QMint use:** loading states everywhere.
  - Titles and headers render immediately; only cells are skeletons.
  - Global top-bar system status "● Simulator ready".
- **Not copying:** Neon's green logo and lime avatar.

### R41. Unify: Loading table with progress toast
- **URL:** https://mobbin.com/screens/be3c7516-09ef-469f-a861-f08395a61f38
- **Task:** 9
- **Pattern:**
  - Real column headers stay visible while row cells are skeletons.
  - A small bottom-right toast reads "Assembling your list. 0 Companies added" with a spinner and a Cancel button.
- **QMint use:** batch benchmark runs. Headers stay visible, and a corner toast shows "Running sweep · 12/200 configs" with Cancel.
- **Not copying:** the warm beige tint.

### R42. v0: Panel empty state
- **URL:** https://mobbin.com/screens/6e23d772-5780-4383-8aa9-50bf26b2c952
- **Task:** 9
- **Pattern:**
  - Centred stack:
    - a 20px icon inside a 28px hairline square
    - a 14px semibold title ("No Database Connected")
    - a two-line muted description
    - one small filled button
  - No illustration.
- **QMint use:** route-level empty states (`/certificates` with none issued: "No certificates yet" → "Mint a note").
- **Not copying:** v0/Vercel branding. The pattern itself is generic.

### R43. Linear Mobile (iOS fallback): My issues, dark
- **URL:** https://mobbin.com/screens/2b4047d8-3247-40db-8e3e-9e0d6b982f91
- **Task:** 10
- **Pattern:**
  - Large 22px title with action icons in a pill on the right.
  - Segmented pill tabs (Assigned / Created / Subscribed).
  - Group headers ("In Progress") in muted 13px with `+`.
  - Single-line rows about 44px, truncated with an ellipsis, status icon leading.
  - Floating bottom bar with four icons plus a separate circular search button.
- **QMint use:** mobile `/app`.
  - Single-line run rows (status dot, mono id, truncated title).
  - Group headers.
  - Search reachable from the bottom-right thumb zone.
- **Not copying:**
  - The floating rounded pill tab bar. We will use a plain top bar with a menu sheet; a bottom bar is overkill for a research site.
  - Linear's priority glyphs.

### R44. GitHub (iOS fallback): CI job steps
- **URL:** https://mobbin.com/screens/e3adcd59-f277-46d1-a6a4-ec0019be8c72
- **Task:** 10, 7
- **Pattern:**
  - Header "CI / build-and-test" with subtitle "Failed after 20s".
  - Full-width rows: status icon (✓ / ✕ / ⊘ skipped), mono step name, duration on a second line in muted text, chevron on the right.
  - A floating "Re-run ▾" button.
- **QMint use:** mobile `/lab/*` run detail. The step rows from R30 collapse into two-line rows (name / duration·status).
- **Not copying:** GitHub's green/red filled circle icons. We use a 6px dot plus a status word.

### R45. Resend: Footer with system status
- **URL:** https://mobbin.com/sites/sections/9301c687-40d0-4d8d-bbb8-b1325bac2679
- **Task:** 2
- **Pattern:**
  - Pure black footer.
  - Address and social icons on the left, then a status pill: green dot + "All systems operational".
  - Five link columns with 13px white headers and muted 13px links at about 20px row gap.
- **QMint use:** `/` footer columns: Research / Lab / Docs / Project (GitHub, License, Citation). Plain-text status "● Verifier online · v0.x".
- **Not copying:** the top black-to-grey gradient fade and the address block.

### R46. Autosend: Footer with mono column headers
- **URL:** https://mobbin.com/sites/sections/f413db09-0a6f-44df-ae35-125468d270dc
- **Task:** 2
- **Pattern:**
  - Column headers in 11px uppercase mono with wide tracking (SOLUTIONS, DOCS, RESOURCES).
  - Links in 13px sans.
  - "© 2026 · Peerlist Inc." in mono under the logo.
- **QMint use:** footer and sidebar section headers in Geist Mono uppercase 11px. This confirms the mono-label convention.
- **Not copying:** the "Compare: SendGrid / Loops / Resend" competitor links.

### R47. Better Stack: Uptime availability table
- **URL:** https://mobbin.com/screens/a6fefc36-f40b-4a53-9bd9-f1199becd668
- **Task:** 5
- **Pattern:**
  - Table: Time period / Availability / Downtime / Incidents / Longest / Avg.
  - Numeric columns right-aligned, with high-precision values ("100.0000%"). "none" in muted text instead of 0.
  - A From/To date range plus "Calculate" in the table footer.
- **QMint use:** `/benchmarks` summary table.
  - Right-aligned, fixed-precision numbers (`2.31e-5`, `99.982%`).
  - Muted "—" for not-applicable.
  - A custom range footer.
- **Not copying:** the dense multi-colour stacked line chart above it.

### Anti-pattern references (logged, deliberately avoided)

- **Better Stack hero** (https://mobbin.com/screens/dbd41312-1fe5-4908-91e2-9f767004ebca): glowing light beams, purple CTA.
- **Shopify Editions developer section** (https://mobbin.com/sites/sections/1a1c2145-71da-40a3-9e78-56b515a907e8): neon glow frame around the screenshot.
- **ToDesktop hero** (https://mobbin.com/sites/sections/03ac58c4-657f-4005-a4c7-2486d0641a5d): gradient glow plus badge above the headline.
- **Stripe homepage hero** (https://mobbin.com/screens/d4ed06ce-1cde-43ca-89a4-49551cced134): signature mesh gradient.

These are exactly the "glow gradient / neon" tropes the brief excludes.

## Synthesis: design decisions

1. **App shell.**
   - One left sidebar, 240px, collapsible to a 48px icon rail.
   - Sidebar items: 13px with 16px line icons, 32px rows. The active item gets a filled `--surface-2` row with no accent bar.
   - Section headers in Geist Mono 11px uppercase muted (R1, R3, R46).
   - No double sidebar (rejecting R6's rail + panel).
2. **Header.**
   - 48px app top bar: breadcrumb on the left, a centred page title or nothing, then system status and ⌘K hint on the right.
   - 56px marketing nav: logo on the left; links, a hairline vertical divider and one small white primary button on the right (R1, R8).
3. **Status = dot + word, never a pill.**
   - A 6px dot plus a 13px status word ("● Verified", "● Rejected", "○ Pending").
   - Durations and counts sit right-aligned in mono.
   - Filled tags are reserved for at most one uppercase outcome tag per detail page (R1, R30, R40, R44).
4. **Tables.**
   - 32px rows (36px for lists with titles), hairline row dividers, no zebra striping.
   - Units shown in headers (`t_verify ms`); numbers in Geist Mono, right-aligned, fixed precision; muted "—" for N/A.
   - Sorted column gets a faint header shade. Footer shows record count and range (R6, R23, R47).
5. **Detail pages** follow the R33/R4 model:
   - Summary card: outcome box on the left plus a 4-column label/value grid.
   - Then collapsible sections (Trace, Parameters, Raw measurements, Reproduce).
   - Right metadata rail of 280px on ≥1280px screens.
   - A "Reproduce" section with a copyable CLI command is mandatory (R17 "View code").
6. **Step and progress rows.**
   - Grouped steps, each showing a mono status word and duration right-aligned, with a chevron to expand (R30).
   - The live step shows an mm:ss timer and hairline outline (R31).
   - Failures expand inline with a red mono reason and a plain-language explanation (R32).
   - The same component collapses to two-line rows on mobile (R44).
7. **Staged lab workflow.**
   - `/lab/mint` and `/lab/attack` show every stage up front as stacked cards (Configure → Run → Verify). Future stages are dimmed and inert until reached (R28).
   - Guided mode adds a numbered hairline stepper (R29).
8. **Parameter controls.**
   - Each row: label on the left, mono value on the right, and a per-param reset ×. A 2px-track slider sits below, with min/max endpoint labels.
   - Optional parameters are opt-in via checkbox (R16, R17).
   - Advanced params live in an accordion or right sheet with type/unit captions (R7).
9. **Charts.**
   - Greyscale series with exactly one mint highlight series. Three horizontal gridlines max and no vertical grid.
   - Dashed segment for incomplete or in-progress data. Area fill at 8% alpha or less.
   - Mono legend chips ("● p95 3.2 ms").
   - KPI tabs double as the chart selector (R20, R22, R23).
   - Comparisons use horizontal bar lists where only the featured row is coloured (R38), or a 4% mint column tint (R39).
10. **Empty states.**
    - In-panel: a 16px icon and one or two lines of muted text, with no button unless a direct action exists (R15).
    - Route-level: an icon in a 28px hairline square, a 14px title, a two-line description, and one small button (R42).
    - Never use illustrations.
    - Tone is factual ("No attack runs yet. Runs you start in the lab appear here.").
11. **Loading.**
    - Titles, headers and column labels render immediately; only cells are skeletons, with dividers kept (R40, R41).
    - Long jobs show a corner toast with progress and Cancel, plus an expected-duration line (R31, R41).
12. **Command palette.**
    - 560px centred, flat 60% black scrim (no blur).
    - Groups: Actions / Recent / Pages, with 11px mono group labels and em-dash breadcrumb suffixes.
    - Active row gets a 2px mint left bar.
    - Footer with key hints (`↑↓ ↵ Tab Esc`) and a result count (R12, R13).
    - Sidebar search opens an anchored dropdown (R14).
13. **Docs and research layout.**
    - Three columns: 220px nav, 65ch prose, 180px "On this page" TOC with accent on the active item only.
    - A collapsible "Sources" block at the top of research articles. "Copy as Markdown" on each page (R25, R26).
    - Schema objects use inline "Show properties +" rows (R27).
14. **Verification and certificate presentation.**
    - Verdict callout with a 2px mint left bar and one plain sentence, followed by key/values (R36).
    - Lifecycle timeline on a 1px vertical line with right-aligned UTC timestamps (R35).
    - Export footer: Download JSON / Print / Copy verify command (R37).
    - Mono hashes truncated in the middle with copy (R21).
15. **Mobile.**
    - ≤768px: sidebar becomes a top bar (48px) plus a full-height menu sheet listing the same sections. No floating bottom tab bar.
    - Tables collapse to single-line rows (status dot · mono id · truncated title · right value) with group headers (R43).
    - Detail metadata grids reflow to 2 columns, then 1.
    - 16px side gutters.
    - Gap: Mobbin returned no usable mobile-web screens (queries 24, 30), so this is based on the iOS references R43/R44.

## Originality guardrails

| Reference brand | Distinctive elements we will **not** copy |
|---|---|
| Vercel | Triangle mark; black split "Visit" button; deployment screenshot thumbnails; four-tile product footer; blue chart series; the "Production Checklist" strikethrough pattern; Geist is used as a typeface only, not with Vercel's layout signatures verbatim |
| Linear | "The X system for Y" headline formula; diagonal gradient on product frame; priority-bar and circular status glyphs; multicolour label chips; "x.0" section numbering; floating pill mobile tab bar |
| Stripe | Mesh/diagonal gradient art; blurple accents; decorative angled shapes; large promo onboarding panel |
| Supabase | Green brand buttons and bars; double sidebar (icon rail + panel); "PRODUCTION" orange badge |
| PlanetScale | Logo; coloured avatar squares; node cards with coloured icon headers; cyan/green series palette |
| Resend | Black-to-grey gradient footer fade; its app's API-key onboarding step-card styling |
| Raycast | Not found on Mobbin web (query 9). Nothing referenced, so nothing to avoid beyond its well-known glossy gradient icons |
| Mintlify / GitBook / Devin | Green branding; emoji page icons; tick-minimap TOC; floating "Ask AI" input |
| Railway / Laravel Cloud / Emergent | Purple AI-fix CTAs; filled red/pink error rows; filled light-blue current-step row |
| Better Stack / Shopify / ToDesktop | Glow beams, neon frames, navy-tinted dark palette, "badge above headline" hero |
| Aside / Base / Wise | "SOTA / #1 / Cheapest" claim framing; crypto-chain comparison context; brand logos in table rows |
| General | No glassmorphism, no glow, no card mosaics larger than 2 columns on content pages, no pills for status, accent `#B6F3D1` limited to: active TOC item, palette active bar, one chart series, verification bar, primary-focus ring |
