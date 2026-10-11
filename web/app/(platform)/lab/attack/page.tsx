import type { Metadata } from "next";
import { AttackLab } from "@/components/lab/attack-lab";
import { LabHeader } from "@/components/lab/lab-header";

export const metadata: Metadata = {
  title: "Counterfeiting simulator",
  description: "Try to copy a Wiesner quantum note. Compare honest acceptance, counterfeit success, Monte Carlo intervals, the (3/4)^n theorem and certified SDP bounds.",
};

export default function Page() {
  return (
    <main id="main" className="container-wide grid gap-10 py-10 sm:py-12">
      <LabHeader
        eyebrow="Lab / Attack"
        title="Counterfeiting simulator"
        lead="Hand a counterfeiter one genuine note and see how often they can make the bank accept two. Exact model values, Monte Carlo estimates and proven bounds are kept apart, so you can tell what is computed, what is sampled and what is proven."
      />
      <AttackLab />
    </main>
  );
}
