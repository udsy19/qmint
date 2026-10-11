import type { Metadata } from "next";
import { connection } from "next/server";
import { ApiFailure } from "@/components/shell/api-failure";
import { isEntryKind } from "@/components/research/kinds";
import { ResearchIndex, type Filters } from "@/components/research/research-index";
import { SourceFiles, StatusGlossary } from "@/components/research/provenance";
import { load } from "@/components/shell/load";
import type { StatusTone } from "@/components/shell/status-mark";
import { STATIC_SNAPSHOT } from "@/lib/api/static";

export const metadata: Metadata = { title: "Research library" };

const TONES: StatusTone[] = ["done", "partial", "open", "skipped", "danger"];

export default async function ResearchPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  if (!STATIC_SNAPSHOT) await connection(); // request-time render; the static export prerenders from the snapshot
  // The static export has no request, so query-string filters (?game=…) are not applied on first load there.
  const sp: Record<string, string | string[] | undefined> = STATIC_SNAPSHOT ? {} : await searchParams;
  const one = (k: string) => (Array.isArray(sp[k]) ? sp[k][0] : sp[k]) ?? "";
  const kind = one("kind");
  const tone = one("status") as StatusTone;
  const initial: Filters = {
    q: one("q"),
    kind: isEntryKind(kind) ? kind : "all",
    game: one("game"),
    tone: TONES.includes(tone) ? tone : "all",
  };
  const res = await load("/api/v1/research/sources");

  return (
    <main id="main" className="container-content grid gap-8 py-8 lg:py-10">
      <header className="grid gap-3">
        <p className="label-mono text-subtle">Library</p>
        <h1 className="text-h2">Research library</h1>
        <p className="max-w-prose text-sm text-muted">
          Papers, transcribed theorems, proof obligations, datasets, corrections and the novelty audit, read directly from
          the lane A, D and E files in this repository. Each entry keeps the verification status written in its own file;
          nothing here is upgraded or merged by the website.
        </p>
      </header>
      {res.ok ? (
        <>
          <ResearchIndex entries={res.body.data.sources} initial={initial} />
          <div className="grid gap-0">
            <StatusGlossary items={res.body.data.glossary} />
            <SourceFiles files={res.body.data.files} snapshot={res.body.data.snapshot_date ?? null} />
          </div>
        </>
      ) : (
        <ApiFailure what="the research library" kind={res.kind} message={res.message} />
      )}
    </main>
  );
}
