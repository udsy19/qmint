import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Small Geist-Pixel-inspired 3×3 loading motif (brand status element). Purely decorative: pair it with
 * visible text such as "Running 4 000 shots…". Under reduced motion the cells stay static.
 */
export function PixelLoader({ className, label = "Loading" }: { className?: string; label?: string }) {
  const delays = [0, 1, 2, 7, 8, 3, 6, 5, 4];
  return (
    <span role="status" aria-label={label} className={cn("inline-grid size-3 grid-cols-3 gap-px", className)}>
      {delays.map((d, i) => (
        <span
          key={i}
          aria-hidden
          className="bg-accent opacity-25 animate-[qm-pixel-blink_1.2s_steps(2,end)_infinite]"
          style={{ animationDelay: `${d * 110}ms` }}
        />
      ))}
    </span>
  );
}
