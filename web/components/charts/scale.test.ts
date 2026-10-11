import { describe, expect, it } from "vitest";
import { formatLog10Bound, formatNs, formatPow10, linearDomain, linearTicks, logDomain, logTicks, middleTruncate, paretoFrontier } from "./scale";

describe("chart scale helpers", () => {
  it("log ticks cover whole decades", () => {
    expect(logTicks(15, 3e5)).toEqual([10, 100, 1000, 1e4, 1e5, 1e6]);
    expect(logTicks(-1, 10)).toEqual([]);
    expect(logTicks(1e-12, 1, 4).length).toBeLessThanOrEqual(4);
  });

  it("domains pad and ignore non-positive values on log scale", () => {
    expect(logDomain([0, 15, 3e5])).toEqual([10, 1e6]);
    expect(logDomain([1e4, 2e4])).toEqual([1e3, 1e5]);
    expect(logDomain([0, -1])).toBeNull();
    expect(linearDomain([0.01, 0.03])![0]).toBeLessThan(0.01);
    expect(linearDomain([5, 5])).toEqual([4.5, 5.5]);
  });

  it("picks 1-2-5 linear ticks", () => {
    expect(linearTicks(0.0128, 0.018, 5)).toEqual([0.014, 0.016, 0.018]);
    expect(linearTicks(1, 1)).toEqual([]);
  });

  it("formats nanoseconds and powers of ten", () => {
    expect(formatNs(15_337)).toBe("15.3 µs");
    expect(formatNs(1_948_000)).toBe("1.95 ms");
    expect(formatNs(500)).toBe("500 ns");
    expect(formatPow10(1e-9)).toBe("10⁻⁹");
  });

  it("never turns a missing or tiny bound into 0", () => {
    expect(formatLog10Bound(null)).toBeNull();
    expect(formatLog10Bound(-9.120527772405897)).toBe("7.58e−10");
    expect(formatLog10Bound(-457.152)).toBe("10^−457.15");
    expect(formatLog10Bound(0)).toBe("1");
  });

  it("finds the Pareto frontier when minimising both axes", () => {
    const pts = [
      { id: "a", x: 1, y: 5 },
      { id: "b", x: 2, y: 2 },
      { id: "c", x: 3, y: 3 },
      { id: "d", x: 4, y: 1 },
    ];
    expect(paretoFrontier(pts).map((p) => p.id)).toEqual(["a", "b", "d"]);
  });

  it("middle-truncates long hashes", () => {
    expect(middleTruncate("0123456789abcdef0123456789")).toBe("01234567…23456789");
    expect(middleTruncate("short")).toBe("short");
  });
});
