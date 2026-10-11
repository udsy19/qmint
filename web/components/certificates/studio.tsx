"use client";

import { Play } from "lucide-react";
import * as React from "react";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { Kbd } from "@/components/ui/kbd";
import { PixelLoader } from "@/components/ui/pixel-loader";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/state";
import { ApiError, apiPost } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import {
  AXES,
  INTEGER_PARAMS,
  calibrationPreview,
  defaultsForGame,
  emptyField,
  fromRequest,
  paramNames,
  toRequest,
  type CalibrationSource,
  type Catalog,
  type CertData,
  type FieldErrors,
  type FormState,
  type GameId,
  type NoiseSource,
} from "./form-model";
import { AssumptionsPanel, AxesTable, CalibrationPanel, ExportPanel, ResourcesPanel, TheoremPanel, VerdictPanel } from "./results";

const GAME_LABEL: Record<GameId, string> = {
  W1: "W1 · Wiesner, ideal verifier",
  W1_CV: "W1_CV · Wiesner, classical verification",
  W2: "W2 · Wiesner, noisy threshold",
  S1: "S1 · S-money, ideal two-site",
  S2: "S2 · S-money, realistic (Kent 2022)",
  D1: "D1 · quantum-digital payment (Schiansky 2023)",
  A1: "A1 · anonymity / issuer tracking",
  C1: "C1 · classical double-spend systems",
};

const NOISE_LABEL: Record<NoiseSource, string> = {
  published_kent_2022: "Published, Kent et al. 2022",
  published_schiansky_2023: "Published, Schiansky et al. 2023",
  hypothetical: "Hypothetical (declared)",
  calibration: "From the calibration record",
};

function FormGroup({ title, hint, children }: { title: string; hint?: React.ReactNode; children: React.ReactNode }) {
  return (
    <fieldset className="grid gap-3 border-t border-border pt-4">
      <legend className="float-left mb-1 w-full">
        <span className="label-mono text-subtle">{title}</span>
      </legend>
      {hint ? <p className="-mt-1 text-xs text-subtle">{hint}</p> : null}
      {children}
    </fieldset>
  );
}

type RunState = { status: "idle" | "loading" | "ok" | "error"; data?: CertData; error?: ApiError; ranFor?: string };

export function Studio({ catalog }: { catalog: Catalog }) {
  const first = catalog.presets[0];
  const [form, setForm] = React.useState<FormState>(() => (first ? fromRequest(first.request) : defaultsForGame("W1", catalog)));
  const [presetId, setPresetId] = React.useState<string | null>(first?.id ?? null);
  const [errors, setErrors] = React.useState<FieldErrors>({});
  const [run, setRun] = React.useState<RunState>({ status: "idle" });
  const ctrl = React.useRef<AbortController | null>(null);
  const entry = catalog.games.find((g) => g.game === form.game);
  const signature = JSON.stringify(toRequest(form).request);

  const evaluate = React.useCallback(async (state: FormState) => {
    const { request, errors: errs } = toRequest(state);
    setErrors(errs);
    if (Object.keys(errs).length) return;
    ctrl.current?.abort();
    const c = new AbortController();
    ctrl.current = c;
    setRun((r) => ({ ...r, status: "loading" }));
    try {
      const body = await apiPost("/api/v1/certificates", request, { signal: c.signal, timeoutMs: 30_000 });
      setRun({ status: "ok", data: body.data, ranFor: JSON.stringify(request) });
    } catch (e) {
      if (e instanceof ApiError && e.kind === "aborted") return;
      setRun((r) => ({ ...r, status: "error", error: e instanceof ApiError ? e : new ApiError("network", String(e)) }));
    }
  }, []);

  React.useEffect(() => {
    if (first) void evaluate(fromRequest(first.request));
    return () => ctrl.current?.abort();
    // run the first preset once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const update = (patch: Partial<FormState>) => {
    setPresetId(null);
    setForm((f) => ({ ...f, ...patch }));
  };
  const loadPreset = (id: string) => {
    const p = catalog.presets.find((x) => x.id === id);
    if (!p) return;
    const st = fromRequest(p.request);
    setPresetId(id);
    setForm(st);
    void evaluate(st);
  };
  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    void evaluate(form);
  };
  const onKeyDown = (e: React.KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      void evaluate(form);
    }
  };

  const names = paramNames(entry, form.params);
  const decl = entry?.declarations ?? [];
  const stale = run.status === "ok" && run.ranFor !== signature;

  return (
    <div className="grid gap-10">
      <section aria-labelledby="presets-h" className="grid gap-3">
        <h2 id="presets-h" className="label-mono text-subtle">
          Start from lane D&apos;s examples and the failure states
        </h2>
        <ul className="-mx-4 flex snap-x scroll-px-4 gap-px overflow-x-auto px-4 sm:mx-0 sm:grid sm:grid-cols-2 sm:overflow-visible sm:px-0 xl:grid-cols-3">
          {catalog.presets.map((p) => (
            <li key={p.id} className="min-w-64 snap-start sm:min-w-0">
              <button
                type="button"
                onClick={() => loadPreset(p.id)}
                aria-pressed={presetId === p.id}
                className={cn(
                  "relative grid h-full w-full content-start gap-1 border border-border bg-surface px-3.5 py-3 text-left transition-colors duration-[var(--duration-fast)] hover:bg-surface-hover",
                  presetId === p.id && "bg-surface-raised before:absolute before:inset-y-0 before:left-0 before:w-0.5 before:bg-accent",
                )}
              >
                <span className="text-[0.8125rem] font-medium text-foreground">{p.title}</span>
                <span className="text-xs text-muted">{p.summary}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      <div className="grid items-start gap-10 lg:grid-cols-[340px_minmax(0,1fr)] xl:grid-cols-[372px_minmax(0,1fr)]">
        <form onSubmit={onSubmit} onKeyDown={onKeyDown} aria-label="Certificate request" className="grid gap-5 lg:sticky lg:top-6">
          <Field id="game" label="Protocol / security game" hint={entry ? `protocol: ${entry.protocol_ids.join(", ")}` : undefined}>
            <Select
              value={form.game}
              onValueChange={(g) => {
                setPresetId(null);
                setForm(defaultsForGame(g as GameId, catalog));
              }}
            >
              <SelectTrigger id="game">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {catalog.games.map((g) => (
                  <SelectItem key={g.game} value={g.game}>
                    {GAME_LABEL[g.game]}
                    {g.theorem ? "" : " — no theorem"}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>

          <FormGroup title="Security targets" hint="Maximum adversary success per axis. Leave empty for no target.">
            <div className="grid grid-cols-2 gap-3">
              {AXES.map((a) => (
                <Field key={a.key} id={`t-${a.key}`} label={`${a.label} ${a.symbol}`} error={errors[`target.${a.key}`]}>
                  <Input
                    id={`t-${a.key}`}
                    inputMode="decimal"
                    className="tnum font-mono"
                    placeholder="none"
                    value={form.targets[a.key]}
                    aria-invalid={!!errors[`target.${a.key}`]}
                    onChange={(e) => update({ targets: { ...form.targets, [a.key]: e.target.value } })}
                  />
                </Field>
              ))}
            </div>
          </FormGroup>

          <FormGroup title="Honest-error tolerance">
            <Field
              id="tol"
              label="Fraction of errors honest verification tolerates"
              error={errors.honestError}
              hint={
                entry?.sizing_available
                  ? "Ideal theorems verify exactly: any value > 0 leaves the model (game W2 / S2)."
                  : form.game === "S2"
                    ? "Used as γ_err when γ_err is not set below."
                    : "Not used by this game's theorem; its own thresholds are parameters."
              }
            >
              <Input id="tol" inputMode="decimal" className="tnum font-mono" placeholder="0" value={form.honestError} onChange={(e) => update({ honestError: e.target.value })} />
            </Field>
          </FormGroup>

          <FormGroup title="Channel and theorem parameters" hint="A point value, or an interval [lo, hi] that is propagated to its worst endpoint.">
            <div className="grid gap-3">
              {names.map((k) => {
                const f = form.params[k] ?? emptyField();
                const desc = entry?.theorem?.parameters[k];
                const err = errors[`param.${k}`];
                const set = (pf: typeof f) => update({ params: { ...form.params, [k]: pf } });
                const canInterval = !INTEGER_PARAMS.has(k);
                return (
                  <div key={k} className="grid gap-1.5">
                    <div className="flex items-baseline justify-between gap-2">
                      <label htmlFor={`p-${k}`} className="font-mono text-xs text-foreground" title={desc}>
                        {k}
                      </label>
                      {canInterval ? (
                        <button
                          type="button"
                          aria-pressed={f.mode === "interval"}
                          onClick={() => set({ ...f, mode: f.mode === "point" ? "interval" : "point", lo: f.lo || f.value, hi: f.hi || f.value })}
                          className="font-mono text-[0.6875rem] text-subtle hover:text-foreground aria-pressed:text-foreground"
                        >
                          {f.mode === "interval" ? "interval ✓" : "point · use interval"}
                        </button>
                      ) : null}
                    </div>
                    {f.mode === "point" ? (
                      <Input id={`p-${k}`} inputMode="decimal" className="tnum font-mono" value={f.value} aria-invalid={!!err} aria-describedby={desc ? `p-${k}-d` : undefined} onChange={(e) => set({ ...f, value: e.target.value })} />
                    ) : (
                      <div className="grid grid-cols-2 gap-2">
                        <Input id={`p-${k}`} aria-label={`${k} lower`} inputMode="decimal" className="tnum font-mono" placeholder="lo" value={f.lo} aria-invalid={!!err} onChange={(e) => set({ ...f, lo: e.target.value })} />
                        <Input aria-label={`${k} upper`} inputMode="decimal" className="tnum font-mono" placeholder="hi" value={f.hi} aria-invalid={!!err} onChange={(e) => set({ ...f, hi: e.target.value })} />
                      </div>
                    )}
                    {err ? (
                      <p role="alert" className="text-xs text-danger">
                        {err}
                      </p>
                    ) : desc ? (
                      <p id={`p-${k}-d`} className="text-xs text-subtle">
                        {desc}
                      </p>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </FormGroup>

          {decl.length ? (
            <FormGroup title={`Declared hypotheses (${form.declared.filter((x) => decl.some((d) => d.name === x)).length}/${decl.length})`} hint="Hypotheses that numbers cannot verify. Undeclared ones leave the bound unavailable.">
              <div className="flex gap-3 text-xs">
                <button type="button" className="text-muted underline-offset-4 hover:text-foreground hover:underline" onClick={() => update({ declared: decl.map((d) => d.name) })}>
                  Declare all
                </button>
                <button type="button" className="text-muted underline-offset-4 hover:text-foreground hover:underline" onClick={() => update({ declared: [] })}>
                  Clear
                </button>
              </div>
              <ul className="grid gap-2.5">
                {decl.map((d) => {
                  const on = form.declared.includes(d.name);
                  return (
                    <li key={d.name}>
                      <label className="grid cursor-pointer grid-cols-[1rem_minmax(0,1fr)] gap-2.5">
                        <input
                          type="checkbox"
                          checked={on}
                          onChange={() => update({ declared: on ? form.declared.filter((x) => x !== d.name) : [...form.declared, d.name] })}
                          className="mt-0.5 size-3.5 accent-[var(--accent)]"
                        />
                        <span className="grid gap-0.5">
                          <span className="font-mono text-[0.6875rem] text-foreground">{d.name}</span>
                          {d.description !== d.name.replace(/_/g, " ") ? <span className="text-xs text-subtle">{d.description}</span> : null}
                        </span>
                      </label>
                    </li>
                  );
                })}
              </ul>
            </FormGroup>
          ) : null}

          {entry?.theorem && !entry.sizing_available ? (
            <FormGroup title="Noise source">
              <Select value={form.noiseSource || "unset"} onValueChange={(v) => update({ noiseSource: v === "unset" ? "" : (v as NoiseSource) })}>
                <SelectTrigger aria-label="Noise source">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="unset">Not declared</SelectItem>
                  {catalog.noise_sources.map((n) => (
                    <SelectItem key={n} value={n}>
                      {NOISE_LABEL[n as NoiseSource] ?? n}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormGroup>
          ) : null}

          <FormGroup title="Calibration source" hint={entry?.theorem?.calibration_families.length ? `This theorem accepts: ${entry.theorem.calibration_families.join(", ")}` : undefined}>
            <div role="radiogroup" aria-label="Calibration source" className="grid gap-2">
              {catalog.calibrations.map((c) => {
                const pv = calibrationPreview(entry, c.experiment_family);
                return (
                  <label key={c.source} className="grid cursor-pointer grid-cols-[1rem_minmax(0,1fr)] gap-2.5">
                    <input
                      type="radio"
                      name="calibration"
                      checked={form.calibration === c.source}
                      onChange={() => update({ calibration: c.source as CalibrationSource })}
                      className="mt-0.5 size-3.5 accent-[var(--accent)]"
                    />
                    <span className="grid gap-0.5">
                      <span className="text-xs text-foreground">{c.label}</span>
                      {c.experiment_family ? (
                        <span className={cn("font-mono text-[0.6875rem]", pv === "match" ? "text-subtle" : "text-warn")}>
                          family {c.experiment_family} ·{" "}
                          {pv === "match" ? "matches this theorem" : pv === "ideal" ? "ideal theorem: measured noise is out of model" : "different family: will be rejected"}
                        </span>
                      ) : null}
                    </span>
                  </label>
                );
              })}
            </div>
          </FormGroup>

          <div className="sticky bottom-0 z-sticky -mx-4 flex items-center gap-3 border-t border-border bg-background/95 px-4 py-3 lg:static lg:mx-0 lg:bg-transparent lg:px-0">
            <Button type="submit" variant="accent" size="lg" disabled={run.status === "loading"} className="flex-1 lg:flex-none">
              <Play aria-hidden /> Evaluate and check
            </Button>
            <span className="hidden text-xs text-subtle sm:inline">
              <Kbd>⌘</Kbd> <Kbd>↵</Kbd>
            </span>
          </div>
        </form>

        <div aria-busy={run.status === "loading"} aria-live="polite" className="grid min-w-0 gap-10">
          {run.status === "loading" ? (
            <p className="flex items-center gap-2 text-xs text-muted">
              <PixelLoader label="Evaluating" /> Evaluating with qmint.proofs and running the independent checker…
            </p>
          ) : stale ? (
            <p className="border-l-2 border-warn/60 pl-3 text-xs text-muted">Inputs changed since this result. Evaluate again to update the certificate.</p>
          ) : null}
          {run.status === "error" && run.error ? (
            <ErrorState
              timeout={run.error.kind === "timeout"}
              title={run.error.kind === "validation" ? "The proof engine rejected these inputs" : "Evaluation failed"}
              description={run.error.message}
              detail={run.error.detail ? JSON.stringify(run.error.detail).slice(0, 400) : run.error.kind}
            />
          ) : null}
          {run.data ? (
            <div className={cn("grid gap-10 transition-opacity duration-[var(--duration-base)]", run.status === "loading" && "opacity-50")}>
              <VerdictPanel d={run.data} />
              <div className="border-t border-border pt-8">
                <AxesTable d={run.data} />
              </div>
              <div className="grid gap-10 border-t border-border pt-8 xl:grid-cols-2">
                <TheoremPanel d={run.data} />
                <AssumptionsPanel d={run.data} />
              </div>
              <div className="border-t border-border pt-8">
                <ResourcesPanel d={run.data} />
              </div>
              {run.data.calibration.source !== "none" ? (
                <div className="border-t border-border pt-8">
                  <CalibrationPanel d={run.data} />
                </div>
              ) : null}
              <div className="border-t border-border pt-8">
                <ExportPanel d={run.data} />
              </div>
            </div>
          ) : run.status === "loading" || run.status === "idle" ? (
            <div className="grid gap-4" aria-hidden>
              <Skeleton className="h-6 w-40" />
              <Skeleton className="h-9 w-3/4" />
              <Skeleton className="h-40 w-full" />
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
