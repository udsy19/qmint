"use client";

import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS_TICK, ChartTooltipBody, GRID_STROKE, useReducedMotion } from "./chart-frame";
import { linearDomain, logDomain, logTicks, paretoFrontier, type ParetoPoint } from "./scale";

export interface ScatterDatum extends ParetoPoint {
  label: string;
  group: string;
}

export interface ScatterGroup {
  key: string;
  label: string;
  color: string;
  hollow?: boolean;
}

/**
 * Scatter with an optional Pareto frontier (minimising x and y). Generic: any two costs where
 * lower is better. The frontier is a geometric fact about the plotted points, not a ranking.
 */
export function ScatterPareto({
  data,
  groups,
  xScale = "linear",
  yScale = "linear",
  formatX = (v: number) => String(v),
  formatY = (v: number) => String(v),
  xLabel,
  yLabel,
  frontier = true,
  frontierColor = "var(--chart-3)",
  height = 280,
}: {
  data: ScatterDatum[];
  groups: ScatterGroup[];
  xScale?: "linear" | "log";
  yScale?: "linear" | "log";
  formatX?: (v: number) => string;
  formatY?: (v: number) => string;
  xLabel?: string;
  yLabel?: string;
  frontier?: boolean;
  frontierColor?: string;
  height?: number;
}) {
  const reduced = useReducedMotion();
  const dom = (vals: number[], s: "linear" | "log") => (s === "log" ? logDomain(vals) : linearDomain(vals)) ?? [0, 1];
  const xd = dom(data.map((d) => d.x), xScale);
  const yd = dom(data.map((d) => d.y), yScale);
  const front = frontier ? paretoFrontier(data) : [];
  return (
    <ResponsiveContainer width="100%" height={height} initialDimension={{ width: 640, height }}>
      <ScatterChart margin={{ top: 12, right: 20, bottom: xLabel ? 18 : 4, left: 0 }}>
        <CartesianGrid stroke={GRID_STROKE} vertical={false} />
        <XAxis type="number" dataKey="x" scale={xScale} domain={xd} ticks={xScale === "log" ? logTicks(xd[0], xd[1]) : undefined} tickFormatter={formatX}
          tick={AXIS_TICK} stroke="var(--border)" tickLine={false} allowDataOverflow
          label={xLabel ? { value: xLabel, position: "insideBottom", offset: -10, ...AXIS_TICK } : undefined} />
        <YAxis type="number" dataKey="y" scale={yScale} domain={yd} ticks={yScale === "log" ? logTicks(yd[0], yd[1]) : undefined} tickFormatter={formatY}
          tick={AXIS_TICK} axisLine={false} tickLine={false} width={64} allowDataOverflow
          label={yLabel ? { value: yLabel, angle: -90, position: "insideLeft", ...AXIS_TICK, dy: 40 } : undefined} />
        <Tooltip
          isAnimationActive={false}
          cursor={false}
          content={({ active, payload }) => {
            const p = active && (payload?.[0]?.payload as ScatterDatum | undefined);
            return p && p.label ? <ChartTooltipBody title={p.label} rows={[[xLabel ?? "x", formatX(p.x)], [yLabel ?? "y", formatY(p.y)]]} /> : null;
          }}
        />
        {front.length > 1 ? (
          <Scatter data={front} line={{ stroke: frontierColor, strokeDasharray: "4 3", strokeWidth: 1 }} lineType="joint" shape={() => <g />} isAnimationActive={false} legendType="none" />
        ) : null}
        {groups.map((g) => (
          <Scatter
            key={g.key}
            name={g.label}
            data={data.filter((d) => d.group === g.key)}
            isAnimationActive={!reduced}
            shape={({ cx = 0, cy = 0 }: { cx?: number; cy?: number }) =>
              g.hollow ? <circle cx={cx} cy={cy} r={4} fill="var(--background)" stroke={g.color} strokeWidth={1.5} /> : <circle cx={cx} cy={cy} r={4} fill={g.color} />
            }
          />
        ))}
      </ScatterChart>
    </ResponsiveContainer>
  );
}
