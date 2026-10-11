import type { Metadata } from "next";
import * as React from "react";
import { Button } from "@/components/ui/button";
import { Disclosure } from "@/components/ui/disclosure";
import { EvidenceLabel } from "@/components/ui/evidence-label";
import { Kbd } from "@/components/ui/kbd";
import { PixelLoader } from "@/components/ui/pixel-loader";
import { Readout, ReadoutGroup } from "@/components/ui/readout";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState, UnavailableState } from "@/components/ui/state";
import { TBody, THead, Table, TableCaption, Td, Th, Tr } from "@/components/ui/table";
import { EVIDENCE_LABELS } from "@/lib/evidence";
import { FormDemo, OverlayDemos, TabsDemo } from "./demos";

export const metadata: Metadata = { title: "Design system", robots: { index: false } };

const COLORS: [string, string][] = [
  ["background", "#08090b"], ["surface", "#0e0f12"], ["surface-raised", "#15161a"], ["surface-overlay", "#1b1c21"],
  ["surface-hover", "#1f2026"], ["border", "#23242a"], ["border-strong", "#34353d"], ["foreground", "#f4f4f5"],
  ["muted", "#9a9ba3"], ["subtle", "#80818a"], ["accent", "#b6f3d1"], ["accent-strong", "#8ee8b8"],
  ["warn", "#e6c27a"], ["danger", "#f0a3a3"], ["info", "#aec6ee"],
  ["chart-1", "#b6f3d1"], ["chart-2", "#aec6ee"], ["chart-3", "#e6c27a"], ["chart-4", "#c9b8f0"],
];

const TYPE: [string, string, string][] = [
  ["display-xl", "text-display-xl", "72 / 72 · −4.5% · 560"],
  ["display", "text-display", "56 / 58 · −4% · 560"],
  ["h1", "text-h1", "40 / 44 · −3.2% · 560"],
  ["h2", "text-h2", "28 / 34 · −2.4% · 560"],
  ["h3", "text-h3", "20 / 27 · −1.6% · 560"],
  ["h4", "text-h4", "16 / 24 · −0.8% · 560"],
  ["body-lg", "text-body-lg", "17 / 28 · 400"],
  ["body", "text-body", "15 / 24 · 400"],
  ["sm", "text-sm", "13 / 19.5 · 400"],
  ["xs", "text-xs", "12 / 17 · 400"],
];

const SPACE = [1, 2, 3, 4, 6, 8, 12, 16, 24, 32];
const MOTION: [string, string, string][] = [
  ["instant", "80ms", "hover colour, table row"],
  ["fast", "140ms", "buttons, tabs, chevrons, tooltips"],
  ["base", "220ms", "panels, dialogs, tab content"],
  ["slow", "360ms", "chart transitions, layout"],
  ["deliberate", "640ms", "instrument / token state (hero, lab)"],
];

function Section({ id, n, title, children, note }: { id: string; n: string; title: string; children: React.ReactNode; note?: string }) {
  return (
    <section id={id} aria-labelledby={`${id}-h`} className="grid grid-cols-1 gap-6 border-t border-border py-12 lg:grid-cols-[200px_minmax(0,1fr)] lg:gap-10">
      <header className="grid content-start gap-2">
        <span className="font-pixel text-h3 text-subtle" aria-hidden>{n}</span>
        <h2 id={`${id}-h`} className="text-h4">{title}</h2>
        {note ? <p className="text-xs text-subtle">{note}</p> : null}
      </header>
      <div className="min-w-0">{children}</div>
    </section>
  );
}

export default function DesignSystemPage() {
  return (
    <main id="main" className="container-wide pb-24">
      <header className="grid gap-4 pt-16 pb-12 md:pt-24">
        <p className="label-mono text-subtle">QMint / Design system · v1 · frozen after phase 1</p>
        <h1 className="text-display tracking-tight">
          <span className="font-pixel">QMint</span> design system
        </h1>
        <p className="max-w-prose text-body-lg text-muted">
          Tokens and primitives shared by every route. Dark, precise, quiet. Mint is reserved for the selected action and the scientifically
          decisive number. Spec: <code className="font-mono text-sm text-foreground">docs/design/DESIGN_SYSTEM.md</code>.
        </p>
      </header>

      <Section id="color" n="01" title="Colour" note="CSS variables in app/globals.css; Tailwind: bg-*, text-*, border-*.">
        <ul className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {COLORS.map(([name, hex]) => (
            <li key={name} className="grid gap-2">
              <span className="h-12 rounded-sm border border-border" style={{ background: `var(--${name})` }} />
              <span className="grid">
                <span className="font-mono text-xs text-foreground">--{name}</span>
                <span className="tnum font-mono text-xs text-subtle">{hex}</span>
              </span>
            </li>
          ))}
        </ul>
      </Section>

      <Section id="type" n="02" title="Typography" note="Geist Sans (UI), Geist Mono (data), Geist Pixel Square + Grid (brand accents).">
        <div className="grid gap-5">
          {TYPE.map(([name, cls, spec]) => (
            <div key={name} className="grid items-baseline gap-1 border-b border-hairline pb-4 md:grid-cols-[120px_minmax(0,1fr)_180px] md:gap-6">
              <span className="font-mono text-xs text-subtle">{name}</span>
              <span className={`${cls} min-w-0 text-balance`}>Security, down to the state.</span>
              <span className="tnum font-mono text-xs text-subtle md:text-right">{spec}</span>
            </div>
          ))}
          <div className="grid gap-6 pt-4 md:grid-cols-3">
            <div className="grid gap-2">
              <span className="label-mono text-subtle">Mono · data</span>
              <span className="tnum font-mono text-h3">0.728553 · (3/4)ⁿ</span>
              <span className="font-mono text-sm text-muted">|ψ⟩ = |+⟩⊗|0⟩⊗|−⟩⊗|1⟩</span>
            </div>
            <div className="grid gap-2">
              <span className="label-mono text-subtle">Pixel Square · brand</span>
              <span className="font-pixel text-h1">QMINT 03</span>
            </div>
            <div className="grid gap-2">
              <span className="label-mono text-subtle">Pixel Grid · serials</span>
              <span className="font-pixel-grid text-h3">TKN-7F3A-0008</span>
            </div>
          </div>
          <div className="grid gap-2">
            <span className="label-mono text-subtle">Tabular numerals (.tnum)</span>
            <div className="tnum grid w-fit gap-0.5 text-right font-mono text-sm">
              <span>15.337 µs</span>
              <span>304.207 µs</span>
              <span>1 948.000 µs</span>
            </div>
          </div>
        </div>
      </Section>

      <Section id="space" n="03" title="Space, radius, elevation" note="4px base. Borders before shadows; shadow only on floating layers.">
        <div className="grid gap-8">
          <div className="flex flex-wrap items-end gap-4">
            {SPACE.map((s) => (
              <div key={s} className="grid justify-items-center gap-1.5">
                <span className="bg-border-strong" style={{ width: s * 4, height: s * 4 }} />
                <span className="tnum font-mono text-xs text-subtle">{s * 4}</span>
              </div>
            ))}
          </div>
          <div className="flex flex-wrap gap-6">
            {[["xs", "2px", "rounded-xs"], ["sm", "4px", "rounded-sm"], ["md", "6px", "rounded-md"], ["lg", "10px", "rounded-lg"]].map(([r, v, cls]) => (
              <div key={r} className="grid justify-items-center gap-1.5">
                <span className={`size-14 border border-border-strong bg-surface-raised ${cls}`} />
                <span className="font-mono text-xs text-subtle">rounded-{r} · {v}</span>
              </div>
            ))}
            <div className="grid justify-items-center gap-1.5">
              <span className="size-14 rounded-md bg-surface-raised shadow-raised" />
              <span className="font-mono text-xs text-subtle">shadow-raised</span>
            </div>
            <div className="grid justify-items-center gap-1.5">
              <span className="size-14 rounded-md bg-surface-overlay shadow-overlay" />
              <span className="font-mono text-xs text-subtle">shadow-overlay</span>
            </div>
          </div>
        </div>
      </Section>

      <Section id="motion" n="04" title="Motion" note="Reduced motion collapses every duration to ~0.">
        <Table>
          <THead>
            <Tr>
              <Th>Token</Th>
              <Th numeric>Duration</Th>
              <Th>Use</Th>
            </Tr>
          </THead>
          <TBody>
            {MOTION.map(([t, d, use]) => (
              <Tr key={t}>
                <Td className="font-mono text-xs">--duration-{t}</Td>
                <Td numeric>{d}</Td>
                <Td className="text-muted">{use}</Td>
              </Tr>
            ))}
          </TBody>
          <TableCaption>Easing: ease-out cubic-bezier(0.2, 0, 0, 1) default; ease-in-out for symmetric moves.</TableCaption>
        </Table>
      </Section>

      <Section id="evidence" n="05" title="Evidence labels" note="Glyph shape = origin; glyph colour = tone. Only CERTIFIED is mint.">
        <div className="grid gap-8">
          {(["evidence_kind", "certificate_status", "api_status"] as const).map((g) => (
            <div key={g} className="grid gap-3">
              <span className="label-mono text-subtle">{g.replace("_", " ")}</span>
              <ul className="grid gap-x-8 gap-y-3 sm:grid-cols-2 xl:grid-cols-3">
                {EVIDENCE_LABELS.filter((l) => l.group === g).map((l) => (
                  <li key={l.key} className="grid gap-0.5">
                    <EvidenceLabel kind={l.key} group={g} />
                    <span className="text-xs text-subtle">{l.title}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </Section>

      <Section id="readouts" n="06" title="Readouts">
        <ReadoutGroup>
          <Readout label="Honest acceptance" value={1} evidence={<EvidenceLabel kind="SIMULATOR_IDEAL" />} />
          <Readout
            label="Counterfeit success"
            value={0.7294}
           
            interval={{ lo: 0.7237, hi: 0.7351, confidence: 0.999 }}
            evidence={<EvidenceLabel kind="MONTE_CARLO" />}
          />
          <Readout label="W1 bound (n=1)" value={0.75} emphasis evidence={<EvidenceLabel kind="PUBLISHED_THEOREM" />} />
          <Readout label="S2 bound" value={null} missing="no applicable bound" evidence={<EvidenceLabel kind="UNCERTIFIED" />} />
        </ReadoutGroup>
        <p className="mt-4 text-xs text-subtle">Values above are design-system specimens (from F-F1 handoff), not live API output.</p>
      </Section>

      <Section id="controls" n="07" title="Buttons and fields">
        <div className="grid gap-10">
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="accent">Launch the Lab</Button>
            <Button variant="primary">Primary</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="link">Link</Button>
            <Button variant="danger">Discard run</Button>
            <Button variant="secondary" disabled>
              Disabled
            </Button>
            <Button variant="secondary" size="sm">
              Small
            </Button>
            <Button variant="primary" size="lg">
              Large
            </Button>
          </div>
          <FormDemo />
        </div>
      </Section>

      <Section id="nav" n="08" title="Tabs, disclosure, overlays">
        <div className="grid gap-10">
          <TabsDemo />
          <div className="max-w-xl">
            <Disclosure title="Derivation" meta="analytic">
              <p className="font-mono text-xs leading-relaxed">
                Pr[both copies pass] = Π<sub>i</sub> p<sub>i</sub>; Bruß phase-covariant cloner per qubit (3 + 2√2)/8 ≈ 0.728553.
              </p>
            </Disclosure>
            <Disclosure title="Provenance" meta="seed 2026">
              <p className="font-mono text-xs">qiskit 2.5.2 · qiskit-aer 0.17.2 · circuit sha256 dad2b989…</p>
            </Disclosure>
          </div>
          <OverlayDemos />
          <p className="flex items-center gap-2 text-sm text-muted">
            Keyboard: <Kbd>⌘</Kbd>
            <Kbd>K</Kbd> palette · <Kbd>Esc</Kbd> close · <Kbd>Tab</Kbd> move focus
          </p>
        </div>
      </Section>

      <Section id="table" n="09" title="Data table" note="Mono uppercase heads, hairline rows, numeric columns right-aligned.">
        <Table>
          <THead>
            <Tr>
              <Th>Case</Th>
              <Th numeric>Modelled</Th>
              <Th numeric>Published</Th>
              <Th>Evidence</Th>
            </Tr>
          </THead>
          <TBody>
            <Tr>
              <Td>Jinan · 2.766 km fibre</Td>
              <Td numeric>15.337 µs</Td>
              <Td numeric>15.34 ± 0.01 µs</Td>
              <Td><EvidenceLabel kind="MODELLED_LATENCY" showTooltip={false} /></Td>
            </Tr>
            <Tr>
              <Td>Yiyuan–Mazhan · 60.54 km</Td>
              <Td numeric>304.207 µs</Td>
              <Td numeric>304.20 ± 0.01 µs</Td>
              <Td><EvidenceLabel kind="MODELLED_LATENCY" showTooltip={false} /></Td>
            </Tr>
            <Tr>
              <Td>Classical H1 ledger</Td>
              <Td numeric className="text-muted">—</Td>
              <Td numeric className="text-muted">—</Td>
              <Td><EvidenceLabel kind="NOT_AVAILABLE" group="api_status" showTooltip={false} /></Td>
            </Tr>
          </TBody>
          <TableCaption>Specimen rows from the lane G handoff; live values come from GET /api/v1/benchmarks.</TableCaption>
        </Table>
      </Section>

      <Section id="states" n="10" title="Loading, empty, error, unavailable">
        <div className="grid gap-8">
          <div className="flex items-center gap-3 text-sm text-muted" aria-busy="true">
            <PixelLoader label="Running simulation" /> Running 4 000 shots on aer_simulator…
          </div>
          <div className="grid max-w-xl gap-2" aria-hidden>
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-8 w-2/3" />
            <Skeleton className="h-24 w-full" />
          </div>
          <div className="grid gap-x-10 border-t border-hairline md:grid-cols-2">
            <EmptyState title="No runs yet" description="Mint a token to create your first run. Runs are stored as evidence records with provenance." action={<Button size="sm" variant="secondary">Open the mint lab</Button>} />
            <ErrorState title="The research API did not respond" description="POST /api/v1/lab/mint failed. Check that the API is running on :8787." detail="HTTP 502 · request a1b2c3" action={<Button size="sm" variant="secondary">Retry</Button>} />
            <ErrorState timeout title="Simulation timed out" description="No result after 15 s. Reduce shots or qubits and retry." />
            <UnavailableState title="Classical baselines not available" description="Lane H (classical baselines) has not merged. No numbers are shown rather than invented ones." />
          </div>
        </div>
      </Section>
    </main>
  );
}
