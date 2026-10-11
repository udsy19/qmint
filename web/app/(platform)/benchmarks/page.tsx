import type { Metadata } from "next";
import { connection } from "next/server";
import * as React from "react";
import { EvidenceLabel } from "@/components/ui/evidence-label";
import { Readout, ReadoutGroup } from "@/components/ui/readout";
import { ErrorState, UnavailableState } from "@/components/ui/state";
import { ApiError, apiGet } from "@/lib/api/client";
import { Explorer } from "./_components/explorer";
import type { BenchData } from "./_components/model";
import { ComparabilityMatrix, LatencyCases, PhotonQber, Reproducibility } from "./_components/sections";
import { STATIC_SNAPSHOT } from "@/lib/api/static";

export const metadata: Metadata = { title: "Quantum vs classical" };

function Section({ id, eyebrow, title, lede, children }: { id: string; eyebrow: string; title: string; lede?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-h`} className="grid grid-cols-[minmax(0,1fr)] gap-6 border-t border-border pt-10">
      <div className="grid max-w-3xl gap-2">
        <p className="label-mono text-subtle">{eyebrow}</p>
        <h2 id={`${id}-h`} className="text-h3 text-foreground">
          {title}
        </h2>
        {lede ? <p className="text-sm text-muted">{lede}</p> : null}
      </div>
      {children}
    </section>
  );
}

async function load(): Promise<{ data?: BenchData; error?: ApiError }> {
  try {
    const body = await apiGet("/api/v1/benchmarks", { timeoutMs: 45_000 });
    return { data: body.data };
  } catch (e) {
    return { error: e instanceof ApiError ? e : new ApiError("network", String(e)) };
  }
}

export default async function Page() {
  if (!STATIC_SNAPSHOT) await connection(); // request-time render; the static export prerenders from the snapshot
  const { data, error } = await load();
  return (
    <main id="main" className="container-wide grid grid-cols-[minmax(0,1fr)] gap-12 py-10 md:py-14">
      <header className="grid max-w-3xl gap-4">
        <p className="label-mono text-subtle">Benchmarks · lanes H, G, E</p>
        <h1 className="text-h2 text-foreground md:text-h1">Quantum vs classical</h1>
        <p className="text-body-lg text-muted">
          Seven classical payment constructions against ideal S-money, compared on what each one assumes before any timing is read. There is no single
          score: every pair is either qualified by named concessions or incomparable.
        </p>
      </header>

      {error || !data ? (
        <ErrorState
          timeout={error?.kind === "timeout"}
          title="Benchmarks could not be loaded"
          description="The research API did not answer. Start it with the command below and reload."
          detail={`${error?.kind ?? "error"}: ${error?.message ?? "no data"} · $PY -m uvicorn qmint.api.app:app --port 8787`}
        />
      ) : (
        <>
          <ReadoutGroup aria-label="Summary">
            <Readout label="Classical records" value={data.protocols.filter((r) => r.family === "classical").length} evidence={<EvidenceLabel kind="MODELLED_LATENCY" size="xs" />} />
            <Readout label="Prevent double spend" value={data.protocols.filter((r) => r.family === "classical" && r.double_spend.outcome === "PREVENTED").length} />
            <Readout label="Qualified pairs" value={data.comparability.filter((p) => p.status === "QUALIFIED").length} />
            <Readout label="Incomparable pairs" value={data.comparability.filter((p) => p.status === "INCOMPARABLE").length} />
            <Readout label="Comparable pairs" value={data.comparability.filter((p) => p.status === "COMPARABLE").length}>
              <span className="text-xs text-subtle">none: assumptions never fully match</span>
            </Readout>
          </ReadoutGroup>

          <aside className="max-w-3xl border-l-2 border-warn/60 pl-4 text-sm text-muted">
            <p className="mb-1 font-medium text-foreground">Read before comparing</p>
            {data.comparability_note}
          </aside>

          <Section
            id="constructions"
            eyebrow="Constructions"
            title="Double spending, latency and what each design assumes"
            lede="Each classical row is one lane H BenchmarkRecord. Expand a row for its concessions, record id and the command that regenerates it. Sorting never merges columns into a ranking."
          >
            <Explorer rows={data.protocols} />
          </Section>

          <Section id="matched" eyebrow="Matched topology" title="Quantum and classical on the same network">
            <UnavailableState
              title="Not available yet"
              description={data.matched_topology.reason}
              detail={`expected source: ${data.matched_topology.expected_source}`}
            />
          </Section>

          <Section
            id="comparability"
            eyebrow="X11 comparability matrix"
            title="Concessions, column by column"
            lede="Lane H's matrix compares each classical construction with the ideal S1 model on sixteen dimensions. QUALIFIED means comparable only after the listed concessions are priced in."
          >
            <ComparabilityMatrix pairs={data.comparability} />
          </Section>

          <Section
            id="latency"
            eyebrow="Latency case studies · lane G"
            title="Published topologies and a measured network"
            lede="The Jiang et al. 2024 field topologies reproduce the paper's mean transaction times from fibre length alone. RIPE Atlas gives measured one-way delays (RTT/2) between real anchors."
          >
            <LatencyCases cases={data.latency_cases} />
          </Section>

          <Section
            id="photons"
            eyebrow="Photon data · lane E"
            title="Error rates from the raw Schiansky 2023 archive"
            lede="22 runs of real recorded photon coincidences (Zenodo 7979319), re-analysed independently. The paper's own estimator reproduces both published error rates."
          >
            <PhotonQber photon={data.photon} />
          </Section>

          <Section id="reproduce" eyebrow="Reproducibility" title="Regenerate every number on this page">
            <Reproducibility r={data.reproducibility} />
          </Section>
        </>
      )}
    </main>
  );
}
