# QMint web — design direction (phase 1, Agent A)

Date 2026-10-11 · branch `feat/K-web` · spec: `docs/design/WEBSITE_BRIEF.md` · system: `DESIGN_SYSTEM.md` ·
research: `MOBBIN_RESEARCH.md` (47 references, R1–R47) · ownership: `WEB_OWNERSHIP.md`.

## 1. Repository audit — what is real today

| Lane | Package | Merged | What the website may show from it |
|---|---|---|---|
| F | `qmint.quantum` (bb84, circuits, channels, cloner, references, photonic_model, records, evidence) | yes | BB84 C7 states/Bloch vectors; n ≤ 8 prepare/verify circuits; exact analytic distributions; Aer ideal/noisy runs with seeds; CPTP noise channels (depolarizing, dephasing, amplitude damping, readout); Bruß cloner (3+2√2)/8 ≈ 0.7286 and MVW optimal channel 3/4 per qubit; Clopper–Pearson intervals; resource counts; provenance. Evidence: SIMULATOR_IDEAL / SIMULATOR_NOISY / SYNTHETIC (photonic). |
| J | `qmint.quantum.ionq` | yes | Dry-run cost/approval plans, backend snapshot. Submission disabled in this build → QPU is always "not run". |
| G | `qmint.networks` | yes | Discrete-event causal simulator; Jiang et al. 2024 topologies (2.766 km / 60.54 km) → modelled S-money latency 15.337 µs / 304.207 µs vs published 15.34 / 304.20 µs; RIPE Atlas HEL→TMP fixture (MEASURED_LATENCY, RTT/2 assumption). Classical race actors are TEST FIXTURES only. |
| L | `qmint.core` | yes | Frozen contracts C0–C7, `EvidenceKind`, `CertificateStatus`, `PROTOCOL_GAMES`, `RecordStore`, provenance, lane registry. |
| K wave 1 | `qmint.ui` (static HTML workbench) + `app/site/` | yes | Evidence-badge rules (`evidence_badges.py`) and cited-number rules (`claims.py`) → now served by `/api/v1/evidence/labels` and mirrored by `web/lib/format.ts`. Static renderer is superseded by `web/` and is deleted once phase-2 views cover it (see WEB_OWNERSHIP §Supersession). |
| B, C, D, E, H, I, A | protocols, attacks, proofs, photonics, classical, compiler, research | **no** | Nothing. The API returns `DEMO_ADAPTER` (published analytic formulas, labelled) or `NOT_AVAILABLE` with the reason. No certificate is ever CERTIFIED. |

Consequence for design: **every surface must have an honest "not yet" state** that looks intentional, not broken.
Unavailable is a first-class visual state (`UnavailableState`, `NOT AVAILABLE` label), not an error.

## 2. Direction in one paragraph

An instrument, not a brochure. Near-black field (`#08090B`), hairline structure, Geist Sans for language,
Geist Mono for every number and identifier, Geist Pixel (Square, Grid) only where the product speaks as itself —
the wordmark, section numerals, token serials, a 3×3 loading motif. Mint `#B6F3D1` is spent like a scarce
resource: the one action that runs something, the selected row/tab, the scientifically decisive number,
the focus ring, and the CERTIFIED state (which today never appears). Status is a glyph plus a word, never a
coloured pill. Detail is layered: summary readouts first, technical depth behind disclosures, reproduction
command always present. It must still feel premium with motion disabled.

## 3. Principles (decision rules for phase-2 agents)

1. **Evidence before ornament.** No number without an `EvidenceLabel` and a source; null renders as text ("no applicable bound"), never 0.
2. **One accent per view.** If two things are mint, one of them is wrong.
3. **Borders, not boxes.** Prefer hairline rules and whitespace to cards. A bordered panel must earn its border (it groups inputs or holds a live result).
4. **Mono for machines, Sans for people.** Values, units, ids, seeds, hashes, formulas: Mono with tabular numerals. Explanations: Sans.
5. **Pixel is punctuation.** Never a paragraph, never body UI, ≤ 1 pixel element per viewport on app routes.
6. **Honest states are designed states.** Loading (skeleton cells under real headers), empty, error, timeout, NOT_AVAILABLE, DEMO_ADAPTER all have copy that says what, why and what next.
7. **Density is contextual.** Marketing: generous (section padding 128–160px). App: compact (32–36px rows, 48px header).
8. **Every control does something.** No dead toggles; disabled controls say why (tooltip/hint).
9. **No decorative physics.** No orbitals, particle fields, glowing qubits. Visuals plot real quantities (Bloch vectors, distributions, bounds vs n, light-cone timing).

## 4. Reference map (Mobbin → QMint)

| QMint surface | Pattern adopted | Mobbin refs |
|---|---|---|
| Landing hero / sections | Editorial left-aligned hero, numbered section headers, one white CTA in nav; avoid glow heroes | R8, R9, R10; anti-patterns logged in MOBBIN_RESEARCH |
| Marketing nav / footer | 56px nav, hairline divider before CTA; mono column heads + system status in footer | R8, R45, R46 |
| App shell | 240px sidebar → 48px rail, filled active row, mono section heads; 48px top bar with breadcrumb + ⌘K | R1, R3, R4, R14 |
| Command palette | 560px, flat scrim, grouped results, key-hint footer, mint 2px active bar | R12, R13, R14 |
| /lab/mint, /lab/attack config | Label-left/value-right parameters, 2px slider with min/max, advanced params in disclosure; Configure → Run → Verify stages | R16, R17, R18, R28, R31 |
| Run results | Outcome summary + label/value grid, collapsible Trace / Parameters / Raw / Reproduce | R30, R32, R33, R34 |
| /benchmarks | Greyscale charts with one mint series, ≤3 gridlines, bar list with featured row, comparison table with highlighted column | R20, R21, R22, R23, R38, R39, R47 |
| /certificates | Verdict callout with 2px left bar, key/values, lifecycle timeline, export footer, middle-truncated hashes | R36, R37, R35 |
| /research, /docs | 220px nav, 65ch prose, "On this page" rail, collapsible Sources, schema objects | R25, R26, R27 |
| Loading / empty | Real headers + skeleton cells; progress toast for long jobs; icon + 2 lines, no illustration | R15, R40, R41, R42 |
| Mobile | 48px top bar + full-height sheet, no bottom tab bar, two-line rows, grids reflow 2→1 | R43, R44 |

Originality guardrails (e.g. no Vercel triangle mark or deployment-thumbnail signatures, no Linear "x.0" numbering
or gradient product frame, no Stripe mesh gradients, no Supabase green/double sidebar, no glow beams) are listed per
brand in `MOBBIN_RESEARCH.md §Originality guardrails`. QMint's own identity rests on the Pixel wordmark and
two-digit Pixel section numerals ("01", not "1.0"), the origin-glyph evidence system, and plotted physical quantities.
