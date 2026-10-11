"use client";

import { ChevronRight } from "lucide-react";
import { Collapsible as C } from "radix-ui";
import * as React from "react";
import { cn } from "@/lib/utils";

export const Collapsible = C.Root;
export const CollapsibleTrigger = C.Trigger;
export const CollapsibleContent = C.Content;

/**
 * Disclosure: a titled, collapsible block for technical detail (derivations, provenance, raw JSON).
 * Summary stays readable when closed; the chevron rotates (instant under reduced motion).
 */
export function Disclosure({
  title,
  meta,
  defaultOpen = false,
  children,
  className,
}: {
  title: React.ReactNode;
  meta?: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <C.Root defaultOpen={defaultOpen} className={cn("group/disclosure border-t border-border", className)}>
      <C.Trigger className="flex w-full items-center gap-2 py-3 text-left text-sm text-foreground hover:text-foreground focus-visible:outline-offset-[-2px]">
        <ChevronRight
          className="size-3.5 shrink-0 text-subtle transition-transform duration-[var(--duration-fast)] ease-out group-data-[state=open]/disclosure:rotate-90"
          aria-hidden
        />
        <span className="flex-1 font-medium">{title}</span>
        {meta ? <span className="label-mono text-subtle">{meta}</span> : null}
      </C.Trigger>
      <C.Content className="overflow-hidden pb-4 pl-5.5 text-sm text-muted">{children}</C.Content>
    </C.Root>
  );
}
