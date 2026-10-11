import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Instrument } from "./instrument";
import { loadInstrument } from "./instrument-data";
import { attackResponse, mintResponse } from "./instrument-fixtures";

type Body = { attack?: Parameters<typeof attackResponse>[0]; n?: number; n_qubits?: number; backend?: string };

function fakeApi(calls: { path: string; body: Body }[]) {
  return vi.fn(async (url: string, init: RequestInit) => {
    const body = JSON.parse(String(init.body)) as Body;
    calls.push({ path: url, body });
    const payload = url.endsWith("/lab/mint")
      ? mintResponse(body.n_qubits ?? 1)
      : attackResponse(body.attack ?? "mvw_channel", body.n ?? 1, body.backend === "aer" ? { aer: { value: 0.55, lo: 0.52, hi: 0.58, trials: 2000 } } : undefined);
    return new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } });
  });
}

describe("<Instrument/>", () => {
  const calls: { path: string; body: Body }[] = [];
  beforeEach(() => {
    calls.length = 0;
    vi.stubGlobal("fetch", fakeApi(calls));
  });
  afterEach(() => vi.unstubAllGlobals());

  async function mount() {
    const initial = await loadInstrument({ scenario: "mvw_channel", n: 4, sampled: false });
    calls.length = 0;
    render(
      <TooltipProvider>
        <Instrument initial={initial} />
      </TooltipProvider>,
    );
  }

  it("renders the initial reading with its exact-model label and the theorem bound", async () => {
    await mount();
    expect(document.querySelector('[data-source="exact_model"] [data-evidence="SIMULATOR_IDEAL"]')).not.toBeNull();
    expect(document.querySelector('[data-source="theorem"] [data-evidence="PUBLISHED_THEOREM"]')).not.toBeNull();
    expect(calls).toHaveLength(0); // server-provided initial data, no refetch on mount
  });

  it("selecting the leaked-secret control queries /lab/mint and labels the result OUT-OF-MODEL", async () => {
    await mount();
    await act(async () => fireEvent.click(screen.getByRole("radio", { name: /Leaked secret/ })));
    await waitFor(() => expect(document.querySelector('[data-source="out_of_model"]')).not.toBeNull());
    expect(calls.some((c) => c.path.endsWith("/lab/mint"))).toBe(true);
    expect(document.querySelector('[data-source="out_of_model"] [data-evidence="OUT_OF_MODEL"]')).not.toBeNull();
    expect(screen.getByText(/does not apply/)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/out-of-model control/)).toBeInTheDocument());
  });

  it("Monte Carlo sampling is only offered where the API can run it (cloners, n ≤ 2)", async () => {
    await mount();
    const box = screen.getByRole("checkbox", { name: /sample with Aer/ });
    expect(box).toBeDisabled(); // n = 4
    await act(async () => fireEvent.click(screen.getByRole("radio", { name: "n = 2" })));
    await waitFor(() => expect(box).toBeEnabled());
    await act(async () => fireEvent.click(box));
    await waitFor(() => expect(document.querySelector('[data-source="monte_carlo"]')).not.toBeNull());
    expect(calls.some((c) => c.body.backend === "aer" && c.body.n === 2)).toBe(true);
    expect(screen.getByText(/99% CI/)).toBeInTheDocument();
  });

  it("shows an explicit error state when the API fails", async () => {
    await mount();
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ error: { code: "x", message: "boom" } }), { status: 500 })));
    await act(async () => fireEvent.click(screen.getByRole("radio", { name: /Measure/ })));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/did not answer/));
  });
});
