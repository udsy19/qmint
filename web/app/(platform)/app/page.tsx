import { ArrowRight } from "lucide-react";
import type { Metadata } from "next";
import { connection } from "next/server";
import Link from "next/link";
import * as React from "react";
import { ApiFailure } from "@/components/shell/api-failure";
import { load } from "@/components/shell/load";
import { NAV_ITEMS } from "@/components/shell/nav";
import { StatusMark } from "@/components/shell/status-mark";
import { Disclosure } from "@/components/ui/disclosure";
import { EvidenceLabel } from "@/components/ui/evidence-label";
import { EmptyState } from "@/components/ui/state";
import { TBody, THead, Table, Td, Th, Tr } from "@/components/ui/table";
import type { Schemas } from "@/lib/api/client";
import { formatNumber } from "@/lib/format";
import { STATIC_SNAPSHOT } from "@/lib/api/static";

export const metadata: Metadata = { title: "Research overview" };

function Section({ id, title, source, children, aside }: { id: string; title: string; source?: React.ReactNode; aside?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section aria-labelledby={`${id}-h`} className="grid gap-4 border-t border-border pt-6">
      <header className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <h2 id={`${id}-h`} className="text-h4">
          {title}
        </h2>
        {source ? <p className="font-mono text-xs text-subtle">{source}</p> : null}
        {aside}
      </header>
      {children}
    </section>
  );
}

export default async function OverviewPage() {
  if (!STATIC_SNAPSHOT) await connection(); // request-time render; the static export prerenders from the snapshot
  const [meta, tracker, games, protocols, evidence] = await Promise.all([
    load("/api/v1/meta"),
    load("/api/v1/meta/tracker"),
    load("/api/v1/games"),
    load("/api/v1/protocols"),
    load("/api/v1/evidence"),
  ]);

  return (
    <main id="main" className="container-content grid gap-10 py-8 lg:py-10">
      <header className="grid gap-3">
        <p className="label-mono text-subtle">Research platform</p>
        <h1 className="text-h2">Research overview</h1>
        {meta.ok ? (
          <>
            <dl className="flex flex-wrap gap-x-6 gap-y-1 font-mono text-xs text-subtle">
              <Meta k="git" v={meta.body.data.git_sha.slice(0, 12)} />
              <Meta k="api" v={meta.body.data.api_version} />
              <Meta k="schema" v={meta.body.data.schema_version} />
              {tracker.ok && tracker.body.data.project_phase ? <Meta k="phase" v={tracker.body.data.project_phase} /> : null}
            </dl>
            <p className="max-w-prose text-sm text-muted">{meta.body.data.disclaimer}</p>
          </>
        ) : (
          <ApiFailure what="platform metadata" kind={meta.kind} message={meta.message} />
        )}
      </header>

      <Tools />

      <Section id="gates" title="Research gates" source={tracker.ok ? tracker.body.data.source_file : "project/TRACKER.yaml"}>
        {tracker.ok ? <Gates data={tracker.body.data} /> : <ApiFailure what="gate status" kind={tracker.kind} message={tracker.message} />}
      </Section>

      <Section id="games" title="Security games and theorem anchors" source="/api/v1/games">
        {games.ok ? <Games games={games.body.data} /> : <ApiFailure what="the games registry" kind={games.kind} message={games.message} />}
      </Section>

      <Section id="records" title="Recent experiment records" source={evidence.ok ? `${evidence.body.data.experiments_dir}/run_registry.jsonl` : "/api/v1/evidence"}>
        {evidence.ok ? <Records data={evidence.body.data} /> : <ApiFailure what="experiment records" kind={evidence.kind} message={evidence.message} />}
      </Section>

      <Section id="lanes" title="Lanes" source="project/TRACKER.yaml · tasks">
        {tracker.ok ? <Lanes data={tracker.body.data} /> : <ApiFailure what="lane status" kind={tracker.kind} message={tracker.message} />}
        {meta.ok ? (
          <Disclosure title="Package probe" meta="/api/v1/meta">
            <p className="mb-3 max-w-prose">
              Which lane packages this API process can import. A lane can be merged with only files (lane A writes
              research/, not a package), so this probe and the tracker can differ; the tracker is the record of status.
            </p>
            <ul className="grid gap-1 font-mono text-xs">
              {meta.body.data.lanes.map((l) => (
                <li key={l.lane} className="flex gap-3">
                  <span className="w-4 text-foreground">{l.lane}</span>
                  <span className={l.merged ? "text-muted" : "text-subtle"}>{l.merged ? "present" : "absent"}</span>
                  <span className="min-w-0 truncate text-subtle">{l.detail}</span>
                </li>
              ))}
            </ul>
          </Disclosure>
        ) : null}
      </Section>

      <Section id="protocols" title="Protocol registry" source="/api/v1/protocols · qmint.core.contracts.PROTOCOL_GAMES">
        {protocols.ok ? <Protocols rows={protocols.body.data} /> : <ApiFailure what="the protocol registry" kind={protocols.kind} message={protocols.message} />}
      </Section>
    </main>
  );
}

function Meta({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex gap-1.5">
      <dt>{k}</dt>
      <dd className="text-muted">{v}</dd>
    </div>
  );
}

function Tools() {
  const tools = NAV_ITEMS.filter((n) => n.href !== "/app");
  return (
    <nav aria-label="Tools">
      <ul className="grid grid-cols-2 border-t border-border lg:grid-cols-3">
        {tools.map((t) => (
          <li key={t.href} className="border-b border-border odd:border-r lg:odd:border-r-0 lg:border-r lg:[&:nth-child(3n)]:border-r-0">
            <Link
              href={t.href}
              className="group flex h-full items-start gap-3 px-3 py-3.5 transition-colors duration-[var(--duration-instant)] hover:bg-surface/60 sm:px-4 sm:py-4"
            >
              <t.icon className="mt-0.5 size-4 shrink-0 text-subtle group-hover:text-foreground" aria-hidden />
              <span className="grid min-w-0 flex-1 gap-0.5">
                <span className="text-sm text-foreground">{t.label}</span>
                <span className="hidden text-xs text-subtle sm:block">{t.description}</span>
              </span>
              <ArrowRight className="mt-0.5 size-3.5 shrink-0 text-subtle opacity-0 transition-opacity group-hover:opacity-100" aria-hidden />
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function Gates({ data }: { data: Schemas["TrackerData"] }) {
  return (
    <Table>
      <THead>
        <Tr>
          <Th className="w-14">Gate</Th>
          <Th>Description</Th>
          <Th className="w-36">Status</Th>
          <Th className="hidden w-[38%] md:table-cell">Evidence</Th>
        </Tr>
      </THead>
      <TBody>
        {data.gates.map((g) => (
          <Tr key={g.gate_id}>
            <Td className="font-mono text-xs text-muted">{g.gate_id}</Td>
            <Td className="py-2.5">
              <span className="block">{g.description}</span>
              {g.notes ? <span className="block text-xs text-subtle">{g.notes}</span> : null}
            </Td>
            <Td>
              <StatusMark status={g.status} />
            </Td>
            <Td className="hidden py-2.5 text-xs text-muted md:table-cell">
              {g.evidence.length ? (
                <span className="line-clamp-2" title={g.evidence.join("\n")}>
                  {g.evidence[0]}
                  {g.evidence.length > 1 ? <span className="text-subtle"> +{g.evidence.length - 1}</span> : null}
                </span>
              ) : (
                <span className="text-subtle">none recorded</span>
              )}
            </Td>
          </Tr>
        ))}
      </TBody>
    </Table>
  );
}

function Lanes({ data }: { data: Schemas["TrackerData"] }) {
  const merged = data.tasks.filter((t) => t.status === "MERGED").length;
  const inFlight = data.tasks.filter((t) => t.status === "CLAIMED" || t.status === "IN_REVIEW").length;
  return (
    <div className="grid gap-3">
      <p className="text-sm text-muted">
        <span className="tnum font-mono text-foreground">{merged}</span> tasks merged ·{" "}
        <span className="tnum font-mono text-foreground">{inFlight}</span> in flight ·{" "}
        <span className="tnum font-mono text-foreground">{data.tasks.length - merged - inFlight}</span> open
      </p>
      <Table>
        <THead>
          <Tr>
            <Th className="w-14">Task</Th>
            <Th>Description</Th>
            <Th className="w-32">Status</Th>
            <Th className="hidden w-24 sm:table-cell">Commit</Th>
          </Tr>
        </THead>
        <TBody>
          {data.tasks.map((t) => (
            <Tr key={t.task_id}>
              <Td className="font-mono text-xs text-muted">{t.task_id}</Td>
              <Td className="py-2.5">
                <span className="block">{t.description}</span>
                {t.blockers.length ? <span className="block text-xs text-subtle">Blocker: {t.blockers[0]}</span> : null}
              </Td>
              <Td>
                <StatusMark status={t.status} />
              </Td>
              <Td className="hidden font-mono text-xs text-subtle sm:table-cell">{t.commit ?? "—"}</Td>
            </Tr>
          ))}
        </TBody>
      </Table>
    </div>
  );
}

function Games({ games }: { games: Schemas["GameInfo"][] }) {
  return (
    <ul className="grid">
      {games.map((g) => (
        <li key={g.game_id} className="grid gap-x-6 gap-y-2 border-b border-hairline py-4 md:grid-cols-[72px_minmax(0,1fr)_minmax(0,1.1fr)]">
          <span className="font-mono text-sm text-foreground">{g.game_id}</span>
          <div className="grid min-w-0 content-start gap-1.5">
            <span className="text-sm text-foreground">{g.title}</span>
            <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
              {g.formula ? (
                <code className="font-mono text-[0.8125rem] text-foreground">
                  ε ≤ {g.formula}
                  {g.per_unit_value !== null && g.per_unit_value !== undefined ? (
                    <span className="text-subtle"> · base {formatNumber(g.per_unit_value)}</span>
                  ) : null}
                </code>
              ) : (
                <span className="text-xs text-subtle">no closed-form bound (null, never 0)</span>
              )}
              <EvidenceLabel kind={g.bound_evidence_kind} size="xs" />
            </span>
            {g.protocols.length ? <span className="font-mono text-xs text-subtle">{g.protocols.join(" · ")}</span> : null}
          </div>
          <ul className="grid content-start gap-1">
            {(g.anchors ?? []).length === 0 ? <li className="text-xs text-subtle">No theorem anchored to this game.</li> : null}
            {(g.anchors ?? []).map((a) => (
              <li key={a.ref_id} className="flex min-w-0 items-center gap-2 text-xs">
                <Link href={`/research/${encodeURIComponent(a.ref_id)}`} className="shrink-0 font-mono text-muted underline-offset-4 hover:text-foreground hover:underline">
                  {a.ref_id}
                </Link>
                <StatusMark status={a.status} className="text-[0.625rem]" />
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ul>
  );
}

function Records({ data }: { data: Schemas["EvidenceData"] }) {
  if (!data.records.length) {
    return (
      <EmptyState
        title="No experiment records yet"
        description={`The record store (${data.experiments_dir}/run_registry.jsonl) is empty in this checkout. Records appear here when a lane writes a validated contract payload through qmint.core.records.RecordStore.`}
        detail="$ python scripts/run_core.py --offline --seed 42"
      />
    );
  }
  return (
    <Table>
      <THead>
        <Tr>
          <Th>Record</Th>
          <Th>Contract</Th>
          <Th>Evidence</Th>
          <Th className="hidden md:table-cell">Reproducibility</Th>
          <Th className="hidden md:table-cell">Created (UTC)</Th>
        </Tr>
      </THead>
      <TBody>
        {data.records.slice(0, 12).map((r) => (
          <Tr key={r.record_id}>
            <Td className="max-w-48 truncate font-mono text-xs">{r.record_id}</Td>
            <Td className="font-mono text-xs text-muted">{r.contract}</Td>
            <Td>
              <EvidenceLabel kind={r.evidence_kind} size="xs" />
            </Td>
            <Td className="hidden text-xs text-muted md:table-cell">
              {r.reproducibility}
              {r.flags.length ? <span className="block text-subtle">{r.flags.join(", ")}</span> : null}
            </Td>
            <Td className="tnum hidden font-mono text-xs text-subtle md:table-cell">{r.created_utc}</Td>
          </Tr>
        ))}
      </TBody>
    </Table>
  );
}

function Protocols({ rows }: { rows: Schemas["ProtocolInfo"][] }) {
  return (
    <Table>
      <THead>
        <Tr>
          <Th>Protocol</Th>
          <Th className="hidden sm:table-cell">Family</Th>
          <Th>Games</Th>
          <Th className="hidden md:table-cell">Implementation</Th>
        </Tr>
      </THead>
      <TBody>
        {rows.map((p) => (
          <Tr key={p.protocol_id}>
            <Td className="font-mono text-xs">{p.protocol_id}</Td>
            <Td className="hidden text-xs text-muted sm:table-cell">
              {p.family} · {p.quantum ? "quantum" : "classical"}
            </Td>
            <Td className="font-mono text-xs text-muted">{p.games.join(" ")}</Td>
            <Td className="hidden py-2.5 text-xs text-muted md:table-cell">
              <span className={p.implemented_by_merged_lane ? "text-muted" : "text-subtle"}>
                {p.implemented_by_merged_lane ? "merged lane" : "lane not merged"}
              </span>
              <span className="block text-subtle">{p.note}</span>
            </Td>
          </Tr>
        ))}
      </TBody>
    </Table>
  );
}
