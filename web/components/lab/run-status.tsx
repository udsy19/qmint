"use client";

import { Check, CircleSlash, X } from "lucide-react";
import * as React from "react";
import { Button } from "@/components/ui/button";
import { PixelLoader } from "@/components/ui/pixel-loader";
import { cn } from "@/lib/utils";
import { isActive, type RunPhase } from "./run-state";

const PHASE_TEXT: Record<RunPhase, string> = {
  idle: "Not run yet",
  queued: "Sent · waiting for the quantum worker",
  running: "Computing on the server",
  done: "Done",
  error: "Failed",
  timeout: "Timed out",
  cancelled: "Cancelled",
};

function useElapsed(active: boolean, startedAt?: number, finishedAt?: number): number | null {
  const [now, setNow] = React.useState(() => performance.now());
  React.useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setNow(performance.now()), 100);
    return () => clearInterval(id);
  }, [active]);
  if (startedAt === undefined) return null;
  return Math.max(0, (finishedAt ?? now) - startedAt);
}

/**
 * One-line run status: phase glyph + words (never colour alone), elapsed time, server compute time,
 * and Cancel while active. Announced politely to screen readers.
 */
export function RunStatus({
  phase,
  startedAt,
  finishedAt,
  serverMs,
  onCancel,
  className,
}: {
  phase: RunPhase;
  startedAt?: number;
  finishedAt?: number;
  serverMs?: number | null;
  onCancel?: () => void;
  className?: string;
}) {
  const active = isActive(phase);
  const elapsed = useElapsed(active, startedAt, finishedAt);
  return (
    <div
      data-phase={phase}
      className={cn("flex min-h-8 flex-wrap items-center gap-x-3 gap-y-1 text-sm", className)}
    >
      <span className="inline-flex size-4 items-center justify-center" aria-hidden>
        {active ? (
          <PixelLoader label={PHASE_TEXT[phase]} />
        ) : phase === "done" ? (
          <Check className="size-3.5 text-foreground" />
        ) : phase === "error" || phase === "timeout" ? (
          <X className="size-3.5 text-danger" />
        ) : phase === "cancelled" ? (
          <CircleSlash className="size-3.5 text-subtle" />
        ) : (
          <span className="size-1.5 rounded-full bg-border-strong" />
        )}
      </span>
      <span role="status" aria-live="polite" className={cn(active || phase === "done" ? "text-foreground" : "text-muted")}>
        {PHASE_TEXT[phase]}
      </span>
      {elapsed !== null && phase !== "idle" ? (
        <span className="tnum font-mono text-xs text-subtle">
          {(elapsed / 1000).toFixed(2)} s{serverMs != null && phase === "done" ? ` · server ${Math.round(serverMs)} ms` : ""}
        </span>
      ) : null}
      {active && onCancel ? (
        <Button variant="ghost" size="sm" onClick={onCancel} className="ml-auto">
          Cancel
        </Button>
      ) : null}
    </div>
  );
}
