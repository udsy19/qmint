import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Status word + 8px glyph for workflow / verification statuses (tracker gates, lane tasks, research
 * verification). Same grammar as EvidenceLabel (glyph + word, colour never alone) but these statuses are
 * not evidence kinds, so they get their own small vocabulary. Mint is never used here.
 */
export type StatusTone = "done" | "partial" | "open" | "skipped" | "danger";

const TONE: Record<string, StatusTone> = {
  // tracker
  PASSED: "done",
  MERGED: "done",
  IN_REVIEW: "partial",
  CLAIMED: "partial",
  OPEN: "open",
  SKIPPED: "skipped",
  BLOCKED: "danger",
  // research verification (lane A / D / E files)
  VERIFIED_FROM_SOURCE: "done",
  FULL_TEXT_READ: "done",
  PUBLISHED_REPRODUCED: "done",
  CERTIFIED_NUMERIC: "done",
  VERIFIED_DOWNLOAD: "done",
  VERIFIED_LISTING: "done",
  PUBLISHED_CORRECTION: "done",
  RESOLVED: "done",
  RECOMPUTED_BY_LANE_A: "partial",
  ABSTRACT_READ: "partial",
  NUMERICALLY_SUPPORTED: "partial",
  PARTIALLY_VERIFIED: "partial",
  VERSION_CHANGE: "partial",
  HYPOTHESIS: "partial",
  METADATA_ONLY: "open",
  NOT_VERIFIED: "open",
  CONJECTURE: "open",
  UNSUPPORTED: "skipped",
  OPEN_DISCREPANCY: "open",
  CONFLICT: "danger",
  DISALLOWED: "danger",
};

export function statusTone(status: string): StatusTone {
  return TONE[status] ?? "open";
}

const GLYPH: Record<StatusTone, React.ReactNode> = {
  done: <rect x="1" y="1" width="6" height="6" fill="currentColor" />,
  partial: (
    <>
      <rect x="1.5" y="1.5" width="5" height="5" fill="none" stroke="currentColor" />
      <path d="M1 7 7 1v6Z" fill="currentColor" />
    </>
  ),
  open: <rect x="1.5" y="1.5" width="5" height="5" fill="none" stroke="currentColor" />,
  skipped: <path d="M1.5 1.5 6.5 6.5M6.5 1.5 1.5 6.5" stroke="currentColor" strokeWidth="1.25" />,
  danger: <path d="M4 1 7 7H1Z" fill="none" stroke="currentColor" />,
};

const GLYPH_COLOUR: Record<StatusTone, string> = {
  done: "text-info",
  partial: "text-warn",
  open: "text-subtle",
  skipped: "text-subtle",
  danger: "text-danger",
};

export function StatusMark({ status, className, title }: { status: string; className?: string; title?: string }) {
  const tone = statusTone(status);
  return (
    <span
      data-status={status}
      data-tone={tone}
      title={title}
      className={cn(
        "inline-flex items-center gap-1.5 font-mono text-[0.6875rem] font-medium tracking-[0.04em] whitespace-nowrap uppercase",
        tone === "danger" ? "text-danger" : "text-muted",
        className,
      )}
    >
      <svg viewBox="0 0 8 8" className={cn("size-2 shrink-0", GLYPH_COLOUR[tone])} aria-hidden>
        {GLYPH[tone]}
      </svg>
      {status.replaceAll("_", " ")}
    </span>
  );
}
