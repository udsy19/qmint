"use client";

import * as React from "react";
import { CartesianGrid, ErrorBar, ReferenceArea, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS_TICK, ChartTooltipBody, GRID_STROKE, useNarrow, useReducedMotion } from "./chart-frame";
import { linearDomain, linearTicks, logDomain, logTicks } from "./scale";

export interface IntervalDatum {
  /** Row label (category axis). Must be unique per row. */
  label: string;
  series: string;
  value: number;
  lo?: number | null;
  hi?: number | null;
  /** Extra tooltip lines. */
  detail?: [string, string][];
}

export interface IntervalSeries {
  key: string;
  label: string;
  color: string;
  /** filled = measured/published value, ring = modelled/derived value. */
  marker?: "filled" | "ring" | "diamond";
}

export interface ReferenceBand {
  from: number;
  to: number;
  label: string;
  color: string;
}

export interface ReferenceMark {
  value: number;
  label: string;
  color: string;
  dashed?: boolean;
}

type Shape = (props: { cx?: number; cy?: number }) => React.ReactElement;

function marker(kind: IntervalSeries["marker"], color: string): Shape {
  const M = ({ cx = 0, cy = 0 }: { cx?: number; cy?: number }) =>
    kind === "ring" ? (
      <circle cx={cx} cy={cy} r={3.5} fill="var(--background)" stroke={color} strokeWidth={1.5} />
    ) : kind === "diamond" ? (
      <path d={`M${cx} ${cy - 4.5}L${cx + 4.5} ${cy}L${cx} ${cy + 4.5}L${cx - 4.5} ${cy}Z`} fill={color} />
    ) : (
      <circle cx={cx} cy={cy} r={3.5} fill={color} />
    );
  M.displayName = "IntervalMarker";
  return M;
}

/**
 * Dot + interval plot: one row per datum, value on a linear or log x-axis, error bars from [lo, hi],
 * optional vertical reference bands (e.g. a published ± range) and reference lines (bounds).
 * Generic: used for photon QBER per run, latency case studies, and any estimate-with-interval list.
 */
export function IntervalPlot({
  data,
  series,
  scale = "linear",
  bands = [],
  marks = [],
  formatValue = (v: number) => String(v),
  rowHeight = 22,
  hideRowLabels = false,
  yWidth = 120,
}: {
  data: IntervalDatum[];
  series: IntervalSeries[];
  scale?: "linear" | "log";
  bands?: ReferenceBand[];
  marks?: ReferenceMark[];
  formatValue?: (v: number) => string;
  rowHeight?: number;
  hideRowLabels?: boolean;
  yWidth?: number;
}) {
  const reduced = useReducedMotion();
  const narrow = useNarrow();
  const labelWidth = narrow ? Math.min(yWidth, 128) : yWidth;
  const all = data.flatMap((d) => [d.value, d.lo ?? d.value, d.hi ?? d.value]).concat(bands.flatMap((b) => [b.from, b.to]), marks.map((m) => m.value));
  const domain = (scale === "log" ? logDomain(all) : linearDomain(all)) ?? [0, 1];
  const ticks = scale === "log" ? logTicks(domain[0], domain[1]) : linearTicks(domain[0], domain[1], 5);
  // Rows sit on a numeric index axis (0 at the top) so the input order is the visual order.
  const rows = data.map((d, i) => ({ ...d, row: i, err: [d.value - (d.lo ?? d.value), (d.hi ?? d.value) - d.value] }));
  const indices = rows.map((r) => r.row);
  return (
    <ResponsiveContainer width="100%" height={Math.max(120, rows.length * rowHeight + 48)} initialDimension={{ width: 640, height: 240 }}>
      <ScatterChart margin={{ top: 8, right: 28, bottom: 8, left: 0 }}>
        <CartesianGrid horizontal={false} stroke={GRID_STROKE} />
        <XAxis
          type="number"
          dataKey="value"
          scale={scale}
          domain={domain}
          ticks={ticks}
          allowDataOverflow
          tickFormatter={formatValue}
          tick={AXIS_TICK}
          stroke="var(--border)"
          tickLine={false}
        />
        <YAxis
          type="number"
          dataKey="row"
          reversed
          domain={[-0.6, rows.length - 0.4]}
          ticks={indices}
          tickFormatter={(i: number) => rows[i]?.label ?? ""}
          width={hideRowLabels ? 0 : labelWidth}
          tick={hideRowLabels ? false : { ...AXIS_TICK, fill: "var(--muted)" }}
          tickLine={false}
          axisLine={false}
          interval={0}
        />
        {bands.map((b) => (
          <ReferenceArea key={b.label} x1={b.from} x2={b.to} fill={b.color} fillOpacity={0.12} stroke={b.color} strokeOpacity={0.35} ifOverflow="extendDomain" />
        ))}
        {marks.map((m) => (
          <ReferenceLine key={m.label} x={m.value} stroke={m.color} strokeDasharray={m.dashed === false ? undefined : "4 3"} ifOverflow="extendDomain" />
        ))}
        <Tooltip
          cursor={false}
          isAnimationActive={false}
          content={({ active, payload }) => {
            const p = active && payload?.[0]?.payload as (IntervalDatum & { err: number[] }) | undefined;
            if (!p) return null;
            const s = series.find((x) => x.key === p.series);
            return (
              <ChartTooltipBody
                title={p.label}
                rows={[
                  [s?.label ?? p.series, formatValue(p.value)],
                  ...(p.lo != null && p.hi != null ? ([["interval", `${formatValue(p.lo)} – ${formatValue(p.hi)}`]] as [string, string][]) : []),
                  ...(p.detail ?? []),
                ]}
              />
            );
          }}
        />
        {series.map((s) => (
          <Scatter key={s.key} name={s.label} data={rows.filter((r) => r.series === s.key)} shape={marker(s.marker, s.color)} isAnimationActive={!reduced}>
            <ErrorBar dataKey="err" direction="x" width={4} stroke={s.color} strokeWidth={1.25} />
          </Scatter>
        ))}
      </ScatterChart>
    </ResponsiveContainer>
  );
}
