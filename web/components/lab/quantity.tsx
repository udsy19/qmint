import * as React from "react";
import { EvidenceLabel } from "@/components/ui/evidence-label";
import { Readout } from "@/components/ui/readout";
import { NO_BOUND } from "@/lib/format";
import { cn } from "@/lib/utils";
import { METHOD_TEXT, type LabQuantity } from "./lab-api";

/**
 * One API quantity as a readout: value (null → text, never 0), interval, evidence label, method,
 * and the note on request. All numbers on the lab pages go through this component.
 */
export function QuantityReadout({
  q,
  label,
  emphasis,
  size = "md",
  showNote = false,
  showFormula = true,
  missing = NO_BOUND,
  className,
}: {
  q: LabQuantity;
  label?: React.ReactNode;
  emphasis?: boolean;
  size?: "sm" | "md" | "lg";
  showNote?: boolean;
  showFormula?: boolean;
  missing?: string;
  className?: string;
}) {
  return (
    <Readout
      label={label ?? q.label}
      value={q.value}
      interval={q.interval}
      missing={missing}
      size={size}
      emphasis={emphasis}
      className={className}
      evidence={<EvidenceLabel kind={q.evidence_kind} />}
    >
      <span className="font-mono text-xs text-subtle" data-method={q.method}>
        {METHOD_TEXT[q.method]}
        {showFormula && q.formula ? <span className="text-muted"> · {q.formula}</span> : null}
      </span>
      {showNote && q.note ? <span className="max-w-[36ch] text-xs text-muted">{q.note}</span> : null}
    </Readout>
  );
}

/** Compact source line for detail panels. */
export function QuantitySource({ q, className }: { q: LabQuantity; className?: string }) {
  return (
    <p className={cn("grid gap-0.5 text-xs", className)}>
      <span className="text-foreground">{q.label}</span>
      <span className="font-mono break-all text-subtle">{q.source}</span>
      {q.note ? <span className="text-muted">{q.note}</span> : null}
    </p>
  );
}

/**
 * Readouts in a fixed grid (2 columns, 4 from xl). Used instead of ui/ReadoutGroup where four readouts
 * would wrap: ReadoutGroup keeps its divider and indent on wrapped items (noted in the handoff).
 */
export function ReadoutGrid({ className, ...props }: React.ComponentProps<"dl">) {
  return <dl className={cn("grid grid-cols-2 gap-x-6 gap-y-6 xl:grid-cols-4", className)} {...props} />;
}
