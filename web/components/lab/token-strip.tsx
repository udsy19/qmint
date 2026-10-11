import * as React from "react";
import { cn } from "@/lib/utils";
import type { Schemas } from "@/lib/api/client";

type TeachingQubit = Schemas["TeachingQubit"];

const KET: Record<string, string> = { "0": "|0⟩", "1": "|1⟩", "+": "|+⟩", "-": "|−⟩" };

/** "SN-1066070b41b16889" → "SN-1066 070B 41B1 6889" for the Pixel Grid serial. */
export function formatSerial(serial: string): string {
  const [prefix, hex] = serial.includes("-") ? [serial.slice(0, serial.indexOf("-")), serial.slice(serial.indexOf("-") + 1)] : ["", serial];
  const groups = hex.toUpperCase().match(/.{1,4}/g) ?? [hex];
  return prefix ? `${prefix}-${groups.join(" ")}` : groups.join(" ");
}

/**
 * The note as the holder sees it: a public serial plus n qubits whose states are unknown to them.
 * In teaching mode each cell shows the secret state as an arrow on the x–z great circle of the Bloch
 * sphere (|0⟩ up, |1⟩ down, |+⟩ right, |−⟩ left) — data from the API, not decoration.
 */
export function TokenStrip({
  serial,
  n,
  qubits,
  freshness,
  className,
}: {
  serial: string;
  n: number;
  qubits?: TeachingQubit[] | null;
  freshness?: string;
  className?: string;
}) {
  const revealed = Boolean(qubits?.length);
  return (
    <figure className={cn("grid gap-4", className)} aria-label={`Note ${serial}, ${n} qubits${revealed ? ", secret revealed" : ", states secret"}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <span className="font-pixel-grid text-[1.375rem] leading-none tracking-wide text-foreground sm:text-[1.625rem]">{formatSerial(serial)}</span>
        <span className="label-mono text-subtle">
          public serial · {n} qubit{n === 1 ? "" : "s"}
          {freshness ? ` · ${freshness}` : ""}
        </span>
      </div>
      <ol className="flex flex-wrap gap-2" aria-label="Qubits">
        {Array.from({ length: n }, (_, i) => {
          const q = qubits?.[i];
          return (
            <li key={i} className="grid justify-items-center gap-1.5">
              <QubitGlyph q={q} />
              <span className="tnum font-mono text-[0.6875rem] text-subtle">
                q{i}
                {q ? <span className="text-danger"> {KET[q.state_label] ?? q.state_label}</span> : null}
              </span>
            </li>
          );
        })}
      </ol>
    </figure>
  );
}

function QubitGlyph({ q }: { q?: TeachingQubit }) {
  const hatch = `qm-hatch-${React.useId().replace(/:/g, "")}`;
  const [x, , z] = q?.bloch ?? [0, 0, 0];
  const label = q ? `${KET[q.state_label] ?? q.state_label}, basis ${q.basis}, bit ${q.bit}` : "unknown state";
  return (
    <svg viewBox="0 0 40 40" className="size-11 sm:size-12" role="img" aria-label={label}>
      <rect x="0.5" y="0.5" width="39" height="39" rx="3" className={cn("fill-surface", q ? "stroke-danger/40" : "stroke-border-strong")} />
      {q ? (
        <g className="transition-opacity duration-[var(--duration-deliberate)] ease-out">
          <circle cx="20" cy="20" r="12" className="fill-none stroke-border-strong" />
          <line x1="8" y1="20" x2="32" y2="20" className="stroke-border" strokeDasharray="1.5 2" />
          <line x1="20" y1="8" x2="20" y2="32" className="stroke-border" strokeDasharray="1.5 2" />
          <line x1="20" y1="20" x2={20 + 12 * x} y2={20 - 12 * z} className="stroke-foreground" strokeWidth="1.5" strokeLinecap="round" />
          <circle cx={20 + 12 * x} cy={20 - 12 * z} r="2.25" className="fill-foreground" />
        </g>
      ) : (
        <g>
          <defs>
            <pattern id={hatch} width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <line x1="0" y1="0" x2="0" y2="4" className="stroke-border-strong" strokeWidth="1" />
            </pattern>
          </defs>
          <rect x="6" y="6" width="28" height="28" rx="2" fill={`url(#${hatch})`} />
          <circle cx="20" cy="20" r="6" className="fill-surface stroke-border-strong" />
          <text x="20" y="23" textAnchor="middle" className="fill-subtle font-mono text-[8px]">
            ?
          </text>
        </g>
      )}
    </svg>
  );
}
