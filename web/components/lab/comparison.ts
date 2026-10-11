/** Pure data shaping for the attack comparison chart (unit-tested in comparison.test.ts). */
import type { Schemas } from "@/lib/api/client";
import { tierOf, type LabQuantity, type Tier } from "./lab-api";

type AttackData = Schemas["AttackData"];

export type Role = "honest" | "single" | "counterfeit" | "bound" | "sdp";

export interface ComparisonRow {
  id: string;
  label: string;
  role: Role;
  tier: Tier;
  q: LabQuantity;
  /** Point value (null → not available; drawn as text, never at 0). */
  value: number | null;
  /** CI or certified bracket. */
  lo?: number;
  hi?: number;
}

export interface Comparison {
  groups: { tier: Tier; title: string; caption: string; rows: ComparisonRow[] }[];
  bound: number | null;
  scale: "linear" | "log";
  /** Lower end of the axis (0 for linear, a power of ten for log). */
  min: number;
}

const ROLE_ORDER: Role[] = ["honest", "single", "counterfeit", "sdp", "bound"];

export const TIER_TEXT: Record<Tier, { title: string; caption: string }> = {
  analytic: { title: "Analytic", caption: "exact model values, the published theorem and certified SDP bounds" },
  simulated: { title: "Simulated", caption: "Monte Carlo over fresh secret notes · 95% Clopper–Pearson intervals" },
  hardware: { title: "Hardware", caption: "quantum processor measurements" },
};

export function buildComparison(d: AttackData): Comparison {
  const rows: ComparisonRow[] = [];
  const add = (q: LabQuantity, role: Role, label?: string, lo?: number, hi?: number) =>
    rows.push({ id: q.id, label: label ?? q.label, role, tier: tierOf(q), q, value: q.value ?? null, lo: lo ?? q.interval?.lo, hi: hi ?? q.interval?.hi });

  for (const q of d.honest_acceptance) add(q, "honest");
  add(d.single_copy_pass, "single");
  for (const q of d.counterfeit_success) add(q, "counterfeit");
  if (d.sdp?.status === "OK" && d.sdp.lower && d.sdp.upper_certified) {
    add({ ...d.sdp.upper_certified, id: "sdp_bracket", label: `Optimum, certified (n = ${d.sdp.n})` }, "sdp", undefined, d.sdp.lower.value ?? undefined, d.sdp.upper_certified.value ?? undefined);
  }
  add(d.theorem_bound, "bound");
  rows.push({ id: d.hardware.id, label: "Counterfeit success on a QPU", role: "counterfeit", tier: "hardware", q: d.hardware, value: null });

  const vals = rows.flatMap((r) => [r.value, r.lo]).filter((v): v is number => typeof v === "number" && v > 0);
  const lowest = vals.length ? Math.min(...vals) : 1;
  const scale = lowest < 0.05 ? "log" : "linear";
  const min = scale === "log" ? 10 ** Math.floor(Math.log10(lowest)) : 0;

  const tiers: Tier[] = ["analytic", "simulated", "hardware"];
  return {
    groups: tiers.map((tier) => ({
      tier,
      ...TIER_TEXT[tier],
      rows: rows.filter((r) => r.tier === tier).sort((a, b) => ROLE_ORDER.indexOf(a.role) - ROLE_ORDER.indexOf(b.role)),
    })),
    bound: d.theorem_bound.value ?? null,
    scale,
    min,
  };
}

/** Position of a probability on the axis, as a fraction in [0, 1]. */
export function axisPosition(v: number, scale: Comparison["scale"], min: number): number {
  if (scale === "linear") return Math.min(1, Math.max(0, v));
  if (v <= min) return 0;
  return Math.min(1, Math.max(0, (Math.log10(v) - Math.log10(min)) / (0 - Math.log10(min))));
}

export function axisTicks(scale: Comparison["scale"], min: number): number[] {
  if (scale === "linear") return [0, 0.25, 0.5, 0.75, 1];
  const out: number[] = [];
  for (let e = Math.round(Math.log10(min)); e <= 0; e++) out.push(10 ** e);
  return out;
}
