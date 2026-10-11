/**
 * Fetches everything the instrument needs for one (scenario, n, sampled) selection, through the
 * typed API client only. Works on the server (initial render) and in the browser.
 */
import { apiPost, type RequestOptions } from "@/lib/api/client";
import { buildReadings, getScenario, type ApiAttack, type InstrumentReadings, type MintResponse, type ScenarioId } from "./instrument-model";

export const DEMO_SEED = 42;
/** Fresh notes per Monte Carlo run: ~1 s at n = 8 on the local API. */
export const SAMPLE_TRIALS = 1000;
/** The API solves and certifies the W1 SDP only for n ≤ 2. */
export const SDP_MAX_N = 2;

export interface InstrumentSelection {
  scenario: ScenarioId;
  n: number;
  sampled: boolean;
}

export interface InstrumentSnapshot {
  selection: InstrumentSelection;
  readings: InstrumentReadings;
  /**
   * The note's states are the bank's secret, so they are hidden ("?") except in the leaked-secret
   * control, where the API's TEST_ONLY teaching reveal is exactly the out-of-model premise.
   */
  note: { label: string; states: (string | null)[]; revealed: boolean };
  provenance: { gitSha: string; seed: number };
}

const attackBody = (attack: ApiAttack, n: number, trials: number) => ({
  attack,
  n,
  seed: DEMO_SEED,
  trials,
  include_sdp: n <= SDP_MAX_N,
  // API defaults, required by the generated request type; they only affect A06/A08, not used here.
  max_loss_fraction: 0.5,
  max_error_fraction: 0,
  probes: 10,
});

const mintBody = (n: number, reveal: boolean) => ({
  protocol_id: "wiesner_ideal" as const,
  n_qubits: n,
  seed: DEMO_SEED,
  backend: "exact" as const,
  shots: 1,
  threshold: 0,
  trials: 0,
  teaching_reveal: reveal,
});

export async function loadInstrument(sel: InstrumentSelection, opts: RequestOptions = {}): Promise<InstrumentSnapshot> {
  const scenario = getScenario(sel.scenario);
  const label = `W1 note · n = ${sel.n} · seed ${DEMO_SEED}`;
  const hidden = Array.from({ length: sel.n }, () => null);

  if (scenario.backend.kind === "honest") {
    const mint = await apiPost("/api/v1/lab/mint", mintBody(sel.n, false), opts);
    return {
      selection: sel,
      readings: buildReadings(sel.scenario, sel.n, { kind: "honest", mint }),
      note: { label, states: hidden, revealed: false },
      provenance: { gitSha: mint.provenance.git_sha, seed: DEMO_SEED },
    };
  }

  const attack = scenario.backend.attack;
  const reveal = attack === "CTRL_secret_leak";
  const [perQubit, nQubit, teach] = await Promise.all([
    apiPost("/api/v1/lab/attack", { ...attackBody(attack, 1, 0), include_sdp: false }, opts),
    apiPost("/api/v1/lab/attack", attackBody(attack, sel.n, sel.sampled ? SAMPLE_TRIALS : 0), opts),
    reveal ? apiPost("/api/v1/lab/mint", mintBody(sel.n, true), opts) : Promise.resolve<MintResponse | null>(null),
  ]);
  const revealed = teach?.data.teaching?.qubits.map((q) => q.state_label) ?? null;
  return {
    selection: sel,
    readings: buildReadings(sel.scenario, sel.n, { kind: "attack", perQubit, nQubit }),
    note: { label, states: revealed ?? hidden, revealed: revealed !== null },
    provenance: { gitSha: nQubit.provenance.git_sha, seed: DEMO_SEED },
  };
}
