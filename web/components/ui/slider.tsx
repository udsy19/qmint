"use client";

import { Slider as S } from "radix-ui";
import * as React from "react";
import { cn } from "@/lib/utils";

/** Parameter slider. Pair with a numeric readout (Field + Readout) — never rely on the thumb position alone. */
export function Slider({ className, defaultValue, value, min = 0, max = 100, ...props }: React.ComponentProps<typeof S.Root>) {
  const values = value ?? defaultValue ?? [min];
  return (
    <S.Root
      data-slot="slider"
      defaultValue={defaultValue}
      value={value}
      min={min}
      max={max}
      className={cn("relative flex h-5 w-full touch-none items-center select-none data-[disabled]:opacity-40", className)}
      {...props}
    >
      <S.Track className="relative h-[3px] grow overflow-hidden rounded-full bg-border-strong">
        <S.Range className="absolute h-full bg-accent" />
      </S.Track>
      {values.map((_, i) => (
        <S.Thumb
          key={i}
          className={cn(
            "block size-3.5 rounded-full border border-background bg-foreground shadow-raised",
            "transition-transform duration-[var(--duration-fast)] ease-out hover:scale-110",
            "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
          )}
        />
      ))}
    </S.Root>
  );
}
