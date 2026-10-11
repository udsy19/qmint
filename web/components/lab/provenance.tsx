import * as React from "react";
import { EvidenceLabel } from "@/components/ui/evidence-label";
import type { Schemas } from "@/lib/api/client";
import { cn } from "@/lib/utils";

type Prov = Schemas["ApiProvenance"];
type Run = Schemas["RunInfo"];

function Item({ k, children }: { k: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[8.5rem_minmax(0,1fr)] gap-3 border-b border-hairline py-2 text-sm last:border-0">
      <dt className="label-mono pt-0.5 text-subtle">{k}</dt>
      <dd className="min-w-0 font-mono text-xs break-words text-foreground">{children}</dd>
    </div>
  );
}

/** Run metadata: backend(s), seed, budget, git sha, evidence kind, software versions — reproducible by hand. */
export function ProvenanceList({
  provenance,
  run,
  evidenceKind,
  reproduce,
  className,
}: {
  provenance: Prov;
  run: Run;
  evidenceKind: string | null;
  reproduce: string;
  className?: string;
}) {
  return (
    <dl className={cn("grid", className)}>
      <Item k="Evidence">{evidenceKind ? <EvidenceLabel kind={evidenceKind} /> : "—"}</Item>
      <Item k="Backends">
        <ul className="grid gap-0.5">
          {run.backends.map((b) => (
            <li key={b}>{b}</li>
          ))}
          <li className="text-subtle">QPU: not run (paid submission disabled)</li>
        </ul>
      </Item>
      <Item k="Seed">{run.seed}</Item>
      {run.shots != null ? <Item k="Shots">{run.shots.toLocaleString("en-US")}</Item> : null}
      <Item k="Trials">{run.trials.toLocaleString("en-US")} fresh notes</Item>
      <Item k="Server time">
        {Math.round(run.elapsed_ms)} ms of a {run.deadline_s} s budget
      </Item>
      <Item k="Git">{provenance.git_sha}</Item>
      <Item k="Source">{provenance.source}</Item>
      {provenance.notes ? <Item k="Notes">{provenance.notes}</Item> : null}
      <Item k="Generated">{provenance.generated_at_utc}</Item>
      {Object.keys(provenance.software ?? {}).length ? (
        <Item k="Software">
          {Object.entries(provenance.software ?? {})
            .map(([k, v]) => `${k} ${v}`)
            .join(" · ")}
        </Item>
      ) : null}
      <Item k="Reproduce">
        <code className="block rounded-xs bg-surface px-2 py-1.5 whitespace-pre-wrap text-muted">{reproduce}</code>
      </Item>
    </dl>
  );
}
