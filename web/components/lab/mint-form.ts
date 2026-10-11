/** Mint form state → validated API request (pure; unit-tested). */
import { LIMITS, type LabNoise, type MintRequest } from "./lab-api";
import { parseIntField } from "./controls";

export interface MintForm {
  protocol: MintRequest["protocol_id"];
  n: number;
  threshold: number;
  seedText: string;
  noise: LabNoise;
  backend: MintRequest["backend"];
  shotsText: string;
  trialsText: string;
}

export const DEFAULT_MINT_FORM: MintForm = {
  protocol: "wiesner_ideal",
  n: 4,
  threshold: 1,
  seedText: "42",
  noise: { channel: "none", strength: 0 },
  backend: "aer",
  shotsText: "2000",
  trialsText: "1000",
};

export type MintErrors = Partial<Record<"seed" | "shots" | "trials" | "threshold", string>>;

export function buildMintRequest(f: MintForm, teaching: boolean): { request?: MintRequest; errors: MintErrors } {
  const errors: MintErrors = {};
  const seed = parseIntField(f.seedText, 0, 2 ** 31 - 1, "Seed");
  const shots = parseIntField(f.shotsText, 1, LIMITS.shotsMax, "Shots");
  const trials = parseIntField(f.trialsText, 0, LIMITS.trialsMax, "Trials");
  if (seed.error) errors.seed = seed.error;
  if (f.backend === "aer" && shots.error) errors.shots = shots.error;
  if (trials.error) errors.trials = trials.error;
  const noisy = f.protocol === "wiesner_noisy";
  if (noisy && !(f.threshold >= 1 && f.threshold < f.n)) errors.threshold = "Threshold must be at least 1 and below n (use n ≥ 2).";
  if (Object.keys(errors).length) return { errors };
  return {
    errors,
    request: {
      protocol_id: f.protocol,
      n_qubits: f.n,
      threshold: noisy ? f.threshold : 0,
      seed: seed.value!,
      noise: f.noise.channel === "none" ? { channel: "none", strength: 0 } : f.noise,
      backend: f.backend,
      shots: f.backend === "aer" ? shots.value! : 1,
      trials: trials.value!,
      teaching_reveal: teaching,
    },
  };
}

export function curlFor(path: string, body: unknown): string {
  return `curl -s -X POST http://127.0.0.1:8787${path} \\\n  -H 'content-type: application/json' \\\n  -d '${JSON.stringify(body)}'`;
}
