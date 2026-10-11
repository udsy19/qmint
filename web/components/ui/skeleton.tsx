import * as React from "react";
import { cn } from "@/lib/utils";

/** Loading placeholder. Shimmer collapses to a static block under reduced motion. Not announced to AT — wrap regions in aria-busy. */
export function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      aria-hidden
      className={cn(
        "rounded-xs bg-[linear-gradient(90deg,var(--surface-raised)_0%,var(--surface-hover)_50%,var(--surface-raised)_100%)] bg-[length:200%_100%]",
        "animate-[qm-shimmer_1.6s_linear_infinite]",
        className,
      )}
      {...props}
    />
  );
}
