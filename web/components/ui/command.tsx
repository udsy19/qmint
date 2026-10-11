"use client";

import { Command as C } from "cmdk";
import { Search } from "lucide-react";
import { Dialog as D } from "radix-ui";
import * as React from "react";
import { cn } from "@/lib/utils";
import { DialogOverlay } from "./dialog";

/**
 * Command palette base (cmdk). Shell agent (C) owns the global ⌘K palette and its items;
 * this file only provides styled primitives.
 */
export function Command({ className, ...props }: React.ComponentProps<typeof C>) {
  return <C data-slot="command" className={cn("flex w-full flex-col overflow-hidden text-foreground", className)} {...props} />;
}

export function CommandDialog({
  open,
  onOpenChange,
  label = "Command palette",
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  label?: string;
  children: React.ReactNode;
}) {
  return (
    <D.Root open={open} onOpenChange={onOpenChange}>
      <D.Portal>
        <DialogOverlay />
        <D.Content
          aria-describedby={undefined}
          className="fixed top-[14vh] left-1/2 z-modal w-[calc(100vw-2*var(--gutter))] max-w-[560px] -translate-x-1/2 overflow-hidden rounded-lg bg-surface-overlay shadow-overlay outline-none data-[state=open]:animate-[qm-fade-in_var(--duration-base)_var(--ease-out)]"
        >
          <D.Title className="sr-only">{label}</D.Title>
          <Command label={label} loop>
            {children}
          </Command>
        </D.Content>
      </D.Portal>
    </D.Root>
  );
}

export function CommandInput({ className, ...props }: React.ComponentProps<typeof C.Input>) {
  return (
    <div className="flex items-center gap-2 border-b border-border px-4">
      <Search className="size-4 shrink-0 text-subtle" aria-hidden />
      <C.Input
        className={cn("h-12 w-full bg-transparent text-[0.9375rem] text-foreground outline-none placeholder:text-subtle", className)}
        {...props}
      />
    </div>
  );
}

export function CommandList({ className, ...props }: React.ComponentProps<typeof C.List>) {
  return <C.List className={cn("max-h-[min(60vh,420px)] overflow-y-auto overscroll-contain p-1.5", className)} {...props} />;
}

export function CommandEmpty(props: React.ComponentProps<typeof C.Empty>) {
  return <C.Empty className="px-3 py-8 text-center text-sm text-muted" {...props} />;
}

export function CommandGroup({ className, ...props }: React.ComponentProps<typeof C.Group>) {
  return (
    <C.Group
      className={cn("[&_[cmdk-group-heading]]:label-mono [&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:pt-2.5 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:text-subtle", className)}
      {...props}
    />
  );
}

export function CommandItem({ className, ...props }: React.ComponentProps<typeof C.Item>) {
  return (
    <C.Item
      className={cn(
        "flex h-9 cursor-default items-center gap-2.5 rounded-sm px-2.5 text-sm text-muted select-none",
        "data-[selected=true]:bg-surface-hover data-[selected=true]:text-foreground data-[selected=true]:shadow-[inset_2px_0_0_var(--accent)] data-[disabled=true]:opacity-40",
        "[&_svg]:size-4 [&_svg]:shrink-0",
        className,
      )}
      {...props}
    />
  );
}

export function CommandSeparator({ className, ...props }: React.ComponentProps<typeof C.Separator>) {
  return <C.Separator className={cn("my-1 h-px bg-border", className)} {...props} />;
}

/** Key-hint footer: ↑↓ navigate · ↵ open · esc close (+ optional result count). */
export function CommandFooter({ children }: { children?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-t border-border px-4 py-2 font-mono text-[0.6875rem] text-subtle">
      <span className="flex gap-3">
        <span>↑↓ navigate</span>
        <span>↵ open</span>
        <span>esc close</span>
      </span>
      {children}
    </div>
  );
}
