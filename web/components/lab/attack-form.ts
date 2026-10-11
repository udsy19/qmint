/** Attack form state → validated request, attack catalogue and the verdict sentence (pure; unit-tested). */
import { formatNumber } from "@/lib/format";
import type { Schemas } from "@/lib/api/client";
import { parseIntField } from "./controls";
import { LIMITS, type AttackId, type AttackRequest, type LabNoise } from "./lab-api";

export interface AttackForm {
  attack: AttackId;
  n: number;
  seedText: string;
  trialsText: string;
  noise: LabNoise;
  maxLoss: number;
  maxError: number;
  probes: number;
}

export const DEFAULT_ATTACK_FORM: AttackForm = {
  attack: "A04_mvw_optimal_channel",
  n: 2,
  seedText: "42",
  trialsText: "2000",
  noise: { channel: "none", strength: 0 },
  maxLoss: 0.5,
  maxError: 0,
  probes: 10,
};

export const ATTACK_GROUPS: { title: string; items: { id: AttackId; label: string }[] }[] = [
  {
    title: "Game W1 · theorem applies",
    items: [
      { id: "A01_basis_guess_resend", label: "A01 · measure and resend" },
      { id: "A01b_basis_guess_bayes_resend", label: "A01b · measure, smarter resend" },
      { id: "A02_breidbart_resend", label: "A02 · Breidbart measure-resend" },
      { id: "A02b_breidbart_bayes_resend", label: "A02b · Breidbart, smarter resend" },
      { id: "A03_universal_buzek_hillery", label: "A03 · universal cloner" },
      { id: "A03b_phase_covariant_xz", label: "A03b · phase-covariant cloner" },
      { id: "A04_mvw_optimal_channel", label: "A04 · optimal channel (MVW)" },
    ],
  },
  {
    title: "Outside W1 · no theorem",
    items: [
      { id: "A06_split_and_report_loss", label: "A06 · loss reporting vs toy verifier" },
      { id: "A08_adaptive_oracle_probe", label: "A08 · leaky-oracle probing" },
      { id: "CTRL_secret_leak", label: "Control · secret leaked" },
    ],
  },
];

export function trialsCap(attack: AttackId): number {
  return attack === "A08_adaptive_oracle_probe" ? LIMITS.trialsMaxA08 : LIMITS.trialsMax;
}

export type AttackErrors = Partial<Record<"seed" | "trials", string>>;

export function buildAttackRequest(f: AttackForm): { request?: AttackRequest; errors: AttackErrors } {
  const errors: AttackErrors = {};
  const seed = parseIntField(f.seedText, 0, 2 ** 31 - 1, "Seed");
  const trials = parseIntField(f.trialsText, 0, trialsCap(f.attack), "Trials");
  if (seed.error) errors.seed = seed.error;
  if (trials.error) errors.trials = trials.error;
  if (Object.keys(errors).length) return { errors };
  return {
    errors,
    request: {
      attack: f.attack,
      n: f.n,
      seed: seed.value!,
      trials: trials.value!,
      noise: f.noise.channel === "none" ? { channel: "none", strength: 0 } : f.noise,
      max_loss_fraction: f.maxLoss,
      max_error_fraction: f.maxError,
      probes: f.probes,
      include_sdp: true,
    },
  };
}

type AttackData = Schemas["AttackData"];

export interface Verdict {
  tone: "neutral" | "warn" | "danger";
  text: string;
}

/** One sentence that says what the numbers mean, without overclaiming. */
export function attackVerdict(d: AttackData): Verdict {
  const exact = d.counterfeit_success.find((q) => q.id === "counterfeit_exact")?.value ?? null;
  const bound = d.theorem_bound.value ?? null;
  if (exact === null) return { tone: "neutral", text: "No exact value is available for this attack." };
  const p = formatNumber(exact, { sig: 4 });
  if (d.proof_applicability === "OUT_OF_MODEL") {
    return {
      tone: "danger",
      text: `Forges both notes with probability ${p} — but only by breaking a rule of game W1 (${d.attack === "CTRL_secret_leak" ? "the secret left the bank" : "the bank answers and returns the note"}). The theorem does not apply, and this says nothing against Wiesner money as specified.`,
    };
  }
  if (d.proof_applicability === "NO_THEOREM") {
    return {
      tone: "warn",
      text: `Forges both notes with probability ${p} against the toy loss-tolerant verifier (game W2). No theorem covers this verifier; a loss allowance this generous breaks it.`,
    };
  }
  if (bound === null) return { tone: "neutral", text: `Forges both notes with probability ${p}.` };
  const ratio = exact / bound;
  const at = Math.abs(ratio - 1) < 1e-9;
  return {
    tone: "neutral",
    text: at
      ? `Forges both notes with probability ${p}, exactly the theorem’s (3/4)ⁿ: this attack is optimal, and no attack does better.`
      : `Forges both notes with probability ${p}, ${formatNumber(ratio, { sig: 3 })}× the theorem bound ${formatNumber(bound, { sig: 4 })}. Any value is a lower bound on what the best attacker achieves; the theorem caps all of them.`,
  };
}
