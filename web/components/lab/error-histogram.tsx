import * as React from "react";
import type { Schemas } from "@/lib/api/client";
import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

type Row = Schemas["ErrorCountRow"];

/**
 * Distribution of the number of wrong positions in one verification of this note.
 * Bar = exact probability (lane-F closed form, cross-checked against the bank); tick = Aer frequency.
 * A rule marks the acceptance threshold. Rendered as a table so it reads without the bars.
 */
export function ErrorHistogram({ rows, shots, threshold, className }: { rows: Row[]; shots: number | null; threshold: number; className?: string }) {
  const max = Math.max(...rows.map((r) => Math.max(r.exact_probability, shots ? (r.sampled_count ?? 0) / shots : 0)), 1e-12);
  return (
    <table className={cn("w-full border-collapse text-sm", className)}>
      <caption className="sr-only">
        Wrong positions per verification: exact probability{shots ? " and sampled frequency" : ""}; accept if at most {threshold}
      </caption>
      <thead>
        <tr className="label-mono text-subtle">
          <th scope="col" className="w-14 py-1.5 text-left font-medium">wrong</th>
          <th scope="col" className="py-1.5 text-left font-medium">
            <span className="sr-only">bar</span>
          </th>
          <th scope="col" className="w-20 py-1.5 text-right font-medium">exact</th>
          {shots ? <th scope="col" className="w-20 py-1.5 text-right font-medium">sampled</th> : null}
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => {
          const sampled = shots && r.sampled_count != null ? r.sampled_count / shots : null;
          const isEdge = r.errors === threshold;
          return (
            <tr key={r.errors} className={cn("border-t border-hairline", isEdge && "border-b border-b-warn/50")}>
              <th scope="row" className="tnum py-1 text-left font-mono font-normal text-muted">
                {r.errors}
                <span className="sr-only">{r.accepted ? " (accepted)" : " (rejected)"}</span>
              </th>
              <td className="py-1 pr-3">
                <div className="relative h-3">
                  <div
                    className={cn("absolute inset-y-0 left-0 rounded-[1px] transition-[width] duration-[var(--duration-slow)] ease-out", r.accepted ? "bg-foreground/55" : "bg-border-strong")}
                    style={{ width: `${(r.exact_probability / max) * 100}%` }}
                  />
                  {sampled ? (
                    <div aria-hidden className="absolute -inset-y-0.5 w-0.5 bg-info" style={{ left: `calc(${(sampled / max) * 100}% - 1px)` }} />
                  ) : null}
                </div>
              </td>
              <td className="tnum py-1 text-right font-mono text-xs text-foreground">{formatNumber(r.exact_probability, { sig: 4 })}</td>
              {shots ? <td className="tnum py-1 text-right font-mono text-xs text-muted">{sampled === null ? "—" : formatNumber(sampled, { sig: 4 })}</td> : null}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
