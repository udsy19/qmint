import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import a04 from "./__fixtures__/attack-a04-n2.json";
import a08 from "./__fixtures__/attack-a08-n3.json";
import mintTeach from "./__fixtures__/mint-n3-teaching.json";
import { attackVerdict, buildAttackRequest, DEFAULT_ATTACK_FORM, trialsCap } from "./attack-form";
import { CircuitDiagram } from "./circuit-diagram";
import { axisPosition, axisTicks, buildComparison } from "./comparison";
import { ComparisonChart } from "./comparison-chart";
import { parseIntField } from "./controls";
import { ErrorHistogram } from "./error-histogram";
import { tierOf, type AttackResponse, type MintResponse } from "./lab-api";
import { buildMintRequest, DEFAULT_MINT_FORM } from "./mint-form";
import { QuantityReadout } from "./quantity";
import { RunStatus } from "./run-status";
import { formatSerial, TokenStrip } from "./token-strip";
import { VerificationFlow } from "./verification-flow";

const A04 = a04 as unknown as AttackResponse;
const A08 = a08 as unknown as AttackResponse;
const MINT = mintTeach as unknown as MintResponse;

const wrap = (ui: React.ReactNode) => render(<TooltipProvider>{ui}</TooltipProvider>);

describe("form → request", () => {
  it("validates integer fields against the API caps", () => {
    expect(parseIntField("12", 0, 20, "Seed")).toEqual({ value: 12 });
    expect(parseIntField("1.5", 0, 20, "Seed").error).toMatch(/whole number/);
    expect(parseIntField("21", 0, 20, "Shots").error).toMatch(/between 0 and 20/);
  });

  it("builds a mint request; threshold only for the W2 scheme; teaching is explicit", () => {
    const { request } = buildMintRequest(DEFAULT_MINT_FORM, false);
    expect(request).toMatchObject({ protocol_id: "wiesner_ideal", threshold: 0, teaching_reveal: false, n_qubits: 4 });
    expect(buildMintRequest(DEFAULT_MINT_FORM, true).request?.teaching_reveal).toBe(true);
    const noisy = buildMintRequest({ ...DEFAULT_MINT_FORM, protocol: "wiesner_noisy", n: 1, threshold: 1 }, false);
    expect(noisy.request).toBeUndefined();
    expect(noisy.errors.threshold).toBeTruthy();
    expect(buildMintRequest({ ...DEFAULT_MINT_FORM, shotsText: "20001" }, false).errors.shots).toBeTruthy();
    expect(buildMintRequest({ ...DEFAULT_MINT_FORM, backend: "exact", shotsText: "x" }, false).request?.shots).toBe(1);
  });

  it("caps A08 trials lower than the rest", () => {
    expect(trialsCap("A08_adaptive_oracle_probe")).toBe(400);
    expect(buildAttackRequest({ ...DEFAULT_ATTACK_FORM, attack: "A08_adaptive_oracle_probe", trialsText: "401" }).errors.trials).toBeTruthy();
    expect(buildAttackRequest({ ...DEFAULT_ATTACK_FORM, trialsText: "401" }).request?.trials).toBe(401);
  });
});

describe("attack comparison", () => {
  it("separates analytic, simulated and hardware; QPU is never a number", () => {
    const c = buildComparison(A04.data);
    const byTier = Object.fromEntries(c.groups.map((g) => [g.tier, g.rows.map((r) => r.id)]));
    expect(byTier.analytic).toEqual(expect.arrayContaining(["counterfeit_exact", "w1_theorem_bound", "sdp_bracket"]));
    expect(byTier.simulated).toEqual(expect.arrayContaining(["counterfeit_mc", "honest_accept_mc"]));
    expect(byTier.hardware).toEqual(["qpu"]);
    expect(c.groups.find((g) => g.tier === "hardware")!.rows[0]!.value).toBeNull();
    expect(c.bound).toBeCloseTo(0.5625);
    const sdp = c.groups[0]!.rows.find((r) => r.id === "sdp_bracket")!;
    expect(sdp.lo).toBe(0.5625);
    expect(sdp.hi!).toBeGreaterThanOrEqual(0.5625);
  });

  it("uses a log axis when values span decades", () => {
    expect(axisTicks("log", 0.001)).toEqual([0.001, 0.01, 0.1, 1]);
    expect(axisPosition(0.01, "log", 0.001)).toBeCloseTo(1 / 3);
    expect(axisPosition(0.5, "linear", 0)).toBe(0.5);
    expect(tierOf({ method: "monte_carlo", evidence_kind: "MONTE_CARLO" })).toBe("simulated");
    expect(tierOf({ method: "not_available", evidence_kind: "QPU" })).toBe("hardware");
  });

  it("verdicts: optimal at the bound; out-of-model never claims to beat the theorem", () => {
    expect(attackVerdict(A04.data).text).toMatch(/optimal/);
    const v = attackVerdict(A08.data);
    expect(v.tone).toBe("danger");
    expect(v.text).toMatch(/theorem does not apply/);
  });

  it("renders every row with its value text and the hardware row as not run", () => {
    wrap(<ComparisonChart c={buildComparison(A08.data)} />);
    expect(screen.getByRole("heading", { name: "Hardware" })).toBeInTheDocument();
    expect(screen.getAllByText("not run").length).toBeGreaterThan(0);
    expect(screen.getAllByText("no applicable bound").length).toBeGreaterThan(0); // theorem null → text, not 0
    expect(screen.queryByText("W1 theorem bound")).toBeNull(); // no bound rule when no theorem applies
  });
});

describe("mint components", () => {
  it("token strip hides states unless teaching data is passed", () => {
    const { rerender } = wrap(<TokenStrip serial="SN-0c0e00da99c9c0f5" n={3} />);
    expect(screen.getAllByRole("img", { name: "unknown state" })).toHaveLength(3);
    expect(screen.getByText("SN-0C0E 00DA 99C9 C0F5")).toBeInTheDocument();
    rerender(
      <TooltipProvider>
        <TokenStrip serial="SN-1" n={3} qubits={MINT.data.teaching!.qubits} />
      </TooltipProvider>,
    );
    expect(screen.queryAllByRole("img", { name: "unknown state" })).toHaveLength(0);
    expect(formatSerial("SN-abcdef")).toBe("SN-ABCD EF");
  });

  it("redacted circuit shows no gates; teaching circuit shows X/H", () => {
    const { container, rerender } = render(<CircuitDiagram circuit={MINT.data.circuit} />);
    expect(MINT.data.circuit.redacted).toBe(true);
    expect(container.textContent).not.toMatch(/\bH\b|\bX\b/);
    expect(screen.getByRole("img").getAttribute("aria-label")).toMatch(/secret preparation/);
    rerender(<CircuitDiagram circuit={MINT.data.teaching!.circuit} />);
    const gates = MINT.data.teaching!.circuit.qubits.flatMap((q) => q.prepare);
    if (gates.length) expect(container.textContent).toMatch(/H|X/);
  });

  it("public mint fixture carries no secret outside the teaching block", () => {
    const { teaching, ...pub } = MINT.data;
    expect(teaching).not.toBeNull();
    const text = JSON.stringify(pub);
    for (const k of ['"bases"', '"bits"', '"basis"', '"state_label"', '"qasm2"', '"circuit_sha256"']) expect(text).not.toContain(k);
  });

  it("histogram marks accepted rows and lists exact + sampled values", () => {
    wrap(<ErrorHistogram rows={MINT.data.statistics.error_counts} shots={MINT.data.statistics.shots ?? null} threshold={0} />);
    const rows = screen.getAllByRole("row");
    expect(rows).toHaveLength(MINT.data.statistics.error_counts.length + 1);
    expect(within(rows[1]!).getByText(/accepted/)).toBeInTheDocument();
    expect(within(rows[2]!).getByText(/rejected/)).toBeInTheDocument();
  });

  it("verification flow shows the replay refusal", () => {
    render(<VerificationFlow steps={MINT.data.flow} />);
    expect(screen.getByText("refused")).toBeInTheDocument();
    expect(screen.getByText("Same serial presented again")).toBeInTheDocument();
  });

  it("quantity readout: null renders text, never 0; CI and method shown", () => {
    wrap(<QuantityReadout q={MINT.data.hardware} missing="not run" />);
    expect(screen.getByText("not run")).toBeInTheDocument();
    expect(screen.queryByText("0")).toBeNull();
    const mc = MINT.data.statistics.acceptance.find((q) => q.method === "monte_carlo")!;
    wrap(<QuantityReadout q={mc} />);
    expect(screen.getAllByText(/95% CI/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Monte Carlo · fresh notes/)).toBeInTheDocument();
  });
});

describe("RunStatus", () => {
  it("shows words for each phase and Cancel only while active", () => {
    const { rerender } = render(<RunStatus phase="running" startedAt={0} onCancel={() => {}} />);
    expect(screen.getByRole("status")).toHaveTextContent("Computing on the server");
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
    rerender(<RunStatus phase="timeout" startedAt={0} finishedAt={20} onCancel={() => {}} />);
    expect(screen.getByRole("status")).toHaveTextContent("Timed out");
    expect(screen.queryByRole("button", { name: "Cancel" })).toBeNull();
  });
});

