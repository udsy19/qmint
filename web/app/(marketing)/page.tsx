import type { Metadata } from "next";
import { Hero } from "@/components/marketing/hero/hero";
import { DEMO_SEED, loadInstrument, type InstrumentSnapshot } from "@/components/marketing/hero/instrument-data";
import {
  ClassicalSection,
  ClosingSection,
  LabSection,
  OpenSection,
  PrimitiveSection,
  ProblemSection,
  ProofSection,
  type GameInfo,
  type MetaData,
} from "@/components/marketing/sections";
import { FALLBACK_DISCLAIMER } from "@/components/marketing/site";
import { apiGet, apiPost } from "@/lib/api/client";

export const metadata: Metadata = {
  title: { absolute: "QMint — quantum payment security research" },
  description:
    "Design, attack and verify quantum payment protocols with reproducible experiments and labelled evidence. A research platform, not a payment service.",
};

async function settle<T>(p: Promise<T>): Promise<T | null> {
  try {
    return await p;
  } catch {
    return null;
  }
}

export default async function LandingPage() {
  const opts = { timeoutMs: 8000 };
  // Context values for sections 02 and 05: the W1 SDP bracket (n = 1, 2) and the leaked-secret control.
  const probe = (attack: "A04_mvw_optimal_channel" | "CTRL_secret_leak", n: number, include_sdp: boolean) =>
    apiPost(
      "/api/v1/lab/attack",
      { attack, n, seed: DEMO_SEED, trials: 0, include_sdp, max_loss_fraction: 0.5, max_error_fraction: 0, probes: 10 },
      opts,
    );
  const [games, meta, benchmarks, sdp1, sdp2, leak, initial] = await Promise.all([
    settle(apiGet("/api/v1/games", opts)),
    settle(apiGet("/api/v1/meta", opts)),
    settle(apiGet("/api/v1/benchmarks", opts)),
    settle(probe("A04_mvw_optimal_channel", 1, true)),
    settle(probe("A04_mvw_optimal_channel", 2, true)),
    settle(probe("CTRL_secret_leak", 1, false)),
    settle<InstrumentSnapshot>(loadInstrument({ scenario: "mvw_channel", n: 4, sampled: false }, opts)),
  ]);
  const game = (id: string): GameInfo | null => games?.data.find((g) => g.game_id === id) ?? null;
  const metaData: MetaData | null = meta?.data ?? null;
  const brackets = [sdp1, sdp2].flatMap((r) => (r?.data.sdp ? [r.data.sdp] : []));
  const leakValue = leak?.data.counterfeit_success.find((q) => q.id === "counterfeit_exact") ?? null;

  return (
    <main id="main">
      <Hero initial={initial} />
      <ProblemSection />
      <PrimitiveSection w1={game("W1")} leak={leakValue} />
      <LabSection />
      <ClassicalSection s1={game("S1")} comparability={benchmarks?.data.comparability ?? null} />
      <ProofSection w1={game("W1")} sdp={brackets} photon={benchmarks?.data.photon ?? null} />
      <OpenSection meta={metaData} />
      <ClosingSection disclaimer={metaData?.disclaimer ?? FALLBACK_DISCLAIMER} />
    </main>
  );
}
