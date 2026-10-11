/** Typed lab endpoints (generated types) + small shared helpers for the lab components. */
import { apiPost, type Schemas } from "@/lib/api/client";
import { CLIENT_TIMEOUT_MS } from "./run-state";

export type LabQuantity = Schemas["LabQuantity"];
export type MintRequest = Schemas["MintRequest"];
export type MintResponse = Schemas["MintResponse"];
export type AttackRequest = Schemas["AttackRequest"];
export type AttackResponse = Schemas["AttackResponse"];
export type AttackId = AttackRequest["attack"];
export type LabNoise = Schemas["LabNoise"];
export type NoiseChannel = LabNoise["channel"];

/** Server-side caps (mirrors qmint/api/routes/lab.py; the API re-validates and returns 422). */
export const LIMITS = { nMax: 8, shotsMax: 20_000, trialsMax: 5_000, trialsMaxA08: 400, sdpNMax: 2 } as const;

export function postMint(req: MintRequest, signal: AbortSignal) {
  return apiPost("/api/v1/lab/mint", req, { signal, timeoutMs: CLIENT_TIMEOUT_MS });
}

export function postAttack(req: AttackRequest, signal: AbortSignal) {
  return apiPost("/api/v1/lab/attack", req, { signal, timeoutMs: CLIENT_TIMEOUT_MS });
}

export type Tier = "analytic" | "simulated" | "hardware";

/** Where a number comes from: math (exact/closed form/theorem/certificate), sampling, or a device. */
export function tierOf(q: Pick<LabQuantity, "method" | "evidence_kind">): Tier {
  if (q.evidence_kind === "QPU" || q.evidence_kind === "PHOTON_EXPERIMENT") return "hardware";
  if (q.method === "monte_carlo" || q.method === "aer_sampling") return "simulated";
  return "analytic";
}

export const METHOD_TEXT: Record<LabQuantity["method"], string> = {
  closed_form: "closed form",
  exact_enumeration: "exact",
  aer_sampling: "sampled · Aer shots",
  monte_carlo: "Monte Carlo · fresh notes",
  numerical_sdp: "numerical SDP",
  event_simulation: "event simulation",
  published_value: "published value",
  measured_dataset: "measured dataset",
  not_available: "not available",
};

export const NOISE_LABEL: Record<NoiseChannel, string> = {
  none: "None (ideal)",
  depolarizing: "Depolarizing",
  dephasing: "Dephasing (phase flip)",
  amplitude_damping: "Amplitude damping",
};

export function randomSeed(): number {
  return Math.floor(Math.random() * 2 ** 31);
}
