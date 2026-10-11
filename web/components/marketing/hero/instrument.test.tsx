import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Instrument } from "./instrument";
import { loadInstrument } from "./instrument-data";
import { attackResponse, mintResponse } from "./instrument-fixtures";

type Body = { attack?: Parameters<typeof attackResponse>[0]; n?: number; n_qubits?: number; trials?: number; include_sdp?: boolean; teaching_reveal?: boolean };

function fakeApi(calls: { path: string; body: Body }[]) {
  return vi.fn(async (url: string, init: RequestInit) => {
    const body = JSON.parse(String(init.body)) as Body;
    calls.push({ path: url, body });
    const payload = url.endsWith("/lab/mint")
      ? mintResponse(body.n_qubits ?? 1, { reveal: body.teaching_reveal })
      : attackResponse(body.attack ?? "A04_mvw_optimal_channel", body.n ?? 1, { trials: body.trials, sdp: body.include_sdp });
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

  it("selecting the leaked-secret control calls CTRL_secret_leak, reveals the note and marks it OUT-OF-MODEL", async () => {
    await mount();
    await act(async () => fireEvent.click(screen.getByRole("radio", { name: /Leaked secret/ })));
    await waitFor(() => expect(document.querySelector('[data-source="out_of_model"]')).not.toBeNull());
    expect(calls.some((c) => c.body.attack === "CTRL_secret_leak")).toBe(true);
    expect(calls.some((c) => c.path.endsWith("/lab/mint") && c.body.teaching_reveal === true)).toBe(true);
    expect(document.querySelector('[data-evidence="OUT_OF_MODEL"]')).not.toBeNull();
    expect(screen.getAllByText(/does not apply/).length).toBeGreaterThan(0);
    await waitFor(() => expect(screen.getByText(/out-of-model control/)).toBeInTheDocument());
  });

  it("in-model attacks never ask the API to reveal the secret", async () => {
    await mount();
    await act(async () => fireEvent.click(screen.getByRole("radio", { name: /Measure/ })));
    await waitFor(() => expect(calls.some((c) => c.body.attack === "A01_basis_guess_resend")).toBe(true));
    expect(calls.some((c) => c.body.teaching_reveal)).toBe(false);
  });

  it("Monte Carlo runs fresh notes for attacks and is unavailable for the honest holder", async () => {
    await mount();
    const box = screen.getByRole("checkbox", { name: /Monte Carlo/ });
    expect(box).toBeEnabled();
    await act(async () => fireEvent.click(box));
    await waitFor(() => expect(document.querySelector('[data-source="monte_carlo"] [data-evidence="MONTE_CARLO"]')).not.toBeNull());
    expect(calls.some((c) => c.body.trials === 1000 && c.body.n === 4)).toBe(true);
    expect(screen.getByText(/95% CI/)).toBeInTheDocument();
    await act(async () => fireEvent.click(screen.getByRole("radio", { name: /Honest/ })));
    await waitFor(() => expect(box).toBeDisabled());
  });

  it("shows an explicit error state when the API fails", async () => {
    await mount();
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ error: { code: "x", message: "boom" } }), { status: 500 })));
    await act(async () => fireEvent.click(screen.getByRole("radio", { name: /Measure/ })));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/did not answer/));
  });
});
