import * as React from "react";
import { getEvidenceLabel, type LabelGroup, type Origin, type Tone } from "@/lib/evidence";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "./tooltip";

/**
 * EvidenceLabel — the ONE way to say what kind of evidence a number is.
 * Restrained by design: mono uppercase text + an 8px origin glyph. No filled pills.
 *   glyph (shape) encodes ORIGIN:  theory ■  numeric ◩  simulated □  measured ●  none ×  api ◇
 *   colour encodes TONE, glyph only (text stays muted) — except danger, which also tints text.
 *   Only certificate_status:CERTIFIED has tone "ok" (mint). Colour is never the only channel.
 */
const GLYPH: Record<Origin, React.ReactNode> = {
  theory: <rect x="1" y="1" width="6" height="6" fill="currentColor" />,
  numeric: (
    <>
      <rect x="1.5" y="1.5" width="5" height="5" fill="none" stroke="currentColor" />
      <path d="M1 7 7 1v6Z" fill="currentColor" />
    </>
  ),
  simulated: <rect x="1.5" y="1.5" width="5" height="5" fill="none" stroke="currentColor" />,
  measured: <circle cx="4" cy="4" r="3" fill="currentColor" />,
  none: <path d="M1.5 1.5 6.5 6.5M6.5 1.5 1.5 6.5" stroke="currentColor" strokeWidth="1.25" />,
  api: <path d="M4 1 7 4 4 7 1 4Z" fill="none" stroke="currentColor" />,
};

const TONE_GLYPH: Record<Tone, string> = {
  ok: "text-accent",
  info: "text-info",
  neutral: "text-subtle",
  warn: "text-warn",
  danger: "text-danger",
};

export function EvidenceLabel({
  kind,
  group = "evidence_kind",
  size = "sm",
  showTooltip = true,
  className,
}: {
  kind: string;
  group?: LabelGroup;
  size?: "xs" | "sm";
  showTooltip?: boolean;
  className?: string;
}) {
  const spec = getEvidenceLabel(kind, group);
  const body = (
    <span
      data-slot="evidence-label"
      data-evidence={spec.key}
      data-group={spec.group}
      data-origin={spec.origin}
      data-tone={spec.tone}
      className={cn(
        "inline-flex items-center gap-1.5 font-mono font-medium tracking-[0.06em] uppercase sm:whitespace-nowrap",
        size === "xs" ? "text-[0.625rem]" : "text-[0.6875rem]",
        spec.tone === "danger" ? "text-danger" : spec.tone === "ok" ? "text-accent" : "text-muted",
        className,
      )}
    >
      <svg viewBox="0 0 8 8" className={cn("size-2 shrink-0", TONE_GLYPH[spec.tone])} aria-hidden>
        {GLYPH[spec.origin]}
      </svg>
      {spec.label}
      <span className="sr-only">: {spec.title}</span>
    </span>
  );
  if (!showTooltip) return body;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span tabIndex={0} className="rounded-xs focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">
          {body}
        </span>
      </TooltipTrigger>
      <TooltipContent>{spec.title}</TooltipContent>
    </Tooltip>
  );
}
