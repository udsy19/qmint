import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Minimal, dependency-free math typesetting for the lab explanations (no KaTeX in the toolchain).
 * Variables are italic Sans, operators and numbers upright; fractions are stacked; display blocks
 * carry an aria-label with a spoken form so screen readers do not read glyph soup.
 */
export function V({ children }: { children: React.ReactNode }) {
  return <i className="font-sans italic">{children}</i>;
}

export function Frac({ n, d }: { n: React.ReactNode; d: React.ReactNode }) {
  return (
    <span className="mx-[0.12em] inline-flex flex-col items-center align-middle text-[0.82em] leading-[1.05]">
      <span className="px-[0.15em]">{n}</span>
      <span className="w-full border-t border-current px-[0.15em]">{d}</span>
    </span>
  );
}

export function Sup({ children }: { children: React.ReactNode }) {
  return <sup className="ml-[0.05em] text-[0.7em]">{children}</sup>;
}

export function Ket({ children }: { children: React.ReactNode }) {
  return <span className="font-mono whitespace-nowrap">|{children}⟩</span>;
}

/** Display equation: centred-left block, generous line height, spoken alternative. */
export function MathBlock({ label, children, className }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <div
      role="math"
      aria-label={label}
      className={cn("my-3 overflow-x-auto rounded-sm border border-border bg-surface px-4 py-3 text-[0.95rem] text-foreground", className)}
    >
      <span aria-hidden className="leading-[2] whitespace-nowrap">
        {children}
      </span>
    </div>
  );
}
