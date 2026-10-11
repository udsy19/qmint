"use client";

import { Check, ChevronDown } from "lucide-react";
import { Select as S } from "radix-ui";
import * as React from "react";
import { cn } from "@/lib/utils";
import { fieldBase } from "./input";

export const Select = S.Root;
export const SelectValue = S.Value;
export const SelectGroup = S.Group;

export function SelectTrigger({ className, children, ...props }: React.ComponentProps<typeof S.Trigger>) {
  return (
    <S.Trigger
      data-slot="select-trigger"
      className={cn(fieldBase, "flex items-center justify-between gap-2 text-left data-[placeholder]:text-subtle", className)}
      {...props}
    >
      <span className="truncate">{children}</span>
      <S.Icon asChild>
        <ChevronDown className="size-3.5 shrink-0 text-subtle" aria-hidden />
      </S.Icon>
    </S.Trigger>
  );
}

export function SelectContent({ className, children, position = "popper", ...props }: React.ComponentProps<typeof S.Content>) {
  return (
    <S.Portal>
      <S.Content
        data-slot="select-content"
        position={position}
        sideOffset={4}
        className={cn(
          "z-dropdown max-h-[var(--radix-select-content-available-height)] min-w-[var(--radix-select-trigger-width)] overflow-hidden rounded-md bg-surface-overlay p-1 shadow-overlay",
          "data-[state=open]:animate-[qm-fade-in_var(--duration-fast)_var(--ease-out)]",
          className,
        )}
        {...props}
      >
        <S.Viewport>{children}</S.Viewport>
      </S.Content>
    </S.Portal>
  );
}

export function SelectItem({ className, children, ...props }: React.ComponentProps<typeof S.Item>) {
  return (
    <S.Item
      data-slot="select-item"
      className={cn(
        "relative flex h-7 cursor-default items-center rounded-xs pr-7 pl-2 text-sm text-muted outline-none select-none",
        "data-[highlighted]:bg-surface-hover data-[highlighted]:text-foreground data-[state=checked]:text-foreground",
        "data-[disabled]:pointer-events-none data-[disabled]:opacity-40",
        className,
      )}
      {...props}
    >
      <S.ItemText>{children}</S.ItemText>
      <S.ItemIndicator className="absolute right-2 inline-flex">
        <Check className="size-3.5 text-accent" aria-hidden />
      </S.ItemIndicator>
    </S.Item>
  );
}

export function SelectLabel({ className, ...props }: React.ComponentProps<typeof S.Label>) {
  return <S.Label className={cn("label-mono px-2 py-1.5 text-subtle", className)} {...props} />;
}
