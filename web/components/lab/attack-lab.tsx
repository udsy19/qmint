"use client";

import { Play } from "lucide-react";
import * as React from "react";
import { Button } from "@/components/ui/button";
import { Disclosure } from "@/components/ui/disclosure";
import { EvidenceLabel } from "@/components/ui/evidence-label";
import { Field } from "@/components/ui/input";
import { ReadoutGroup } from "@/components/ui/readout";
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { UnavailableState } from "@/components/ui/state";
import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";
import { ATTACK_GROUPS, attackVerdict, buildAttackRequest, DEFAULT_ATTACK_FORM, trialsCap, type AttackForm } from "./attack-form";
import { buildComparison } from "./comparison";
import { ComparisonChart } from "./comparison-chart";
import { ControlGroup, IntField, NoiseControls, SeedField, SliderField } from "./controls";
import { LIMITS, postAttack, type AttackRequest, type AttackResponse } from "./lab-api";
import { Frac, Ket, MathBlock, Sup, V } from "./math";
import { curlFor } from "./mint-form";
import { ProvenanceList } from "./provenance";
import { QuantityReadout, QuantitySource, ReadoutGrid } from "./quantity";
import { RunFailurePanel } from "./run-failure";
import { isActive, useLabRun } from "./run-state";
import { RunStatus } from "./run-status";
import { SectionHead } from "./section-head";

const APPLICABILITY: Record<AttackResponse["data"]["proof_applicability"], { kind: string; group: "certificate_status" | "evidence_kind"; text: string }> = {
  IN_MODEL: { kind: "PUBLISHED_THEOREM", group: "evidence_kind", text: "inside game W1 · the theorem applies" },
  NO_THEOREM: { kind: "UNCERTIFIED", group: "certificate_status", text: "game W2 toy verifier · no theorem" },
  OUT_OF_MODEL: { kind: "OUT_OF_MODEL", group: "certificate_status", text: "breaks a rule of game W1" },
};

export function AttackLab() {
  const [form, setForm] = React.useState<AttackForm>(DEFAULT_ATTACK_FORM);
  const { state, run, cancel } = useLabRun<AttackRequest, AttackResponse>(postAttack);
  const { request, errors } = buildAttackRequest(form);
  const set = <K extends keyof AttackForm>(k: K, v: AttackForm[K]) => setForm((f) => ({ ...f, [k]: v }));
  const submit = React.useCallback((r?: AttackRequest) => r && run(r), [run]);

  // Default experiment on mount (StrictMode re-issues it once; the stale run is ignored).
  React.useEffect(() => {
    submit(buildAttackRequest(DEFAULT_ATTACK_FORM).request);
  }, [submit]);

  const active = isActive(state.phase);
  const data = state.data;
  const cap = trialsCap(form.attack);

  return (
    <div className="grid gap-10 lg:grid-cols-[17.5rem_minmax(0,1fr)] lg:gap-12">
      <aside aria-label="Attack configuration" className="lg:sticky lg:top-[calc(var(--header-h)+1.5rem)] lg:self-start">
        <form
          className="grid gap-5"
          onSubmit={(e) => {
            e.preventDefault();
            submit(request);
          }}
        >
          <ControlGroup title="Attack">
            <Field id="attack-id" label="Strategy">
              <Select value={form.attack} onValueChange={(v) => set("attack", v as AttackForm["attack"])}>
                <SelectTrigger id="attack-id" aria-label="Strategy">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ATTACK_GROUPS.map((g) => (
                    <SelectGroup key={g.title}>
                      <SelectLabel>{g.title}</SelectLabel>
                      {g.items.map((it) => (
                        <SelectItem key={it.id} value={it.id}>
                          {it.label}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <SliderField
              id="attack-n"
              label="Qubits n"
              value={form.n}
              min={1}
              max={LIMITS.nMax}
              onChange={(v) => set("n", v)}
              hint={`n ≤ ${LIMITS.sdpNMax}: certified SDP bracket is computed live.`}
            />
            {form.attack === "A06_split_and_report_loss" ? (
              <>
                <SliderField id="attack-loss" label="Loss allowance" value={form.maxLoss} min={0} max={1} step={0.05} format={(v) => v.toFixed(2)} onChange={(v) => set("maxLoss", v)} hint="Fraction of positions the toy verifier lets you report as lost." />
                <SliderField id="attack-err" label="Error allowance" value={form.maxError} min={0} max={0.5} step={0.05} format={(v) => v.toFixed(2)} onChange={(v) => set("maxError", v)} hint="Fraction of reported positions allowed to be wrong." />
              </>
            ) : null}
            {form.attack === "A08_adaptive_oracle_probe" ? (
              <SliderField id="attack-probes" label="Z-probes per qubit" value={form.probes} min={1} max={16} onChange={(v) => set("probes", v)} hint="More probes: fewer mistakes, more oracle queries." />
            ) : null}
          </ControlGroup>
          <ControlGroup title="Honest holder">
            <NoiseControls idPrefix="attack" noise={form.noise} onChange={(n) => set("noise", n)} hint="Affects honest acceptance only; attacks face the ideal game." />
          </ControlGroup>
          <ControlGroup title="Monte Carlo">
            <IntField id="attack-trials" label="Trials (fresh notes)" text={form.trialsText} onText={(t) => set("trialsText", t)} error={errors.trials} hint={`0 – ${cap.toLocaleString("en-US")} · 0 = exact values only`} />
            <SeedField id="attack-seed" text={form.seedText} onText={(t) => set("seedText", t)} error={errors.seed} />
          </ControlGroup>
          <div className="grid gap-3 border-t border-border pt-4">
            <Button type="submit" variant="accent" size="lg" disabled={!request || active}>
              <Play aria-hidden /> {active ? "Running…" : "Run attack"}
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
        {!data && active ? <AttackSkeleton /> : null}
        {data ? (
          <div className={cn("grid gap-10 transition-opacity duration-[var(--duration-base)]", active && "opacity-50")}>
            <AttackResults res={data} req={state.dataRequest} />
          </div>
        ) : null}
      </div>
    </div>
  );
}

function AttackResults({ res, req }: { res: AttackResponse; req?: AttackRequest }) {
  const d = res.data;
  const n = req?.n ?? d.attack_result?.token_n ?? 1;
  const cs = Object.fromEntries(d.counterfeit_success.map((q) => [q.id, q]));
  const comparison = React.useMemo(() => buildComparison(d), [d]);
  const verdict = attackVerdict(d);
  const app = APPLICABILITY[d.proof_applicability];

  return (
    <>
      <section aria-labelledby="atk-summary" className="grid gap-5">
        <SectionHead id="atk-summary" index="01" title={d.attack_label} aside={<span className="label-mono text-subtle">game {d.game_id} · n = {n}</span>} />
        <div className="grid gap-3">
          <p className="max-w-prose text-body text-muted">{d.description}</p>
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-subtle">
            <EvidenceLabel kind={app.kind} group={app.group} /> {app.text}
          </p>
        </div>
        <ReadoutGroup>
          {cs.counterfeit_exact ? <QuantityReadout q={cs.counterfeit_exact} label="Counterfeit success · exact" size="lg" /> : null}
          {cs.counterfeit_mc ? <QuantityReadout q={cs.counterfeit_mc} label={`Monte Carlo · ${d.run.trials.toLocaleString("en-US")} notes`} /> : null}
          <QuantityReadout q={d.theorem_bound} label="Theorem bound" />
        </ReadoutGroup>
        <p
          role="status"
          className={cn(
            "max-w-prose border-l-2 py-1 pl-4 text-sm",
            verdict.tone === "danger" ? "border-danger text-foreground" : verdict.tone === "warn" ? "border-warn text-foreground" : "border-border-strong text-foreground",
          )}
        >
          {verdict.text}
        </p>
      </section>

      <section aria-labelledby="atk-compare" className="grid gap-5">
        <SectionHead id="atk-compare" index="02" title="Every number, side by side" aside={<span className="label-mono text-subtle">analytic · simulated · hardware</span>} />
        <ComparisonChart c={comparison} />
      </section>

      <section aria-labelledby="atk-sdp" className="grid gap-5">
        <SectionHead id="atk-sdp" index="03" title="Optimal attack, certified" aside={<span className="label-mono text-subtle">Choi-matrix SDP</span>} />
        {d.sdp && d.sdp.status === "OK" && d.sdp.lower && d.sdp.upper_certified && d.sdp.upper_independent && d.sdp.numerical ? (
          <>
            <p className="max-w-prose text-sm text-muted">
              Over <em>every</em> quantum channel that turns one {n}-qubit note into two, the best counterfeit probability lies in this
              bracket. The lower end is an explicit channel evaluated in exact fractions; the upper ends are dual certificates checked in
              exact rational arithmetic, once by the attack lane and once by an independent code path.
            </p>
            <ReadoutGrid>
              <QuantityReadout q={d.sdp.lower} label="Lower · achieved" showFormula={false} />
              <QuantityReadout q={d.sdp.upper_certified} label="Upper · certified" showFormula={false} />
              <QuantityReadout q={d.sdp.upper_independent} label="Upper · independent" showFormula={false} />
              <QuantityReadout q={d.sdp.numerical} label="Solver value" showFormula={false} />
            </ReadoutGrid>
            <p className="text-xs text-subtle">
              Recorded lane-C evidence: <span className="font-mono">{d.sdp.recorded_evidence}</span>. The SDP is recomputed live for n ≤ 2 and cached.
            </p>
          </>
        ) : d.sdp ? (
          <UnavailableState title="No SDP bracket at this size" description={d.sdp.reason ?? "Unsupported."} />
        ) : (
          <UnavailableState
            title="The W1 SDP does not describe this attack’s game"
            description={d.game_id === "W2" ? "The toy loss-tolerant verifier is game W2; no SDP certificate exists for it." : "This attack steps outside game W1, so the W1 optimum is not the right yardstick."}
          />
        )}
      </section>

      <section aria-label="Explanations and detail" className="grid">
        <Disclosure title="What is being tested, in plain words" defaultOpen>
          <div className="grid max-w-prose gap-2">
            <p>
              A counterfeiter receives one genuine note and tries to hand the bank two. Each qubit hides one of four states; measuring it in
              the wrong basis scrambles it, and quantum mechanics forbids copying an unknown state perfectly. The best any attacker can do
              per qubit is 3/4, so the chance of fooling the bank twice falls exponentially with the number of qubits.
            </p>
            <p>
              Analytic values are exact for the stated model. Simulated values are Monte Carlo runs over fresh secret notes, with 95%
              intervals: they estimate one attack’s success and are therefore lower bounds on the best attacker, never upper bounds. No quantum
              hardware was used.
            </p>
          </div>
        </Disclosure>
        <Disclosure title="The math" meta="MVW 2012">
          <div className="grid max-w-prose gap-2">
            <p>
              A counterfeiting attack is a channel Φ from one qubit register to two. With the secret state ρ<sub>s</sub> drawn uniformly
              from <Ket>0</Ket>, <Ket>1</Ket>, <Ket>+</Ket>, <Ket>−</Ket>, the success probability is linear in Φ’s Choi matrix <V>J</V>:
            </p>
            <MathBlock label="P equals the trace of G n times J, with G n the average over s of rho s transpose tensor rho s tensor rho s">
              P(Φ) = Tr(<V>G</V>
              <sub>n</sub> <V>J</V>), &nbsp; <V>G</V>
              <sub>n</sub> = <Frac n="1" d={<>4<Sup><V>n</V></Sup></>} /> Σ<sub>s</sub> ρ<sub>s</sub>
              <Sup>T</Sup> ⊗ ρ<sub>s</sub> ⊗ ρ<sub>s</sub>
            </MathBlock>
            <p>
              Maximising over <V>J</V> ⪰ 0 with Tr<sub>out</sub> <V>J</V> = 1 is a semidefinite program. Any <V>Y</V> with <V>Y</V> ⊗ 1 ⪰{" "}
              <V>G</V>
              <sub>n</sub> certifies P ≤ Tr <V>Y</V> (weak duality); <V>Y</V> = (3/8)<Sup><V>n</V></Sup>·1 gives the theorem:
            </p>
            <MathBlock label="P forge at most three quarters to the n">
              P<sub>forge</sub> ≤ (<Frac n="3" d="4" />)<Sup><V>n</V></Sup> = {formatNumber(0.75 ** n, { sig: 6 })} &nbsp; (n = {n})
            </MathBlock>
            <p>
              Measure-and-resend reaches only 5/8 per qubit (1/2 · 1 + 1/2 · 1/4): a wrong basis guess passes each copy with probability
              1/2. The phase-covariant cloner reaches (3 + 2√2)/8 ≈ 0.7286; the MVW channel reaches 3/4 exactly.
            </p>
          </div>
        </Disclosure>
        <Disclosure title="Assumptions and notes" meta={`${d.assumptions.length + d.notes.length}`}>
          <ul className="grid list-disc gap-1 pl-4">
            {[...d.assumptions, ...d.notes, d.simulator_caveat].map((a) => (
              <li key={a}>{a}</li>
            ))}
            <li>
              Capabilities: <span className="font-mono text-xs">{d.capabilities.join(", ")}</span>
            </li>
          </ul>
        </Disclosure>
        <Disclosure title="Sources of every number" meta={`${comparison.groups.reduce((a, g) => a + g.rows.length, 0)} values`}>
          <div className="grid gap-3">
            {[...d.honest_acceptance, d.single_copy_pass, ...d.counterfeit_success, d.theorem_bound, d.hardware].map((q) => (
              <QuantitySource key={q.id} q={q} />
            ))}
          </div>
        </Disclosure>
        <Disclosure title="Run metadata and provenance" meta={`seed ${d.run.seed}`}>
          <ProvenanceList provenance={res.provenance} run={d.run} evidenceKind={res.evidence_kind} reproduce={curlFor("/api/v1/lab/attack", req ?? {})} />
        </Disclosure>
        {d.attack_result ? (
          <Disclosure title="Attack record (contract C3)" meta="AttackResult">
            <pre className="overflow-x-auto rounded-sm bg-surface p-3 font-mono text-xs text-muted">{JSON.stringify(d.attack_result, null, 2)}</pre>
          </Disclosure>
        ) : null}
      </section>
    </>
  );
}

function AttackSkeleton() {
  return (
    <div className="grid gap-8" aria-hidden>
      <Skeleton className="h-6 w-72 max-w-full" />
      <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-16" />
        ))}
      </div>
      <Skeleton className="h-72" />
    </div>
  );
}
