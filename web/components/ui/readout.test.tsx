import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Readout } from "./readout";

describe("Readout", () => {
  it("renders a missing bound as text, never 0", () => {
    render(<dl><Readout label="S2 bound" value={null} missing="no applicable bound" /></dl>);
    expect(screen.getByText("no applicable bound")).toBeInTheDocument();
    expect(screen.queryByText("0")).toBeNull();
  });
  it("shows interval and confidence", () => {
    render(<dl><Readout label="p" value={0.7294} interval={{ lo: 0.7237, hi: 0.7351, confidence: 0.999 }} /></dl>);
    expect(screen.getByText("0.7294")).toBeInTheDocument();
    expect(screen.getByText(/\[0\.7237, 0\.7351\]/)).toBeInTheDocument();
    expect(screen.getByText(/99\.9% CI/)).toBeInTheDocument();
  });
});
