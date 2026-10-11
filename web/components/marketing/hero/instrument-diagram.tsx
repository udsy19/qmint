import { cn } from "@/lib/utils";
import { STATE_KET, StateCell, type Bb84Label } from "../state-glyph";
import { fmtProb, getScenario, type InstrumentReadings } from "./instrument-model";
import s from "./instrument.module.css";

/**
 * The instrument's schematic: note → channel → two verifications → joint outcome.
 * Plots only API values; animation is the branch strokes drawing on each new reading.
 */
const W = 360;
const CX = W / 2;
const V1 = 76;
const V2 = W - 76;

export function InstrumentDiagram({
  readings,
  states,
  tokenId,
  runKey,
}: {
  readings: InstrumentReadings;
  states: string[];
  tokenId: string;
  /** Changes whenever a new reading arrives so the strokes redraw. */
  runKey: string;
}) {
  const scenario = getScenario(readings.scenario);
  const honest = readings.scenario === "honest";
  const out = !scenario.inModel;
  const n = states.length;
  const cell = n > 4 ? 26 : 30;
  const gap = n > 4 ? 6 : 10;
  const rowW = n * cell + (n - 1) * gap;
  const x0 = CX - rowW / 2 + cell / 2;

  const branch = (x: number) => `M${CX} 190 C${CX} 236 ${x} 228 ${x} 268`;
  const merge = (x: number) => `M${x} 312 C${x} 344 ${CX} 336 ${CX} 362`;
  const nodeStroke = out ? "var(--danger)" : "var(--border-strong)";

  return (
    <svg
      viewBox={`0 0 ${W} 412`}
      className="mx-auto block h-auto w-full max-w-[420px]"
      role="img"
      aria-label={`Schematic: a ${n}-qubit note passes through ${scenario.label}; ${honest ? "one verification" : "two verifications"} follow.`}
    >
      {/* note */}
      <text x={CX} y={18} textAnchor="middle" className="fill-subtle font-pixel-grid text-[10px] tracking-[0.04em]">
        {tokenId}
      </text>
      {states.map((st, i) => (
        <g key={i}>
          <StateCell cx={x0 + i * (cell + gap)} cy={52} size={cell} state={st as Bb84Label} />
          <text x={x0 + i * (cell + gap)} y={52 + cell / 2 + 14} textAnchor="middle" className="fill-subtle font-mono text-[10px]">
            {STATE_KET[st as Bb84Label]}
          </text>
        </g>
      ))}

      {/* stem + channel node */}
      <line x1={CX} y1={98} x2={CX} y2={150} stroke="var(--border-strong)" />
      <g key={`node-${runKey}`}>
        <rect
          x={CX - 70}
          y={150}
          width={140}
          height={40}
          rx={2}
          fill="var(--surface)"
          stroke={nodeStroke}
          strokeDasharray={honest ? "3 3" : undefined}
        />
        <text x={CX} y={167} textAnchor="middle" className={cn("font-mono text-[11px]", out ? "fill-danger" : "fill-foreground")}>
          {honest ? "no counterfeiter" : scenario.operator}
        </text>
        <text x={CX} y={181} textAnchor="middle" className="fill-subtle font-mono text-[9px] tracking-[0.06em] uppercase">
          {out ? "out of model" : honest ? "genuine note" : "1 → 2 channel"}
        </text>
      </g>

      {/* branches */}
      <g key={`br-${runKey}`} fill="none" strokeWidth={1}>
        <path d={branch(V1)} pathLength={1} stroke="var(--muted)" className={s.draw} />
        <path
          d={branch(V2)}
          pathLength={honest ? undefined : 1}
          stroke={honest ? "var(--border-strong)" : "var(--muted)"}
          strokeDasharray={honest ? "3 4" : undefined}
          className={honest ? undefined : s.draw}
        />
        {!honest && (
          <>
            <path d={merge(V1)} pathLength={1} stroke="var(--accent)" strokeOpacity={0.7} className={s.drawLate} />
            <path d={merge(V2)} pathLength={1} stroke="var(--accent)" strokeOpacity={0.7} className={s.drawLate} />
          </>
        )}
      </g>

      {/* verifiers */}
      <Verifier x={V1} index={1} value={readings.single.value} active />
      <Verifier x={V2} index={2} value={honest ? null : readings.single.value} active={!honest} />

      {/* joint outcome */}
      <g key={`j-${runKey}`} className={honest ? undefined : s.fade}>
        {honest ? (
          <text x={CX} y={380} textAnchor="middle" className="fill-subtle font-mono text-[10px]">
            joint pass not defined: one note, one check
          </text>
        ) : (
          <>
            <rect x={CX - 3.5} y={360} width={7} height={7} fill={out ? "var(--danger)" : "var(--accent)"} />
            <text x={CX} y={388} textAnchor="middle" className="fill-subtle font-mono text-[9.5px] tracking-[0.06em] uppercase">
              both pass
            </text>
            <text x={CX} y={405} textAnchor="middle" className={cn("tnum font-mono text-[13px]", out ? "fill-danger" : "fill-accent")}>
              {fmtProb(readings.joint.value)}
            </text>
          </>
        )}
      </g>
    </svg>
  );
}

function Verifier({ x, index, value, active }: { x: number; index: 1 | 2; value: number | null; active: boolean }) {
  return (
    <g opacity={active ? 1 : 0.45}>
      <rect x={x - 59} y={268} width={118} height={44} rx={2} fill="var(--surface)" stroke="var(--border-strong)" strokeDasharray={active ? undefined : "3 3"} />
      <text x={x} y={285} textAnchor="middle" className="fill-foreground font-mono text-[11px]">
        {`V${index === 1 ? "₁" : "₂"} · verify`}
      </text>
      <text x={x} y={302} textAnchor="middle" className="tnum fill-muted font-mono text-[10.5px]">
        {active ? `P(pass) ${fmtProb(value)}` : "no second note"}
      </text>
    </g>
  );
}
