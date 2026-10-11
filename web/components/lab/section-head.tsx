import * as React from "react";

/** Numbered results section heading ("01 Token"): mono index, Sans title, optional right-side meta. */
export function SectionHead({ id, index, title, aside }: { id?: string; index: string; title: string; aside?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2 border-b border-border pb-3">
      <h2 id={id} className="flex items-baseline gap-3 text-h4 text-foreground">
        <span className="tnum font-mono text-xs text-subtle">{index}</span>
        {title}
      </h2>
      {aside}
    </div>
  );
}
