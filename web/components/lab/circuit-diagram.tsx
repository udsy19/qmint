import * as React from "react";
import type { Schemas } from "@/lib/api/client";
import { cn } from "@/lib/utils";

type Circuit = Schemas["CircuitDescription"];

const ROW = 34;
const TOP = 30;
const LEFT = 40;
const GATE = 22;
const COL = 34;

const GATE_TEXT: Record<string, string> = { x: "X", h: "H" };

/**
 * Prepare → channel → verify circuit, drawn from the API's per-qubit op lists (C7 order, q0 on top).
 * Redacted (default): preparation and verification are hatched "secret" boxes — the gates would reveal
 * the bases. Teaching mode: X for bit 1, H for the X basis, H again before the Z measurement.
 */
export function CircuitDiagram({ circuit, className }: { circuit: Circuit; className?: string }) {
  const n = circuit.qubits.length;
  const redacted = circuit.redacted;
  const hasChannel = circuit.qubits.some((q) => q.channel.length > 0);
  const prepCols = redacted ? 1 : 2;
  const verifyCols = redacted ? 2 : 2; // [H?, measure] or [secret box (wide)]
  const xPrep = LEFT + 16;
  const xBar1 = xPrep + prepCols * COL + (redacted ? 18 : 4);
  const xChan = xBar1 + 14;
  const xBar2 = hasChannel ? xChan + COL + 4 : xBar1;
  const xVerify = xBar2 + 14;
  const xEnd = xVerify + verifyCols * COL + 8;
  const width = xEnd + 34;
  const height = TOP + n * ROW + 6;
  const y = (i: number) => TOP + i * ROW + ROW / 2 - 4;
  const hatch = `qm-circ-hatch-${React.useId().replace(/:/g, "")}`;
  const channelName = circuit.qubits.find((q) => q.channel.length)?.channel[0] ?? "";

  const summary = redacted
    ? `${n}-qubit circuit: secret preparation${hasChannel ? `, channel ${channelName}` : ""}, secret-basis measurement`
    : `${n}-qubit circuit. ` +
      circuit.qubits
        .map((q) => `q${q.index}: ${q.prepare.length ? q.prepare.map((g) => GATE_TEXT[g] ?? g).join(" then ") : "no gate"}, measure ${q.verify.includes("h") ? "after H" : "directly"}`)
        .join("; ");

  return (
    <div className={cn("overflow-x-auto", className)}>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full min-w-[300px]" style={{ maxWidth: width * 1.5 }} role="img" aria-label={summary}>
        <defs>
          <pattern id={hatch} width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="4" className="stroke-border-strong" strokeWidth="1" />
          </pattern>
        </defs>
        {/* stage captions */}
        <g className="fill-subtle font-mono text-[8px] tracking-wider uppercase">
          <text x={xPrep} y={12}>prepare</text>
          {hasChannel ? <text x={xChan} y={12}>channel</text> : null}
          <text x={xVerify} y={12}>verify</text>
        </g>
        {/* barriers */}
        {[xBar1, ...(hasChannel ? [xBar2] : [])].map((bx) => (
          <line key={bx} x1={bx} x2={bx} y1={TOP - 6} y2={height - 4} className="stroke-border-strong" strokeDasharray="2 3" />
        ))}
        {circuit.qubits.map((q, i) => {
          const yy = y(i);
          const measureX = redacted ? xVerify + COL * 2 - 4 - GATE : xVerify + COL;
          return (
            <g key={q.index}>
              <text x={4} y={yy + 3.5} className="fill-muted font-mono text-[9px]">
                q{q.index}
              </text>
              <text x={20} y={yy + 3.5} className="fill-subtle font-mono text-[8px]">
                |0⟩
              </text>
              <line x1={LEFT} x2={measureX} y1={yy} y2={yy} className="stroke-border-strong" />
              {/* classical wire */}
              <line x1={measureX + GATE} x2={xEnd + 4} y1={yy - 1.5} y2={yy - 1.5} className="stroke-border" />
              <line x1={measureX + GATE} x2={xEnd + 4} y1={yy + 1.5} y2={yy + 1.5} className="stroke-border" />
              <text x={xEnd + 8} y={yy + 3} className="fill-subtle font-mono text-[8px]">
                c{q.index}
              </text>
              {redacted ? (
                <SecretBox x={xPrep} y={yy} w={COL + 4} hatch={hatch} label="prep" />
              ) : (
                q.prepare.map((g, k) => <Gate key={k} x={xPrep + (q.prepare.length === 1 && g === "h" ? COL : k * COL)} y={yy} text={GATE_TEXT[g] ?? g} />)
              )}
              {q.channel.length ? <Gate x={xChan} y={yy} text="ℰ" tone="channel" /> : null}
              {redacted ? (
                <SecretBox x={xVerify} y={yy} w={COL * 2 - 4} hatch={hatch} label="measure" meter />
              ) : (
                <>
                  {q.verify.includes("h") ? <Gate x={xVerify} y={yy} text="H" /> : null}
                  <Meter x={measureX} y={yy} />
                </>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function Gate({ x, y, text, tone }: { x: number; y: number; text: string; tone?: "channel" }) {
  return (
    <g>
      <rect
        x={x}
        y={y - GATE / 2}
        width={GATE}
        height={GATE}
        rx={2}
        className={tone === "channel" ? "fill-surface stroke-warn/60" : "fill-surface-raised stroke-border-strong"}
      />
      <text x={x + GATE / 2} y={y + 4} textAnchor="middle" className={cn("font-mono text-[11px]", tone === "channel" ? "fill-warn" : "fill-foreground")}>
        {text}
      </text>
    </g>
  );
}

function Meter({ x, y }: { x: number; y: number }) {
  return (
    <g>
      <rect x={x} y={y - GATE / 2} width={GATE} height={GATE} rx={2} className="fill-surface-raised stroke-border-strong" />
      <path d={`M ${x + 5} ${y + 5} A 6 6 0 0 1 ${x + GATE - 5} ${y + 5}`} className="fill-none stroke-foreground" />
      <line x1={x + GATE / 2} y1={y + 5} x2={x + GATE - 6} y2={y - 5} className="stroke-foreground" />
    </g>
  );
}

function SecretBox({ x, y, w, hatch, label, meter }: { x: number; y: number; w: number; hatch: string; label: string; meter?: boolean }) {
  return (
    <g>
      <rect x={x} y={y - GATE / 2} width={w} height={GATE} rx={2} fill={`url(#${hatch})`} className="stroke-border-strong" />
      <rect x={x + 3} y={y - 6} width={meter ? w - 26 : w - 6} height={12} rx={1.5} className="fill-background" />
      <text x={x + (meter ? (w - 20) / 2 : w / 2)} y={y + 3} textAnchor="middle" className="fill-muted font-mono text-[7.5px] tracking-wider uppercase">
        {label}
      </text>
      {meter ? <Meter x={x + w - GATE} y={y} /> : null}
    </g>
  );
}
