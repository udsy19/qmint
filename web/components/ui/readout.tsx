import * as React from "react";
import { NOT_REPORTED, formatInterval, formatValue } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * Readout: one labelled scientific number. Value is mono + tabular; unit and interval are quieter.
 * `value === null` renders the `missing` text (e.g. "no applicable bound") — never 0.
 * Always pass an `evidence` node (usually <EvidenceLabel/>) for numbers that came from data.
 */
export function Readout({
  label,
  value,
  unit,
  interval,
  missing = NOT_REPORTED,
  evidence,
  size = "md",
  emphasis = false,
  className,
  children,
}: {
  label: React.ReactNode;
  value: number | null | undefined;
  unit?: string;
  interval?: { lo: number; hi: number; confidence?: number | null } | null;
  missing?: string;
  evidence?: React.ReactNode;
  size?: "sm" | "md" | "lg";
  /** Accent the value (one per group at most: the scientifically decisive number). */
  emphasis?: boolean;
  className?: string;
  children?: React.ReactNode;
}) {
  const isMissing = value === null || value === undefined;
  return (
    <div data-slot="readout" className={cn("grid min-w-0 content-start gap-1.5", className)}>
      <dt className="label-mono text-subtle">{label}</dt>
      <dd className="grid gap-1">
        <span className="flex items-baseline gap-1.5">
          <span
            className={cn(
              "tnum font-mono tracking-tight",
              size === "sm" && "text-sm",
              size === "md" && "text-xl",
              size === "lg" && "text-[2rem] leading-none",
              isMissing ? "text-sm text-muted italic" : emphasis ? "text-accent" : "text-foreground",
            )}
          >
            {formatValue(value, missing)}
          </span>
          {unit && !isMissing ? <span className="font-mono text-xs text-subtle">{unit}</span> : null}
        </span>
        {interval ? (
          <span className="tnum font-mono text-xs text-muted">
            {formatInterval(interval.lo, interval.hi)}
            {interval.confidence ? <span className="text-subtle"> · {Math.round(interval.confidence * 1000) / 10}% CI</span> : null}
          </span>
        ) : null}
        {evidence ? <span>{evidence}</span> : null}
        {children}
      </dd>
    </div>
  );
}

/** Horizontal group of readouts separated by hairlines (wraps to 2 columns on mobile). */
export function ReadoutGroup({ className, ...props }: React.ComponentProps<"dl">) {
  return (
    <dl
      className={cn(
        "grid grid-cols-2 gap-x-4 gap-y-6 sm:flex sm:flex-wrap sm:gap-0 sm:[&>[data-slot=readout]]:border-l sm:[&>[data-slot=readout]]:border-border sm:[&>[data-slot=readout]]:px-6 sm:[&>[data-slot=readout]:first-child]:border-0 sm:[&>[data-slot=readout]:first-child]:pl-0",
        className,
      )}
      {...props}
    />
  );
}
