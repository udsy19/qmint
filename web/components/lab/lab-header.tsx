import * as React from "react";

/** Page header for the lab routes: mono eyebrow, one h1, a lead, and the research-only disclaimer. */
export function LabHeader({ eyebrow, title, lead }: { eyebrow: string; title: string; lead: string }) {
  return (
    <header className="grid max-w-3xl gap-3">
      <p className="label-mono text-subtle">{eyebrow}</p>
      <h1 className="text-h2 text-foreground sm:text-h1">{title}</h1>
      <p className="text-body-lg text-muted">{lead}</p>
      <p className="text-xs text-subtle">
        Research simulation on a local simulator. Not money, not a payment service, and nothing here runs on quantum hardware.
      </p>
    </header>
  );
}
