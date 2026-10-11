"use client";

import { Tabs as T } from "radix-ui";
import * as React from "react";
import { cn } from "@/lib/utils";

export const Tabs = T.Root;

/** Underline tabs: hairline baseline, active tab gets a 1px foreground rule — no pills. */
export function TabsList({ className, ...props }: React.ComponentProps<typeof T.List>) {
  return (
    <T.List
      data-slot="tabs-list"
      className={cn("flex items-center gap-5 overflow-x-auto border-b border-border [scrollbar-width:none]", className)}
      {...props}
    />
  );
}

export function TabsTrigger({ className, ...props }: React.ComponentProps<typeof T.Trigger>) {
  return (
    <T.Trigger
      data-slot="tabs-trigger"
      className={cn(
        "relative -mb-px inline-flex h-9 items-center gap-1.5 border-b border-transparent text-sm whitespace-nowrap text-muted",
        "transition-colors duration-[var(--duration-fast)] ease-out hover:text-foreground",
        "data-[state=active]:border-foreground data-[state=active]:text-foreground",
        "focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-ring disabled:opacity-40",
        className,
      )}
      {...props}
    />
  );
}

export function TabsContent({ className, ...props }: React.ComponentProps<typeof T.Content>) {
  return (
    <T.Content
      data-slot="tabs-content"
      className={cn("pt-5 outline-none data-[state=active]:animate-[qm-fade-in_var(--duration-base)_var(--ease-out)]", className)}
      {...props}
    />
  );
}
