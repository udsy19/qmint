import { Info } from "lucide-react";
import * as React from "react";
import { cn } from "@/lib/utils";

/** Small, server-safe building blocks for documentation prose. */
export function P({ children, className }: { children: React.ReactNode; className?: string }) {
  return <p className={cn("text-[0.9375rem] leading-7 text-muted [&_strong]:font-medium [&_strong]:text-foreground", className)}>{children}</p>;
}

export function C({ children }: { children: React.ReactNode }) {
  return <code className="rounded-xs bg-surface-raised px-1 py-px font-mono text-[0.8125rem] text-foreground">{children}</code>;
}

export function A({ href, children }: { href: string; children: React.ReactNode }) {
  const external = /^https?:/.test(href);
  return (
    <a href={href} {...(external ? { target: "_blank", rel: "noreferrer" } : {})} className="text-foreground underline decoration-border-strong underline-offset-4 hover:decoration-foreground">
      {children}
      {external ? <span className="sr-only"> (opens in a new tab)</span> : null}
    </a>
  );
}

export function H3({ children, id }: { children: React.ReactNode; id?: string }) {
  return (
    <h3 id={id} className="mt-2 scroll-mt-[calc(var(--header-h)+16px)] text-[0.9375rem] font-medium text-foreground">
      {children}
    </h3>
  );
}

export function UL({ children }: { children: React.ReactNode }) {
  return <ul className="grid list-[square] gap-1.5 pl-5 text-[0.9375rem] leading-7 text-muted marker:text-border-strong [&_strong]:font-medium [&_strong]:text-foreground">{children}</ul>;
}

export function Callout({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <aside className="flex gap-3 rounded-md border border-border px-4 py-3">
      <Info className="mt-0.5 size-4 shrink-0 text-info" aria-hidden />
      <div className="grid gap-1 text-sm leading-6 text-muted">
        {title ? <p className="font-medium text-foreground">{title}</p> : null}
        {children}
      </div>
    </aside>
  );
}

/** Two-or-more column reference table in prose. First column is Mono. */
export function RefTable({ head, rows, mono = [0] }: { head: string[]; rows: React.ReactNode[][]; mono?: number[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-border">
            {head.map((h) => (
              <th key={h} scope="col" className="label-mono h-8 pr-4 text-left align-middle font-medium text-subtle last:pr-0">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-hairline align-top">
              {r.map((c, j) => (
                <td key={j} className={cn("py-2.5 pr-4 leading-6 last:pr-0", mono.includes(j) ? "font-mono text-[0.8125rem] whitespace-nowrap text-foreground" : "text-muted")}>
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
