import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EVIDENCE_LABELS, getEvidenceLabel } from "@/lib/evidence";
import { EvidenceLabel } from "./evidence-label";
import { TooltipProvider } from "./tooltip";

describe("evidence labels", () => {
  it("covers every frozen EvidenceKind, CertificateStatus and API status", () => {
    const keys = (g: string) => EVIDENCE_LABELS.filter((l) => l.group === g).map((l) => l.key).sort();
    expect(keys("evidence_kind")).toHaveLength(14);
    expect(keys("certificate_status")).toEqual(["CERTIFIED", "INFEASIBLE", "OUT_OF_MODEL", "UNCERTIFIED", "UNSAFE"]);
    expect(keys("api_status")).toEqual(["DEMO_ADAPTER", "NOT_AVAILABLE"]);
  });

  it("only CERTIFIED is mint (tone ok)", () => {
    expect(EVIDENCE_LABELS.filter((l) => l.tone === "ok").map((l) => `${l.group}:${l.key}`)).toEqual(["certificate_status:CERTIFIED"]);
  });

  it("simulated and measured never share a label", () => {
    const sim = new Set(EVIDENCE_LABELS.filter((l) => l.origin === "simulated").map((l) => l.label));
    for (const l of EVIDENCE_LABELS.filter((x) => x.origin === "measured")) expect(sim.has(l.label)).toBe(false);
  });

  it("renders text + accessible description, not colour alone", () => {
    render(
      <TooltipProvider>
        <EvidenceLabel kind="MONTE_CARLO" />
      </TooltipProvider>,
    );
    const el = document.querySelector('[data-evidence="MONTE_CARLO"]');
    expect(el).toHaveAttribute("data-origin", "simulated");
    expect(el?.textContent).toContain(getEvidenceLabel("MONTE_CARLO").label);
    expect(screen.getByText(/LOWER bound on worst-case/i, { selector: ".sr-only" })).toBeInTheDocument();
  });

  it("throws on unknown keys instead of rendering a blank badge", () => {
    expect(() => getEvidenceLabel("MADE_UP")).toThrow(/unknown evidence label/);
  });
});
