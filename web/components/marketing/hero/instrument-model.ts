/**
 * Pure model behind the landing-page instrument (no React, no fetch).
 *
 * Maps an attack scenario plus the API responses it needs to the readings the instrument shows.
 * Every reading keeps the API's own evidence kind and method; the only value this module computes is
 * the leaked-secret control (square of the API's closed-form honest acceptance), which is labelled
 * OUT-OF-MODEL and says how it was derived.
 */
import type { PostResponse, Quantity, Schemas } from "@/lib/api/client";
import type { LabelGroup } from "@/lib/evidence";

export type AttackResponse = PostResponse<"/api/v1/lab/attack">;
export type MintResponse = PostResponse<"/api/v1/lab/mint">;
export type ApiAttack = Schemas["AttackRequest"]["attack"];

export type ScenarioId = "honest" | "measure_resend" | "bruss_cloner" | "mvw_channel" | "leaked_secret";

export interface Scenario {
  id: ScenarioId;
  label: string;
  /** Short operator name drawn on the channel node. */
  operator: string;
  /** What the API is asked: an attack on /lab/attack, or the honest note from /lab/mint (control). */
  backend: { kind: "attack"; attack: ApiAttack } | { kind: "mint_control" };
  inModel: boolean;
  /** Whether a Monte Carlo (Aer) run exists for this scenario in the API. */
  sampleable: boolean;
  summary: string;
}

export const SCENARIOS: readonly Scenario[] = [
  {
    id: "honest",
    label: "Honest holder",
    operator: "id",
    backend: { kind: "attack", attack: "honest" },
    inModel: true,
    sampleable: false,
    summary: "The genuine note is verified once. There is no second note, so a joint pass is not defined.",
  },
  {
    id: "measure_resend",
    label: "Measure–resend",
    operator: "measure, prepare ×2",
    backend: { kind: "attack", attack: "measure_resend" },
    inModel: true,
    sampleable: false,
    summary: "Measure each qubit in a random BB84 basis, then prepare two copies of what was seen.",
  },
  {
    id: "bruss_cloner",
    label: "Phase-covariant cloner",
    operator: "Bruß cloner U",
    backend: { kind: "attack", attack: "bruss_cloner" },
    inModel: true,
    sampleable: true,
    summary: "Bruß et al. 2000 optimal 1→2 phase-covariant cloner on every qubit. Optimises fidelity, not this game.",
  },
  {
    id: "mvw_channel",
    label: "MVW optimal channel",
    operator: "MVW channel Φ",
    backend: { kind: "attack", attack: "mvw_channel" },
    inModel: true,
    sampleable: true,
    summary: "Molina–Vidick–Watrous 2012 §3.2 optimal counterfeiting channel. It meets the W1 bound exactly.",
  },
  {
    id: "leaked_secret",
    label: "Leaked secret (control)",
    operator: "secret → 2 notes",
    backend: { kind: "mint_control" },
    inModel: false,
    sampleable: false,
    summary: "The bank's bases and bits leak, so the forger prepares two genuine notes. This breaks W1's assumptions on purpose.",
  },
] as const;

export function getScenario(id: ScenarioId): Scenario {
  const s = SCENARIOS.find((x) => x.id === id);
  if (!s) throw new Error(`unknown scenario ${id}`);
  return s;
}

/** Where a displayed probability comes from. Drives the label and the copy under it. */
export type ProbabilitySource = "theorem" | "exact_model" | "monte_carlo" | "out_of_model" | "not_applicable";

export interface Reading {
  id: string;
  label: string;
  value: number | null;
  source: ProbabilitySource;
  /** Key + group for <EvidenceLabel/>. */
  evidence: { kind: string; group: LabelGroup };
  /** Quiet mono qualifier, e.g. "exact enumeration", "aer sampling · 2000 shots". */
  method: string;
  formula: string | null;
  interval: { lo: number; hi: number; confidence: number | null } | null;
  note: string | null;
  apiSource: string;
  /** Overrides the generic source sentence when the generic one would be wrong (e.g. honest acceptance). */
  explain?: string;
}

const METHOD_TEXT: Record<Quantity["method"], string> = {
  closed_form: "closed form",
  exact_enumeration: "exact enumeration",
  aer_sampling: "aer sampling",
  event_simulation: "event simulation",
  published_value: "published value",
  measured_dataset: "measured dataset",
  not_available: "not available",
};

function sourceOf(q: Quantity): ProbabilitySource {
  if (q.value === null) return "not_applicable";
  if (q.evidence_kind === "PUBLISHED_THEOREM") return "theorem";
  if (q.method === "aer_sampling" || q.evidence_kind === "MONTE_CARLO") return "monte_carlo";
  return "exact_model";
}

export function fromQuantity(q: Quantity, label = q.label): Reading {
  return {
    id: q.id,
    label,
    value: q.value,
    source: sourceOf(q),
    evidence: { kind: q.evidence_kind, group: "evidence_kind" },
    method: METHOD_TEXT[q.method],
    formula: q.formula ? prettyFormula(q.formula) : null,
    interval: q.interval ? { lo: q.interval.lo, hi: q.interval.hi, confidence: q.interval.confidence ?? null } : null,
    note: q.note ?? null,
    apiSource: q.source,
  };
}

function find(list: Quantity[], id: string): Quantity | undefined {
  return list.find((q) => q.id === id);
}

export interface InstrumentReadings {
  scenario: ScenarioId;
  n: number;
  /** P(both verifications pass) for ONE qubit. */
  perQubit: Reading;
  /** P(both verifications pass) for the n-qubit note: the headline. */
  joint: Reading;
  /** P(one given copy passes), n qubits. */
  single: Reading;
  /** W1 theorem bound (3/4)^n; `applies` is false outside the model. */
  bound: Reading & { applies: boolean };
  /** Aer Monte Carlo estimate with CI, when the API ran one. */
  sampled: Reading | null;
  apiStatus: "OK" | "DEMO_ADAPTER" | "NOT_AVAILABLE";
  apiReason: string | null;
}

export interface AttackInputs {
  kind: "attack";
  perQubit: AttackResponse;
  nQubit: AttackResponse;
}
export interface ControlInputs {
  kind: "mint_control";
  perQubit: MintResponse;
  nQubit: MintResponse;
  /** The W1 theorem bound for the same n, taken from an attack response (any attack) or null. */
  theorem: Quantity | null;
}

const OUT_OF_MODEL_NOTE =
  "OUT OF MODEL: W1 assumes the bank keeps bases and bits secret. With the secret, the forger prepares two genuine notes; each passes with the honest acceptance probability.";

function controlReading(m: MintResponse, n: number, id: string, label: string): Reading {
  const honest = find(m.data.statistics.acceptance, "honest_accept_note_analytic");
  const p = honest?.value ?? null;
  return {
    id,
    label,
    value: p === null ? null : p * p,
    source: p === null ? "not_applicable" : "out_of_model",
    evidence: { kind: "OUT_OF_MODEL", group: "certificate_status" },
    method: "derived · (honest acceptance)²",
    formula: n === 1 ? "p_honest²" : "(p_honest,note)²",
    interval: null,
    note: OUT_OF_MODEL_NOTE,
    apiSource: `POST /api/v1/lab/mint → honest_accept_note_analytic (${honest?.source ?? "missing"})`,
  };
}

export function buildReadings(scenarioId: ScenarioId, n: number, inputs: AttackInputs | ControlInputs): InstrumentReadings {
  const scenario = getScenario(scenarioId);
  if ((scenario.backend.kind === "attack") !== (inputs.kind === "attack")) {
    throw new Error(`scenario ${scenarioId} needs ${scenario.backend.kind} inputs, got ${inputs.kind}`);
  }

  if (inputs.kind === "mint_control") {
    const single = find(inputs.nQubit.data.statistics.acceptance, "honest_accept_note_analytic");
    const theorem = inputs.theorem;
    return {
      scenario: scenarioId,
      n,
      perQubit: controlReading(inputs.perQubit, 1, "control_per_qubit", "Both pass · per qubit"),
      joint: controlReading(inputs.nQubit, n, "control_joint", `Both pass · n = ${n}`),
      single: single
        ? { ...fromQuantity(single, "One copy passes"), evidence: { kind: "OUT_OF_MODEL", group: "certificate_status" }, source: "out_of_model" }
        : notApplicable("single_verification_pass", "One copy passes", "honest acceptance missing from the API response"),
      bound: theorem
        ? { ...fromQuantity(theorem, "W1 bound · any counterfeiter"), applies: false, note: "Does not apply: the secret leaked, which W1 excludes." }
        : { ...notApplicable("w1_theorem_bound", "W1 bound · any counterfeiter", "theorem unavailable"), applies: false },
      sampled: null,
      apiStatus: inputs.nQubit.status,
      apiReason: inputs.nQubit.reason ?? null,
    };
  }

  const d1 = inputs.perQubit.data;
  const dn = inputs.nQubit.data;
  const exact1 = find(d1.double_verification_success, "double_verification_success");
  const exactN = find(dn.double_verification_success, "double_verification_success");
  const aer = find(dn.double_verification_success, "double_verification_success_aer");
  return {
    scenario: scenarioId,
    n,
    perQubit: exact1 ? fromQuantity(exact1, "Both pass · per qubit") : notApplicable("pq", "Both pass · per qubit", "missing"),
    joint: exactN ? fromQuantity(exactN, `Both pass · n = ${n}`) : notApplicable("joint", `Both pass · n = ${n}`, "missing"),
    single:
      scenarioId === "honest"
        ? { ...fromQuantity(dn.single_verification_pass, "Genuine note passes"), explain: "Honest acceptance of a random ideal note, closed form" }
        : fromQuantity(dn.single_verification_pass, "One copy passes"),
    bound: { ...fromQuantity(dn.theorem_bound, "W1 bound · any counterfeiter"), applies: true },
    sampled: aer ? { ...fromQuantity(aer, "Both pass · sampled"), method: `aer sampling · ${aerShots(aer)}` } : null,
    apiStatus: inputs.nQubit.status,
    apiReason: inputs.nQubit.reason ?? null,
  };
}

function aerShots(q: Quantity): string {
  const m = q.note?.match(/(\d+)\/(\d+) shots/);
  return m ? `${Number(m[2]).toLocaleString("en-US")} shots` : "shots";
}

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

/** Human sentence for the live region. */
export function describe(r: InstrumentReadings): string {
  const s = getScenario(r.scenario);
  const v = r.joint.value;
  const what: Record<ProbabilitySource, string> = {
    theorem: "published theorem",
    exact_model: "exact model value",
    monte_carlo: "Monte Carlo estimate",
    out_of_model: "out-of-model control",
    not_applicable: "not applicable",
  };
  if (v === null) return `${s.label}, n = ${r.n}: both-pass probability not applicable. ${r.joint.note ?? ""}`.trim();
  return `${s.label}, n = ${r.n}: both verifications pass with probability ${fmtProb(v)} (${what[r.joint.source]}). W1 bound ${fmtProb(r.bound.value)}${r.bound.applies ? "" : ", not applicable"}.`;
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
/** The API's Aer cloner circuit needs 3n qubits ≤ 8. */
export const MAX_SAMPLED_N = 2;
