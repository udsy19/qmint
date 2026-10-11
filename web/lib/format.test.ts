import { describe, expect, it } from "vitest";
import { NO_BOUND, formatInterval, formatNumber, formatValue } from "./format";

describe("formatNumber", () => {
  it("keeps tiny probabilities visible (never 0)", () => {
    expect(formatNumber(1e-9)).toBe("1.000e−9");
    expect(formatNumber(0.75 ** 64)).not.toBe("0");
  });
  it("formats ordinary values compactly", () => {
    expect(formatNumber(0.75)).toBe("0.75");
    expect(formatNumber(0.728553390593)).toBe("0.728553");
    expect(formatNumber(8)).toBe("8");
  });
  it("renders missing values as text, never 0", () => {
    expect(formatValue(null, NO_BOUND)).toBe("no applicable bound");
    expect(formatValue(undefined)).toBe("not reported");
  });
  it("formats intervals", () => {
    expect(formatInterval(0.7237, 0.7351)).toBe("[0.7237, 0.7351]");
  });
  it("refuses non-finite numbers", () => {
    expect(() => formatNumber(Number.NaN)).toThrow();
  });
});
