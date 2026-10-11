import type { Metadata } from "next";
import { LabHeader } from "@/components/lab/lab-header";
import { MintLab } from "@/components/lab/mint-lab";

export const metadata: Metadata = {
  title: "Quantum money laboratory",
  description: "Mint a Wiesner note, send it through a noise channel and watch the bank verify it — exact, sampled and Monte Carlo, with provenance.",
};

export default function Page() {
  return (
    <main id="main" className="container-wide grid gap-10 py-10 sm:py-12">
      <LabHeader
        eyebrow="Lab / Mint"
        title="Quantum money laboratory"
        lead="Mint a Wiesner quantum note, pass it through a noise channel, and let the bank verify it. Every number says whether it is exact, sampled or simulated, and where it came from."
      />
      <MintLab />
    </main>
  );
}
