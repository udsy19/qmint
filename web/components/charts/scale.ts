/**
 * Pure chart helpers shared by every QMint chart (no React, unit-tested).
 * Charts never invent data: these only position, format and summarise what the API returned.
 */

/** Powers of ten covering [min, max] (both > 0), at most `max` ticks (thinned evenly). */
export function logTicks(min: number, max: number, maxTicks = 6): number[] {
  if (!(min > 0) || !(max > 0) || min > max) return [];
  const lo = Math.floor(Math.log10(min));
  const hi = Math.ceil(Math.log10(max));
  const all: number[] = [];
  for (let e = lo; e <= hi; e++) all.push(10 ** e);
  if (all.length <= maxTicks) return all;
  const step = Math.ceil(all.length / maxTicks);
  return all.filter((_, i) => i % step === 0);
}

/** Log-scale domain padded to whole decades so points never sit on the frame. */
export function logDomain(values: number[]): [number, number] | null {
  const pos = values.filter((v) => Number.isFinite(v) && v > 0);
  if (!pos.length) return null;
  // Exact powers of ten are pushed one decade out so no point sits on the frame.
  const lo = Math.log10(Math.min(...pos));
  const hi = Math.log10(Math.max(...pos));
  return [10 ** (Number.isInteger(lo) ? lo - 1 : Math.floor(lo)), 10 ** (Number.isInteger(hi) ? hi + 1 : Math.ceil(hi))];
}

/** Linear domain with fractional padding; degenerate ranges get a symmetric pad. */
export function linearDomain(values: number[], pad = 0.08): [number, number] | null {
  const v = values.filter(Number.isFinite);
  if (!v.length) return null;
  let lo = Math.min(...v);
  let hi = Math.max(...v);
  if (lo === hi) {
    const d = Math.abs(lo) * 0.1 || 1;
    return [lo - d, hi + d];
  }
  const d = (hi - lo) * pad;
  lo -= d;
  hi += d;
  return [lo, hi];
}

/** "Nice" linear ticks (1/2/5 × 10^k steps) inside [lo, hi]. */
export function linearTicks(lo: number, hi: number, count = 5): number[] {
  if (!Number.isFinite(lo) || !Number.isFinite(hi) || hi <= lo) return [];
  const raw = (hi - lo) / Math.max(1, count);
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? 10 * mag;
  const out: number[] = [];
  for (let t = Math.ceil(lo / step) * step; t <= hi + step * 1e-9; t += step) out.push(Number(t.toPrecision(12)));
  return out;
}

const SI: [number, string][] = [
  [1e9, "s"],
  [1e6, "ms"],
  [1e3, "µs"],
  [1, "ns"],
];

/** Nanoseconds → human unit (15 337 ns → "15.3 µs"). Deterministic, 3 significant figures. */
export function formatNs(ns: number): string {
  const a = Math.abs(ns);
  for (const [f, u] of SI) {
    if (a >= f || f === 1) return `${Number((ns / f).toPrecision(3))} ${u}`;
  }
  return `${ns} ns`;
}

const SUP: Record<string, string> = { "-": "⁻", "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", ".": "·" };

/** 1e-9 → "10⁻⁹"; only for exact powers of ten (axis ticks). */
export function formatPow10(v: number): string {
  const e = Math.round(Math.log10(v));
  return `10${String(e).replace(/./g, (c) => SUP[c] ?? c)}`;
}

/**
 * A probability bound given in log10 form. Representable values use scientific notation
 * ("7.58e−10"); tiny ones stay in exponent form ("10^−457.15"). null → null (caller prints text, never 0).
 */
export function formatLog10Bound(log10: number | null | undefined): string | null {
  if (log10 === null || log10 === undefined || !Number.isFinite(log10)) return null;
  if (log10 > -300) {
    const v = 10 ** log10;
    if (v >= 1e-3) return String(Number(v.toPrecision(4)));
    const [m, e] = v.toExponential(2).split("e");
    return `${m}e${Number(e) < 0 ? "−" : ""}${Math.abs(Number(e))}`;
  }
  return `10^${log10 < 0 ? "−" : ""}${Math.abs(log10).toFixed(2)}`;
}

export interface ParetoPoint {
  id: string;
  x: number;
  y: number;
}

/** Points not dominated when minimising both x and y, sorted by x (ties: lower y wins). */
export function paretoFrontier<T extends ParetoPoint>(points: T[]): T[] {
  const sorted = [...points].filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y)).sort((a, b) => a.x - b.x || a.y - b.y);
  const out: T[] = [];
  let best = Infinity;
  for (const p of sorted) {
    if (p.y < best) {
      out.push(p);
      best = p.y;
    }
  }
  return out;
}

/** Middle-truncate a hash or id for display ("7ac9e453…a2d4cf6f0"); full value goes in title/copy. */
export function middleTruncate(s: string, head = 8, tail = 8): string {
  return s.length <= head + tail + 1 ? s : `${s.slice(0, head)}…${s.slice(-tail)}`;
}
