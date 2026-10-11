import { describe, expect, it } from "vitest";
import { attackResponse, mintResponse } from "./instrument-fixtures";
import { buildReadings, describe as describeReadings, logPosition, prettyFormula, SCENARIOS, type ApiAttack } from "./instrument-model";

const attack = (a: ApiAttack, n: number, opts: Parameters<typeof attackResponse>[2] = {}) =>
  ({ kind: "attack", perQubit: attackResponse(a, 1), nQubit: attackResponse(a, n, opts) }) as const;

describe("hero instrument: scenario → probability source and label", () => {
  it("scenarios map to the API's attack ids; only the control is out of model", () => {
    expect(SCENARIOS.map((s) => (s.backend.kind === "attack" ? s.backend.attack : "honest"))).toEqual([
      "honest",
      "A01_basis_guess_resend",
      "A03b_phase_covariant_xz",
      "A04_mvw_optimal_channel",
      "CTRL_secret_leak",
    ]);
    expect(SCENARIOS.filter((s) => !s.inModel).map((s) => s.id)).toEqual(["leaked_secret"]);
  });

  it("MVW channel: exact model value from the API, theorem bound labelled THEOREM", () => {
    const r = buildReadings("mvw_channel", 4, attack("A04_mvw_optimal_channel", 4));
    expect(r.joint.value).toBeCloseTo(0.31640625, 12);
    expect(r.joint.source).toBe("exact_model");
    expect(r.joint.evidence).toEqual({ kind: "SIMULATOR_IDEAL", group: "evidence_kind" });
    expect(r.joint.method).toBe("exact enumeration");
    expect(r.perQubit.value).toBe(0.75);
    expect(r.bound.source).toBe("theorem");
    expect(r.bound.evidence.kind).toBe("PUBLISHED_THEOREM");
    expect(r.bound.formula).toBe("(3/4)ⁿ");
    expect(r.bound.applies).toBe(true);
    expect(r.sampled).toBeNull();
    expect(r.optimum).toBeNull(); // n > 2: no SDP
  });

  it("n ≤ 2: the certified SDP upper end is a CERTIFIED-NUMERIC reading", () => {
    const r = buildReadings("mvw_channel", 2, attack("A04_mvw_optimal_channel", 2, { sdp: true }));
    expect(r.optimum?.source).toBe("certified_numeric");
    expect(r.optimum?.evidence.kind).toBe("CERTIFIED_NUMERIC");
    expect(r.optimum?.value).toBe(0.562500000007276);
  });

  it("measure-resend: (5/8)^n is an exact model value, never the theorem", () => {
    const r = buildReadings("measure_resend", 2, attack("A01_basis_guess_resend", 2));
    expect(r.joint.value).toBeCloseTo(0.390625, 12);
    expect(r.joint.source).toBe("exact_model");
    expect(r.joint.evidence.kind).not.toBe("PUBLISHED_THEOREM");
  });

  it("Monte Carlo: MONTE-CARLO reading with its interval and the number of fresh notes", () => {
    const r = buildReadings("phase_covariant", 2, attack("A03b_phase_covariant_xz", 2, { trials: 1000, wins: 526 }));
    expect(r.sampled?.source).toBe("monte_carlo");
    expect(r.sampled?.evidence.kind).toBe("MONTE_CARLO");
    expect(r.sampled?.value).toBe(0.526);
    expect(r.sampled?.interval?.confidence).toBe(0.95);
    expect(r.sampled?.method).toBe("monte carlo · 1,000 fresh notes");
    expect(r.joint.source).toBe("exact_model");
  });

  it("honest holder: honest acceptance from /lab/mint; joint pass is not applicable (null, never 0)", () => {
    const r = buildReadings("honest", 4, { kind: "honest", mint: mintResponse(4) });
    expect(r.applicability).toBe("HONEST");
    expect(r.joint.value).toBeNull();
    expect(r.joint.source).toBe("not_applicable");
    expect(r.single.value).toBe(1);
    expect(r.single.label).toBe("Genuine note passes");
    expect(r.bound.evidence.kind).toBe("PUBLISHED_THEOREM");
    expect(describeReadings(r)).toMatch(/not applicable/);
  });

  it("leaked secret: the API's CTRL_secret_leak value, marked out of model; the bound does not apply", () => {
    const r = buildReadings("leaked_secret", 4, attack("CTRL_secret_leak", 4, { trials: 1000 }));
    expect(r.applicability).toBe("OUT_OF_MODEL");
    expect(r.joint.value).toBe(1);
    expect(r.joint.source).toBe("out_of_model");
    expect(r.joint.evidence.kind).toBe("SIMULATOR_IDEAL"); // the API's kind is kept
    expect(r.sampled?.source).toBe("out_of_model");
    expect(r.bound.value).toBeNull();
    expect(r.bound.applies).toBe(false);
    expect(describeReadings(r)).toMatch(/out-of-model control.*does not apply/);
  });

  it("refuses inputs from the wrong backend", () => {
    expect(() => buildReadings("honest", 1, attack("A04_mvw_optimal_channel", 1))).toThrow();
    expect(() => buildReadings("mvw_channel", 1, { kind: "honest", mint: mintResponse(1) })).toThrow();
  });
});

describe("helpers", () => {
  it("prettyFormula", () => {
    expect(prettyFormula("(1/2 + 1/(2*sqrt(2)))^N")).toBe("(1/2 + 1/(2√2))ᴺ");
    expect(prettyFormula("(3/4)^n  [exact rational per qubit]")).toBe("(3/4)ⁿ");
  });
  it("logPosition maps [1e-3, 1] to [0, 1] and refuses null/0", () => {
    expect(logPosition(1)).toBe(1);
    expect(logPosition(1e-3)).toBe(0);
    expect(logPosition(0.1)).toBeCloseTo(2 / 3, 12);
    expect(logPosition(1e-9)).toBe(0);
    expect(logPosition(null)).toBeNull();
    expect(logPosition(0)).toBeNull();
  });
});
