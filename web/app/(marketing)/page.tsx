import type { Metadata } from "next";
import { Hero } from "@/components/marketing/hero/hero";
import { loadInstrument, type InstrumentSnapshot } from "@/components/marketing/hero/instrument-data";
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
import { FALLBACK_DISCLAIMER } from "@/components/marketing/research-values";
import { apiGet } from "@/lib/api/client";

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
  const opts = { timeoutMs: 5000 };
  const [games, meta, initial] = await Promise.all([
    settle(apiGet("/api/v1/games", opts)),
    settle(apiGet("/api/v1/meta", opts)),
    settle<InstrumentSnapshot>(loadInstrument({ scenario: "mvw_channel", n: 4, sampled: false }, opts)),
  ]);
  const game = (id: string): GameInfo | null => games?.data.find((g) => g.game_id === id) ?? null;
  const metaData: MetaData | null = meta?.data ?? null;

  return (
    <main id="main">
      <Hero initial={initial} />
      <ProblemSection />
      <PrimitiveSection w1={game("W1")} />
      <LabSection />
      <ClassicalSection s1={game("S1")} />
      <ProofSection w1={game("W1")} />
      <OpenSection meta={metaData} />
      <ClosingSection disclaimer={metaData?.disclaimer ?? FALLBACK_DISCLAIMER} />
    </main>
  );
}
