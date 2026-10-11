"use client";

import { Toaster as Sonner, toast } from "sonner";

/** Toasts: bottom-right, quiet surface, text-first. Use for run completion / copy / export — not for errors that block a form. */
export function Toaster() {
  return (
    <Sonner
      theme="dark"
      position="bottom-right"
      gap={8}
      toastOptions={{
        classNames: {
          toast:
            "!rounded-md !border-0 !bg-surface-overlay !text-foreground !shadow-overlay !font-sans !text-sm !gap-2 !px-4 !py-3",
          description: "!text-muted !text-xs",
          actionButton: "!bg-foreground !text-background !rounded-sm",
          cancelButton: "!bg-surface-raised !text-muted !rounded-sm",
          error: "[&_[data-icon]]:!text-danger",
          success: "[&_[data-icon]]:!text-accent",
        },
      }}
    />
  );
}

export { toast };
