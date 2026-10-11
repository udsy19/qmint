/** Pure view-model for the benchmark explorer (sorting, filtering, labels). No data is created here. */
import type { GetResponse, Schemas } from "@/lib/api/client";

export type BenchData = GetResponse<"/api/v1/benchmarks">["data"];
export type Row = Schemas["ProtocolRow"];
export type Outcome = Row["double_spend"]["outcome"];
export type Comparability = Row["comparability_status"];

export const OUTCOME: Record<Outcome, { label: string; tone: "fg" | "info" | "warn" | "danger"; glyph: string; rank: number }> = {
  PREVENTED: { label: "Prevented", tone: "fg", glyph: "■", rank: 0 },
  BOUNDED_BY_THEOREM: { label: "Bounded (theorem)", tone: "info", glyph: "■", rank: 1 },
  DETECTED_NOT_PREVENTED: { label: "Detected, not prevented", tone: "warn", glyph: "◩", rank: 2 },
  OUT_OF_MODEL: { label: "Out of model", tone: "danger", glyph: "×", rank: 3 },
  SUCCEEDS: { label: "Succeeds", tone: "danger", glyph: "×", rank: 4 },
};

export const COMPARABILITY: Record<Comparability, { label: string; hint: string; rank: number }> = {
  REFERENCE: { label: "Reference", hint: "the quantum model every classical pair is compared against", rank: 0 },
  COMPARABLE: { label: "Comparable", hint: "matched assumptions", rank: 1 },
  QUALIFIED: { label: "Qualified", hint: "comparable only after pricing the listed concessions", rank: 2 },
  INCOMPARABLE: { label: "Incomparable", hint: "fails the double-spend goal or uses a different trust model", rank: 3 },
  NO_PAIR: { label: "No X11 pair", hint: "this variant has no row in lane H's comparability matrix", rank: 4 },
};

const FLEX: Record<string, string> = {
  late_choice_any_site: "Late choice, any site",
  preassigned_site: "Site fixed at issuance",
  online_any_site: "Any site, online",
  none: "None",
};

export function flexibilityLabel(v: string): string {
  return FLEX[v] ?? v.replace(/_/g, " ");
}

/** "net-h-synthetic-3site-100km" → "3 sites · 100 km" */
export function networkLabel(id: string | null): string {
  if (!id) return "any";
  const m = /(\d+)site-(\d+)km/.exec(id);
  return m ? `${m[1]} sites · ${m[2]} km` : id;
}

export function variantLabel(v: string | null): string {
  return v ? v.replace(/_/g, " ") : "";
}

export type SortKey = "construction" | "outcome" | "local" | "commit" | "flexibility" | "comparability";
export type SortDir = "asc" | "desc";

export interface Filters {
  network: string;
  family: "all" | "quantum" | "classical";
  outcome: "all" | Outcome;
  comparability: "all" | Comparability;
  query: string;
}

export const DEFAULT_FILTERS: Filters = { network: "all", family: "all", outcome: "all", comparability: "all", query: "" };

export function networks(rows: Row[]): string[] {
  return [...new Set(rows.map((r) => r.network_id).filter((n): n is string => !!n))].sort();
}

/** Quantum reference rows have no network (their matched-topology latency is NOT_AVAILABLE) and match every network. */
export function filterRows(rows: Row[], f: Filters): Row[] {
  const q = f.query.trim().toLowerCase();
  return rows.filter(
    (r) =>
      (f.network === "all" || r.network_id === null || r.network_id === f.network) &&
      (f.family === "all" || r.family === f.family) &&
      (f.outcome === "all" || r.double_spend.outcome === f.outcome) &&
      (f.comparability === "all" || r.comparability_status === f.comparability) &&
      (!q || `${r.code} ${r.label} ${r.variant ?? ""} ${r.trust_model} ${r.privacy}`.toLowerCase().includes(q)),
  );
}

function key(r: Row, k: SortKey): number | string | null {
  switch (k) {
    case "construction":
      return `${r.family === "quantum" ? "0" : "1"}${r.code}${r.variant ?? ""}${r.network_id ?? ""}`;
    case "outcome":
      return OUTCOME[r.double_spend.outcome].rank;
    case "local":
      return r.local_validation?.value ?? null;
    case "commit":
      return r.pre_presentation_commit?.value ?? null;
    case "flexibility":
      return flexibilityLabel(r.flexibility);
    case "comparability":
      return COMPARABILITY[r.comparability_status].rank;
  }
}

/** Stable sort; missing values (null) always go last regardless of direction. */
export function sortRows(rows: Row[], k: SortKey, dir: SortDir): Row[] {
  const s = dir === "asc" ? 1 : -1;
  return rows
    .map((r, i) => ({ r, i, v: key(r, k) }))
    .sort((a, b) => {
      if (a.v === null && b.v === null) return a.i - b.i;
      if (a.v === null) return 1;
      if (b.v === null) return -1;
      const c = typeof a.v === "number" && typeof b.v === "number" ? a.v - b.v : String(a.v).localeCompare(String(b.v));
      return c === 0 ? a.i - b.i : c * s;
    })
    .map((x) => x.r);
}
