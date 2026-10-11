"use client";

import { Check, Copy } from "lucide-react";
import * as React from "react";
import { ChartFrame, IntervalPlot, SERIES, formatNs, middleTruncate, type IntervalDatum } from "@/components/charts";
import { EvidenceLabel } from "@/components/ui/evidence-label";
import { Readout } from "@/components/ui/readout";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TBody, THead, Td, Th, Tr } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { COMPARABILITY, type BenchData } from "./model";

type Quantity = BenchData["latency_cases"][number]["quantities"][number];

const KIND_SERIES: Record<string, { label: string; color: string; marker: "filled" | "ring" | "diamond" }> = {
  MODELLED_LATENCY: { label: "modelled (QMint)", color: SERIES.quantum, marker: "ring" },
  PUBLISHED_AGGREGATE: { label: "published", color: SERIES.classical, marker: "filled" },
  MEASURED_LATENCY: { label: "measured (RIPE Atlas)", color: SERIES.extra, marker: "filled" },
  BOUND: { label: "light-cone lower bound", color: SERIES.bound, marker: "diamond" },
};

const SHORT: Record<string, string> = {
  "jiang2024-intracity": "Jinan",
  "jiang2024-intercity": "Yiyuan–Mazhan",
  "ripe-prb6330-prb6251": "HEL → TMP",
  "ripe-prb6979-prb6251": "FRA → TMP",
};

const QSHORT: Record<string, string> = {
  smoney_modelled: "S-money, modelled",
  smoney_published: "S-money, published",
  classical_crosscheck: "classical 2L/c, published",
  classical_free_space: "classical 2D/c, published",
  lightcone_bound: "light cone",
  one_way_p50: "one-way delay p50",
  smoney_modelled_median: "S-money, modelled",
};

const FALLBACK = { label: "other", color: SERIES.muted, marker: "filled" as const };
const kindSeries = (k: string) => KIND_SERIES[k] ?? FALLBACK;

function seriesOf(q: Quantity): string {
  return q.id === "lightcone_bound" ? "BOUND" : q.evidence_kind;
}

/** Readouts on a fixed 2/3-column grid (wrapping flex rows misalign the hairlines). */
function ReadoutGrid({ children, cols = 2 }: { children: React.ReactNode; cols?: 2 | 3 }) {
  return <dl className={cn("grid grid-cols-2 gap-x-6 gap-y-5", cols === 3 && "sm:grid-cols-3")}>{children}</dl>;
}

const sig = (v: number | null | undefined, n = 4) => (v === null || v === undefined ? null : Number(v.toPrecision(n)));

export function CopyText({ text, label }: { text: string; label?: string }) {
  const [done, setDone] = React.useState(false);
  return (
    <button
      type="button"
      aria-label={label ?? `Copy ${text}`}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setDone(true);
          setTimeout(() => setDone(false), 1200);
        } catch {
          setDone(false);
        }
      }}
      className="inline-flex size-6 shrink-0 items-center justify-center rounded-xs text-subtle hover:bg-surface-hover hover:text-foreground"
    >
      {done ? <Check className="size-3.5" aria-hidden /> : <Copy className="size-3.5" aria-hidden />}
    </button>
  );
}

export function LatencyCases({ cases }: { cases: BenchData["latency_cases"] }) {
  const data: IntervalDatum[] = cases.flatMap((c) =>
    c.quantities
      .filter((q) => q.value !== null)
      .map((q) => ({
        label: `${SHORT[c.id] ?? c.title} · ${QSHORT[q.id] ?? q.label}`,
        series: seriesOf(q),
        value: q.value!,
        lo: q.interval?.lo ?? null,
        hi: q.interval?.hi ?? null,
        detail: [["source", q.source.slice(0, 48)]] as [string, string][],
      })),
  );
  const used = [...new Set(data.map((d) => d.series))];
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-8">
      <ChartFrame
        title="Transaction timing vs the light cone"
        summary="Log-scale latencies for four two-site cases: modelled S-money times, the published Jiang 2024 aggregates, RIPE Atlas one-way delays and the light-cone lower bound for each link."
        legend={used.map((k) => {
          const s = kindSeries(k);
          return { label: s.label, color: s.color, shape: s.marker === "ring" ? "ring" : s.marker === "diamond" ? "square" : "dot" };
        })}
        caption="Error bars: published ± (Jiang), p05–p95 of RTT/2 (RIPE), min–max over 20 seeds (modelled on RIPE samples). Each case is its own topology; rows are not a matched quantum-vs-classical benchmark."
        table={
          <Table>
            <THead>
              <Tr>
                <Th>Case · quantity</Th>
                <Th numeric>ns</Th>
                <Th>Evidence</Th>
              </Tr>
            </THead>
            <TBody>
              {cases.flatMap((c) =>
                c.quantities.map((q) => (
                  <Tr key={c.id + q.id}>
                    <Td className="text-xs">{`${c.title} · ${q.label}`}</Td>
                    <Td numeric>{q.value ?? "—"}</Td>
                    <Td>
                      <EvidenceLabel kind={q.evidence_kind} showTooltip={false} />
                    </Td>
                  </Tr>
                )),
              )}
            </TBody>
          </Table>
        }
      >
        <IntervalPlot
          data={data}
          scale="log"
          yWidth={210}
          rowHeight={24}
          series={used.map((k) => ({ key: k, ...kindSeries(k) }))}
          formatValue={formatNs}
        />
      </ChartFrame>

      <div className="grid grid-cols-[minmax(0,1fr)] gap-x-10 gap-y-8 lg:grid-cols-2">
        {cases.map((c) => (
          <section key={c.id} aria-labelledby={`case-${c.id}`} className="grid content-start gap-4 border-t border-border pt-5">
            <div className="grid gap-1">
              <p className="label-mono text-subtle">{c.kind === "paper_topology" ? "Paper topology" : "Measured network"}</p>
              <h3 id={`case-${c.id}`} className="text-h4 text-foreground">
                {c.title}
              </h3>
            </div>
            <ReadoutGrid>
              {c.quantities.map((q) => {
                const ms = Math.max(...c.quantities.map((x) => x.value ?? 0)) >= 1e6;
                const f = ms ? 1e6 : 1e3;
                return (
                  <Readout
                    key={q.id}
                    size="sm"
                    label={q.label.replace(/ \(.*\)$/, "")}
                    value={q.value === null ? null : sig(q.value / f, 5)}
                    unit={ms ? "ms" : "µs"}
                    interval={q.interval ? { lo: sig(q.interval.lo / f, 5)!, hi: sig(q.interval.hi / f, 5)! } : null}
                    evidence={<EvidenceLabel kind={q.evidence_kind} size="xs" />}
                  />
                );
              })}
            </ReadoutGrid>
            <ul className="grid gap-1 text-xs text-subtle">
              {c.assumptions.map((a) => (
                <li key={a}>— {a}</li>
              ))}
            </ul>
            <p className="font-mono text-[0.6875rem] break-all text-subtle">{c.reproduce}</p>
            <p className="text-xs break-words text-subtle">{c.sources.join(" · ")}</p>
          </section>
        ))}
      </div>
    </div>
  );
}

const pct = (v: number) => `${(v * 100).toFixed(2)}%`;

export function PhotonQber({ photon }: { photon: BenchData["photon"] }) {
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-10">
      <div className="grid grid-cols-[minmax(0,1fr)] gap-x-10 gap-y-10 lg:grid-cols-2">
        {photon.bases.map((b) => {
          const runs = photon.runs.filter((r) => r.basis === b.basis);
          const data: IntervalDatum[] = runs.map((r) => ({
            label: `${r.folder} ${String(r.chunk).padStart(2, "0")}`,
            series: "run",
            value: r.qber,
            lo: r.ci_lo,
            hi: r.ci_hi,
            detail: [
              ["errors / sifted", `${r.n_errors} / ${r.n_sifted}`],
              ["pairs", String(r.n_pairs)],
            ],
          }));
          const pub = b.published;
          const pooled = b.pooled;
          return (
            <section key={b.basis} aria-labelledby={`basis-${b.basis}`} className="grid min-w-0 content-start gap-5">
              <h3 id={`basis-${b.basis}`} className="text-h4 text-foreground">
                {b.label}
              </h3>
              <ReadoutGrid cols={3}>
                {[
                  ["Pooled QBER", pooled],
                  ["Paper's estimator", b.state_averaged],
                  ["Published", pub],
                ].map(([label, q]) => {
                  const qq = q as typeof pooled;
                  return (
                    <Readout
                      key={label as string}
                      size="sm"
                      label={label as string}
                      value={sig(qq.value)}
                      interval={qq.interval ? { lo: sig(qq.interval.lo)!, hi: sig(qq.interval.hi)!, confidence: qq.interval.confidence } : null}
                      evidence={<EvidenceLabel kind={qq.evidence_kind} size="xs" />}
                    />
                  );
                })}
              </ReadoutGrid>
              <ChartFrame
                title={`QBER per run, ${b.basis} basis`}
                summary={`${runs.length} runs of the ${b.label} archive with 95% Clopper–Pearson intervals against the published ${pct(pub.value!)} ± ${pct(pub.interval!.hi - pub.value!)} and the pooled interval.`}
                legend={[
                  { label: "run QBER, 95% Clopper–Pearson", color: SERIES.quantum, shape: "dot" },
                  { label: "published ±", color: SERIES.classical, shape: "band" },
                  { label: "pooled hull", color: SERIES.bound, shape: "dash" },
                ]}
                table={
                  <Table>
                    <THead>
                      <Tr>
                        <Th>Run</Th>
                        <Th numeric>Errors</Th>
                        <Th numeric>Sifted</Th>
                        <Th numeric>QBER</Th>
                        <Th numeric>95% CI</Th>
                      </Tr>
                    </THead>
                    <TBody>
                      {runs.map((r) => (
                        <Tr key={r.chunk}>
                          <Td className="font-mono text-xs">{`${r.folder}/chunk${String(r.chunk).padStart(2, "0")}`}</Td>
                          <Td numeric>{r.n_errors}</Td>
                          <Td numeric>{r.n_sifted}</Td>
                          <Td numeric>{r.qber.toFixed(5)}</Td>
                          <Td numeric>{`${r.ci_lo.toFixed(5)}–${r.ci_hi.toFixed(5)}`}</Td>
                        </Tr>
                      ))}
                    </TBody>
                  </Table>
                }
              >
                <IntervalPlot
                  data={data}
                  rowHeight={16}
                  yWidth={86}
                  series={[{ key: "run", label: "QBER", color: SERIES.quantum, marker: "filled" }]}
                  bands={pub.interval ? [{ from: pub.interval.lo, to: pub.interval.hi, label: "published", color: SERIES.classical }] : []}
                  marks={
                    pooled.interval
                      ? [
                          { value: pooled.interval.lo, label: "pooled lo", color: SERIES.bound },
                          { value: pooled.interval.hi, label: "pooled hi", color: SERIES.bound },
                        ]
                      : []
                  }
                  formatValue={(v) => v.toFixed(4)}
                />
              </ChartFrame>
              <p className="text-xs text-subtle">
                Runs are overdispersed (χ²/dof = {b.run_dispersion_chi2_per_dof.toFixed(1)}): per-run Clopper–Pearson intervals assume i.i.d. trials, so the pooled hull
                is the conservative interval. First-half vs second-half split differs, p = {b.holdout_p_value.toPrecision(2)}. Calibration record{" "}
                <span className="font-mono">{b.calibration_id}</span>.
              </p>
            </section>
          );
        })}
      </div>
      <dl className="grid gap-x-10 gap-y-4 border-t border-border pt-5 text-xs sm:grid-cols-3">
        <div className="grid gap-1">
          <dt className="label-mono text-subtle">Not observable from the archive</dt>
          <dd className="text-muted">{photon.not_observable.join(", ")} — left null, never filled from the paper.</dd>
        </div>
        <div className="grid gap-1">
          <dt className="label-mono text-subtle">Dataset</dt>
          <dd className="font-mono break-all text-muted">
            Zenodo {photon.dataset.zenodo_record} · {photon.dataset.license} · sha256 {middleTruncate(String(photon.dataset.sha256))}
          </dd>
        </div>
        <div className="grid gap-1">
          <dt className="label-mono text-subtle">Reproduce</dt>
          <dd className="font-mono text-muted">{photon.reproduce}</dd>
        </div>
      </dl>
    </div>
  );
}

export function ComparabilityMatrix({ pairs }: { pairs: BenchData["comparability"] }) {
  const [id, setId] = React.useState(pairs[0]?.pair_id ?? "");
  const pair = pairs.find((p) => p.pair_id === id) ?? pairs[0];
  if (!pair) return null;
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[260px_minmax(0,1fr)]">
      <div className="lg:hidden">
        <Select value={id} onValueChange={setId}>
          <SelectTrigger aria-label="Comparison pair">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {pairs.map((p) => (
              <SelectItem key={p.pair_id} value={p.pair_id}>
                {p.pair_id} · {COMPARABILITY[p.status].label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <ul role="listbox" aria-label="Comparison pairs" className="hidden content-start lg:grid">
        {pairs.map((p) => (
          <li key={p.pair_id}>
            <button
              type="button"
              role="option"
              aria-selected={p.pair_id === pair.pair_id}
              onClick={() => setId(p.pair_id)}
              className={cn(
                "relative flex w-full items-center justify-between gap-3 border-b border-hairline py-2 pr-2 pl-3 text-left text-[0.8125rem] text-muted hover:bg-surface hover:text-foreground",
                p.pair_id === pair.pair_id && "bg-surface-raised text-foreground before:absolute before:inset-y-0 before:left-0 before:w-0.5 before:bg-accent",
              )}
            >
              <span className="font-mono text-xs">{p.pair_id.replace("X11-", "")}</span>
              <span className={cn("text-xs", p.status === "INCOMPARABLE" ? "text-warn" : "text-subtle")}>{COMPARABILITY[p.status].label}</span>
            </button>
          </li>
        ))}
      </ul>
      <div className="grid min-w-0 content-start gap-4">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h3 className="font-mono text-sm text-foreground">{pair.left_protocol}</h3>
          <span className="text-xs text-subtle">vs</span>
          <span className="font-mono text-sm text-muted">{pair.right_protocol}</span>
          <span className={cn("ml-auto text-xs", pair.status === "INCOMPARABLE" ? "text-warn" : "text-muted")}>
            {COMPARABILITY[pair.status].label} — {COMPARABILITY[pair.status].hint}
          </span>
        </div>
        <Table className="min-w-[640px] table-fixed">
          <THead>
            <Tr className="hover:bg-transparent">
              <Th className="w-44">Dimension</Th>
              <Th>Classical construction</Th>
              <Th>S1 ideal (Kent 2022)</Th>
            </Tr>
          </THead>
          <TBody>
            {pair.columns.map((c) => (
              <Tr key={c.column} className="align-top">
                <Td className="h-auto py-2.5 font-mono text-[0.6875rem] text-subtle">{c.column.replace(/_/g, " ")}</Td>
                <Td className="h-auto py-2.5 text-xs text-foreground">{c.left}</Td>
                <Td className="h-auto py-2.5 text-xs text-muted">{c.right}</Td>
              </Tr>
            ))}
          </TBody>
        </Table>
      </div>
    </div>
  );
}

export function Reproducibility({ r }: { r: BenchData["reproducibility"] }) {
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-8 md:grid-cols-2">
      <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] content-start gap-2">
        <p className="label-mono text-subtle">Commands (repo root, $PY = shared venv python)</p>
        <ul className="grid grid-cols-[minmax(0,1fr)] gap-1">
          {r.commands.map((c) => (
            <li key={c} className="flex items-center gap-2 rounded-sm border border-border bg-surface px-3 py-1.5">
              <code className="min-w-0 flex-1 truncate font-mono text-xs text-foreground" title={c}>
                {c}
              </code>
              <CopyText text={c} />
            </li>
          ))}
        </ul>
      </div>
      <dl className="grid content-start gap-4 text-xs">
        <div className="grid gap-1">
          <dt className="label-mono text-subtle">Lane H records generated at</dt>
          <dd className="font-mono break-all text-muted">{r.lane_h_git_shas.join(", ")}</dd>
        </div>
        <div className="grid gap-1">
          <dt className="label-mono text-subtle">Environment lock</dt>
          <dd className="font-mono break-all text-muted">{r.environment_locks.join(", ")}</dd>
        </div>
        <div className="grid gap-1">
          <dt className="label-mono text-subtle">Evidence files</dt>
          <dd className="grid gap-0.5 font-mono text-muted">
            {r.evidence_files.map((f) => (
              <span key={f} className="break-all">
                {f}
              </span>
            ))}
          </dd>
        </div>
      </dl>
    </div>
  );
}
