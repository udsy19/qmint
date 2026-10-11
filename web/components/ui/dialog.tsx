"use client";

import { X } from "lucide-react";
import { Dialog as D } from "radix-ui";
import * as React from "react";
import { cn } from "@/lib/utils";

export const Dialog = D.Root;
export const DialogTrigger = D.Trigger;
export const DialogClose = D.Close;

export function DialogOverlay({ className, ...props }: React.ComponentProps<typeof D.Overlay>) {
  return (
    <D.Overlay
      className={cn("fixed inset-0 z-overlay bg-black/60 data-[state=open]:animate-[qm-fade-in_var(--duration-fast)_var(--ease-out)]", className)}
      {...props}
    />
  );
}

export function DialogContent({
  className,
  children,
  showClose = true,
  ...props
}: React.ComponentProps<typeof D.Content> & { showClose?: boolean }) {
  return (
    <D.Portal>
      <DialogOverlay />
      <D.Content
        data-slot="dialog-content"
        className={cn(
          "fixed top-[12vh] left-1/2 z-modal w-[calc(100vw-2*var(--gutter))] max-w-lg -translate-x-1/2 rounded-lg bg-surface-overlay shadow-overlay outline-none",
          "data-[state=open]:animate-[qm-fade-in_var(--duration-base)_var(--ease-out)]",
          className,
        )}
        {...props}
      >
        {children}
        {showClose ? (
          <D.Close className="absolute top-3 right-3 rounded-xs p-1 text-subtle transition-colors hover:text-foreground" aria-label="Close">
            <X className="size-4" aria-hidden />
          </D.Close>
        ) : null}
      </D.Content>
    </D.Portal>
  );
}

export function DialogHeader({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("grid gap-1 border-b border-border px-5 py-4", className)} {...props} />;
}
export function DialogTitle({ className, ...props }: React.ComponentProps<typeof D.Title>) {
  return <D.Title className={cn("text-h4 text-foreground", className)} {...props} />;
}
export function DialogDescription({ className, ...props }: React.ComponentProps<typeof D.Description>) {
  return <D.Description className={cn("text-sm text-muted", className)} {...props} />;
}
export function DialogBody({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("px-5 py-4", className)} {...props} />;
}
export function DialogFooter({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("flex justify-end gap-2 border-t border-border px-5 py-3", className)} {...props} />;
}
