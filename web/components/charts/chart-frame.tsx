"use client";

import { Table2 } from "lucide-react";
import * as React from "react";
import { cn } from "@/lib/utils";

/** Series colours (DESIGN_SYSTEM §8): 1 = QMint/quantum (mint), 2 = comparison/classical, 3 = bounds, 4 = extra. */
export const SERIES = {
  quantum: "var(--chart-1)",
  classical: "var(--chart-2)",
  bound: "var(--chart-3)",
  extra: "var(--chart-4)",
  muted: "var(--chart-axis)",
} as const;

export const AXIS_TICK = { fill: "var(--chart-axis)", fontSize: 11, fontFamily: "var(--font-mono)" } as const;
export const GRID_STROKE = "var(--chart-grid)";

export type LegendShape = "dot" | "ring" | "line" | "dash" | "band" | "square";

export interface LegendItem {
  label: string;
  color: string;
  shape: LegendShape;
}

function Glyph({ shape, color }: { shape: LegendShape; color: string }) {
  return (
    <svg viewBox="0 0 12 8" className="h-2 w-3 shrink-0" aria-hidden>
      {shape === "dot" && <circle cx="6" cy="4" r="3" fill={color} />}
      {shape === "ring" && <circle cx="6" cy="4" r="2.5" fill="none" stroke={color} strokeWidth="1.25" />}
      {shape === "square" && <rect x="3" y="1" width="6" height="6" fill={color} />}
      {shape === "line" && <path d="M0 4h12" stroke={color} strokeWidth="1.5" />}
      {shape === "dash" && <path d="M0 4h12" stroke={color} strokeWidth="1.25" strokeDasharray="3 2" />}
      {shape === "band" && <rect x="0" y="1" width="12" height="6" fill={color} opacity="0.25" />}
    </svg>
  );
}

/** Mono text legend with 8px glyphs (never coloured boxes). */
export function ChartLegend({ items, className }: { items: LegendItem[]; className?: string }) {
  return (
    <ul className={cn("flex flex-wrap gap-x-4 gap-y-1.5", className)}>
      {items.map((it) => (
        <li key={it.label} className="flex items-center gap-1.5 font-mono text-[0.6875rem] text-muted">
          <Glyph shape={it.shape} color={it.color} />
          {it.label}
        </li>
      ))}
    </ul>
  );
}

/**
 * Figure wrapper for every chart: title, legend, the plot (role="img" with a textual summary) and a
 * data-table toggle so the numbers are always reachable without the picture (a11y + verification).
 */
export function ChartFrame({
  title,
  summary,
  legend,
  caption,
  table,
  height,
  className,
  children,
}: {
  title: React.ReactNode;
  /** One-sentence textual summary of what the chart shows (screen readers, alt text). */
  summary: string;
  legend?: LegendItem[];
  caption?: React.ReactNode;
  /** Accessible data-table alternative. */
  table?: React.ReactNode;
  /** Fixed plot height; omit when the chart sizes itself. */
  height?: number;
  className?: string;
  children: React.ReactNode;
}) {
  const [showTable, setShowTable] = React.useState(false);
  const id = React.useId();
  return (
    <figure className={cn("grid min-w-0 gap-3", className)}>
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <figcaption className="text-sm font-medium text-foreground">{title}</figcaption>
        {table ? (
          <button
            type="button"
            aria-expanded={showTable}
            aria-controls={id}
            onClick={() => setShowTable((s) => !s)}
            className="inline-flex items-center gap-1.5 rounded-xs font-mono text-[0.6875rem] tracking-[0.06em] text-subtle uppercase hover:text-foreground"
          >
            <Table2 className="size-3.5" aria-hidden />
            {showTable ? "Hide data" : "Show data"}
          </button>
        ) : null}
      </div>
      {legend?.length ? <ChartLegend items={legend} /> : null}
      <div role="img" aria-label={summary} style={height ? { height } : undefined} className="min-w-0">
        {children}
      </div>
      {caption ? <p className="text-xs text-subtle">{caption}</p> : null}
      {table ? (
        <div id={id} hidden={!showTable}>
          {table}
        </div>
      ) : null}
    </figure>
  );
}

const RM_QUERY = "(prefers-reduced-motion: reduce)";
function subscribeReducedMotion(cb: () => void) {
  const mq = typeof window !== "undefined" ? window.matchMedia?.(RM_QUERY) : undefined;
  mq?.addEventListener?.("change", cb);
  return () => mq?.removeEventListener?.("change", cb);
}

/** recharts animation gate: final state immediately under reduced motion (and during SSR). */
export function useReducedMotion(): boolean {
  return React.useSyncExternalStore(
    subscribeReducedMotion,
    () => window.matchMedia?.(RM_QUERY).matches ?? true,
    () => true,
  );
}

/** Shared tooltip body (mono, overlay surface). */
export function ChartTooltipBody({ title, rows }: { title: React.ReactNode; rows: [React.ReactNode, React.ReactNode][] }) {
  return (
    <div className="grid min-w-44 gap-1 rounded-md bg-surface-overlay px-3 py-2 text-xs shadow-overlay">
      <p className="font-medium text-foreground">{title}</p>
      {rows.map(([k, v], i) => (
        <p key={i} className="flex justify-between gap-4">
          <span className="text-subtle">{k}</span>
          <span className="tnum font-mono text-foreground">{v}</span>
        </p>
      ))}
    </div>
  );
}

const NARROW_QUERY = "(max-width: 639px)";
function subscribeNarrow(cb: () => void) {
  const mq = typeof window !== "undefined" ? window.matchMedia?.(NARROW_QUERY) : undefined;
  mq?.addEventListener?.("change", cb);
  return () => mq?.removeEventListener?.("change", cb);
}

/** True below the `sm` breakpoint: charts shrink their label gutters. */
export function useNarrow(): boolean {
  return React.useSyncExternalStore(subscribeNarrow, () => window.matchMedia?.(NARROW_QUERY).matches ?? false, () => false);
}
