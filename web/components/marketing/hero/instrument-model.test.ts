import { describe, expect, it } from "vitest";
import { attackResponse, mintResponse, theorem } from "./instrument-fixtures";
import { buildReadings, describe as describeReadings, logPosition, prettyFormula, SCENARIOS } from "./instrument-model";

const attack = (a: Parameters<typeof attackResponse>[0], n: number, aer?: Parameters<typeof attackResponse>[2]) =>
  ({ kind: "attack", perQubit: attackResponse(a, 1), nQubit: attackResponse(a, n, aer) }) as const;

describe("hero instrument: scenario → probability source and label", () => {
  it("MVW channel: exact model value from the API, theorem bound labelled THEOREM", () => {
    const r = buildReadings("mvw_channel", 4, attack("mvw_channel", 4));
    expect(r.joint.value).toBeCloseTo(0.31640625, 12);
    expect(r.joint.source).toBe("exact_model");
    expect(r.joint.evidence).toEqual({ kind: "SIMULATOR_IDEAL", group: "evidence_kind" });
    expect(r.joint.method).toBe("exact enumeration");
    expect(r.joint.formula).toBe("(3/4)ⁿ");
    expect(r.perQubit.value).toBe(0.75);
    expect(r.bound.source).toBe("theorem");
    expect(r.bound.evidence.kind).toBe("PUBLISHED_THEOREM");
    expect(r.bound.applies).toBe(true);
    expect(r.sampled).toBeNull();
    expect(r.apiStatus).toBe("DEMO_ADAPTER");
  });

  it("measure-resend: (5/8)^n is an exact model value, never the theorem", () => {
    const r = buildReadings("measure_resend", 2, attack("measure_resend", 2));
    expect(r.joint.value).toBeCloseTo(0.390625, 12);
    expect(r.joint.source).toBe("exact_model");
    expect(r.joint.evidence.kind).not.toBe("PUBLISHED_THEOREM");
  });

  it("sampled cloner: Monte Carlo reading with its 99% interval and shot count", () => {
    const r = buildReadings("bruss_cloner", 2, attack("bruss_cloner", 2, { aer: { value: 0.526, lo: 0.497, hi: 0.555, trials: 2000 } }));
    expect(r.sampled?.source).toBe("monte_carlo");
    expect(r.sampled?.interval).toEqual({ lo: 0.497, hi: 0.555, confidence: 0.99 });
    expect(r.sampled?.method).toBe("aer sampling · 2,000 shots");
    expect(r.joint.source).toBe("exact_model");
  });

  it("honest holder: joint pass is not applicable (null, never 0)", () => {
    const r = buildReadings("honest", 4, attack("honest", 4));
    expect(r.joint.value).toBeNull();
    expect(r.joint.source).toBe("not_applicable");
    expect(r.single.label).toBe("Genuine note passes");
    expect(r.single.explain).toMatch(/honest acceptance/i);
    expect(describeReadings(r)).toMatch(/not applicable/);
  });

  it("leaked secret: OUT-OF-MODEL control derived from the API's honest acceptance; bound does not apply", () => {
    const r = buildReadings("leaked_secret", 4, {
      kind: "mint_control",
      perQubit: mintResponse(1),
      nQubit: mintResponse(4),
      theorem: theorem(4),
    });
    expect(r.joint.value).toBe(1);
    expect(r.joint.source).toBe("out_of_model");
    expect(r.joint.evidence).toEqual({ kind: "OUT_OF_MODEL", group: "certificate_status" });
    expect(r.joint.apiSource).toMatch(/lab\/mint/);
    expect(r.single.evidence.kind).toBe("OUT_OF_MODEL");
    expect(r.bound.applies).toBe(false);
    expect(r.bound.evidence.kind).toBe("PUBLISHED_THEOREM");
    expect(describeReadings(r)).toMatch(/out-of-model control/);
  });

  it("leaked secret squares a noisy honest acceptance (two independent genuine notes)", () => {
    const r = buildReadings("leaked_secret", 2, { kind: "mint_control", perQubit: mintResponse(1, 0.9), nQubit: mintResponse(2, 0.9), theorem: null });
    expect(r.joint.value).toBeCloseTo(0.81 ** 2, 12);
    expect(r.perQubit.value).toBeCloseTo(0.81, 12);
    expect(r.bound.value).toBeNull();
  });

  it("refuses inputs from the wrong backend", () => {
    expect(() => buildReadings("leaked_secret", 1, attack("mvw_channel", 1))).toThrow();
    expect(() =>
      buildReadings("mvw_channel", 1, { kind: "mint_control", perQubit: mintResponse(1), nQubit: mintResponse(1), theorem: null }),
    ).toThrow();
  });

  it("only the leaked-secret control is out of model, and only cloners can be sampled", () => {
    expect(SCENARIOS.filter((s) => !s.inModel).map((s) => s.id)).toEqual(["leaked_secret"]);
    expect(SCENARIOS.filter((s) => s.sampleable).map((s) => s.id)).toEqual(["bruss_cloner", "mvw_channel"]);
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
