import { describe, expect, it } from "vitest";
import { calibrationPreview, fromRequest, toRequest, type CertRequest, type GameEntry } from "./form-model";

const s2: CertRequest = {
  game: "S2",
  protocol_id: "s_money_kent_2022_realistic",
  targets: { epsilon_unf: 1e-9, epsilon_cor: 1e-9 },
  parameters: { N: 40000000, P_noqub: { lo: 0.0037, hi: 0.0038 }, theta: 0.1745 },
  declared_assumptions: ["table6_A_two_bases"],
  noise_source: "hypothetical",
  calibration: "none",
};

describe("certificate form model", () => {
  it("round-trips a request with points and intervals", () => {
    const { request, errors } = toRequest(fromRequest(s2));
    expect(errors).toEqual({});
    expect(request.parameters).toEqual(s2.parameters);
    expect(request.targets).toEqual({ epsilon_unf: 1e-9, epsilon_cor: 1e-9 });
    expect(request.noise_source).toBe("hypothetical");
  });

  it("empty target means no target, never 0", () => {
    const st = fromRequest(s2);
    st.targets.epsilon_cor = "";
    expect(toRequest(st).request.targets).toEqual({ epsilon_unf: 1e-9 });
  });

  it("rejects invalid numbers, non-integer sizes, reversed intervals and out-of-range targets", () => {
    const st = fromRequest(s2);
    st.params.N = { mode: "point", value: "4.5", lo: "", hi: "" };
    st.params.P_noqub = { mode: "interval", value: "", lo: "0.004", hi: "0.003" };
    st.params.theta = { mode: "point", value: "abc", lo: "", hi: "" };
    st.targets.epsilon_unf = "0";
    const { errors } = toRequest(st);
    expect(Object.keys(errors).sort()).toEqual(["param.N", "param.P_noqub", "param.theta", "target.epsilon_unf"]);
  });

  it("accepts unicode minus and ×10^ notation", () => {
    const st = fromRequest(s2);
    st.targets.epsilon_unf = "1×10^−6";
    expect(toRequest(st).request.targets?.epsilon_unf).toBe(1e-6);
  });

  it("previews calibration family checks from the theorem's declared families", () => {
    const entry = { sizing_available: false, theorem: { calibration_families: ["kent_2022"] } } as unknown as GameEntry;
    expect(calibrationPreview(entry, "schiansky_2023")).toBe("mismatch");
    expect(calibrationPreview(entry, "kent_2022")).toBe("match");
    expect(calibrationPreview({ sizing_available: true } as GameEntry, "schiansky_2023")).toBe("ideal");
    expect(calibrationPreview(entry, null)).toBe("none");
  });
});
