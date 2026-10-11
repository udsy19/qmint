"use client";

import { EyeOff, Play, ShieldAlert } from "lucide-react";
import * as React from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogBody, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Disclosure } from "@/components/ui/disclosure";
import { EvidenceLabel } from "@/components/ui/evidence-label";
import { Field } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";
import { CircuitDiagram } from "./circuit-diagram";
import { ControlGroup, IntField, NoiseControls, SeedField, SliderField } from "./controls";
import { ErrorHistogram } from "./error-histogram";
import { LIMITS, postMint, type MintRequest, type MintResponse } from "./lab-api";
import { Frac, Ket, MathBlock, Sup, V } from "./math";
import { buildMintRequest, curlFor, DEFAULT_MINT_FORM, type MintForm } from "./mint-form";
import { ProvenanceList } from "./provenance";
import { QuantityReadout, QuantitySource, ReadoutGrid } from "./quantity";
import { RunFailurePanel } from "./run-failure";
import { isActive, useLabRun } from "./run-state";
import { RunStatus } from "./run-status";
import { SectionHead } from "./section-head";
import { TokenStrip } from "./token-strip";
import { VerificationFlow } from "./verification-flow";

export function MintLab() {
  const [form, setForm] = React.useState<MintForm>(DEFAULT_MINT_FORM);
  const [teaching, setTeaching] = React.useState(false);
  const [confirmOpen, setConfirmOpen] = React.useState(false);
  const { state, run, cancel } = useLabRun<MintRequest, MintResponse>(postMint);
  const { request, errors } = buildMintRequest(form, teaching);
  const set = <K extends keyof MintForm>(k: K, v: MintForm[K]) => setForm((f) => ({ ...f, [k]: v }));

  const submit = React.useCallback((r?: MintRequest) => r && run(r), [run]);
  // Run the default experiment on mount. (Under StrictMode the first request is aborted by the
  // simulated unmount and immediately re-issued; the stale run id is ignored.)
  React.useEffect(() => {
    submit(buildMintRequest(DEFAULT_MINT_FORM, false).request);
  }, [submit]);

  const setTeachingAndRun = (on: boolean) => {
    setTeaching(on);
    submit(buildMintRequest(form, on).request);
  };

  const active = isActive(state.phase);
  const data = state.data;
  const noisy = form.protocol === "wiesner_noisy";

  return (
    <div className="grid gap-10 lg:grid-cols-[17.5rem_minmax(0,1fr)] lg:gap-12">
      <aside aria-label="Experiment configuration" className="lg:sticky lg:top-[calc(var(--header-h)+1.5rem)] lg:self-start">
        <form
          className="grid gap-5"
          onSubmit={(e) => {
            e.preventDefault();
            submit(request);
          }}
        >
          <ControlGroup title="Protocol">
            <Field id="mint-protocol" label="Scheme">
              <Select value={form.protocol} onValueChange={(v) => set("protocol", v as MintForm["protocol"])}>
                <SelectTrigger id="mint-protocol" aria-label="Scheme">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="wiesner_ideal">Wiesner · exact verifier (W1)</SelectItem>
                  <SelectItem value="wiesner_noisy">Wiesner · error threshold (W2)</SelectItem>
                </SelectContent>
              </Select>
            </Field>
            <SliderField id="mint-n" label="Qubits n" value={form.n} min={1} max={LIMITS.nMax} onChange={(v) => set("n", v)} hint={`Dense simulation cap: n ≤ ${LIMITS.nMax}.`} />
            {noisy ? (
              <SliderField
                id="mint-threshold"
                label="Threshold t"
                value={Math.min(form.threshold, Math.max(1, form.n - 1))}
                min={1}
                max={Math.max(1, form.n - 1)}
                disabled={form.n < 2}
                onChange={(v) => set("threshold", v)}
                hint={errors.threshold ?? "Accept if at most t positions are wrong."}
              />
            ) : null}
          </ControlGroup>
          <ControlGroup title="Channel">
            <NoiseControls idPrefix="mint" noise={form.noise} onChange={(n) => set("noise", n)} />
          </ControlGroup>
          <ControlGroup title="Sampling">
            <SeedField id="mint-seed" text={form.seedText} onText={(t) => set("seedText", t)} error={errors.seed} />
            <Field id="mint-backend" label="Backend">
              <Select value={form.backend} onValueChange={(v) => set("backend", v as MintForm["backend"])}>
                <SelectTrigger id="mint-backend" aria-label="Backend">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="aer">Exact + Aer simulator shots</SelectItem>
                  <SelectItem value="exact">Exact only</SelectItem>
                </SelectContent>
              </Select>
            </Field>
            {form.backend === "aer" ? (
              <IntField id="mint-shots" label="Shots" text={form.shotsText} onText={(t) => set("shotsText", t)} error={errors.shots} hint={`1 – ${LIMITS.shotsMax.toLocaleString("en-US")}`} />
            ) : null}
            <IntField id="mint-trials" label="Fresh-note trials" text={form.trialsText} onText={(t) => set("trialsText", t)} error={errors.trials} hint={`0 – ${LIMITS.trialsMax.toLocaleString("en-US")} · honest Monte Carlo`} />
          </ControlGroup>
          <div className="grid gap-3 border-t border-border pt-4">
            <Button type="submit" variant="accent" size="lg" disabled={!request || active}>
              <Play aria-hidden /> {active ? "Running…" : "Mint and verify"}
            </Button>
            <RunStatus phase={state.phase} startedAt={state.startedAt} finishedAt={state.finishedAt} serverMs={data?.data.run.elapsed_ms} onCancel={cancel} />
          </div>
        </form>
      </aside>

      <div className="grid min-w-0 content-start gap-10" aria-busy={active}>
        {(state.phase === "error" || state.phase === "timeout" || state.phase === "cancelled") && (
          <div className="grid gap-1">
            <RunFailurePanel phase={state.phase} failure={state.failure} onRetry={() => submit(request)} />
            {data ? <p className="label-mono text-subtle">Below: the last completed run, unchanged</p> : null}
          </div>
        )}
        {!data && active ? <ResultsSkeleton /> : null}
        {data ? (
          <div className={cn("grid gap-10 transition-opacity duration-[var(--duration-base)]", active && "opacity-50")}>
            <MintResults
              res={data}
              req={state.dataRequest}
              onReveal={() => setConfirmOpen(true)}
              onHide={() => setTeachingAndRun(false)}
              busy={active}
            />
          </div>
        ) : null}
      </div>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reveal the bank’s secret?</DialogTitle>
            <DialogDescription>Teaching mode only. This re-runs the same seed and asks the bank’s TEST-ONLY leak control for this note’s bases and bits.</DialogDescription>
          </DialogHeader>
          <DialogBody className="grid gap-2 text-sm text-muted">
            <p>A real bank never discloses them. Anyone holding them can print perfect copies, so every security statement on this page stops applying to this note.</p>
            <p>
              <EvidenceLabel kind="OUT_OF_MODEL" group="certificate_status" /> is how the result will be labelled.
            </p>
          </DialogBody>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="ghost">Keep hidden</Button>
            </DialogClose>
            <Button
              variant="danger"
              onClick={() => {
                setConfirmOpen(false);
                setTeachingAndRun(true);
              }}
            >
              <ShieldAlert aria-hidden /> Reveal secret
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}


function MintResults({ res, req, onReveal, onHide, busy }: { res: MintResponse; req?: MintRequest; onReveal: () => void; onHide: () => void; busy: boolean }) {
  const d = res.data;
  const t = d.teaching;
  const acc = Object.fromEntries(d.statistics.acceptance.map((q) => [q.id, q]));
  const serial = String(d.token.public_metadata?.serial ?? d.token.token_id);
  const verify = d.flow.find((s) => s.id === "verify");

  return (
    <>
      {t ? (
        <div role="alert" className="flex flex-wrap items-start gap-3 border-l-2 border-danger bg-danger-muted px-4 py-3">
          <ShieldAlert className="mt-0.5 size-4 text-danger" aria-hidden />
          <div className="grid min-w-0 flex-1 gap-1">
            <p className="flex flex-wrap items-center gap-2 text-sm text-foreground">
              Teaching mode: the secret of this note is shown
              <EvidenceLabel kind="OUT_OF_MODEL" group="certificate_status" />
            </p>
            <p className="text-xs text-muted">{t.warning}</p>
          </div>
          <Button variant="secondary" size="sm" onClick={onHide} disabled={busy}>
            <EyeOff aria-hidden /> Hide secret
          </Button>
        </div>
      ) : null}

      <section aria-labelledby="mint-token" className="grid gap-5">
        <SectionHead
          id="mint-token"
          index="01"
          title="Token"
          aside={
            t ? null : (
              <Button variant="ghost" size="sm" onClick={onReveal} disabled={busy}>
                Reveal secret (teaching mode)…
              </Button>
            )
          }
        />
        <TokenStrip serial={serial} n={d.token.n_prepared} qubits={t?.qubits} freshness={`minted ${d.token.state_kind.replace(/_/g, " ")}`} />
        <p className="max-w-prose text-sm text-muted">
          The holder gets a serial number and {d.token.n_prepared} qubits. Each qubit is one of four states, <Ket>0</Ket> <Ket>1</Ket>{" "}
          <Ket>+</Ket> <Ket>−</Ket>, and only the bank knows which. {t ? "Teaching mode shows them as arrows on the x–z circle of the Bloch sphere." : "Here they stay hidden, exactly as for a real holder."}
        </p>
      </section>

      <section aria-labelledby="mint-accept" className="grid gap-5">
        <SectionHead
          id="mint-accept"
          index="02"
          title="Honest acceptance"
          aside={
            verify ? (
              <span className="label-mono text-subtle">
                this verification: <span className={verify.result === "accepted" ? "text-foreground" : "text-danger"}>{verify.result}</span>
              </span>
            ) : null
          }
        />
        <ReadoutGrid>
          {acc.honest_accept_note_exact ? <QuantityReadout q={acc.honest_accept_note_exact} label="This note · exact" size="lg" /> : null}
          {acc.honest_accept_mean ? <QuantityReadout q={acc.honest_accept_mean} label="Any note · closed form" showFormula={false} /> : null}
          {acc.honest_accept_note_aer ? <QuantityReadout q={acc.honest_accept_note_aer} label={`This note · ${d.statistics.shots?.toLocaleString("en-US")} shots`} /> : null}
          {acc.honest_accept_mc ? <QuantityReadout q={acc.honest_accept_mc} label={`Fresh notes · ${d.run.trials.toLocaleString("en-US")} trials`} /> : null}
        </ReadoutGrid>
        <div className="grid gap-2 border-t border-hairline pt-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
          <QuantityReadout q={d.theorem} label={d.protocol.game_id === "W1" ? "Best possible counterfeiter (W1)" : "Counterfeiting bound (W2)"} size="sm" showNote />
          <QuantityReadout q={d.hardware} label="Quantum hardware" size="sm" missing="not run" />
        </div>
      </section>

      <div className="grid gap-10 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <section aria-labelledby="mint-circuit" className="grid content-start gap-5">
          <SectionHead id="mint-circuit" index="03" title="Preparation circuit" aside={<span className="label-mono text-subtle">{t ? "teaching view" : "gates redacted"}</span>} />
          <CircuitDiagram circuit={t ? t.circuit : d.circuit} />
          <p className="text-xs text-subtle">
            {t
              ? "X sets bit 1; H rotates into the X basis. The bank undoes H before measuring in Z."
              : "Hatched boxes hide the gates: an H gate would reveal that qubit’s basis."}{" "}
            {d.circuit.noise_description ? "ℰ is the declared noise channel. " : ""}
            {d.circuit.bit_order_note}.
          </p>
        </section>
        <section aria-labelledby="mint-flow" className="grid content-start gap-5">
          <SectionHead id="mint-flow" index="04" title="Verification flow" />
          <VerificationFlow steps={d.flow} />
        </section>
      </div>

      <section aria-labelledby="mint-stats" className="grid gap-5">
        <SectionHead
          id="mint-stats"
          index="05"
          title="Measurement statistics"
          aside={<span className="label-mono text-subtle">accept if wrong ≤ {d.statistics.threshold}</span>}
        />
        <ErrorHistogram rows={d.statistics.error_counts} shots={d.statistics.shots ?? null} threshold={d.statistics.threshold} />
        <p className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-subtle">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-4 rounded-[1px] bg-foreground/55" aria-hidden /> exact probability (accepted)
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-4 rounded-[1px] bg-border-strong" aria-hidden /> exact probability (rejected)
          </span>
          {d.statistics.shots ? (
            <span className="inline-flex items-center gap-1.5">
              <span className="h-3 w-0.5 bg-info" aria-hidden /> Aer frequency
            </span>
          ) : null}
          <span>{d.statistics.error_counts_note}</span>
        </p>
      </section>

      <section aria-label="Explanations and detail" className="grid">
        <Disclosure title="What is going on, in plain words" defaultOpen>
          <div className="grid max-w-prose gap-2">
            <p>
              The bank prepares each qubit in a state only it knows. To check a note, it measures every qubit the way it was
              prepared: a genuine, undisturbed note always gives the expected answers. Noise on the way (the channel you picked)
              flips some answers, which is why a threshold verifier tolerates a few wrong positions.
            </p>
            <p>
              Measuring destroys the note, so the bank verifies once, marks the serial spent, refuses the same serial again,
              and issues a fresh note. Statistics below the first verification are the bank re-preparing the same note in
              simulation — a holder can never do that.
            </p>
          </div>
        </Disclosure>
        <Disclosure title="The math" meta="closed forms">
          <div className="grid max-w-prose gap-2">
            <p>
              Each position is wrong with probability <V>e</V>
              <sub>i</sub>, set by the channel and that qubit’s state. The number of wrong positions <V>K</V> is a sum of
              independent Bernoulli variables, and the bank accepts when <V>K</V> ≤ <V>t</V>:
            </p>
            <MathBlock label="P accept equals the sum over k from 0 to t of P K equals k">
              P<sub>acc</sub> = Σ<sub>k ≤ t</sub> P[<V>K</V> = <V>k</V>], &nbsp; <V>K</V> = Σ<sub>i</sub> Bernoulli(<V>e</V>
              <sub>i</sub>)
            </MathBlock>
            <p>
              Depolarizing noise of strength <V>p</V> gives <V>e</V> = <Frac n={<V>p</V>} d="2" /> for every state; dephasing
              hits only X-basis states (<V>e</V> = <V>p</V>); amplitude damping <V>γ</V> leaves <Ket>0</Ket> alone, flips{" "}
              <Ket>1</Ket> with probability <V>γ</V>, and gives <Frac n={<>1 − √(1−<V>γ</V>)</>} d="2" /> on <Ket>±</Ket>.
            </p>
            <p>
              For game W1 (exact verifier, one note in, two out) Molina, Vidick and Watrous proved that no counterfeiter
              succeeds with probability above
            </p>
            <MathBlock label="three quarters to the power n">
              P<sub>forge</sub> ≤ (<Frac n="3" d="4" />)<Sup>
                <V>n</V>
              </Sup>
              {" "}= {formatNumber(0.75 ** d.token.n_prepared, { sig: 4 })} for <V>n</V> = {d.token.n_prepared}
            </MathBlock>
            <p>That theorem does not cover a threshold verifier (W2): no published closed form exists there.</p>
          </div>
        </Disclosure>
        <Disclosure title="Protocol and assumptions" meta={d.protocol.security_model_id}>
          <ul className="grid list-disc gap-1 pl-4">
            <li>{d.protocol.verifier_rule}</li>
            {d.protocol.proof_assumptions.map((a) => (
              <li key={a} className="font-mono text-xs">
                {a}
              </li>
            ))}
            {d.protocol.unsupported_extensions.map((a) => (
              <li key={a}>Not covered: {a}</li>
            ))}
            <li>{d.simulator_caveat}</li>
          </ul>
        </Disclosure>
        <Disclosure title="Sources of every number" meta={`${d.statistics.acceptance.length + 2} values`}>
          <div className="grid gap-3">
            {[...d.statistics.acceptance, d.theorem, d.hardware].map((q) => (
              <QuantitySource key={q.id} q={q} />
            ))}
          </div>
        </Disclosure>
        <Disclosure title="Run metadata and provenance" meta={`seed ${d.run.seed}`}>
          <ProvenanceList provenance={res.provenance} run={d.run} evidenceKind={res.evidence_kind} reproduce={curlFor("/api/v1/lab/mint", req ?? {})} />
        </Disclosure>
        <Disclosure title="Public token record" meta="TokenRecord">
          <pre className="overflow-x-auto rounded-sm bg-surface p-3 font-mono text-xs text-muted">{JSON.stringify(d.token, null, 2)}</pre>
        </Disclosure>
        {t ? (
          <Disclosure title="Teaching data: outcomes, QASM, resources" meta="TEST-ONLY">
            <div className="grid gap-4">
              <p>
                Expected outcome <span className="font-mono text-foreground">{t.expected_outcome}</span>. Most likely outcomes
                (exact{t.outcome_distribution_truncated ? ", top 32" : ""}):
              </p>
              <ul className="grid gap-1 font-mono text-xs sm:grid-cols-2">
                {t.outcome_distribution.map((o) => (
                  <li key={o.outcome} className="flex justify-between gap-4 border-b border-hairline py-1">
                    <span className={o.outcome === t.expected_outcome ? "text-foreground" : "text-muted"}>{o.outcome}</span>
                    <span className="tnum">{formatNumber(o.probability, { sig: 4 })}</span>
                  </li>
                ))}
              </ul>
              <p className="font-mono text-xs break-all text-subtle">circuit sha256 {t.circuit_sha256}</p>
              {t.qasm2 ? <pre className="overflow-x-auto rounded-sm bg-surface p-3 font-mono text-xs text-muted">{t.qasm2}</pre> : null}
              <pre className="overflow-x-auto rounded-sm bg-surface p-3 font-mono text-xs text-muted">{JSON.stringify(t.resources, null, 2)}</pre>
            </div>
          </Disclosure>
        ) : null}
      </section>
    </>
  );
}

function ResultsSkeleton() {
  return (
    <div className="grid gap-8" aria-hidden>
      <div className="grid gap-4">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-8 w-80 max-w-full" />
        <div className="flex gap-2">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="size-12" />
          ))}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-16" />
        ))}
      </div>
      <Skeleton className="h-48" />
    </div>
  );
}
