"use client";

import { ArrowDown, ArrowUp, ChevronRight, Search } from "lucide-react";
import * as React from "react";
import { ChartFrame, IntervalPlot, SERIES, formatNs, type IntervalDatum } from "@/components/charts";
import { EvidenceLabel } from "@/components/ui/evidence-label";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TBody, THead, Td, Th, Tr } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import {
  COMPARABILITY,
  DEFAULT_FILTERS,
  OUTCOME,
  filterRows,
  flexibilityLabel,
  networkLabel,
  networks,
  sortRows,
  variantLabel,
  type Filters,
  type Outcome,
  type Row,
  type SortDir,
  type SortKey,
} from "./model";

const TONE = { fg: "text-foreground", info: "text-info", warn: "text-warn", danger: "text-danger" } as const;

export function OutcomeCell({ outcome }: { outcome: Outcome }) {
  const o = OUTCOME[outcome];
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-[0.8125rem]", TONE[o.tone])}>
      <span aria-hidden className="font-mono text-[0.625rem]">
        {o.glyph}
      </span>
      {o.label}
    </span>
  );
}

function Segmented<T extends string>({ label, value, options, onChange }: { label: string; value: T; options: { value: T; label: string }[]; onChange: (v: T) => void }) {
  return (
    <div role="group" aria-label={label} className="inline-flex h-8 items-center rounded-sm border border-border-strong bg-surface p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "h-full rounded-xs px-2.5 text-xs whitespace-nowrap text-muted transition-colors duration-[var(--duration-fast)] hover:text-foreground",
            value === o.value && "bg-surface-raised text-foreground",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function SortHeader({ k, label, sort, onSort, numeric, className }: { k: SortKey; label: string; sort: { k: SortKey; dir: SortDir }; onSort: (k: SortKey) => void; numeric?: boolean; className?: string }) {
  const active = sort.k === k;
  const Icon = sort.dir === "asc" ? ArrowUp : ArrowDown;
  return (
    <Th numeric={numeric} aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : "none"} className={className}>
      <button type="button" onClick={() => onSort(k)} className={cn("inline-flex items-center gap-1 uppercase hover:text-foreground", active && "text-foreground")}>
        {label}
        <Icon className={cn("size-3", active ? "opacity-100" : "opacity-0")} aria-hidden />
      </button>
    </Th>
  );
}

function Lat({ q, reason }: { q: Row["local_validation"]; reason?: string | null }) {
  if (!q || q.value === null) {
    return <span className="font-sans text-xs text-subtle italic" title={reason ?? undefined}>{reason ? "not on matched topology" : "—"}</span>;
  }
  return <span title={`${q.value} ns · ${q.source}`}>{formatNs(q.value)}</span>;
}

function DetailItem({ k, children, mono }: { k: string; children: React.ReactNode; mono?: boolean }) {
  return (
    <div className="grid min-w-0 gap-1">
      <dt className="label-mono text-subtle">{k}</dt>
      <dd className={cn("text-[0.8125rem] break-words text-muted", mono && "font-mono text-xs")}>{children}</dd>
    </div>
  );
}

function RowDetail({ r }: { r: Row }) {
  return (
    <dl className="grid gap-x-8 gap-y-4 py-4 sm:grid-cols-2 lg:grid-cols-3">
      <DetailItem k="Double spend">{r.double_spend.detail || OUTCOME[r.double_spend.outcome].label}</DetailItem>
      <DetailItem k="Adversary">{r.adversary}</DetailItem>
      <DetailItem k="Trust model">{r.trust_model}</DetailItem>
      <DetailItem k="Trusted hardware">{r.trusted_hardware}</DetailItem>
      <DetailItem k="Pre-distribution">{r.pre_distribution}</DetailItem>
      <DetailItem k="Privacy">{r.privacy}</DetailItem>
      {r.cross_check ? <DetailItem k="Network cross-check">{formatNs(r.cross_check.value ?? 0)} · {r.cross_check.note}</DetailItem> : null}
      {r.pre_presentation_commit ? <DetailItem k="Commit before presentation">{r.pre_presentation_commit.note}</DetailItem> : null}
      {r.latency_unavailable_reason ? <DetailItem k="Latency">{r.latency_unavailable_reason}</DetailItem> : null}
      {r.latency_basis ? <DetailItem k="Latency basis">{r.latency_basis}</DetailItem> : null}
      <DetailItem k="Comparability">
        {COMPARABILITY[r.comparability_status].label}
        {r.comparability_pair ? <span className="font-mono text-xs"> · {r.comparability_pair}</span> : null} — {COMPARABILITY[r.comparability_status].hint}
      </DetailItem>
      <DetailItem k="Evidence">
        <EvidenceLabel kind={r.evidence_kind} /> <span className="text-xs">{r.method}</span>
      </DetailItem>
      <DetailItem k="Record id" mono>{r.id}</DetailItem>
      {r.record_git_sha ? <DetailItem k="Lane H git sha" mono>{r.record_git_sha}</DetailItem> : null}
      <DetailItem k="Reproduce" mono>{r.reproduce}</DetailItem>
      {r.sources.length ? <DetailItem k="Sources">{r.sources.join(" · ")}</DetailItem> : null}
    </dl>
  );
}

export function Explorer({ rows }: { rows: Row[] }) {
  const nets = React.useMemo(() => networks(rows), [rows]);
  const [f, setF] = React.useState<Filters>({ ...DEFAULT_FILTERS, network: nets[0] ?? "all" });
  const [sort, setSort] = React.useState<{ k: SortKey; dir: SortDir }>({ k: "construction", dir: "asc" });
  const [open, setOpen] = React.useState<Set<string>>(new Set());
  const shown = React.useMemo(() => sortRows(filterRows(rows, f), sort.k, sort.dir), [rows, f, sort]);
  const onSort = (k: SortKey) => setSort((s) => ({ k, dir: s.k === k && s.dir === "asc" ? "desc" : "asc" }));
  const toggle = (id: string) =>
    setOpen((o) => {
      const n = new Set(o);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });

  const plot: IntervalDatum[] = shown
    .filter((r) => r.family === "classical" && r.local_validation?.value != null)
    .flatMap((r) => {
      const name = `${r.code} ${variantLabel(r.variant)}${f.network === "all" ? ` · ${networkLabel(r.network_id)}` : ""}`;
      const out: IntervalDatum[] = [{ label: name, series: "local", value: r.local_validation!.value!, detail: [["record", r.id.slice(-12)]] }];
      if (r.pre_presentation_commit?.value) out.push({ label: `${name} · commit`, series: "commit", value: r.pre_presentation_commit.value });
      return out;
    });

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-10">
      <div className="grid grid-cols-[minmax(0,1fr)] gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <Segmented
            label="Network"
            value={f.network}
            onChange={(network) => setF({ ...f, network })}
            options={[...nets.map((n) => ({ value: n, label: networkLabel(n) })), { value: "all", label: "All networks" }]}
          />
          <Segmented
            label="Family"
            value={f.family}
            onChange={(family) => setF({ ...f, family })}
            options={[
              { value: "all", label: "All" },
              { value: "quantum", label: "Quantum" },
              { value: "classical", label: "Classical" },
            ]}
          />
          <Select value={f.outcome} onValueChange={(v) => setF({ ...f, outcome: v as Filters["outcome"] })}>
            <SelectTrigger aria-label="Double-spend outcome" className="w-auto min-w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Any double-spend outcome</SelectItem>
              {(Object.keys(OUTCOME) as Outcome[]).map((o) => (
                <SelectItem key={o} value={o}>
                  {OUTCOME[o].label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={f.comparability} onValueChange={(v) => setF({ ...f, comparability: v as Filters["comparability"] })}>
            <SelectTrigger aria-label="Comparability" className="w-auto min-w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Any comparability</SelectItem>
              {(["REFERENCE", "QUALIFIED", "INCOMPARABLE", "NO_PAIR"] as const).map((c) => (
                <SelectItem key={c} value={c}>
                  {COMPARABILITY[c].label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="relative w-full sm:ml-auto sm:w-56">
            <Search className="pointer-events-none absolute top-2 left-2.5 size-4 text-subtle" aria-hidden />
            <Input aria-label="Search constructions" placeholder="Search" value={f.query} onChange={(e) => setF({ ...f, query: e.target.value })} className="pl-8" />
          </div>
        </div>
        <p className="text-xs text-subtle" aria-live="polite">
          {shown.length} of {rows.length} rows · classical latencies are MODELLED lower bounds (light-cone propagation + declared processing) on SYNTHETIC networks
        </p>

        <Table className="min-w-[1080px]">
          <THead>
            <Tr className="hover:bg-transparent">
              <SortHeader k="construction" label="Construction" sort={sort} onSort={onSort} />
              <SortHeader k="outcome" label="Double spend" sort={sort} onSort={onSort} />
              <SortHeader k="local" label="Local validation" sort={sort} onSort={onSort} numeric />
              <SortHeader k="commit" label="Commit before use" sort={sort} onSort={onSort} numeric />
              <Th>Trust · hardware</Th>
              <SortHeader k="flexibility" label="Flexibility" sort={sort} onSort={onSort} />
              <Th>Privacy</Th>
              <SortHeader k="comparability" label="vs S1" sort={sort} onSort={onSort} />
            </Tr>
          </THead>
          <TBody>
            {shown.map((r) => {
              const isOpen = open.has(r.id);
              return (
                <React.Fragment key={r.id}>
                  <Tr data-state={isOpen ? "selected" : undefined}>
                    <Td className="max-w-64">
                      <button type="button" onClick={() => toggle(r.id)} aria-expanded={isOpen} className="flex items-start gap-2 text-left">
                        <ChevronRight className={cn("mt-0.5 size-3.5 shrink-0 text-subtle transition-transform duration-[var(--duration-fast)]", isOpen && "rotate-90")} aria-hidden />
                        <span className="grid gap-0.5">
                          <span className="text-[0.8125rem] text-foreground">
                            <span className="font-mono">{r.code}</span> {r.label.replace(/^\S+\s/, "")}
                          </span>
                          <span className="font-mono text-[0.6875rem] text-subtle">
                            {r.family === "quantum" ? "ideal model · theorem" : f.network === "all" ? `${variantLabel(r.variant)} · ${networkLabel(r.network_id)}` : variantLabel(r.variant)}
                          </span>
                        </span>
                      </button>
                    </Td>
                    <Td>
                      <OutcomeCell outcome={r.double_spend.outcome} />
                    </Td>
                    <Td numeric>
                      <Lat q={r.local_validation} reason={r.latency_unavailable_reason} />
                    </Td>
                    <Td numeric>
                      <Lat q={r.pre_presentation_commit} reason={r.family === "quantum" ? r.latency_unavailable_reason : null} />
                    </Td>
                    <Td className="max-w-60">
                      <span className="line-clamp-2 text-xs text-muted" title={`${r.trust_model} · ${r.trusted_hardware}`}>
                        {r.trust_model}
                      </span>
                    </Td>
                    <Td className="text-xs whitespace-nowrap text-muted">{flexibilityLabel(r.flexibility)}</Td>
                    <Td className="max-w-52">
                      <span className="line-clamp-2 text-xs text-muted" title={r.privacy}>
                        {r.privacy}
                      </span>
                    </Td>
                    <Td className="whitespace-nowrap">
                      <span className="text-xs text-foreground" title={COMPARABILITY[r.comparability_status].hint}>
                        {COMPARABILITY[r.comparability_status].label}
                      </span>
                      {r.comparability_pair ? <span className="block font-mono text-[0.6875rem] text-subtle">{r.comparability_pair}</span> : null}
                    </Td>
                  </Tr>
                  {isOpen ? (
                    <tr className="border-b border-hairline bg-surface/40">
                      <td colSpan={8} className="px-0 pl-6">
                        <RowDetail r={r} />
                      </td>
                    </tr>
                  ) : null}
                </React.Fragment>
              );
            })}
          </TBody>
        </Table>
        {shown.length === 0 ? <p className="py-6 text-sm text-muted">No construction matches these filters.</p> : null}
      </div>

      {plot.length ? (
        <ChartFrame
          title="Classical latency, presentation to local accept"
          summary={`Modelled local validation latency for ${plot.length} classical rows on a log scale; S1 is absent because no matched-topology run exists.`}
          legend={[
            { label: "local validation (MODELLED)", color: SERIES.classical, shape: "dot" },
            { label: "Stage-II commit before presentation", color: SERIES.classical, shape: "ring" },
          ]}
          caption="Log scale. Lower bounds: light-cone link delay plus declared processing (site 10 µs, coordinator 50 µs). S1 has no point here: its matched-topology timing is lane GH (not merged), so the two families never share this axis."
          table={
            <Table>
              <THead>
                <Tr>
                  <Th>Row</Th>
                  <Th>Quantity</Th>
                  <Th numeric>ns</Th>
                </Tr>
              </THead>
              <TBody>
                {plot.map((d) => (
                  <Tr key={d.label + d.series}>
                    <Td className="text-xs">{d.label}</Td>
                    <Td className="text-xs text-muted">{d.series === "local" ? "local validation" : "commit before presentation"}</Td>
                    <Td numeric>{d.value}</Td>
                  </Tr>
                ))}
              </TBody>
            </Table>
          }
        >
          <IntervalPlot
            data={plot}
            scale="log"
            yWidth={200}
            series={[
              { key: "local", label: "local validation", color: SERIES.classical, marker: "filled" },
              { key: "commit", label: "commit before presentation", color: SERIES.classical, marker: "ring" },
            ]}
            formatValue={formatNs}
          />
        </ChartFrame>
      ) : null}
    </div>
  );
}
