/**
 * Fetches everything the instrument needs for one (scenario, n, sampled) selection, through the
 * typed API client only. Works on the server (initial render) and in the browser.
 */
import { apiPost, type RequestOptions } from "@/lib/api/client";
import {
  buildReadings,
  getScenario,
  type InstrumentReadings,
  type MintResponse,
  type ScenarioId,
} from "./instrument-model";

export const DEMO_SEED = 42;
export const SAMPLE_SHOTS = 2000;

export interface InstrumentSelection {
  scenario: ScenarioId;
  n: number;
  sampled: boolean;
}

export interface InstrumentSnapshot {
  selection: InstrumentSelection;
  readings: InstrumentReadings;
  /** Issuer view of the seeded demo note (public teaching example) for the per-qubit glyphs. */
  note: { tokenId: string; states: string[]; seed: number };
  provenance: { gitSha: string; generatedAt: string };
}

const mint = (n: number, opts: RequestOptions) =>
  apiPost("/api/v1/lab/mint", { protocol_id: "wiesner_ideal", n_qubits: n, seed: DEMO_SEED, backend: "analytic", shots: 1 }, opts);

export async function loadInstrument(sel: InstrumentSelection, opts: RequestOptions = {}): Promise<InstrumentSnapshot> {
  const scenario = getScenario(sel.scenario);
  let readings: InstrumentReadings;
  let noteResp: MintResponse;

  if (scenario.backend.kind === "attack") {
    const attack = scenario.backend.attack;
    const sampled = sel.sampled && scenario.sampleable;
    const body = (n: number, aer: boolean) =>
      ({ protocol_id: "wiesner_ideal", game: "W1", attack, n, seed: DEMO_SEED, backend: aer ? "aer" : "analytic", shots: SAMPLE_SHOTS }) as const;
    const [perQubit, nQubit, note] = await Promise.all([
      apiPost("/api/v1/lab/attack", body(1, false), opts),
      apiPost("/api/v1/lab/attack", body(sel.n, sampled), opts),
      mint(sel.n, opts),
    ]);
    readings = buildReadings(sel.scenario, sel.n, { kind: "attack", perQubit, nQubit });
    noteResp = note;
  } else {
    const [perQubit, nQubit, ref] = await Promise.all([
      mint(1, opts),
      mint(sel.n, opts),
      apiPost(
        "/api/v1/lab/attack",
        { protocol_id: "wiesner_ideal", game: "W1", attack: "honest", n: sel.n, seed: DEMO_SEED, backend: "analytic", shots: 1 },
        opts,
      ),
    ]);
    readings = buildReadings(sel.scenario, sel.n, { kind: "mint_control", perQubit, nQubit, theorem: ref.data.theorem_bound });
    noteResp = nQubit;
  }

  return {
    selection: sel,
    readings,
    note: {
      tokenId: noteResp.data.token.token_id,
      states: noteResp.data.issuer_view.qubits.map((q) => q.state_label),
      seed: DEMO_SEED,
    },
    provenance: { gitSha: noteResp.provenance.git_sha, generatedAt: noteResp.provenance.generated_at_utc },
  };
}
