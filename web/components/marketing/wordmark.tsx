import { cn } from "@/lib/utils";

/**
 * QMint identity.
 * Mark: a 2×2 plate of the four BB84 polarisation axes (|0⟩ |+⟩ / |−⟩ |1⟩). Each axis is a
 * state the bank can prepare, and together they are the alphabet of a Wiesner note.
 * Wordmark: "QMint" set in Geist Pixel Square (the only Pixel cut used for brand type).
 * Static copy of the mark: /public/brand/qmint-mark.svg.
 */
export function Mark({ className, size = 18 }: { className?: string; size?: number }) {
  return (
    <svg viewBox="0 0 20 20" width={size} height={size} className={cn("shrink-0", className)} aria-hidden>
      <rect x="0.5" y="0.5" width="19" height="19" fill="none" stroke="currentColor" strokeOpacity="0.35" />
      <path d="M10 0.5v19M0.5 10h19" stroke="currentColor" strokeOpacity="0.35" />
      {/* |0⟩ vertical */}
      <path d="M5.25 2.5v5" stroke="currentColor" strokeWidth="1.5" />
      {/* |+⟩ 45° */}
      <path d="M12.75 7.25 17.25 2.75" stroke="currentColor" strokeWidth="1.5" />
      {/* |−⟩ 135° */}
      <path d="M2.75 12.75 7.25 17.25" stroke="currentColor" strokeWidth="1.5" />
      {/* |1⟩ horizontal */}
      <path d="M12.5 15h5" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2 text-foreground", className)}>
      <Mark />
      <span className="font-pixel text-[1.125rem] leading-none tracking-[0.01em]">QMint</span>
    </span>
  );
}
