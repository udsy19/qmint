/**
 * Test fixtures for the hero instrument: minimal API responses with the shapes and per-qubit values the
 * research API returned (POST /api/v1/lab/attack and /lab/mint, seed 42, main @ 02aeab1). Tests only.
 */
import type { ApiAttack, AttackResponse, LabQuantity, MintResponse } from "./instrument-model";

const prov = { source: "test", git_sha: "02aeab1000000000000000000000000000000000", generated_at_utc: "2026-10-11T00:00:00+00:00", seed: 42, software: {}, notes: null };

export function q(id: string, value: number | null, extra: Partial<LabQuantity> = {}): LabQuantity {
  return { id, label: id, value, unit: "probability", evidence_kind: "SIMULATOR_IDEAL", method: "exact_enumeration", source: "qmint.test", ...extra } as LabQuantity;
}

const PER_QUBIT: Partial<Record<ApiAttack, { single: number; both: number }>> = {
  A01_basis_guess_resend: { single: 0.75, both: 0.625 },
  A03b_phase_covariant_xz: { single: 0.8535533905932737, both: (3 + 2 * Math.SQRT2) / 8 },
  A04_mvw_optimal_channel: { single: 0.8333333333333334, both: 0.75 },
  CTRL_secret_leak: { single: 1, both: 1 },
};

export function attackResponse(attack: ApiAttack, n: number, opts: { trials?: number; wins?: number; sdp?: boolean } = {}): AttackResponse {
  const per = PER_QUBIT[attack];
  if (!per) throw new Error(`no fixture for ${attack}`);
  const out = attack === "CTRL_secret_leak";
  const counterfeit: LabQuantity[] = [q("counterfeit_exact", per.both ** n, { formula: `(${per.both})^n` })];
  if (opts.trials) {
    const wins = opts.wins ?? Math.round(per.both ** n * opts.trials);
    counterfeit.push(
      q("counterfeit_mc", wins / opts.trials, {
        evidence_kind: "MONTE_CARLO",
        method: "monte_carlo",
        interval: { lo: Math.max(0, wins / opts.trials - 0.03), hi: Math.min(1, wins / opts.trials + 0.03), confidence: 0.95, method: "clopper_pearson_0.95" },
        note: `${wins}/${opts.trials} fresh notes; LOWER bound`,
      }),
    );
  }
  const sdp =
    opts.sdp && n <= 2
      ? {
          n,
          status: "OK",
          reason: null,
          lower: q("sdp_lower", 0.75 ** n),
          upper_certified: q("sdp_upper_certified", n === 1 ? 0.750000000003638 : 0.562500000007276, { evidence_kind: "CERTIFIED_NUMERIC" }),
          upper_independent: q("sdp_upper_independent", 0.75 ** n, { evidence_kind: "CERTIFIED_NUMERIC" }),
          numerical: q("sdp_numerical", 0.75 ** n, { evidence_kind: "NUMERICAL_SDP", method: "numerical_sdp" }),
          recorded_evidence: "handoffs/C-C1-evidence.json",
        }
      : null;
  return {
    status: "OK",
    evidence_kind: "SIMULATOR_IDEAL",
    reason: null,
    provenance: prov,
    data: {
      attack,
      attack_label: attack,
      description: "",
      game_id: "W1",
      proof_applicability: out ? "OUT_OF_MODEL" : "IN_MODEL",
      capabilities: [],
      honest_acceptance: [q("honest_accept_mean", 1, { method: "closed_form" })],
      single_copy_pass: q("single_copy_pass", per.single ** n),
      counterfeit_success: counterfeit,
      theorem_bound: out
        ? q("theorem_bound", null, { evidence_kind: "UNCERTIFIED", method: "not_available", note: "OUT_OF_MODEL: the theorem assumes the secret stays with the bank" })
        : q("w1_theorem_bound", 0.75 ** n, { evidence_kind: "PUBLISHED_THEOREM", method: "closed_form", formula: "(3/4)^n" }),
      sdp,
      hardware: q("qpu", null, { evidence_kind: "QPU", method: "not_available" }),
      attack_result: null,
      assumptions: [],
      notes: [],
      run: { backends: [], seed: 42, shots: null, trials: opts.trials ?? 0, elapsed_ms: 1, deadline_s: 20, limits: {} },
      simulator_caveat: "",
    },
  } as unknown as AttackResponse;
}

const STATES = ["0", "-", "+", "1", "0", "0", "+", "1"];

export function mintResponse(n: number, opts: { reveal?: boolean } = {}): MintResponse {
  return {
    status: "OK",
    evidence_kind: "SIMULATOR_IDEAL",
    reason: null,
    provenance: prov,
    data: {
      token: { token_id: "wiesner-SN-test" },
      statistics: { threshold: 0, shots: null, acceptance: [q("honest_accept_mean", 1, { method: "closed_form" })], error_counts: [], error_counts_note: "" },
      theorem: q("w1_theorem_bound", 0.75 ** n, { evidence_kind: "PUBLISHED_THEOREM", method: "closed_form", formula: "(3/4)^n" }),
      teaching: opts.reveal ? { qubits: STATES.slice(0, n).map((s, index) => ({ index, state_label: s })) } : null,
    },
  } as unknown as MintResponse;
}
