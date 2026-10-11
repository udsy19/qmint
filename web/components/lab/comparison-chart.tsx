import * as React from "react";
import { EvidenceLabel } from "@/components/ui/evidence-label";
import { formatNumber, NO_BOUND } from "@/lib/format";
import { cn } from "@/lib/utils";
import { axisPosition, axisTicks, type Comparison, type ComparisonRow } from "./comparison";
import { METHOD_TEXT } from "./lab-api";

function pct(x: number): string {
  return `${(x * 100).toFixed(3)}%`;
}

function tickText(v: number, scale: Comparison["scale"]): string {
  if (scale === "linear") return v === 0 ? "0" : String(v);
  const e = Math.round(Math.log10(v));
  return e === 0 ? "1" : `10${e < 0 ? "⁻" : ""}${String(Math.abs(e)).replace(/\d/g, (c) => "⁰¹²³⁴⁵⁶⁷⁸⁹"[Number(c)] ?? c)}`;
}

/**
 * Dot plot of every probability for one attack, grouped Analytic / Simulated / Hardware. The W1
 * theorem bound (when one applies) is a dashed amber rule through every row, so "is anything above
 * the bound?" is answered at a glance. CIs are whiskers; the certified SDP optimum is a bracket.
 */
export function ComparisonChart({ c, className }: { c: Comparison; className?: string }) {
  const ticks = axisTicks(c.scale, c.min);
  const boundX = c.bound != null ? axisPosition(c.bound, c.scale, c.min) : null;
  return (
    <figure className={cn("grid gap-6", className)}>
      {c.groups.map((g) => (
        <section key={g.tier} aria-labelledby={`cmp-${g.tier}`} className="grid gap-1">
          <header className="flex flex-wrap items-baseline gap-x-3 border-b border-border pb-2">
            <h3 id={`cmp-${g.tier}`} className="label-mono text-foreground">
              {g.title}
            </h3>
            <p className="text-xs text-subtle">{g.caption}</p>
          </header>
          <ul className="grid">
            {g.rows.map((r) => (
              <Row key={r.id} r={r} c={c} boundX={boundX} />
            ))}
          </ul>
        </section>
      ))}
      <div aria-hidden className="grid grid-cols-1 md:grid-cols-[minmax(0,15rem)_minmax(0,1fr)_9.5rem] md:gap-x-4">
        <span className="hidden md:block" />
        <div className="relative mx-1.5 h-5">
          {ticks.map((t) => (
            <span key={t} className="tnum absolute -translate-x-1/2 font-mono text-[0.625rem] text-chart-axis" style={{ left: pct(axisPosition(t, c.scale, c.min)) }}>
              {tickText(t, c.scale)}
            </span>
          ))}
        </div>
      </div>
      <figcaption className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-subtle">
        <span className="inline-flex items-center gap-1.5">
          <span className="size-2 rounded-full bg-foreground" aria-hidden /> point value
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-px w-4 bg-muted" aria-hidden /> 95% interval / certified bracket
        </span>
        {boundX !== null ? (
          <span className="inline-flex items-center gap-1.5">
            <span className="h-3 border-l border-dashed border-chart-3" aria-hidden /> W1 theorem bound
          </span>
        ) : null}
        <span>{c.scale === "log" ? "log scale" : "linear scale"} · probability</span>
      </figcaption>
    </figure>
  );
}

function Row({ r, c, boundX }: { r: ComparisonRow; c: Comparison; boundX: number | null }) {
  const x = r.value != null ? axisPosition(r.value, c.scale, c.min) : null;
  const lo = r.lo != null ? axisPosition(r.lo, c.scale, c.min) : null;
  const hi = r.hi != null ? axisPosition(r.hi, c.scale, c.min) : null;
  const isBound = r.role === "bound";
  const isCounterfeit = r.role === "counterfeit";
  return (
    <li
      data-row={r.id}
      className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 border-b border-hairline py-2.5 md:grid-cols-[minmax(0,15rem)_minmax(0,1fr)_9.5rem]"
    >
      <div className="col-span-1 grid min-w-0 gap-1 md:col-span-1">
        <span className={cn("text-sm", isCounterfeit ? "text-foreground" : "text-muted")}>{r.label}</span>
        <span className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
          <EvidenceLabel kind={r.q.evidence_kind} size="xs" />
          <span className="font-mono text-[0.625rem] text-subtle">{METHOD_TEXT[r.q.method]}</span>
        </span>
      </div>
      <div className="relative order-3 col-span-2 mx-1.5 h-5 md:order-none md:col-span-1">
        <span aria-hidden className="absolute inset-x-0 top-1/2 h-px bg-chart-grid" />
        {boundX !== null ? <span aria-hidden className="absolute inset-y-0 border-l border-dashed border-chart-3/80" style={{ left: pct(boundX) }} /> : null}
        {lo !== null && hi !== null ? (
          <span
            aria-hidden
            className={cn("absolute top-1/2 -translate-y-1/2 bg-muted", r.role === "sdp" ? "h-2 min-w-1 rounded-[1px] bg-info/70" : "h-px")}
            style={{ left: pct(lo), width: `max(1px, ${pct(hi - lo)})` }}
          />
        ) : null}
        {x !== null && r.role !== "sdp" ? (
          <span
            aria-hidden
            className={cn(
              "absolute top-1/2 -translate-x-1/2 -translate-y-1/2 transition-[left] duration-[var(--duration-slow)] ease-out",
              isBound ? "h-3 w-0.5 bg-chart-3" : "size-2 rounded-full",
              !isBound && (isCounterfeit ? "bg-foreground" : "bg-muted"),
            )}
            style={{ left: pct(x) }}
          />
        ) : null}
        {x === null ? <span className="absolute top-1/2 left-0 -translate-y-1/2 text-xs text-subtle italic">{r.tier === "hardware" ? "not run" : "—"}</span> : null}
      </div>
      <div className="order-2 text-right md:order-none">
        <span className={cn("tnum font-mono text-sm whitespace-nowrap", r.role === "sdp" && "text-xs", r.value == null ? "text-xs text-muted italic" : "text-foreground")}>
          {r.role === "sdp" && r.lo != null && r.hi != null
            ? `${formatNumber(r.lo, { sig: 4 })} – ${formatNumber(r.hi, { sig: 6 })}`
            : r.value == null
              ? r.tier === "hardware"
                ? "not run"
                : NO_BOUND
              : formatNumber(r.value, { sig: 4 })}
        </span>
        {r.lo != null && r.hi != null && r.role !== "sdp" ? (
          <span className="tnum block font-mono text-[0.625rem] text-subtle">
            [{formatNumber(r.lo, { sig: 3 })}, {formatNumber(r.hi, { sig: 3 })}]
          </span>
        ) : null}
      </div>
    </li>
  );
}
