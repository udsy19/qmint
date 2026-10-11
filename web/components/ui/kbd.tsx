import * as React from "react";
import { cn } from "@/lib/utils";

export function Kbd({ className, ...props }: React.ComponentProps<"kbd">) {
  return (
    <kbd
      data-slot="kbd"
      className={cn(
        "inline-flex h-5 min-w-5 items-center justify-center rounded-xs border border-border-strong bg-surface-raised px-1 font-mono text-[0.6875rem] text-muted",
        className,
      )}
      {...props}
    />
  );
}
