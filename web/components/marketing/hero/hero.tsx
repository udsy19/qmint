import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import type { InstrumentSnapshot } from "./instrument-data";
import { Instrument } from "./instrument";

export function Hero({ initial }: { initial: InstrumentSnapshot | null }) {
  return (
    <section aria-labelledby="hero-title" className="pt-12 pb-24 md:pt-16 md:pb-32">
      <div className="container-wide">
        <div className="grid gap-10 lg:grid-cols-12 lg:items-end lg:gap-8">
          <div className="grid gap-7 lg:col-span-8">
            <p className="label-mono text-subtle">QMint / Quantum security research</p>
            <h1 id="hero-title" className="max-w-[13ch] text-[2.75rem] leading-[1.02] font-[560] tracking-[-0.045em] text-balance sm:text-display md:text-display-xl">
              Security, down to the state.
            </h1>
            <p className="max-w-[52ch] text-body-lg text-muted">
              Design, attack and verify quantum payment protocols. Every number comes from a reproducible experiment and
              says what kind of evidence it is.
            </p>
            <div className="flex flex-wrap gap-3">
              <Button asChild variant="primary" size="lg">
                <Link href="/app">
                  Launch the Lab <ArrowRight />
                </Link>
              </Button>
              <Button asChild variant="secondary" size="lg">
                <Link href="/research">Explore the research</Link>
              </Button>
            </div>
          </div>
          <dl className="grid gap-3 border-l border-border pl-5 text-sm lg:col-span-4 lg:mb-1">
            <div className="grid gap-0.5">
              <dt className="label-mono text-subtle">Below</dt>
              <dd className="text-muted">
                {process.env.NEXT_PUBLIC_QMINT_STATIC === "1"
                  ? "Results precomputed by the research API (static snapshot). Pick an attack on a Wiesner note and read what each verifier sees."
                  : "A live call to the research API. Pick an attack on a Wiesner note and read what each verifier sees."}
              </dd>
            </div>
            <div className="grid gap-0.5">
              <dt className="label-mono text-subtle">Not</dt>
              <dd className="text-muted">Money, a payment service or deployable quantum currency.</dd>
            </div>
          </dl>
        </div>

        <div className="mt-12 md:mt-14">
          <Instrument initial={initial} />
        </div>
      </div>
    </section>
  );
}
