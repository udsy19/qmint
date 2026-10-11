/**
 * Test fixtures for the hero instrument: minimal API responses with the exact shapes and values the
 * research API returned (POST /api/v1/lab/attack and /lab/mint, seed 42, 2026-10-11). Tests only.
 */
import type { Quantity } from "@/lib/api/client";
import type { AttackResponse, MintResponse } from "./instrument-model";

const prov = { source: "test", git_sha: "6a8053eee2dbac62854ca24905631d1538f98517", generated_at_utc: "2026-10-11T00:00:00+00:00", seed: 42, software: {}, notes: null };

export function q(id: string, value: number | null, extra: Partial<Quantity> = {}): Quantity {
  return { id, label: id, value, unit: "probability", evidence_kind: "SIMULATOR_IDEAL", method: "exact_enumeration", source: "qmint.test", ...extra } as Quantity;
}

export function theorem(n: number): Quantity {
  return q("w1_theorem_bound", 0.75 ** n, { evidence_kind: "PUBLISHED_THEOREM", method: "closed_form", formula: "(3/4)^n", source: "MVW 2012" });
}

export function attackResponse(
  attack: AttackResponse["data"]["attack"],
  n: number,
  opts: { aer?: { value: number; lo: number; hi: number; trials: number } } = {},
): AttackResponse {
  const per = { honest: null, measure_resend: 0.625, bruss_cloner: (3 + 2 * Math.SQRT2) / 8, mvw_channel: 0.75 }[attack];
  const single = { honest: 1, measure_resend: 0.75, bruss_cloner: 0.8535533905932737, mvw_channel: 0.8333333333333334 }[attack];
  const double: Quantity[] =
    per === null
      ? [q("double_verification_success", null, { evidence_kind: "UNCERTIFIED", method: "not_available", note: "not applicable: there is only one genuine note and no counterfeiter" })]
      : [q("double_verification_success", per ** n, { formula: attack === "mvw_channel" ? "(3/4)^n  [exact rational per qubit]" : "(5/8)^n" })];
  if (opts.aer) {
    double.push(
      q("double_verification_success_aer", opts.aer.value, {
        method: "aer_sampling",
        interval: { lo: opts.aer.lo, hi: opts.aer.hi, confidence: 0.99, method: "clopper_pearson_0.99" },
        note: `${Math.round(opts.aer.value * opts.aer.trials)}/${opts.aer.trials} shots over 4 random notes`,
      }),
    );
  }
  return {
    status: "DEMO_ADAPTER",
    evidence_kind: "SIMULATOR_IDEAL",
    reason: "demo adapter reason",
    provenance: prov,
    data: {
      attack,
      attack_label: attack,
      description: "",
      honest_acceptance: [q("honest_accept_mean", 1, { method: "closed_form" })],
      single_verification_pass: q("single_verification_pass", single ** n, { method: attack === "honest" ? "closed_form" : "exact_enumeration" }),
      double_verification_success: double,
      theorem_bound: theorem(n),
      attack_result: null,
      assumptions: [],
      notes: [],
    },
  } as unknown as AttackResponse;
}

const STATES = ["0", "-", "+", "1", "0", "0", "+", "1"];

export function mintResponse(n: number, pHonest = 1): MintResponse {
  return {
    status: "OK",
    evidence_kind: "SIMULATOR_IDEAL",
    reason: null,
    provenance: prov,
    data: {
      token: { token_id: `demo-wiesner-n${n}-s42` },
      issuer_view: { qubits: STATES.slice(0, n).map((s, index) => ({ index, state_label: s })) },
      statistics: {
        acceptance: [
          q("honest_accept_note_analytic", pHonest ** n, { method: "closed_form", source: "qmint.quantum.channels.analytic_note_accept_probability" }),
          q("honest_accept_mean_analytic", pHonest ** n, { method: "closed_form" }),
        ],
      },
    },
  } as unknown as MintResponse;
}
