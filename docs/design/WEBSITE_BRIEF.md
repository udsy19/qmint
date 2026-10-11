# QMint — Build a World-Class Quantum Security Website

> Human-authored brief (2026-10-11), assigned to lane K. Verbatim. Lead notes at the bottom.

You are an elite product designer, creative director, frontend architect, and senior full-stack engineer.

Your task is to **design and implement the complete QMint website and interactive research platform**, taking inspiration from the design quality of Vercel, Linear, Raycast, Stripe, and other exceptional developer-first products.

**You MUST use the Mobbin MCP extensively for design research before writing the interface.**

This is not a request for a landing-page mockup, wireframe, or design proposal. Build a fully functional, responsive, visually exceptional web application integrated with the existing QMint project.

The standard I expect is that the website could plausibly be featured on Awwwards, while maintaining the usability, precision, and restraint of Vercel or Linear.

## 1. Understand the Product First

QMint is an open-source quantum money and payment security research platform.

It allows researchers, engineers, and curious users to explore:

- Quantum money and quantum token generation.
- Quantum no-cloning and counterfeiting resistance.
- Double-spending attacks.
- Wiesner quantum money and S-money protocols.
- Quantum versus classical payment security.
- Quantum verification experiments.
- Security proofs, certificate generation, and resource optimization.
- Experimental evidence and published research.

Read the project's existing master research plan, architecture, source code, APIs, and documentation before designing anything.

The website has two distinct purposes:

**A. Public-facing website:** Communicate QMint's vision, scientific foundations, research contributions, and capabilities through an incredibly well-designed experience.

**B. Interactive research platform:** Let users configure quantum payment experiments, run simulations, inspect attacks, visualize evidence, and explore mathematical security guarantees.

These must feel like parts of the same thoughtfully designed product.

Do not claim QMint provides commercial banking services or deployable physical quantum currency. Make the distinction between research demonstrations and proven deployment capabilities clear.

## 2. Mandatory Design Research Using Mobbin MCP

Before implementing UI, check whether Mobbin MCP is installed and authenticated in Claude Code.

If not installed, use the official integration:

```bash
claude mcp add mobbin --scope user --transport http https://api.mobbin.com/mcp
```

Then authenticate using the Claude Code MCP interface.

If authentication is required, ask the human to complete it. Do not claim Mobbin research was performed if the integration was unavailable.

Once connected, actively use the Mobbin MCP tools:

- `search_screens`
- `search_flows`
- `search_sections`

### Reference products

Study these products and identify specific patterns worth adapting.

**Vercel — https://vercel.com**

Study typography, negative space, editorial sections, monochrome hierarchy, developer dashboards, code previews, product showcases, and elegant page composition.

**Linear — https://linear.app**

Study its dark-mode design, compact navigation, subtle borders, muted colors, information density, tables, settings, sidebars, keyboard-first interactions, and micro-animations.

**Raycast — https://raycast.com**

Study the clarity of developer tooling, command palettes, polished empty states, onboarding, and refined interaction details.

**Stripe — https://stripe.com**

Study complex financial interfaces, API documentation, data-rich dashboards, and how complicated technical concepts are explained through accessible visualizations.

Also look for relevant references from Resend, GitHub, Supabase, PlanetScale, and scientific or analytics platforms where useful.

### Specific Mobbin research tasks

Search for excellent examples of:

1. Dark SaaS dashboards and developer platforms.
2. Premium technology landing pages.
3. Minimal navigation bars and application sidebars.
4. Interactive configuration tools.
5. Analytics dashboards with sophisticated charts.
6. Research and documentation layouts.
7. Multi-step simulations and workflow interfaces.
8. Result summaries with expandable technical details.
9. Command palettes, loading states, and empty states.
10. Responsive mobile layouts for dense technical applications.

Inspect the actual returned screens and flows, not merely their descriptions.

Document at least 10 useful references where available. Record the product, available reference link, specific pattern, and intended application to QMint.

Create `docs/design/MOBBIN_RESEARCH.md`.

**Important:** Take inspiration from established interaction patterns without copying anyone's distinctive layout, artwork, brand assets, or visual identity. We want QMint to have its own recognizably original design.

## 3. Visual Direction — Extremely Important

The aesthetic is:

**Modern. Dark. Technical. Minimal. Precise. Quietly futuristic.**

Imagine Vercel and Linear collaborating on a quantum computing research product.

The design should feel engineered, not decorated.

### Design principles

- Dark-mode first.
- Near-black rather than pure black everywhere.
- Very restrained use of color.
- Beautiful typography.
- Generous negative space.
- Clean grid alignment.
- Hairline borders and subtle separators.
- Dense technical information only where appropriate.
- Purposeful animations.
- Excellent spacing and optical alignment.
- Thoughtful hover, focus, loading, and transition states.
- High-quality responsive behavior.

The visual language should communicate credibility, precision, and sophistication.

### Suggested palette

Use design tokens rather than hardcoded colors throughout the components.

Starting direction:

```css
--background: #08090B;
--surface: #101114;
--surface-raised: #17181C;
--border: #26272D;

--foreground: #F4F4F5;
--muted: #94959D;
--subtle: #62636C;

--accent: #B6F3D1;
```

These are starting references, not immutable values. Refine through actual visual testing.

Use the mint accent sparingly for selected actions, active states, and meaningful scientific highlights.

Avoid a neon-green cyberpunk aesthetic.

### Absolutely avoid

- Generic AI-generated SaaS layouts.
- Huge glowing gradients behind every element.
- Purple-and-blue gradient overload.
- Random floating 3D objects.
- Stock illustrations of padlocks or cryptocurrency coins.
- Excessive glassmorphism.
- Busy particle fields.
- Giant decorative orbital diagrams.
- Too many cards and rounded containers.
- Gratuitous animation.
- Overusing colored badges.
- Unnecessary emojis and decorative icons.
- Making every section look like the same repeated grid.

The website should feel premium even with every animation disabled.

## 4. Typography — Use All Three Geist Families

Reference:

https://vercel.com/font

Install the official `geist` package and use the actual licensed package fonts.

Use:

**Geist Sans**

Primary interface font. Use for body copy, buttons, navigation, documentation, large headlines, and general UI.

**Geist Mono**

Use for code, token identifiers, quantum state notation, numerical measurements, experimental parameters, labels, and technical annotations.

**Geist Pixel**

Use sparingly as a distinctive brand element.

Explore the Square, Grid, Circle, Triangle, and Line variants. Choose one or two as the main visual accents rather than mixing all five indiscriminately.

Potential uses include:

- QMint wordmark explorations.
- Large experimental section numbers.
- Token serial identifiers.
- Select hero typography.
- Decorative technical labels.
- Small purposeful loading or status motifs.

Do not set entire paragraphs in Geist Pixel.

Create a coherent typography scale with carefully controlled font weights, tracking, leading, and optical alignment.

Use tabular numerals wherever numerical data must align.

The three families should work together as one intentional system.

## 5. Design the Public Landing Page

Route: `/`

The landing page must be visually exceptional.

### Navigation

A compact, refined navigation bar.

Left: QMint wordmark.

Center or right: Product, Research, Benchmarks, Documentation, GitHub.

Primary CTA: Launch Lab.

Make navigation sticky only when it improves usability.

### Hero section

Create a distinctive editorial hero.

Suggested positioning:

Eyebrow:
`QMINT / QUANTUM SECURITY RESEARCH`

Headline:
**Security, down to the state.**

Supporting text:
"Design, challenge, and verify quantum payment protocols with reproducible experiments and inspectable evidence."

Primary CTA:
`Launch the Lab`

Secondary CTA:
`Explore the Research`

This copy is a starting point. Refine the text for precision and visual impact.

### Hero visualization

Do not use a random abstract quantum illustration.

Build a custom interactive demonstration inspired by the physics of quantum money.

Concept:

A quantum token appears in the center of an ultra-minimal black interface.

The user selects an attack scenario. The visualization branches into two verification attempts.

Show the results of a clearly defined protocol experiment or analytical reference calculation.

Use precise lines, minimal shapes, state labels, geometric patterns, and deliberate animation.

The visualization should resemble a beautifully engineered scientific instrument, not a video-game interface.

Real interactions are essential. No fake terminal animation pretending that code is executing.

### Sections below the hero

Build a distinctive editorial progression:

**01 — The Problem**

Explain the difference between preventing digital copying and preventing double spending, and why trust assumptions matter.

**02 — The Quantum Primitive**

Introduce unknown quantum states and no-cloning, including the limitations of what no-cloning alone guarantees.

**03 — The Interactive Laboratory**

Showcase token issuance, attack simulations, verification experiments, and security analysis.

**04 — Quantum vs Classical**

Show a meaningful comparison with classical cryptography and payment architectures under explicitly matched assumptions.

**05 — Proof, Not Hype**

Present theoretical bounds, numerical findings, experimental measurements, and their provenance. Never mix them without labeling.

**06 — Open Research**

Present source code, protocols, published papers, reproducible datasets, and research contributions.

End with a beautiful, minimal call-to-action and footer.

Every section should have a unique, considered composition.

Avoid using the same card layout repeatedly.

## 6. Build the Interactive Research Platform

The app should feel closer to Linear or a premium developer console than a consumer fintech dashboard.

Use a sophisticated application shell:

- Compact left sidebar.
- Clear top-level navigation.
- Minimal header.
- Consistent content-width system.
- Context-sensitive tools.
- Collapsible technical detail panels.
- Thoughtful breadcrumbs and page titles.
- Responsive mobile navigation.

Create these routes:

### `/app` — Research Overview

A calm overview dashboard displaying recent experiments, protocol options, saved runs, and links to the main tools.

Data must be real from the backend or clearly identified as demonstration fixtures.

### `/lab/mint` — Quantum Money Laboratory

Let users configure a quantum token experiment.

Inputs include protocol, qubit count, random seed, and supported preparation settings.

Display:

- Token representation.
- Quantum state preparation.
- Verification flow.
- Circuit visualization where supported.
- Measurement statistics.
- Run metadata and provenance.

Provide interactive explanations without obscuring the scientific details.

### `/lab/attack` — Counterfeiting Simulator

Build a compelling interactive adversarial experiment.

Allow users to select the supported attack model, protocol, number of states, and noise parameters.

Compare:

- Honest acceptance.
- Counterfeiting success.
- Double-verification success.
- Appropriate theoretical bounds.
- Confidence intervals for Monte Carlo results.

Clearly separate analytical formulas, simulations, and hardware measurements.

Make the attack experiment understandable to a nonexpert while preserving rigorous technical detail.

### `/benchmarks` — Quantum vs Classical

Create a research-quality benchmark dashboard.

Include sortable tables, filters, comparison charts, assumptions, execution times, error bars, and reproducibility links.

Provide meaningful visual comparisons rather than invented performance metrics.

Include appropriate fair classical baselines and make incomparable security models explicit.

### `/certificates` — Security Certificate Studio

This should become one of QMint's most interesting interfaces.

Let users specify security targets, honest-error tolerance, channel parameters, and supported adversary assumptions.

Show:

- Which security theorem or estimator applies.
- Whether the requested parameters satisfy its assumptions.
- Resource estimates.
- Feasibility and uncertainty.
- Exportable certificate data.
- Independent verification status.

Do not call an ordinary numerical estimate a formal proof.

A failed or unsupported certification must have an explicit, informative state.

### `/research` — Research Library

Build a beautiful research index containing papers, experiments, security games, protocol notes, and citations.

Make dense technical information unusually readable.

### `/docs` — Developer Documentation

Build documentation inspired by high-quality developer platforms.

Include API references, example experiments, reproducibility instructions, architecture, limitations, and scientific methodology.

## 7. Interactions and Motion

The site must feel alive without becoming distracting.

Use subtle motion for:

- Navigation transitions.
- Tab changes.
- Progressive experiment execution.
- Token state changes.
- Chart updates.
- Parameter adjustments.
- Expandable mathematical details.
- Loading, success, and failure states.

Prefer CSS transitions when sufficient. Use Framer Motion/Motion only where it meaningfully improves the result.

Respect reduced-motion preferences.

Aim for exceptionally responsive input handling.

Never sacrifice readability or scientific accuracy for visual effects.

## 8. Technical Stack

Preferred stack:

- Next.js App Router.
- React and TypeScript.
- Tailwind CSS.
- shadcn/ui primitives, customized heavily.
- Official Geist font package.
- Lucide icons.
- Recharts, Plotly, or other appropriate visualization tools.
- FastAPI integration with the existing QMint research backend.
- Playwright for end-to-end tests.
- Vitest or equivalent for UI unit tests.

Inspect the existing repository first and preserve compatible infrastructure.

Do not create a second competing backend if the project already has one.

Create typed API clients and explicit schema contracts.

If an endpoint is unfinished, implement a clearly labeled local demonstration adapter using deterministic fixtures or established analytical calculations.

Never fabricate empirical quantum results.

All visible controls must perform a meaningful action.

Implement real loading, validation, empty, success, timeout, and error states.

## 9. Parallel Agent Execution

If Claude Code supports multiple agents, orchestrate the work in parallel.

First establish shared design tokens, component contracts, route ownership, and backend API interfaces.

Then assign independent agents:

**Agent A — Design Research and Design System** — Use Mobbin MCP, analyze references, define the visual system, typography, component primitives, spacing rules, and design documentation.

**Agent B — Landing Page and Brand** — Build the public website, hero visualization, original QMint visual identity, editorial sections, and responsive marketing experience.

**Agent C — Application Shell and Research UI** — Build the dashboard, navigation, research library, documentation shell, tables, filters, and shared platform layouts.

**Agent D — Quantum Lab Experiences** — Implement the token-generation and counterfeiting interfaces using the backend contracts.

**Agent E — Benchmarks and Certificate Studio** — Build the scientific data visualizations, benchmark explorer, configuration interfaces, and security certificate views.

**Agent F — Integration and Quality** — Own cross-route accessibility, responsive audits, Playwright testing, API integration checks, design consistency, and performance testing.

Each agent must work in a separate Git worktree or otherwise isolated scope.

Do not let agents independently invent incompatible visual systems.

Do not overwrite unrelated research work.

Do not commit secrets, force-push, or deploy to production without authorization.

Merge only after the relevant tests pass.

## 10. Visual QA Is Mandatory

Do not rely on the fact that the page compiles.

Start the actual development server.

Open the rendered website in a browser using available browser automation.

Capture and review screenshots at: 1440px desktop, 1920px desktop, 768px tablet, 390px mobile.

Inspect every major page.

Look for: weak hierarchy, misaligned typography, inconsistent spacing, excessive borders, overcrowded panels, generic repeated cards, broken responsive layouts, awkward font combinations, poor chart readability, low contrast, empty visual regions with no purpose, motion that distracts from content.

Iterate based on the rendered result.

Compare against the quality of the Mobbin references, not just the code.

Perform a dedicated polish pass after the first functional implementation.

## 11. Acceptance Requirements

- A complete, responsive public landing page.
- An original, coherent QMint design identity.
- All three Geist font families integrated deliberately.
- Documented research using Mobbin MCP.
- Working app navigation.
- An interactive quantum token laboratory.
- An interactive counterfeiting experiment.
- A usable benchmark explorer.
- A security certificate interface with honest verification states.
- Research and documentation pages.
- Typed API integration.
- No fabricated scientific results.
- Accessible keyboard navigation.
- Reduced-motion support.
- Meaningful loading and error states.
- Passing TypeScript and lint checks.
- Passing relevant component and end-to-end tests.
- Browser-verified desktop and mobile layouts.
- A reproducible local development workflow.

Create `docs/design/DESIGN_SYSTEM.md`, `docs/design/MOBBIN_RESEARCH.md`, and `docs/design/VISUAL_QA.md`.

Record actual screenshots, test results, and implementation limitations.

## 12. Execution Order

1. Audit the existing QMint repository.
2. Research design patterns using Mobbin MCP.
3. Produce a short design direction and reference map.
4. Establish the design system and UI/API contracts.
5. Dispatch parallel implementation agents.
6. Build the public landing page and shared app shell.
7. Implement the interactive research tools.
8. Integrate the research backend.
9. Run tests and inspect actual browser screenshots.
10. Perform a meticulous typography, motion, and visual-polish pass.
11. Produce implementation documentation and a working preview.

Do not stop after the research phase. Do not stop after building the landing page. Do not treat mock data as a completed backend integration. Finish as much of the working website as the environment permits, and document any blocked capabilities accurately.

## 13. Final Standard

A **distinctive, technically credible, exceptionally polished research platform** that feels as carefully designed as Vercel and Linear. Appeals to a quantum researcher, security engineer, startup founder, and sophisticated technical investor. Restraint over decoration, typography over effects, meaningful interactions over demos, evidence over marketing hype.

---

## Lead notes (binding, added by the orchestrator)

- **Mobbin MCP is installed and authenticated** in this environment (`mcp__mobbin__search_screens`, `mcp__mobbin__search_flows`, `mcp__mobbin__search_sections`; verified 2026-10-11). Load via ToolSearch `select:mcp__mobbin__search_screens,mcp__mobbin__search_flows,mcp__mobbin__search_sections`.
- **Locations:** Next.js app in `web/` (use **pnpm**, never npm/yarn — disk has ~8 GB free; pnpm hard-links from its store). FastAPI research API in `qmint/api/` (Python, shared venv `/Users/udsy/PycharmProjects/Qollab-QMint/.venv`, fastapi/uvicorn/httpx installed). Design docs in `docs/design/`. Python API tests in `tests/unit/api/`.
- **One backend:** the API wraps merged QMint modules (`qmint.quantum`, `qmint.networks`, `qmint.core`, and — once merged — `qmint.protocols`, `qmint.attacks`, `qmint.proofs`, `qmint.classical`, `qmint.photonics`, `qmint.compiler`). Every API response carries frozen-contract `EvidenceKind` labels. For lanes not yet merged, endpoints return a clearly labelled `DEMO_ADAPTER` result computed from published analytical formulas (e.g. W1 `(3/4)^n` is a published theorem), never invented empirical values; or `NOT_AVAILABLE` with the reason.
- **Supersession:** the wave-1 static workbench (`qmint/ui/*` HTML renderer, `app/site/`) is replaced by `web/`. Move reusable evidence-badge / claim-validation logic behind the API and delete the static renderer once its views are covered (no dead code).
- Research honesty rules from `project/AGENT_RULES.md` apply to every number shown on the site.
