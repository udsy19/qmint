"use client";

import { Check, Copy, Download, ExternalLink, Minus, X } from "lucide-react";
import * as React from "react";
import { ChartFrame, LineBandChart, SERIES, formatLog10Bound, middleTruncate } from "@/components/charts";
import { Button } from "@/components/ui/button";
import { Disclosure } from "@/components/ui/disclosure";
import { EvidenceLabel } from "@/components/ui/evidence-label";
import { Readout } from "@/components/ui/readout";
import { UnavailableState } from "@/components/ui/state";
import { Table, TBody, THead, Td, Th, Tr } from "@/components/ui/table";
import { toast } from "@/components/ui/toast";
import { NO_BOUND } from "@/lib/format";
import { cn } from "@/lib/utils";
import { AXES, type CertData } from "./form-model";

type Verdict = CertData["classification"]["verdict"];

const VERDICT: Record<Verdict, { bar: string; title: string }> = {
  CERTIFIED: { bar: "before:bg-accent", title: "text-accent" },
  UNCERTIFIED: { bar: "before:bg-warn", title: "text-foreground" },
  INFEASIBLE: { bar: "before:bg-warn", title: "text-foreground" },
  OUT_OF_MODEL: { bar: "before:bg-danger", title: "text-danger" },
};

export function PanelTitle({ eyebrow, title, aside }: { eyebrow: string; title: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-1">
      <div className="grid gap-1">
        <p className="label-mono text-subtle">{eyebrow}</p>
        <h3 className="text-h4 text-foreground">{title}</h3>
      </div>
      {aside}
    </div>
  );
}

export function VerdictPanel({ d }: { d: CertData }) {
  const v = d.classification.verdict;
  const st = VERDICT[v];
  return (
    <section
      aria-labelledby="verdict-h"
      className={cn("relative grid gap-4 py-1 pl-5 before:absolute before:inset-y-0 before:left-0 before:w-0.5", st.bar)}
    >
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <EvidenceLabel kind={v} group="certificate_status" />
        <span className="font-mono text-xs text-subtle">
          {d.game} · {d.protocol_id}
        </span>
      </div>
      <h2 id="verdict-h" className={cn("text-h3", st.title)}>
        {d.classification.headline}
      </h2>
      <dl className="grid gap-x-8 gap-y-2 text-xs sm:grid-cols-[auto_minmax(0,1fr)]">
        <dt className="label-mono text-subtle">Independent checker</dt>
        <dd className="flex flex-wrap items-center gap-2 text-muted">
          <EvidenceLabel kind={d.checker.status} group="certificate_status" size="xs" />
          <span className="font-mono">{d.checker.checker_id ?? "—"}</span>
          <span className="text-subtle">only this status can be CERTIFIED</span>
        </dd>
        {v !== "CERTIFIED" ? (
          <>
            <dt className="label-mono text-subtle">Studio classification</dt>
            <dd className="text-subtle">{d.classification.derived_from}</dd>
          </>
        ) : null}
      </dl>
      {d.classification.reasons.length ? (
        <ul className="grid gap-1.5 text-[0.8125rem] text-muted">
          {d.classification.reasons.slice(0, 6).map((r) => (
            <li key={r} className="flex gap-2">
              <span aria-hidden className="text-subtle">
                —
              </span>
              <span className="min-w-0 break-words">{r}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function TargetMark({ meets, applicable, target }: { meets: boolean | null | undefined; applicable: boolean; target: number | null | undefined }) {
  if (target == null) return <span className="text-xs text-subtle">no target</span>;
  if (!applicable) return <span className="text-xs text-warn">cannot be checked</span>;
  return meets ? (
    <span className="inline-flex items-center gap-1 text-xs text-foreground">
      <Check className="size-3.5" aria-hidden /> ≤ target
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-xs text-danger">
      <X className="size-3.5" aria-hidden /> exceeds target
    </span>
  );
}

type Step = CertData["axes"][number]["uncertainty"][number];
const sig = (v: number) => Number(v.toPrecision(4));

export function AxesTable({ d }: { d: CertData }) {
  const anchors = new Map(d.theorem?.axes.map((a) => [a.axis, a]) ?? []);
  const byParam = new Map<string, { axis: string; step: Step }[]>();
  for (const a of d.axes) for (const u of a.uncertainty) byParam.set(u.parameter, [...(byParam.get(u.parameter) ?? []), { axis: a.label, step: u }]);
  const uncertainty = [...byParam.entries()];
  return (
    <section aria-labelledby="axes-h" className="grid gap-4">
      <PanelTitle eyebrow="Bound per axis" title={<span id="axes-h">Upper bounds on adversary success</span>} />
      <ul className="grid gap-0 sm:hidden">
        {d.axes.map((a) => {
          const bound = formatLog10Bound(a.result.log10_value);
          const failedA = a.result.failed_assumptions ?? [];
          return (
            <li key={a.axis} className="grid gap-1.5 border-b border-hairline py-3">
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-[0.8125rem] text-foreground">
                  {a.label} <span className="font-mono text-[0.6875rem] text-subtle">{AXES.find((x) => x.key === a.axis)?.symbol}</span>
                </span>
                <span className="tnum font-mono text-[0.8125rem]">{bound ?? <span className="font-sans text-xs text-muted italic">{NO_BOUND}</span>}</span>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <EvidenceLabel kind={a.result.evidence_kind} size="xs" />
                <span className="flex items-center gap-2 text-xs text-subtle">
                  {a.target != null ? <span className="tnum font-mono">target {a.target.toExponential(0).replace("e-", "e−")}</span> : null}
                  <TargetMark meets={a.meets_target} applicable={a.applicable} target={a.target} />
                </span>
              </div>
              <p className="line-clamp-2 text-xs break-words text-subtle">{failedA.length ? failedA.join("; ") : a.result.notes}</p>
            </li>
          );
        })}
      </ul>
      <Table className="hidden min-w-[720px] sm:table">
        <THead>
          <Tr className="hover:bg-transparent">
            <Th>Axis</Th>
            <Th numeric>Target</Th>
            <Th numeric>Bound</Th>
            <Th>Evidence</Th>
            <Th>Theorem</Th>
            <Th>Target check</Th>
          </Tr>
        </THead>
        <TBody>
          {d.axes.map((a) => {
            const bound = formatLog10Bound(a.result.log10_value);
            const anchor = anchors.get(a.axis);
            const failedA = a.result.failed_assumptions ?? [];
            const note = failedA.length ? failedA.join("; ") : a.result.notes;
            return (
              <Tr key={a.axis} className="align-top">
                <Td className="h-auto py-3">
                  <span className="grid gap-0.5">
                    <span className="text-[0.8125rem]">{a.label}</span>
                    <span className="font-mono text-[0.6875rem] text-subtle">{AXES.find((x) => x.key === a.axis)?.symbol}</span>
                  </span>
                </Td>
                <Td numeric className="h-auto py-3">
                  {a.target != null ? a.target.toExponential(0).replace("e-", "e−") : <span className="text-subtle">—</span>}
                </Td>
                <Td numeric className="h-auto py-3">
                  {bound ? (
                    <span title={`log10 = ${a.result.log10_value}`}>{bound}</span>
                  ) : (
                    <span className="font-sans text-xs text-muted italic">{NO_BOUND}</span>
                  )}
                </Td>
                <Td className="h-auto py-3">
                  <EvidenceLabel kind={a.result.evidence_kind} size="xs" />
                </Td>
                <Td className="h-auto max-w-72 py-3">
                  <span className="grid gap-1">
                    <span className="font-mono text-[0.6875rem] text-muted">{a.result.theorem_id ?? anchor?.bound_id ?? "—"}</span>
                    <span className="line-clamp-3 text-xs break-words text-subtle" title={note}>
                      {note}
                    </span>
                  </span>
                </Td>
                <Td className="h-auto py-3">
                  <TargetMark meets={a.meets_target} applicable={a.applicable} target={a.target} />
                </Td>
              </Tr>
            );
          })}
        </TBody>
      </Table>
      {uncertainty.length ? (
        <div className="grid gap-2">
          <p className="label-mono text-subtle">Uncertainty propagation</p>
          <ul className="grid gap-2 text-xs text-muted">
            {uncertainty.map(([param, u]) => (
              <li key={param} className="grid gap-x-4 gap-y-0.5 sm:grid-cols-[12rem_minmax(0,1fr)]">
                <span className="tnum font-mono text-foreground">
                  {param} ∈ [{sig(u[0]!.step.lo)}, {sig(u[0]!.step.hi)}]
                </span>
                <span className="grid gap-0.5">
                  {u.map(({ axis, step }) => (
                    <span key={axis} className={cn(step.direction === "undocumented" && "text-warn")}>
                      <span className="text-subtle">{axis}:</span> {step.endpoint_used}
                    </span>
                  ))}
                </span>
              </li>
            ))}
          </ul>
          <p className="text-xs text-subtle">
            A measured interval is moved into the bound at its worst endpoint (documented monotonicity); the theorem&apos;s domain must hold on every corner. A confidence
            interval is not a statement about the adversary.
          </p>
        </div>
      ) : null}
    </section>
  );
}

export function TheoremPanel({ d }: { d: CertData }) {
  const t = d.theorem;
  if (!t) {
    return (
      <section aria-label="Theorem" className="grid gap-3">
        <PanelTitle eyebrow="Which theorem applies" title="No applicable theorem" />
        <p className="text-sm text-muted">{d.no_theorem_reason}</p>
      </section>
    );
  }
  return (
    <section aria-label="Theorem" className="grid gap-4">
      <PanelTitle
        eyebrow="Which theorem applies"
        title={
          <span>
            <span className="font-mono">{t.claim_id}</span> · {(t.axes.find((a) => a.axis === "epsilon_unf") ?? t.axes[0])?.anchor.split(";")[0]}
          </span>
        }
        aside={<EvidenceLabel kind={t.status === "NUMERICALLY_SUPPORTED" ? "PUBLISHED_AGGREGATE" : "PUBLISHED_THEOREM"} />}
      />
      <p className="max-w-prose text-sm text-muted">{t.statement}</p>
      <dl className="grid gap-x-8 gap-y-3 text-xs sm:grid-cols-2">
        <div className="grid gap-1">
          <dt className="label-mono text-subtle">Quantifier over adversaries</dt>
          <dd className="text-muted">{t.quantifier}</dd>
        </div>
        <div className="grid gap-1">
          <dt className="label-mono text-subtle">Finite size</dt>
          <dd className="text-muted">{t.finite_or_asymptotic}</dd>
        </div>
        <div className="grid gap-1">
          <dt className="label-mono text-subtle">Status in registry</dt>
          <dd className="font-mono text-muted">{t.status}</dd>
        </div>
        {t.citation ? (
          <div className="grid gap-1">
            <dt className="label-mono text-subtle">Source</dt>
            <dd className="text-muted">
              {t.citation}{" "}
              {t.url ? (
                <a href={t.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 text-foreground underline decoration-border-strong underline-offset-4 hover:decoration-foreground">
                  open <ExternalLink className="size-3" aria-hidden />
                </a>
              ) : null}
            </dd>
          </div>
        ) : null}
      </dl>
      <Disclosure title="Bounds, anchors and domains" meta={`${t.axes.length} axes`}>
        <ul className="grid gap-3">
          {t.axes.map((a) => (
            <li key={a.bound_id} className="grid gap-0.5">
              <span className="font-mono text-xs text-foreground">
                {a.bound_id} · {a.formula}
              </span>
              <span className="text-xs">{a.anchor}</span>
              <span className="text-xs text-subtle">domain: {a.domain}</span>
            </li>
          ))}
        </ul>
      </Disclosure>
      <Disclosure title="Caveats" meta={`${t.caveats.length}`}>
        <ul className="grid gap-2">
          {t.caveats.map((c) => (
            <li key={c} className="text-xs">
              {c}
            </li>
          ))}
        </ul>
      </Disclosure>
    </section>
  );
}

export function AssumptionsPanel({ d }: { d: CertData }) {
  const failed = [...new Set(d.axes.flatMap((a) => a.result.failed_assumptions ?? []))];
  const checked = [...new Set(d.axes.flatMap((a) => a.result.assumptions_checked ?? []))];
  return (
    <section aria-labelledby="assume-h" className="grid gap-4">
      <PanelTitle eyebrow="Assumption check per predicate" title={<span id="assume-h">Hypotheses</span>} />
      {d.declarations.length ? (
        <ul className="grid gap-2">
          {d.declarations.map((x) => (
            <li key={x.name} className="grid grid-cols-[1rem_minmax(0,1fr)] gap-2 text-xs">
              {x.declared ? <Check className="mt-0.5 size-3.5 text-foreground" aria-label="declared" /> : <X className="mt-0.5 size-3.5 text-warn" aria-label="not declared" />}
              <span className="grid gap-0.5">
                <span className="font-mono text-[0.6875rem] text-muted">{x.name}</span>
                {x.description !== x.name.replace(/_/g, " ") ? <span className="text-subtle">{x.description}</span> : null}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-subtle">No declarable hypotheses: this game has no registered theorem.</p>
      )}
      {checked.length || failed.length ? (
        <div className="grid gap-1.5 text-xs">
          <p className="label-mono text-subtle">Machine-checked predicates</p>
          {checked.map((c) => (
            <p key={c} className="flex gap-2 text-muted">
              <Check className="mt-0.5 size-3.5 shrink-0" aria-label="passed" />
              <span className="font-mono break-all">{c}</span>
            </p>
          ))}
          {failed.map((c) => (
            <p key={c} className="flex gap-2 text-danger">
              <X className="mt-0.5 size-3.5 shrink-0" aria-label="failed" />
              <span className="font-mono break-all">{c}</span>
            </p>
          ))}
        </div>
      ) : null}
      <p className="flex gap-2 text-xs text-subtle">
        <Minus className="mt-0.5 size-3.5 shrink-0" aria-hidden /> Physical hypotheses (no side channels, equal detectors, Fock mixtures) cannot be verified from numbers: they are declared, and recorded as declared.
      </p>
    </section>
  );
}

export function ResourcesPanel({ d }: { d: CertData }) {
  const s = d.sizing;
  const curve = s.curve ?? [];
  const q = Object.fromEntries(s.quantities.map((x) => [x.id, x]));
  const nMin = q.n_min?.value ?? null;
  const target = d.axes.find((a) => a.axis === "epsilon_unf")?.target;
  return (
    <section aria-labelledby="res-h" className="grid gap-5">
      <PanelTitle eyebrow="Resource estimate" title={<span id="res-h">{s.label}</span>} aside={s.status === "OK" ? <EvidenceLabel kind="PUBLISHED_THEOREM" /> : null} />
      {s.status === "OK" ? (
        <>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-3">
            {s.quantities.map((x) => (
              <Readout key={x.id} size="sm" label={x.label} value={x.value} emphasis={x.id === "n_min"}>
                {x.note && x.id === "requested_size" ? <span className="text-xs text-subtle">{x.note}</span> : null}
              </Readout>
            ))}
          </dl>
          {curve.length > 1 ? (
            <ChartFrame
              title="Ideal bound vs token size"
              summary={`log10 of the ${d.game} ideal bound falls linearly with size; the target line crosses it at n = ${nMin}.`}
              legend={[
                { label: "log₁₀ bound (theorem)", color: SERIES.quantum, shape: "line" },
                { label: "target", color: SERIES.bound, shape: "dash" },
              ]}
              caption={q.n_min?.note ?? undefined}
              height={240}
              table={
                <Table>
                  <THead>
                    <Tr>
                      <Th numeric>n</Th>
                      <Th numeric>log₁₀ bound</Th>
                    </Tr>
                  </THead>
                  <TBody>
                    {curve.map((p) => (
                      <Tr key={p.n}>
                        <Td numeric>{p.n}</Td>
                        <Td numeric>{p.log10_bound.toFixed(4)}</Td>
                      </Tr>
                    ))}
                  </TBody>
                </Table>
              }
            >
              <LineBandChart
                data={curve.map((p) => ({ n: p.n, bound: p.log10_bound }))}
                x="n"
                xLabel="n"
                series={[{ key: "bound", label: "log₁₀ bound", color: SERIES.quantum }]}
                hlines={target ? [{ y: Math.log10(target), label: `target ${target.toExponential(0)}`, color: SERIES.bound }] : []}
                vlines={nMin ? [{ x: nMin, label: `n = ${nMin}`, color: SERIES.bound }] : []}
                formatY={(v) => v.toFixed(0)}
                height={240}
              />
            </ChartFrame>
          ) : null}
        </>
      ) : (
        <UnavailableState title="No theorem sizing for this game" description={s.reason} className="py-2" />
      )}
      <UnavailableState title="Resource optimisation · not available" description={d.optimization.reason} className="py-2" />
    </section>
  );
}

export function CalibrationPanel({ d }: { d: CertData }) {
  const c = d.calibration;
  if (c.source === "none") return null;
  return (
    <section aria-labelledby="cal-h" className="grid gap-3">
      <PanelTitle
        eyebrow="Calibration source"
        title={<span id="cal-h">{c.calibration_id}</span>}
        aside={c.data_origin ? <EvidenceLabel kind={c.data_origin} /> : null}
      />
      <p className={cn("text-sm", c.family_matches === false ? "text-danger" : "text-muted")}>{c.note}</p>
      <dl className="grid gap-x-8 gap-y-2 text-xs sm:grid-cols-2">
        <div className="grid gap-1">
          <dt className="label-mono text-subtle">Experiment family</dt>
          <dd className="font-mono text-muted">
            {c.experiment_family} → theorem accepts {c.accepted_families.length ? c.accepted_families.join(", ") : "no measured family"}
          </dd>
        </div>
        {Object.entries(c.intervals).map(([k, iv]) => (
          <div key={k} className="grid gap-1">
            <dt className="label-mono text-subtle">{k.replace("_interval", "").replace("_", " ")}</dt>
            <dd className="tnum font-mono text-muted">
              [{iv.lo}, {iv.hi}]
            </dd>
          </div>
        ))}
        {c.dataset_sha256 ? (
          <div className="grid gap-1">
            <dt className="label-mono text-subtle">Dataset sha256</dt>
            <dd className="font-mono text-muted" title={c.dataset_sha256}>
              {middleTruncate(c.dataset_sha256)}
            </dd>
          </div>
        ) : null}
      </dl>
    </section>
  );
}

export function ExportPanel({ d }: { d: CertData }) {
  const e = d.export;
  const pretty = React.useMemo(() => JSON.stringify(JSON.parse(e.canonical_json), null, 2), [e.canonical_json]);
  const download = () => {
    const url = URL.createObjectURL(new Blob([e.canonical_json], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = e.filename;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Certificate exported", { description: e.filename });
  };
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(e.canonical_json);
      toast.success("Canonical JSON copied");
    } catch {
      toast.error("Clipboard not available");
    }
  };
  return (
    <section aria-labelledby="export-h" className="grid gap-4">
      <PanelTitle
        eyebrow="Export"
        title={<span id="export-h">Certificate JSON</span>}
        aside={
          <div className="flex gap-2">
            <Button size="sm" variant="secondary" onClick={copy}>
              <Copy aria-hidden /> Copy
            </Button>
            <Button size="sm" variant="primary" onClick={download}>
              <Download aria-hidden /> Download
            </Button>
          </div>
        }
      />
      <dl className="grid gap-x-8 gap-y-2 text-xs sm:grid-cols-3">
        <div className="grid gap-1">
          <dt className="label-mono text-subtle">sha256 (canonical JSON)</dt>
          <dd className="font-mono text-muted" title={e.sha256}>
            {middleTruncate(e.sha256)}
          </dd>
        </div>
        <div className="grid gap-1">
          <dt className="label-mono text-subtle">OBLIGATIONS.yaml sha256</dt>
          <dd className="font-mono text-muted" title={e.obligations_sha256}>
            {middleTruncate(e.obligations_sha256)}
          </dd>
        </div>
        <div className="grid gap-1">
          <dt className="label-mono text-subtle">Status in file</dt>
          <dd>
            <EvidenceLabel kind={d.checked_certificate.proof_check_status} group="certificate_status" size="xs" />
          </dd>
        </div>
      </dl>
      <Disclosure title="Preview" meta={e.filename}>
        <pre className="max-h-80 overflow-auto rounded-sm border border-border bg-surface p-3 font-mono text-[0.6875rem] leading-relaxed text-muted">{pretty}</pre>
      </Disclosure>
      <p className="text-xs text-subtle">
        The file is the checker&apos;s output, unchanged: sorted keys, no whitespace, hashed as UTF-8. A bound in it is a transcribed theorem evaluated at your parameters;
        it is a proof only where the independent checker says CERTIFIED, and only inside the stated model.
      </p>
    </section>
  );
}
