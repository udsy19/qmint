/**
 * Pure model behind the landing-page instrument (no React, no fetch).
 *
 * Maps an attack scenario plus the API responses it needs to the readings the instrument shows.
 * Every reading keeps the API's own value, evidence kind, method and interval; this module only
 * chooses which quantity goes where and marks out-of-model results with the API's proof applicability.
 */
import type { PostResponse, Schemas } from "@/lib/api/client";
import type { LabelGroup } from "@/lib/evidence";

export type AttackResponse = PostResponse<"/api/v1/lab/attack">;
export type MintResponse = PostResponse<"/api/v1/lab/mint">;
export type ApiAttack = Schemas["AttackRequest"]["attack"];
export type LabQuantity = Schemas["LabQuantity"];
export type Applicability = AttackResponse["data"]["proof_applicability"];

export type ScenarioId = "honest" | "measure_resend" | "phase_covariant" | "mvw_channel" | "leaked_secret";

export interface Scenario {
  id: ScenarioId;
  label: string;
  /** Short operator name drawn on the channel node. */
  operator: string;
  /** Honest holder reads /lab/mint; every other scenario is a /lab/attack id. */
  backend: { kind: "attack"; attack: ApiAttack } | { kind: "honest" };
  /** Static copy of the API's proof_applicability, so the list can mark the control before any fetch. */
  inModel: boolean;
  summary: string;
}

export const SCENARIOS: readonly Scenario[] = [
  {
    id: "honest",
    label: "Honest holder",
    operator: "id",
    backend: { kind: "honest" },
    inModel: true,
    summary: "The genuine note is verified once. There is no second note, so a joint pass is not defined.",
  },
  {
    id: "measure_resend",
    label: "Measure–resend",
    operator: "measure, prepare ×2",
    backend: { kind: "attack", attack: "A01_basis_guess_resend" },
    inModel: true,
    summary: "Guess Z or X for each qubit, measure it, then prepare two copies of what was seen.",
  },
  {
    id: "phase_covariant",
    label: "Phase-covariant cloner",
    operator: "Bruß cloner U",
    backend: { kind: "attack", attack: "A03b_phase_covariant_xz" },
    inModel: true,
    summary: "Bruß et al. 2000 cloner tuned to the circle containing |0⟩ |1⟩ |+⟩ |−⟩. Optimises fidelity, not this game.",
  },
  {
    id: "mvw_channel",
    label: "MVW optimal channel",
    operator: "MVW channel Φ",
    backend: { kind: "attack", attack: "A04_mvw_optimal_channel" },
    inModel: true,
    summary: "Molina–Vidick–Watrous 2012 optimal counterfeiting channel. It meets the W1 bound exactly.",
  },
  {
    id: "leaked_secret",
    label: "Leaked secret (control)",
    operator: "secret → 2 notes",
    backend: { kind: "attack", attack: "CTRL_secret_leak" },
    inModel: false,
    summary: "The bank's bases and bits leak, so the forger prepares two genuine notes. This breaks W1's assumptions on purpose.",
  },
] as const;

export function getScenario(id: ScenarioId): Scenario {
  const s = SCENARIOS.find((x) => x.id === id);
  if (!s) throw new Error(`unknown scenario ${id}`);
  return s;
}

/** Where a displayed probability comes from. Drives the copy under it. */
export type ProbabilitySource =
  | "theorem"
  | "certified_numeric"
  | "exact_model"
  | "monte_carlo"
  | "out_of_model"
  | "not_applicable";

export interface Reading {
  id: string;
  label: string;
  value: number | null;
  source: ProbabilitySource;
  /** Key + group for <EvidenceLabel/>: always the API's evidence kind. */
  evidence: { kind: string; group: LabelGroup };
  /** Quiet mono qualifier, e.g. "exact enumeration", "monte carlo · 1,000 fresh notes". */
  method: string;
  formula: string | null;
  interval: { lo: number; hi: number; confidence: number | null } | null;
  note: string | null;
  apiSource: string;
  /** Overrides the generic source sentence when the generic one would be wrong (e.g. honest acceptance). */
  explain?: string;
}

const METHOD_TEXT: Record<LabQuantity["method"], string> = {
  closed_form: "closed form",
  exact_enumeration: "exact enumeration",
  aer_sampling: "aer sampling",
  monte_carlo: "monte carlo",
  numerical_sdp: "numerical SDP",
  event_simulation: "event simulation",
  published_value: "published value",
  measured_dataset: "measured dataset",
  not_available: "not available",
};

function sourceOf(q: LabQuantity, outOfModel: boolean): ProbabilitySource {
  if (q.value === null) return "not_applicable";
  if (outOfModel) return "out_of_model";
  if (q.evidence_kind === "PUBLISHED_THEOREM") return "theorem";
  if (q.evidence_kind === "CERTIFIED_NUMERIC") return "certified_numeric";
  if (q.method === "monte_carlo" || q.method === "aer_sampling" || q.evidence_kind === "MONTE_CARLO") return "monte_carlo";
  return "exact_model";
}

export function fromQuantity(q: LabQuantity, label = q.label, outOfModel = false): Reading {
  const trials = q.method === "monte_carlo" ? q.note?.match(/\/(\d+) fresh notes/)?.[1] : undefined;
  return {
    id: q.id,
    label,
    value: q.value,
    source: sourceOf(q, outOfModel),
    evidence: { kind: q.evidence_kind, group: "evidence_kind" },
    method: trials ? `${METHOD_TEXT[q.method]} · ${Number(trials).toLocaleString("en-US")} fresh notes` : METHOD_TEXT[q.method],
    formula: q.formula ? prettyFormula(q.formula) : null,
    interval: q.interval ? { lo: q.interval.lo, hi: q.interval.hi, confidence: q.interval.confidence ?? null } : null,
    note: q.note ?? null,
    apiSource: q.source,
  };
}

export interface InstrumentReadings {
  scenario: ScenarioId;
  n: number;
  applicability: Applicability | "HONEST";
  /** P(both verifications pass) for ONE qubit. */
  perQubit: Reading;
  /** P(both verifications pass) for the n-qubit note: the headline for attacks. */
  joint: Reading;
  /** P(one given copy passes) for attacks; honest acceptance for the honest holder. */
  single: Reading;
  /** W1 theorem bound (3/4)^n, or the API's "no theorem" quantity. */
  bound: Reading & { applies: boolean };
  /** Certified upper end of the W1 optimum (lane C/D SDP), n ≤ 2 only. */
  optimum: Reading | null;
  /** Monte Carlo estimate over fresh notes, when trials > 0. */
  sampled: Reading | null;
  apiStatus: "OK" | "DEMO_ADAPTER" | "NOT_AVAILABLE";
  apiReason: string | null;
}

export type ReadingInputs =
  | { kind: "attack"; perQubit: AttackResponse; nQubit: AttackResponse }
  | { kind: "honest"; mint: MintResponse };

const find = (list: LabQuantity[], id: string) => list.find((q) => q.id === id);

function notApplicable(id: string, label: string, note: string): Reading {
  return {
    id,
    label,
    value: null,
    source: "not_applicable",
    evidence: { kind: "UNCERTIFIED", group: "evidence_kind" },
    method: "not available",
    formula: null,
    interval: null,
    note,
    apiSource: "qmint.api",
  };
}

export function buildReadings(scenarioId: ScenarioId, n: number, inputs: ReadingInputs): InstrumentReadings {
  const scenario = getScenario(scenarioId);
  if (scenario.backend.kind !== inputs.kind) {
    throw new Error(`scenario ${scenarioId} needs ${scenario.backend.kind} inputs, got ${inputs.kind}`);
  }

  if (inputs.kind === "honest") {
    const d = inputs.mint.data;
    const honest = find(d.statistics.acceptance, "honest_accept_mean") ?? d.statistics.acceptance[0];
    const none = "not applicable: one genuine note, one verification, no counterfeiter";
    return {
      scenario: scenarioId,
      n,
      applicability: "HONEST",
      perQubit: notApplicable("pq", "Both pass · per qubit", none),
      joint: notApplicable("joint", `Both pass · n = ${n}`, none),
      single: honest
        ? { ...fromQuantity(honest, "Genuine note passes"), explain: "Honest acceptance of the genuine note, closed form" }
        : notApplicable("honest", "Genuine note passes", "honest acceptance missing from the API response"),
      bound: { ...fromQuantity(d.theorem, "W1 bound · any counterfeiter"), applies: d.theorem.value !== null },
      optimum: null,
      sampled: null,
      apiStatus: inputs.mint.status,
      apiReason: inputs.mint.reason ?? null,
    };
  }

  const d1 = inputs.perQubit.data;
  const dn = inputs.nQubit.data;
  const out = dn.proof_applicability === "OUT_OF_MODEL";
  const exact1 = find(d1.counterfeit_success, "counterfeit_exact");
  const exactN = find(dn.counterfeit_success, "counterfeit_exact");
  const mc = find(dn.counterfeit_success, "counterfeit_mc");
  const upper = dn.sdp?.status === "OK" ? dn.sdp.upper_certified : null;
  return {
    scenario: scenarioId,
    n,
    applicability: dn.proof_applicability,
    perQubit: exact1 ? fromQuantity(exact1, "Both pass · per qubit", out) : notApplicable("pq", "Both pass · per qubit", "missing"),
    joint: exactN ? fromQuantity(exactN, `Both pass · n = ${n}`, out) : notApplicable("joint", `Both pass · n = ${n}`, "missing"),
    single: fromQuantity(dn.single_copy_pass, "One copy passes", out),
    bound: {
      ...fromQuantity(dn.theorem_bound, "W1 bound · any counterfeiter"),
      applies: dn.theorem_bound.value !== null && dn.proof_applicability === "IN_MODEL",
    },
    optimum: upper ? fromQuantity(upper, `Optimum ≤ · n = ${n}`) : null,
    sampled: mc ? fromQuantity(mc, "Both pass · sampled", out) : null,
    apiStatus: inputs.nQubit.status,
    apiReason: inputs.nQubit.reason ?? null,
  };
}

/** Human sentence for the live region. */
export function describe(r: InstrumentReadings): string {
  const s = getScenario(r.scenario);
  const what: Record<ProbabilitySource, string> = {
    theorem: "published theorem",
    certified_numeric: "certified numeric bound",
    exact_model: "exact model value",
    monte_carlo: "Monte Carlo estimate",
    out_of_model: "out-of-model control",
    not_applicable: "not applicable",
  };
  if (r.applicability === "HONEST") {
    return `${s.label}, n = ${r.n}: the genuine note passes with probability ${fmtProb(r.single.value)}; a joint pass is not applicable.`;
  }
  const v = r.joint.value;
  if (v === null) return `${s.label}, n = ${r.n}: both-pass probability not available. ${r.joint.note ?? ""}`.trim();
  const bound = r.bound.applies ? `W1 bound ${fmtProb(r.bound.value)}.` : "The W1 bound does not apply.";
  return `${s.label}, n = ${r.n}: both verifications pass with probability ${fmtProb(v)} (${what[r.joint.source]}). ${bound}`;
}

/** API formula strings → display notation: "(1/2 + 1/(2*sqrt(2)))^N" → "(1/2 + 1/(2√2))ᴺ". */
export function prettyFormula(f: string): string {
  return f
    .replace(/\*?sqrt\((\d+)\)/g, "√$1")
    .replace(/\^n\b/g, "ⁿ")
    .replace(/\^N\b/g, "ᴺ")
    .replace(/\s+\[.*\]$/, "");
}

export function fmtProb(v: number | null): string {
  if (v === null) return "n/a";
  if (v === 1 || v === 0) return String(v);
  if (v < 1e-3) return v.toExponential(3);
  return String(Number(v.toPrecision(6)));
}

/** Position of p on the instrument's log10 scale [10^min, 1] as a fraction 0..1 (clamped). */
export function logPosition(p: number | null, minExp = -3): number | null {
  if (p === null || p <= 0) return null;
  const x = (Math.log10(p) - minExp) / -minExp;
  return Math.min(1, Math.max(0, x));
}

export const N_OPTIONS = [1, 2, 4, 8] as const;
