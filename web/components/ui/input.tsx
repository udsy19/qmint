import * as React from "react";
import { cn } from "@/lib/utils";

export const fieldBase =
  "h-8 w-full min-w-0 rounded-sm border border-border-strong bg-surface px-2.5 text-sm text-foreground " +
  "placeholder:text-subtle transition-[border-color,background-color] duration-[var(--duration-fast)] ease-out " +
  "hover:border-[#45464f] focus-visible:border-accent/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/25 " +
  "disabled:cursor-not-allowed disabled:opacity-40 aria-invalid:border-danger/60 aria-invalid:ring-danger/20";

export function Input({ className, type = "text", ...props }: React.ComponentProps<"input">) {
  return <input data-slot="input" type={type} className={cn(fieldBase, type === "number" && "tnum font-mono", className)} {...props} />;
}

export function Label({ className, ...props }: React.ComponentProps<"label">) {
  return <label data-slot="label" className={cn("text-xs font-medium text-muted", className)} {...props} />;
}

/** Label + control + optional hint/error, wired with ids for a11y. */
export function Field({
  id,
  label,
  hint,
  error,
  children,
  className,
}: {
  id: string;
  label: React.ReactNode;
  hint?: React.ReactNode;
  error?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("grid gap-1.5", className)}>
      <Label htmlFor={id}>{label}</Label>
      {children}
      {error ? (
        <p id={`${id}-error`} role="alert" className="text-xs text-danger">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="text-xs text-subtle">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
