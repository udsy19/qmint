"use client";

import { Area, CartesianGrid, ComposedChart, Line, ReferenceDot, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS_TICK, ChartTooltipBody, GRID_STROKE, useReducedMotion } from "./chart-frame";
import { linearDomain, linearTicks, logTicks } from "./scale";

export interface LineSeries {
  key: string;
  label: string;
  color: string;
  dashed?: boolean;
  /** Optional CI band: data keys of the lower and upper band edges. */
  band?: { lo: string; hi: string };
}

export interface HLine {
  y: number;
  label: string;
  color: string;
}

export interface VLine {
  x: number;
  label: string;
  color: string;
}

/**
 * Line chart with optional confidence bands, horizontal bound/target lines and vertical markers.
 * x and y may each be linear or log. Generic: used for bound-vs-size curves (y in log10 units),
 * and for any series with a CI band.
 */
export function LineBandChart({
  data,
  x,
  series,
  hlines = [],
  vlines = [],
  xScale = "linear",
  yScale = "linear",
  yDomain,
  formatX = (v: number) => String(v),
  formatY = (v: number) => String(v),
  xLabel,
  height = 260,
}: {
  data: Record<string, number | null>[];
  x: string;
  series: LineSeries[];
  hlines?: HLine[];
  vlines?: VLine[];
  xScale?: "linear" | "log";
  yScale?: "linear" | "log";
  yDomain?: [number, number];
  formatX?: (v: number) => string;
  formatY?: (v: number) => string;
  xLabel?: string;
  height?: number;
}) {
  const reduced = useReducedMotion();
  const xs = data.map((d) => d[x]).filter((v): v is number => typeof v === "number");
  const xTicks = xScale === "log" && xs.length ? logTicks(Math.min(...xs), Math.max(...xs)) : undefined;
  const ys = data.flatMap((d) => series.map((s) => d[s.key])).filter((v): v is number => typeof v === "number").concat(hlines.map((h) => h.y));
  const yd = yDomain ?? (yScale === "linear" ? linearDomain(ys, 0.04) : null);
  const yTicks = yScale === "linear" && yd ? linearTicks(yd[0], yd[1], 4) : undefined;
  const banded = data.map((d) => {
    const row: Record<string, unknown> = { ...d };
    for (const s of series) if (s.band) row[`${s.key}__band`] = [d[s.band.lo], d[s.band.hi]];
    return row;
  });
  return (
    <ResponsiveContainer width="100%" height={height} initialDimension={{ width: 640, height }}>
      <ComposedChart data={banded} margin={{ top: 12, right: 20, bottom: xLabel ? 18 : 4, left: 0 }}>
        <CartesianGrid vertical={false} stroke={GRID_STROKE} />
        <XAxis
          type="number"
          dataKey={x}
          scale={xScale}
          domain={["dataMin", "dataMax"]}
          ticks={xTicks}
          tickFormatter={formatX}
          tick={AXIS_TICK}
          stroke="var(--border)"
          tickLine={false}
          label={xLabel ? { value: xLabel, position: "insideBottom", offset: -10, ...AXIS_TICK } : undefined}
        />
        <YAxis scale={yScale} domain={yd ?? ["auto", "auto"]} ticks={yTicks} tickFormatter={formatY} tick={AXIS_TICK} axisLine={false} tickLine={false} width={56} allowDataOverflow />
        <Tooltip
          isAnimationActive={false}
          cursor={{ stroke: "var(--border-strong)" }}
          content={({ active, payload, label }) =>
            active && payload?.length ? (
              <ChartTooltipBody
                title={`${xLabel ?? x} = ${formatX(Number(label))}`}
                rows={series.flatMap((s) => {
                  const v = payload[0]?.payload?.[s.key];
                  return typeof v === "number" ? ([[s.label, formatY(v)]] as [string, string][]) : [];
                })}
              />
            ) : null
          }
        />
        {series.map((s) =>
          s.band ? (
            <Area key={`${s.key}-band`} dataKey={`${s.key}__band`} stroke="none" fill={s.color} fillOpacity={0.08} isAnimationActive={!reduced} />
          ) : null,
        )}
        {hlines.map((h) => (
          <ReferenceLine key={h.label} y={h.y} stroke={h.color} strokeDasharray="4 3" ifOverflow="extendDomain"
            label={{ value: h.label, position: "insideTopRight", fill: h.color, fontSize: 11, fontFamily: "var(--font-mono)" }} />
        ))}
        {vlines.map((v) => (
          <ReferenceLine key={v.label} x={v.x} stroke={v.color} strokeDasharray="2 3" ifOverflow="extendDomain"
            label={{ value: v.label, position: "insideTopLeft", fill: v.color, fontSize: 11, fontFamily: "var(--font-mono)" }} />
        ))}
        {vlines.flatMap((v) => hlines.map((h) => <ReferenceDot key={`${v.label}-${h.label}`} x={v.x} y={h.y} r={3} fill={v.color} stroke="none" />))}
        {series.map((s) => (
          <Line key={s.key} type="linear" dataKey={s.key} stroke={s.color} strokeWidth={1.5} strokeDasharray={s.dashed ? "4 3" : undefined} dot={false} isAnimationActive={!reduced} connectNulls={false} />
        ))}
      </ComposedChart>
    </ResponsiveContainer>
  );
}
