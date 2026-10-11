import { describe, expect, it } from "vitest";
import { crumbsFor, isActive, NAV_ITEMS } from "./nav";

describe("platform nav", () => {
  it("covers every platform route exactly once", () => {
    expect(NAV_ITEMS.map((n) => n.href)).toEqual(["/app", "/lab/mint", "/lab/attack", "/benchmarks", "/certificates", "/research", "/docs"]);
  });

  it("marks parents active for nested routes but not prefixes of other words", () => {
    expect(isActive("/research/P01", "/research")).toBe(true);
    expect(isActive("/docs", "/docs")).toBe(true);
    expect(isActive("/applications", "/app")).toBe(false);
  });

  it("builds breadcrumbs, with /lab as a non-link group and resolved dynamic labels", () => {
    expect(crumbsFor("/lab/attack")).toEqual([
      { href: null, label: "Lab" },
      { href: "/lab/attack", label: "Attack" },
    ]);
    const resolve = (href: string, seg: string) => (href.startsWith("/docs/") ? `Doc:${seg}` : undefined);
    expect(crumbsFor("/docs/cli", resolve)).toEqual([
      { href: "/docs", label: "Docs" },
      { href: "/docs/cli", label: "Doc:cli" },
    ]);
    expect(crumbsFor("/research/T-MVW12-THM1").at(-1)).toEqual({ href: "/research/T-MVW12-THM1", label: "T-MVW12-THM1" });
  });
});
