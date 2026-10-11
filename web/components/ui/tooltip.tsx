"use client";

import { Tooltip as T } from "radix-ui";
import * as React from "react";
import { cn } from "@/lib/utils";

export const TooltipProvider = T.Provider;
export const Tooltip = T.Root;
export const TooltipTrigger = T.Trigger;

export function TooltipContent({ className, sideOffset = 6, children, ...props }: React.ComponentProps<typeof T.Content>) {
  return (
    <T.Portal>
      <T.Content
        data-slot="tooltip-content"
        sideOffset={sideOffset}
        className={cn(
          "z-tooltip max-w-72 rounded-sm bg-surface-overlay px-2 py-1.5 text-xs leading-snug text-foreground shadow-overlay",
          "data-[state=delayed-open]:animate-[qm-fade-in_var(--duration-fast)_var(--ease-out)]",
          className,
        )}
        {...props}
      >
        {children}
      </T.Content>
    </T.Portal>
  );
}
