"use client";

import { ArrowUpRight, RotateCcw } from "lucide-react";
import Link from "next/link";
import * as React from "react";
import { Button } from "@/components/ui/button";
import { EvidenceLabel } from "@/components/ui/evidence-label";
import { PixelLoader } from "@/components/ui/pixel-loader";
import { ErrorState } from "@/components/ui/state";
import { ApiError } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { loadInstrument, SAMPLE_SHOTS, type InstrumentSelection, type InstrumentSnapshot } from "./instrument-data";
import { InstrumentDiagram } from "./instrument-diagram";
import {
  describe,
  fmtProb,
  getScenario,
  logPosition,
  MAX_SAMPLED_N,
  N_OPTIONS,
  SCENARIOS,
  type ProbabilitySource,
  type Reading,
  type ScenarioId,
} from "./instrument-model";

const SOURCE_TEXT: Record<ProbabilitySource, string> = {
  theorem: "Published theorem: an upper bound for every counterfeiter",
  exact_model: "Exact model value for this one attack: a lower bound on the worst case",
  monte_carlo: "Monte Carlo estimate with a confidence interval: a lower bound on the worst case",
  out_of_model: "Out-of-model control: the game's assumptions are deliberately broken",
  not_applicable: "Not applicable",
};

type Status = { kind: "idle" } | { kind: "loading" } | { kind: "error"; error: ApiError | Error };

export function Instrument({ initial }: { initial: InstrumentSnapshot | null }) {
  const [sel, setSel] = React.useState<InstrumentSelection>(
    initial?.selection ?? { scenario: "mvw_channel", n: 4, sampled: false },
  );
  const [snap, setSnap] = React.useState<InstrumentSnapshot | null>(initial);
  const [status, setStatus] = React.useState<Status>({ kind: "idle" });
  const [run, setRun] = React.useState(0);
  const first = React.useRef(initial !== null);

  React.useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    const ctrl = new AbortController();
    setStatus({ kind: "loading" });
    loadInstrument(sel, { signal: ctrl.signal, timeoutMs: 12_000 })
      .then((s) => {
        setSnap(s);
        setStatus({ kind: "idle" });
        setRun((r) => r + 1);
      })
      .catch((e: unknown) => {
        if (e instanceof ApiError && e.kind === "aborted") return;
        setStatus({ kind: "error", error: e as Error });
      });
    return () => ctrl.abort();
  }, [sel]);

  const scenario = getScenario(sel.scenario);
  const canSample = scenario.sampleable && sel.n <= MAX_SAMPLED_N;
  const busy = status.kind === "loading";
  const r = snap?.readings;

  return (
    <section
      aria-labelledby="instrument-title"
      className="relative overflow-hidden rounded-md border border-border bg-[color-mix(in_oklab,var(--surface)_55%,var(--background))]"
    >
      {/* header strip */}
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-b border-border px-4 py-3 sm:px-5">
        <h2 id="instrument-title" className="label-mono text-muted">
          Instrument <span className="text-subtle">·</span> game W1 <span className="text-subtle">·</span> Wiesner note
        </h2>
        <div className="flex items-center gap-4">
          {busy ? <Busy /> : null}
          <NSelector value={sel.n} onChange={(n) => setSel((s) => ({ ...s, n, sampled: s.sampled && n <= MAX_SAMPLED_N }))} />
        </div>
      </div>

      <div className="grid md:grid-cols-[240px_minmax(0,1fr)] lg:grid-cols-[232px_minmax(0,1fr)_300px] xl:grid-cols-[256px_minmax(0,1fr)_320px]">
        {/* scenarios */}
        <fieldset className="border-b border-border p-4 sm:p-5 md:border-r md:border-b-0">
          <legend className="label-mono float-left mb-3 w-full text-subtle">Attack scenario</legend>
          <div className="clear-both grid gap-px">
            {SCENARIOS.map((sc) => (
              <ScenarioOption
                key={sc.id}
                id={sc.id}
                label={sc.label}
                inModel={sc.inModel}
                checked={sel.scenario === sc.id}
                onSelect={(id) => setSel((s) => ({ ...s, scenario: id, sampled: s.sampled && getScenario(id).sampleable }))}
              />
            ))}
          </div>
          <p className="mt-4 text-xs leading-relaxed text-muted">{scenario.summary}</p>
          <label
            className={cn(
              "mt-4 flex items-start gap-2.5 text-xs",
              canSample ? "cursor-pointer text-foreground" : "cursor-not-allowed text-subtle",
            )}
          >
            <input
              type="checkbox"
              className="mt-0.5 size-3.5 accent-[var(--accent)]"
              checked={sel.sampled && canSample}
              disabled={!canSample}
              onChange={(e) => setSel((s) => ({ ...s, sampled: e.target.checked }))}
              aria-describedby="sample-hint"
            />
            <span>
              Also sample with Aer
              <span id="sample-hint" className="mt-0.5 block text-subtle">
                {canSample
                  ? `${SAMPLE_SHOTS.toLocaleString("en-US")} shots, 99% Clopper–Pearson interval`
                  : scenario.sampleable
                    ? `cloning circuit needs 3n ≤ 8 qubits: n ≤ ${MAX_SAMPLED_N} only`
                    : "no circuit sampler for this scenario in the API"}
              </span>
            </span>
          </label>
        </fieldset>

        {/* diagram */}
        <div
          className={cn(
            "relative flex min-h-[340px] items-center justify-center px-4 py-6 transition-opacity duration-[var(--duration-base)]",
            busy && "opacity-60",
          )}
          aria-busy={busy}
        >
          {snap && r ? (
            <InstrumentDiagram readings={r} states={snap.note.states} tokenId={snap.note.tokenId} runKey={`${run}`} />
          ) : status.kind === "error" ? null : (
            <Busy />
          )}
          {status.kind === "error" ? (
            <div className="absolute inset-0 flex items-center justify-center bg-background/90 p-6">
              <ErrorState
                timeout={status.error instanceof ApiError && status.error.kind === "timeout"}
                title="The research API did not answer"
                description="The instrument only shows values computed by the API. Start it with uvicorn qmint.api.app:app, then retry."
                detail={status.error.message}
                action={
                  <Button size="sm" onClick={() => setSel((s) => ({ ...s }))}>
                    <RotateCcw /> Retry
                  </Button>
                }
              />
            </div>
          ) : null}
        </div>

        {/* readouts */}
        <div
          className="grid content-start gap-5 border-t border-border p-4 sm:p-5 md:col-span-2 md:grid-cols-2 md:gap-x-10 lg:col-span-1 lg:grid-cols-1 lg:border-t-0 lg:border-l"
          aria-busy={busy}
        >
          {r ? (
            <>
              <div className="grid content-start gap-5">
                <Headline reading={r.scenario === "honest" ? r.single : r.joint} />
                <LogScale joint={r.joint} bound={r.bound} />
              </div>
              <dl className="grid">
                {r.scenario === "honest" ? <Row reading={r.joint} /> : null}
                <Row reading={r.perQubit} />
                {r.scenario === "honest" ? null : <Row reading={r.single} />}
                <Row reading={r.bound} muted={!r.bound.applies} suffix={r.bound.applies ? undefined : "does not apply"} />
                {r.sampled ? <Row reading={r.sampled} /> : null}
              </dl>
            </>
          ) : (
            <p className="text-sm text-muted">Waiting for the API.</p>
          )}
        </div>
      </div>

      {/* footer: API status + provenance */}
      <div className="flex flex-col gap-3 border-t border-border px-4 py-3 text-xs sm:px-5 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-subtle">
          {r && r.apiStatus !== "OK" ? <EvidenceLabel kind={r.apiStatus} group="api_status" size="xs" /> : null}
          {r?.apiReason ? <span className="min-w-0">{r.apiReason}</span> : null}
          {snap ? (
            <span className="tnum font-mono">
              seed {snap.note.seed} · git {snap.provenance.gitSha.slice(0, 7)}
            </span>
          ) : null}
        </div>
        <Link
          href={`/lab/attack`}
          className="inline-flex shrink-0 items-center gap-1 text-muted transition-colors duration-[var(--duration-fast)] hover:text-foreground"
        >
          Full parameters in the attack lab <ArrowUpRight className="size-3.5" aria-hidden />
        </Link>
      </div>

      <p className="sr-only" role="status" aria-live="polite">
        {busy ? "Updating" : r ? describe(r) : ""}
      </p>
    </section>
  );
}

function Busy() {
  return (
    <span className="inline-flex items-center gap-2 font-mono text-[0.6875rem] text-subtle">
      <PixelLoader label="Querying the research API" />
      querying API
    </span>
  );
}

function ScenarioOption({
  id,
  label,
  inModel,
  checked,
  onSelect,
}: {
  id: ScenarioId;
  label: string;
  inModel: boolean;
  checked: boolean;
  onSelect: (id: ScenarioId) => void;
}) {
  return (
    <label
      className={cn(
        "group relative flex cursor-pointer items-center justify-between gap-3 rounded-sm py-2 pr-2 pl-3 text-sm transition-colors duration-[var(--duration-instant)]",
        "has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-1 has-[:focus-visible]:outline-ring",
        checked ? "bg-surface-raised text-foreground" : "text-muted hover:bg-surface-hover hover:text-foreground",
      )}
    >
      <span
        aria-hidden
        className={cn(
          "absolute top-1.5 bottom-1.5 left-0 w-0.5 rounded-xs transition-colors duration-[var(--duration-fast)]",
          checked ? (inModel ? "bg-accent" : "bg-danger") : "bg-transparent",
        )}
      />
      <input type="radio" name="instrument-scenario" value={id} checked={checked} onChange={() => onSelect(id)} className="sr-only" />
      <span>{label}</span>
      {!inModel ? <span className="label-mono text-[0.625rem] text-danger">out of model</span> : null}
    </label>
  );
}

function NSelector({ value, onChange }: { value: number; onChange: (n: number) => void }) {
  return (
    <fieldset className="flex items-center gap-2">
      <legend className="sr-only">Number of qubits n</legend>
      <span aria-hidden className="label-mono text-subtle">
        n
      </span>
      <div className="flex rounded-sm border border-border">
        {N_OPTIONS.map((n) => (
          <label
            key={n}
            className={cn(
              "tnum relative flex h-7 min-w-8 cursor-pointer items-center justify-center border-l border-border px-2 font-mono text-xs first:border-l-0",
              "has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-ring",
              value === n ? "bg-surface-raised text-foreground" : "text-subtle hover:text-foreground",
            )}
          >
            <input
              type="radio"
              name="instrument-n"
              value={n}
              aria-label={`n = ${n}`}
              checked={value === n}
              onChange={() => onChange(n)}
              className="sr-only"
            />
            {n}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function Label({ reading }: { reading: Reading }) {
  return <EvidenceLabel kind={reading.evidence.kind} group={reading.evidence.group} size="xs" />;
}

function Headline({ reading }: { reading: Reading }) {
  const out = reading.source === "out_of_model";
  return (
    <div className="grid gap-2" data-source={reading.source}>
      <p className="label-mono text-subtle">{reading.label}</p>
      {reading.value === null ? (
        <p className="text-sm text-muted italic">{reading.note ?? "not applicable"}</p>
      ) : (
        <p className={cn("tnum font-mono text-[2.25rem] leading-none tracking-tight", out ? "text-danger" : "text-accent")}>
          {fmtProb(reading.value)}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <Label reading={reading} />
        <span className="font-mono text-[0.6875rem] text-subtle">{reading.method}</span>
      </div>
      <p className="text-xs leading-relaxed text-muted">
        {reading.explain ?? SOURCE_TEXT[reading.source]}
        {reading.formula ? (
          <>
            {" · "}
            <span className="font-mono text-subtle">{reading.formula}</span>
          </>
        ) : null}
      </p>
    </div>
  );
}

function Row({ reading, muted = false, suffix }: { reading: Reading; muted?: boolean; suffix?: string }) {
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-3 gap-y-1 border-t border-hairline py-2.5" data-source={reading.source}>
      <dt className="text-xs text-muted">{reading.label}</dt>
      <dd className={cn("tnum text-right font-mono text-sm", muted ? "text-subtle line-through decoration-subtle/60" : "text-foreground")}>
        {reading.value === null ? <span className="text-xs text-subtle italic no-underline">n/a</span> : fmtProb(reading.value)}
      </dd>
      <dd className="col-span-2 flex flex-wrap items-center gap-x-2 gap-y-1">
        <Label reading={reading} />
        {reading.interval ? (
          <span className="tnum font-mono text-[0.6875rem] text-subtle">
            [{fmtProb(reading.interval.lo)}, {fmtProb(reading.interval.hi)}]
            {reading.interval.confidence ? ` · ${Math.round(reading.interval.confidence * 100)}% CI` : ""}
          </span>
        ) : null}
        {reading.source === "monte_carlo" ? <span className="font-mono text-[0.6875rem] text-subtle">{reading.method}</span> : null}
        {suffix ? <span className="font-mono text-[0.6875rem] text-danger">{suffix}</span> : null}
      </dd>
    </div>
  );
}

/** Log10 probability rule from 10⁻³ to 1: the attack's joint value against the theorem bound. */
function LogScale({ joint, bound }: { joint: Reading; bound: Reading & { applies: boolean } }) {
  const pj = logPosition(joint.value);
  const pb = logPosition(bound.value);
  const ticks = [
    { at: 0, t: "10⁻³" },
    { at: 1 / 3, t: "10⁻²" },
    { at: 2 / 3, t: "10⁻¹" },
    { at: 1, t: "1" },
  ];
  return (
    <div aria-hidden className="pt-1">
      <div className="relative h-6">
        <div className="absolute inset-x-0 top-3 h-px bg-border-strong" />
        {ticks.map((t) => (
          <div key={t.t} className="absolute top-2 h-2 w-px bg-border-strong" style={{ left: `${t.at * 100}%` }} />
        ))}
        {pb !== null ? (
          <div
            className={cn("absolute top-0 h-6 w-0 border-l border-dashed", bound.applies ? "border-chart-3" : "border-subtle")}
            style={{ left: `${pb * 100}%`, transition: "left var(--duration-deliberate) var(--ease-out)" }}
          />
        ) : null}
        {pj !== null ? (
          <div
            className={cn("absolute top-[9px] size-[7px] -translate-x-1/2", joint.source === "out_of_model" ? "bg-danger" : "bg-accent")}
            style={{ left: `${pj * 100}%`, transition: "left var(--duration-deliberate) var(--ease-out)" }}
          />
        ) : null}
      </div>
      <div className="relative mt-1 h-4 font-mono text-[0.625rem] text-subtle">
        {ticks.map((t, i) => (
          <span
            key={t.t}
            className={cn("absolute", i === 0 ? "" : i === ticks.length - 1 ? "-translate-x-full" : "-translate-x-1/2")}
            style={{ left: `${t.at * 100}%` }}
          >
            {t.t}
          </span>
        ))}
      </div>
      <div className="mt-1 flex gap-4 font-mono text-[0.625rem] text-subtle">
        <span className="inline-flex items-center gap-1.5">
          <span className={cn("size-[7px]", joint.source === "out_of_model" ? "bg-danger" : "bg-accent")} /> both pass
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-0 border-l border-dashed border-chart-3" /> W1 bound
        </span>
      </div>
    </div>
  );
}
