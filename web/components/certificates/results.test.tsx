import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import d1 from "./__fixtures__/d1-schiansky.json";
import w1 from "./__fixtures__/w1-n73.json";
import w1priv from "./__fixtures__/w1-privacy.json";
import type { CertData } from "./form-model";
import { AxesTable, ExportPanel, VerdictPanel } from "./results";

// Fixtures are real POST /api/v1/certificates responses (lane D engine + checker) for catalog presets.
const wrap = (ui: React.ReactNode) => render(<TooltipProvider>{ui}</TooltipProvider>);

describe("certificate results", () => {
  it("shows CERTIFIED only when the independent checker says so", () => {
    wrap(<VerdictPanel d={w1 as unknown as CertData} />);
    expect(screen.getAllByText("CERTIFIED").length).toBeGreaterThan(0);
  });

  it("D1 renders UNCERTIFIED with the checker's reason even though the bound meets the target", () => {
    const d = d1 as unknown as CertData;
    expect(d.axes.find((a) => a.axis === "epsilon_unf")!.meets_target).toBe(true);
    const { container } = wrap(<VerdictPanel d={d} />);
    expect(within(container).queryByText("CERTIFIED")).toBeNull();
    expect(container.textContent).toMatch(/never certified/);
  });

  it("a missing privacy theorem renders as 'no applicable bound', never 0", () => {
    const { container } = wrap(<AxesTable d={w1priv as unknown as CertData} />);
    const rows = [...container.querySelectorAll("tbody tr")];
    const priv = rows.find((r) => r.textContent?.includes("Privacy"))!;
    const boundCell = priv.querySelectorAll("td")[2]!;
    expect(boundCell.textContent).toBe("no applicable bound");
    expect(priv.textContent).toContain("cannot be checked");
  });

  it("exports the checker's canonical JSON and hash unchanged", () => {
    const d = w1priv as unknown as CertData;
    wrap(<ExportPanel d={d} />);
    expect(JSON.parse(d.export.canonical_json).proof_check_status).toBe("UNCERTIFIED");
    expect(screen.getByTitle(d.export.sha256)).toBeInTheDocument();
  });
});
