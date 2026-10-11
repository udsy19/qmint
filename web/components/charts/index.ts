/** Generic chart primitives (owned by agent E; importable by lab agent D). Built on recharts 3 + design tokens. */
export { AXIS_TICK, ChartFrame, ChartLegend, ChartTooltipBody, GRID_STROKE, SERIES, useNarrow, useReducedMotion, type LegendItem, type LegendShape } from "./chart-frame";
export { IntervalPlot, type IntervalDatum, type IntervalSeries, type ReferenceBand, type ReferenceMark } from "./interval-plot";
export { LineBandChart, type HLine, type LineSeries, type VLine } from "./line-band-chart";
export { ScatterPareto, type ScatterDatum, type ScatterGroup } from "./scatter-pareto";
export * from "./scale";
