import { cn } from "@/lib/utils";

/**
 * A BB84 state drawn as a polarisation axis inside a hairline cell:
 * |0⟩ vertical, |1⟩ horizontal, |+⟩ 45°, |−⟩ 135° (the H/V/D/A photonic convention).
 * Shared by the hero instrument and section 02. Pure SVG, no motion of its own.
 */
export type Bb84Label = "0" | "1" | "+" | "-";

export const STATE_ANGLE: Record<Bb84Label, number> = { "0": 0, "1": 90, "+": 45, "-": 135 };
export const STATE_KET: Record<Bb84Label, string> = { "0": "|0⟩", "1": "|1⟩", "+": "|+⟩", "-": "|−⟩" };
export const STATE_BASIS: Record<Bb84Label, "Z" | "X"> = { "0": "Z", "1": "Z", "+": "X", "-": "X" };

/** SVG fragment (use inside an <svg>): cell centred on (cx, cy). */
export function StateCell({
  cx,
  cy,
  size,
  state,
  className,
}: {
  cx: number;
  cy: number;
  size: number;
  state: Bb84Label | null;
  className?: string;
}) {
  const h = size / 2;
  const r = h * 0.62;
  return (
    <g className={className}>
      <rect x={cx - h} y={cy - h} width={size} height={size} fill="var(--background)" stroke="var(--border-strong)" strokeWidth={1} />
      {state === null ? (
        <text x={cx} y={cy + 3.5} textAnchor="middle" className="fill-subtle font-mono text-[10px]">
          ?
        </text>
      ) : (
        <g
          style={{
            transform: `rotate(${STATE_ANGLE[state]}deg)`,
            transformOrigin: `${cx}px ${cy}px`,
            transition: "transform var(--duration-deliberate) var(--ease-out)",
          }}
        >
          <line x1={cx} y1={cy - r} x2={cx} y2={cy + r} stroke="var(--foreground)" strokeWidth={1.5} strokeLinecap="square" />
          <circle cx={cx} cy={cy - r} r={1.6} fill="var(--foreground)" />
        </g>
      )}
    </g>
  );
}

/** Stand-alone glyph (its own <svg>), used in prose and the section 02 plate. */
export function StateGlyph({ state, size = 32, className, title }: { state: Bb84Label; size?: number; className?: string; title?: string }) {
  return (
    <svg
      viewBox={`0 0 ${size + 2} ${size + 2}`}
      width={size + 2}
      height={size + 2}
      className={cn("shrink-0 overflow-visible", className)}
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
    >
      <StateCell cx={(size + 2) / 2} cy={(size + 2) / 2} size={size} state={state} />
    </svg>
  );
}
