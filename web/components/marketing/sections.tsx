import { ArrowRight, ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { EvidenceLabel } from "@/components/ui/evidence-label";
import type { GetResponse } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import {
  DATASETS,
  LANE_C_LEAK_CONTROL,
  REFERENCES,
  REPO_URL,
  SDP_W1,
  ZENODO_QBER,
} from "./research-values";
import { prettyFormula } from "./hero/instrument-model";
import { Section } from "./section";
import { STATE_BASIS, STATE_KET, StateGlyph, type Bb84Label } from "./state-glyph";

export type GameInfo = GetResponse<"/api/v1/games">["data"][number];
export type MetaData = GetResponse<"/api/v1/meta">["data"];

/* ------------------------------------------------------------------------------------------ */
/* 01 — The problem                                                                             */
/* ------------------------------------------------------------------------------------------ */

const TRUST = [
  { code: "H1", name: "Online ledger", cost: "Every payment waits for a coordinator round trip, and the coordinator sees where you pay." },
  { code: "H5", name: "Secure hardware", cost: "Spending twice is blocked only while the tamper-resistance assumption holds." },
  { code: "H6", name: "Offline e-cash", cost: "Both merchants accept. The double spender is identified later, at deposit." },
] as const;

export function ProblemSection() {
  return (
    <Section
      id="problem"
      index="01"
      kicker="The problem"
      title="Copying is free. Spending twice is the attack."
      lead="Digital value is a string of bits, and bits copy perfectly. Classical payment systems don't stop the copy. They make the second spend fail, and the way they do that decides whom you have to trust."
    >
      <div className="grid gap-px overflow-hidden border border-border bg-border md:grid-cols-2">
        <figure className="grid content-between gap-10 bg-background p-6 md:p-10">
          <CopyFigure />
          <figcaption className="grid gap-2">
            <p className="label-mono text-subtle">Copy</p>
            <p className="max-w-[44ch] text-muted">
              Duplicating a token is undetectable: both copies are identical down to the last bit. Nothing about the data
              says which one is the original.
            </p>
          </figcaption>
        </figure>
        <figure className="grid content-between gap-10 bg-background p-6 md:p-10">
          <SpendFigure />
          <figcaption className="grid gap-2">
            <p className="label-mono text-subtle">Double spend</p>
            <p className="max-w-[44ch] text-muted">
              The same value is presented at two places at once. If the sites are far enough apart, no signal can reach one
              from the other in time, so something must already have been arranged.
            </p>
          </figcaption>
        </figure>
      </div>

      <div className="mt-16 grid gap-6 md:grid-cols-12 md:gap-8">
        <p className="label-mono text-subtle md:col-span-3">Where classical systems put the trust</p>
        <ol className="md:col-span-9">
          {TRUST.map((t) => (
            <li key={t.code} className="grid gap-1 border-t border-border py-5 sm:grid-cols-[4rem_12rem_1fr] sm:gap-6">
              <span className="font-mono text-xs text-subtle">{t.code}</span>
              <span className="text-foreground">{t.name}</span>
              <span className="text-muted">{t.cost}</span>
            </li>
          ))}
          <li className="border-t border-border pt-5 text-xs text-subtle">
            Classical comparators from lane H (<span className="font-mono">qmint/classical</span>). Section 04 matches them
            against S-money.
          </li>
        </ol>
      </div>
    </Section>
  );
}

function CopyFigure() {
  const bits = "10110010";
  return (
    <svg viewBox="0 0 320 120" className="h-auto w-full max-w-[360px]" aria-hidden>
      <g className="font-mono text-[13px]">
        {bits.split("").map((b, i) => (
          <text key={i} x={18 + i * 15} y={64} className="fill-foreground">
            {b}
          </text>
        ))}
        <path d="M140 60 C170 60 170 30 196 30M140 60 C170 60 170 90 196 90" fill="none" stroke="var(--border-strong)" />
        {[30, 90].map((y) =>
          bits.split("").map((b, i) => (
            <text key={`${y}-${i}`} x={204 + i * 13.5} y={y + 4} className="fill-muted">
              {b}
            </text>
          )),
        )}
      </g>
      <text x={204} y={116} className="fill-subtle font-mono text-[9px] tracking-[0.06em] uppercase">
        identical
      </text>
    </svg>
  );
}

function SpendFigure() {
  return (
    <svg viewBox="0 0 320 120" className="h-auto w-full max-w-[360px]" aria-hidden>
      <rect x={146} y={8} width={28} height={16} fill="none" stroke="var(--foreground)" />
      <text x={160} y={20} textAnchor="middle" className="fill-foreground font-mono text-[9px]">
        $
      </text>
      <path d="M160 24 L56 92M160 24 L264 92" stroke="var(--border-strong)" fill="none" />
      <path d="M56 104 L264 104" stroke="var(--border-strong)" strokeDasharray="2 4" />
      {[56, 264].map((x, i) => (
        <g key={x}>
          <rect x={x - 22} y={92} width={44} height={24} fill="var(--background)" stroke="var(--border-strong)" />
          <text x={x} y={108} textAnchor="middle" className="fill-muted font-mono text-[10px]">
            {i === 0 ? "site A" : "site B"}
          </text>
        </g>
      ))}
      <text x={160} y={100} textAnchor="middle" className="fill-subtle font-mono text-[8.5px] tracking-[0.06em] uppercase">
        no time to ask
      </text>
    </svg>
  );
}

/* ------------------------------------------------------------------------------------------ */
/* 02 — The quantum primitive                                                                   */
/* ------------------------------------------------------------------------------------------ */

const STATES: Bb84Label[] = ["0", "1", "+", "-"];

export function PrimitiveSection({ w1 }: { w1: GameInfo | null }) {
  const limits = [
    {
      t: "Imperfect copies still pass sometimes.",
      d: (
        <>
          The best counterfeiting channel passes both checks with probability 3/4 per qubit. Security is the exponent,{" "}
          <span className="font-mono text-foreground">{prettyFormula(w1?.formula ?? "(3/4)^n")}</span>, which reaches 10⁻⁹ only at n = 73.
        </>
      ),
      label: { kind: "PUBLISHED_THEOREM", group: "evidence_kind" as const },
    },
    {
      t: "The secret is the security.",
      d: (
        <>
          If the bank&apos;s bases and bits leak, a forger prepares two genuine notes and passes both checks with
          probability <span className="tnum font-mono text-foreground">{LANE_C_LEAK_CONTROL.value}</span>. QMint
          runs this as a control.
        </>
      ),
      label: { kind: "OUT_OF_MODEL", group: "certificate_status" as const },
    },
    {
      t: "Real channels lose and flip photons.",
      d: "A verifier that tolerates errors and loss plays a different game (W2), with no closed-form bound here. Against a toy verifier that allows half the qubits to be lost, an attack that splits the note and reports losses wins every time.",
      label: { kind: "MONTE_CARLO", group: "evidence_kind" as const },
    },
    {
      t: "A simulator copies freely.",
      d: "A simulated state vector is classical data. Nothing on this site demonstrates physical no-cloning; it computes what the model predicts.",
      label: { kind: "SIMULATOR_IDEAL", group: "evidence_kind" as const },
    },
  ];

  return (
    <Section
      id="primitive"
      index="02"
      kicker="The quantum primitive"
      title="A note made of states nobody can read without disturbing them."
      lead="In Wiesner's scheme the bank prepares each qubit in one of four states and keeps the choice secret. To verify, it measures each qubit in the basis it chose. An unknown quantum state cannot be copied exactly, and a measurement in the wrong basis randomises the answer."
    >
      <div className="grid gap-12 lg:grid-cols-12 lg:gap-8">
        <figure className="lg:col-span-5">
          <div className="grid grid-cols-4 border-y border-border">
            {STATES.map((s, i) => (
              <div key={s} className={cn("grid justify-items-center gap-3 py-8", i > 0 && "border-l border-border")}>
                <StateGlyph state={s} size={44} />
                <span className="font-mono text-sm text-foreground">{STATE_KET[s]}</span>
                <span className="label-mono text-subtle">basis {STATE_BASIS[s]}</span>
              </div>
            ))}
          </div>
          <figcaption className="mt-4 max-w-[46ch] text-xs leading-relaxed text-subtle">
            The four BB84 states, drawn as polarisation axes. States in the same basis are orthogonal; across bases they
            overlap with probability 1/2. That overlap is what a counterfeiter cannot avoid.
          </figcaption>
        </figure>

        <div className="lg:col-span-7 lg:pl-8">
          <p className="label-mono mb-6 text-subtle">What no-cloning alone does not give you</p>
          <ol className="grid gap-px overflow-hidden border border-border bg-border sm:grid-cols-2">
            {limits.map((l, i) => (
              <li key={l.t} className="grid content-start gap-3 bg-background p-6">
                <span className="font-mono text-xs text-subtle">{String.fromCharCode(97 + i)}.</span>
                <p className="text-h4 text-foreground">{l.t}</p>
                <p className="text-sm text-muted">{l.d}</p>
                <EvidenceLabel kind={l.label.kind} group={l.label.group} size="xs" />
              </li>
            ))}
          </ol>
          <p className="mt-4 text-xs text-subtle">
            Sources: MVW 2012 (arXiv:1202.4010); lane D <span className="font-mono">qmint/proofs/ideal_bounds.py</span> (n_min);
            lane C <span className="font-mono">handoffs/C-C1-evidence.json</span> (ctrl_secret_leak, a06_toy_w2).
          </p>
        </div>
      </div>
    </Section>
  );
}

/* ------------------------------------------------------------------------------------------ */
/* 03 — The interactive laboratory                                                              */
/* ------------------------------------------------------------------------------------------ */

const TOOLS = [
  {
    href: "/lab/mint",
    verb: "Issue",
    title: "Mint a note",
    body: "Prepare up to eight BB84 qubits from a seed. Inspect the circuit, its exact outcome distribution, Aer shot counts and the noise you declare.",
    api: "POST /api/v1/lab/mint",
    kinds: ["SIMULATOR_IDEAL", "SIMULATOR_NOISY"],
  },
  {
    href: "/lab/attack",
    verb: "Attack",
    title: "Counterfeit it",
    body: "Run measure–resend, cloners and the MVW optimal channel. Exact model values, sampled estimates with intervals, and the theorem they cannot beat.",
    api: "POST /api/v1/lab/attack",
    kinds: ["PUBLISHED_THEOREM", "SIMULATOR_IDEAL"],
  },
  {
    href: "/certificates",
    verb: "Certify",
    title: "Ask for a guarantee",
    body: "State a security target and an error tolerance. See which theorem applies, whether your parameters meet its assumptions, and an explicit UNCERTIFIED when nothing does.",
    api: "POST /api/v1/certificates",
    kinds: ["UNCERTIFIED"],
  },
  {
    href: "/benchmarks",
    verb: "Compare",
    title: "Benchmark against classical",
    body: "Latency of S-money against ledger, quorum, escrow and signature designs on the same networks, with comparability stated row by row.",
    api: "GET /api/v1/benchmarks",
    kinds: ["MODELLED_LATENCY", "MEASURED_LATENCY"],
  },
] as const;

export function LabSection() {
  return (
    <Section
      id="lab"
      index="03"
      kicker="The interactive laboratory"
      title="Four instruments, one evidence trail."
      lead="Every result in the lab comes from the research API with its evidence kind, method, seed and git revision attached. You can reproduce any number from the command line."
    >
      <ul className="border-b border-border">
        {TOOLS.map((t) => (
          <li key={t.href} className="border-t border-border">
            <Link
              href={t.href}
              className="group grid gap-3 py-7 transition-colors duration-[var(--duration-fast)] md:grid-cols-12 md:items-baseline md:gap-8 md:py-9"
            >
              <span className="label-mono text-subtle md:col-span-2">{t.verb}</span>
              <span className="text-h2 text-foreground md:col-span-4">{t.title}</span>
              <span className="grid gap-3 md:col-span-5">
                <span className="text-muted">{t.body}</span>
                <span className="flex flex-wrap items-center gap-x-4 gap-y-1">
                  <span className="font-mono text-xs text-subtle">{t.api}</span>
                  {t.kinds.map((k) => (
                    <EvidenceLabel key={k} kind={k} size="xs" showTooltip={false} />
                  ))}
                </span>
              </span>
              <span className="hidden justify-self-end text-subtle transition-[color,transform] duration-[var(--duration-fast)] group-hover:translate-x-0.5 group-hover:text-foreground md:col-span-1 md:block">
                <ArrowRight className="size-5" aria-hidden />
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Section>
  );
}

/* ------------------------------------------------------------------------------------------ */
/* 04 — Quantum vs classical                                                                    */
/* ------------------------------------------------------------------------------------------ */

const MATCHED = [
  { need: "Late site choice, online infrastructure acceptable", best: "H1 ledger (H2 if replicated)", gives: "Validation waits a coordinator round trip; coordinator learns the site; unavailable under partition." },
  { need: "Instant local acceptance, site known at issuance", best: "H3 preassigned, or H4 + H3 signed binding", gives: "Late-choice flexibility; the issuer learns the site at issuance." },
  { need: "Late choice, local acceptance, issuer must not learn the site", best: "H3 late-commit escrow with oblivious transfer", gives: "Security becomes computational. The OT is an ideal functionality, not implemented." },
  { need: "No Stage-II message at all", best: "H5 secure hardware", gives: "Requires tamper resistance; if it fails, the double spend succeeds (tested, out of model)." },
  { need: "Offline, payer privacy", best: "H6 Chaum–Fiat–Naor e-cash", gives: "Detection, not prevention: both merchants accept, the spender is identified at deposit." },
] as const;

export function ClassicalSection({ s1 }: { s1: GameInfo | null }) {
  return (
    <Section
      id="classical"
      index="04"
      kicker="Quantum vs classical"
      title="Under matched assumptions, the difference is the adversary model, not speed."
    >
      <div className="grid gap-12 lg:grid-cols-12 lg:gap-8">
        <div className="grid content-start gap-6 lg:col-span-4">
          <blockquote className="border-l-2 border-foreground pl-5">
            <p className="text-body-lg text-foreground">
              S-money is not coordination-free. Before presentation, the bit c = b ⊕ z must be relayed to both sites. A
              classical late-commit escrow with private commitment has the same causal structure and the same latency.
            </p>
          </blockquote>
          <p className="text-muted">
            What remains is what each side assumes. The ideal S-money bound{" "}
            <span className="font-mono text-foreground">{prettyFormula(s1?.formula ?? "(1/2 + 1/(2*sqrt(2)))^N")}</span> is information-theoretic.
            The classical constructions that match it rely on hardness assumptions or trusted setup. A claim that quantum
            tokens are faster needs a scenario where those assumptions are ruled out.
          </p>
          <div className="grid gap-2 text-xs text-subtle">
            <EvidenceLabel kind="PUBLISHED_THEOREM" size="xs" />
            <span>
              Kent et al. 2022, Table I steps 7–9 and Lemma 1 (arXiv:2104.11717v4). Lane H{" "}
              <span className="font-mono">reports/classical_baseline_notes/README.md</span>.
            </span>
          </div>
        </div>

        <div className="min-w-0 lg:col-span-8">
          <div className="hidden grid-cols-[1fr_1fr_1.3fr] gap-6 border-b border-border pb-3 md:grid">
            <span className="label-mono text-subtle">Requirement</span>
            <span className="label-mono text-subtle">Strongest classical design</span>
            <span className="label-mono text-subtle">What it gives up vs ideal S-money</span>
          </div>
          <ul>
            {MATCHED.map((m) => (
              <li key={m.need} className="grid gap-2 border-b border-hairline py-5 md:grid-cols-[1fr_1fr_1.3fr] md:gap-6">
                <span className="text-sm text-muted">{m.need}</span>
                <span className="text-sm text-foreground">{m.best}</span>
                <span className="text-sm text-muted">{m.gives}</span>
              </li>
            ))}
          </ul>
          <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-subtle">
            <EvidenceLabel kind="MODELLED_LATENCY" size="xs" />
            <span>Lower bounds on synthetic light-cone networks, not measurements.</span>
            <span className="tnum font-mono">7 qualified · 4 incomparable · 0 directly comparable</span>
          </div>
        </div>
      </div>
    </Section>
  );
}

/* ------------------------------------------------------------------------------------------ */
/* 05 — Proof, not hype                                                                         */
/* ------------------------------------------------------------------------------------------ */

export function ProofSection({ w1 }: { w1: GameInfo | null }) {
  return (
    <Section
      id="proof"
      index="05"
      kicker="Proof, not hype"
      title="Three kinds of evidence, never blended."
      lead="A theorem bounds every adversary. A numerical result is only as good as its certificate. A measurement describes one apparatus. QMint labels each number with which one it is."
    >
      <div className="grid border-y border-border lg:grid-cols-3">
        {/* theorem */}
        <article className="grid content-start gap-6 border-b border-border py-10 lg:border-r lg:border-b-0 lg:pr-8">
          <EvidenceLabel kind="PUBLISHED_THEOREM" />
          <p className="font-mono text-[2.75rem] leading-none tracking-tight text-foreground">
            {w1?.formula ? prettyFormula(w1.formula) : "(3/4)ⁿ"}
          </p>
          <p className="text-muted">
            Upper bound on the probability that any counterfeiter turns one Wiesner note into two that both pass
            {w1 ? "" : " (API offline: transcribed value)"}.
          </p>
          <Source>
            {w1?.source ?? "Molina, Vidick & Watrous 2012, arXiv:1202.4010"} · game {w1?.game_id ?? "W1"} ·{" "}
            <span className="font-mono">GET /api/v1/games</span>
          </Source>
        </article>

        {/* numerical */}
        <article className="grid content-start gap-6 border-b border-border py-10 lg:border-r lg:border-b-0 lg:px-8">
          <EvidenceLabel kind={SDP_W1.evidence} />
          <div className="grid gap-2 font-mono">
            <p className="tnum text-[1.375rem] leading-tight tracking-tight text-foreground">
              {SDP_W1.n1.lower} ≤ OPT₁ ≤ {SDP_W1.n1.upper}
            </p>
            <p className="tnum text-sm text-muted">
              {SDP_W1.n2.lower} ≤ OPT₂ ≤ {SDP_W1.n2.upper}
            </p>
          </div>
          <p className="text-muted">
            QMint solved the counterfeiting SDP over every quantum channel, then certified the dual with exact rational
            arithmetic. An independent checker re-verified it. The bracket around 0.75 is the certificate, not a rounding.
          </p>
          <Source>
            Lane C <span className="font-mono">{SDP_W1.artefact}</span> · lane D re-verification{" "}
            <span className="font-mono">qmint/proofs/sdp_exact.py</span>
          </Source>
        </article>

        {/* measured */}
        <article className="grid content-start gap-6 py-10 lg:pl-8">
          <EvidenceLabel kind={ZENODO_QBER.evidence} />
          <table className="w-full text-left">
            <caption className="sr-only">Quantum bit error rate, this work vs the published paper</caption>
            <thead>
              <tr className="label-mono text-subtle">
                <th scope="col" className="pb-2 font-medium">QBER</th>
                <th scope="col" className="pb-2 text-right font-medium">Reproduced</th>
                <th scope="col" className="pb-2 text-right font-medium">Paper</th>
              </tr>
            </thead>
            <tbody className="tnum font-mono">
              {ZENODO_QBER.rows.map((r) => (
                <tr key={r.basis} className="border-t border-hairline">
                  <th scope="row" className="py-2.5 text-sm font-normal text-muted">{r.basis}</th>
                  <td className="py-2.5 text-right text-[1.375rem] leading-none tracking-tight text-foreground">
                    {r.ours.toFixed(4)}
                    <span className="text-sm text-subtle">%</span>
                    <span className="mt-1 block text-[0.6875rem] text-subtle">± {r.oursSe.toFixed(4)}</span>
                  </td>
                  <td className="py-2.5 text-right align-top text-sm text-muted">
                    {r.paper.toFixed(2)}%<span className="mt-1 block text-[0.6875rem] text-subtle">± {r.paperPm.toFixed(2)}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-muted">
            Error rates recomputed from {ZENODO_QBER.pairs.toLocaleString("en-US")} raw photon coincidence pairs over{" "}
            {ZENODO_QBER.runs} runs, using the paper&apos;s own estimator. Loss and multiphoton probability can&apos;t be
            observed from the archive, so no security claim follows from this.
          </p>
          <Source>
            Schiansky et al. 2023, Nat. Commun. 14, 3849 · data{" "}
            <a className="underline decoration-border-strong underline-offset-2 hover:text-foreground" href={DATASETS[0].href}>
              doi:{DATASETS[0].doi}
            </a>{" "}
            · lane E <span className="font-mono">reports/data_working/schiansky2023</span>
          </Source>
        </article>
      </div>
      <p className="mt-6 max-w-[72ch] text-sm text-subtle">
        A fourth kind sits underneath: Monte Carlo. A sampled attack success is a lower bound on what the worst attacker
        achieves, so QMint always reports it with its interval and never as a ceiling.
      </p>
    </Section>
  );
}

function Source({ children }: { children: React.ReactNode }) {
  return <p className="border-t border-hairline pt-4 text-xs leading-relaxed text-subtle">{children}</p>;
}

/* ------------------------------------------------------------------------------------------ */
/* 06 — Open research                                                                           */
/* ------------------------------------------------------------------------------------------ */

const REPRODUCE = [
  { cmd: "python -m qmint.attacks.report --out handoffs/C-C1-evidence.json", what: "W1 SDP, certified duals, attack lower bounds (lane C, ~110 s)" },
  { cmd: "python -m qmint.proofs.reproduce", what: "Theorem bounds and paper reproductions, independently checked (lane D)" },
  { cmd: "python -m qmint.photonics.schiansky2023", what: "QBER from the Zenodo archive (lane E; archive download required)" },
  { cmd: "python -m qmint.classical.run_baselines --pqc-reps 5", what: "Classical comparators H0–H6 and the comparability matrix (lane H)" },
] as const;

export function OpenSection({ meta }: { meta: MetaData | null }) {
  const lanes = meta?.lanes ?? null;
  const merged = lanes?.filter((l) => l.merged).length ?? null;
  return (
    <Section
      id="open"
      index="06"
      kicker="Open research"
      title="Everything is in the repository."
      lead="Protocols, attacks, proofs, datasets and this website are one open codebase. Every number above can be traced to a file, a seed and a commit."
    >
      <div className="grid gap-16 lg:grid-cols-12 lg:gap-8">
        <div className="grid content-start gap-8 lg:col-span-5">
          <a href={REPO_URL} className="group grid gap-2">
            <span className="label-mono text-subtle">Source · MIT License</span>
            <span className="inline-flex items-center gap-2 font-mono text-h3 break-all text-foreground group-hover:underline group-hover:decoration-border-strong group-hover:underline-offset-4">
              github.com/udsy19/qmint <ArrowUpRight className="size-5 shrink-0 text-subtle" aria-hidden />
            </span>
          </a>
          {lanes ? (
            <div className="grid gap-3">
              <p className="label-mono text-subtle">
                Research lanes merged <span className="tnum text-foreground">{merged}</span>
                <span className="tnum"> / {lanes.length}</span>
              </p>
              <ul className="flex flex-wrap gap-1" aria-label="Research lanes">
                {lanes.map((l) => (
                  <li
                    key={l.lane}
                    title={`${l.lane}: ${l.description}${l.merged ? "" : " (not merged)"}`}
                    className={cn(
                      "grid size-7 place-items-center border font-mono text-[0.6875rem]",
                      l.merged ? "border-border-strong text-foreground" : "border-dashed border-border text-subtle",
                    )}
                  >
                    {l.lane}
                    <span className="sr-only">
                      {" "}
                      {l.description}, {l.merged ? "merged" : "not merged"}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="text-xs text-subtle">
                Live from <span className="font-mono">GET /api/v1/meta</span>. Dashed lanes are in flight.
              </p>
            </div>
          ) : (
            <p className="text-sm text-muted">Lane status is unavailable while the research API is offline.</p>
          )}
          <div className="grid gap-3">
            <p className="label-mono text-subtle">Reproduce from the repository root</p>
            <ul className="grid border-t border-border">
              {REPRODUCE.map((r) => (
                <li key={r.cmd} className="grid gap-1 border-b border-hairline py-3">
                  <code className="font-mono text-xs break-all text-foreground">{r.cmd}</code>
                  <span className="text-xs text-subtle">{r.what}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="lg:col-span-7">
          <p className="label-mono mb-4 text-subtle">Primary sources</p>
          <ul className="border-t border-border">
            {REFERENCES.map((r) => (
              <li key={r.id} className="border-b border-border">
                <a href={r.href} className="group grid gap-1 py-5 sm:grid-cols-[3rem_1fr] sm:gap-4">
                  <span className="font-mono text-xs text-subtle">{r.id}</span>
                  <span className="grid gap-1">
                    <span className="text-foreground group-hover:underline group-hover:decoration-border-strong group-hover:underline-offset-4">
                      {r.title}
                    </span>
                    <span className="text-sm text-muted">
                      {r.cite} · <span className="font-mono text-xs">{r.doi ? `doi:${r.doi}` : r.href.replace("https://", "")}</span>
                    </span>
                    <span className="text-xs text-subtle">{r.role}</span>
                  </span>
                </a>
              </li>
            ))}
          </ul>
          <p className="label-mono mt-10 mb-4 text-subtle">Datasets</p>
          <ul className="border-t border-border">
            {DATASETS.map((d) => (
              <li key={d.id} className="border-b border-border">
                <a href={d.href} className="group grid gap-1 py-4 sm:grid-cols-[1fr_auto] sm:gap-4">
                  <span className="text-sm text-muted group-hover:text-foreground">{d.note}</span>
                  <span className="font-mono text-xs text-subtle">doi:{d.doi}</span>
                </a>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </Section>
  );
}

/* ------------------------------------------------------------------------------------------ */
/* Closing call to action                                                                       */
/* ------------------------------------------------------------------------------------------ */

export function ClosingSection({ disclaimer }: { disclaimer: string }) {
  return (
    <section aria-labelledby="closing-title" className="border-t border-border py-24 md:py-32">
      <div className="container-wide grid gap-12 md:grid-cols-12 md:gap-8">
        <div className="grid content-start gap-8 md:col-span-7">
          <h2 id="closing-title" className="max-w-[16ch] text-h1 md:text-display">
            Put a note under attack.
          </h2>
          <div className="flex flex-wrap gap-3">
            <Button asChild variant="accent" size="lg">
              <Link href="/app">
                Launch the Lab <ArrowRight />
              </Link>
            </Button>
            <Button asChild variant="secondary" size="lg">
              <Link href="/docs">Read the docs</Link>
            </Button>
          </div>
        </div>
        <aside aria-label="Disclaimer" className="grid content-end gap-3 md:col-span-5">
          <p className="label-mono text-warn">Research platform</p>
          <p className="text-sm text-muted">{disclaimer}</p>
        </aside>
      </div>
    </section>
  );
}
