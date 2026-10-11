import { ArrowLeft, ArrowUpRight } from "lucide-react";
import type { Metadata } from "next";
import { connection } from "next/server";
import Link from "next/link";
import { notFound } from "next/navigation";
import { EntryFields, LEAD_FIELDS } from "@/components/research/entry-fields";
import { KIND_SINGULAR } from "@/components/research/kinds";
import { ApiFailure } from "@/components/shell/api-failure";
import { load } from "@/components/shell/load";
import { StatusMark } from "@/components/shell/status-mark";
import { apiGet, ApiError, type Schemas } from "@/lib/api/client";
import { STATIC_SNAPSHOT } from "@/lib/api/static";


type Props = { params: Promise<{ id: string }> };

type EntryPath = "/api/v1/research/sources/{entry_id}";

/** Static export: one page per entry in the snapshot. Normal mode renders any id at request time. */
export async function generateStaticParams(): Promise<{ id: string }[]> {
  if (!STATIC_SNAPSHOT) return [];
  const lib = await apiGet("/api/v1/research/sources");
  return lib.data.sources.map((s) => ({ id: s.id }));
}

/** The typed client has no path-parameter templating; the concrete path is passed under the template's type. */
async function fetchEntry(id: string) {
  try {
    const body = await apiGet(`/api/v1/research/sources/${encodeURIComponent(id)}` as EntryPath, { timeoutMs: 10_000 });
    return { ok: true as const, body };
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return { ok: false as const, notFound: true as const };
    const err = e instanceof ApiError ? e : new ApiError("network", (e as Error).message);
    return { ok: false as const, notFound: false as const, kind: err.kind, message: err.message };
  }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  return { title: `${decodeURIComponent(id)} · Research` };
}

function doiUrl(doi: string) {
  return `https://doi.org/${doi}`;
}

export default async function ResearchEntryPage({ params }: Props) {
  if (!STATIC_SNAPSHOT) await connection(); // request-time render; the static export prerenders from the snapshot
  const id = decodeURIComponent((await params).id);
  const [res, lib] = await Promise.all([fetchEntry(id), load("/api/v1/research/sources")]);
  const ids = lib.ok ? lib.body.data.sources.map((s) => s.id) : [];
  if (!res.ok && res.notFound) notFound();

  return (
    <main id="main" className="container-content grid gap-8 py-8 lg:py-10">
      <Link href="/research" className="inline-flex w-fit items-center gap-1.5 text-sm text-muted hover:text-foreground">
        <ArrowLeft className="size-3.5" aria-hidden /> Research library
      </Link>
      {!res.ok ? (
        <>
          <h1 className="font-mono text-h3">{id}</h1>
          <ApiFailure what={`research entry ${id}`} kind={res.kind} message={res.message} />
        </>
      ) : (
        <Entry data={res.body.data} glossary={lib.ok ? lib.body.data.glossary : []} ids={ids} />
      )}
    </main>
  );
}

function Entry({ data, glossary, ids }: { data: Schemas["ResearchEntryDetail"]; glossary: Schemas["GlossaryItem"][]; ids: string[] }) {
  const e = data.entry;
  const definition = glossary.find((g) => g.status === e.status);
  const lead = data.fields.find((f) => LEAD_FIELDS.includes(f.key) && f.kind === "text");
  const rest = data.fields.filter((f) => f !== lead);
  const citations = [...e.urls.map((u) => ({ href: u, label: u })), ...e.dois.filter((d) => !e.urls.some((u) => u.includes(d))).map((d) => ({ href: doiUrl(d), label: `doi:${d}` }))];

  return (
    <article className="grid gap-8">
      <header className="grid gap-3">
        <p className="label-mono text-subtle">
          {KIND_SINGULAR[e.kind]} · <span className="normal-case">{e.id}</span>
        </p>
        <h1 className="max-w-[46rem] text-h2 text-balance">{e.title}</h1>
        {e.title_source ? <p className="text-xs text-subtle">Title from {e.title_source}; not present in the matrix row.</p> : null}
        {e.subtitle ? <p className="max-w-[46rem] text-sm text-muted">{e.subtitle}</p> : null}
      </header>

      <dl className="grid grid-cols-1 gap-x-8 gap-y-4 border-y border-border py-5 sm:grid-cols-2 lg:grid-cols-[1.1fr_0.6fr_1.3fr_1.3fr]">
        <div className="grid content-start gap-1.5">
          <dt className="label-mono text-subtle">Status</dt>
          <dd className="grid gap-1">
            <StatusMark status={e.status} />
            {definition ? <span className="text-xs text-muted">{definition.definition}</span> : null}
            {e.verification !== e.status ? <span className="text-xs text-subtle">{e.verification}</span> : null}
          </dd>
        </div>
        <div className="grid content-start gap-1.5">
          <dt className="label-mono text-subtle">Game</dt>
          <dd className="flex flex-wrap gap-2 font-mono text-sm">
            {e.games.length ? (
              e.games.map((g) => (
                <Link key={g} href={`/research?game=${encodeURIComponent(g)}`} className="text-foreground underline-offset-4 hover:underline">
                  {g}
                </Link>
              ))
            ) : (
              <span className="text-subtle">none stated</span>
            )}
          </dd>
        </div>
        <div className="grid content-start gap-1.5">
          <dt className="label-mono text-subtle">Anchor</dt>
          <dd className="text-sm text-muted">{e.anchor ?? <span className="text-subtle">—</span>}</dd>
        </div>
        <div className="grid content-start gap-1.5">
          <dt className="label-mono text-subtle">Source file</dt>
          <dd className="font-mono text-xs [overflow-wrap:anywhere] text-muted">{e.source_file}</dd>
        </div>
      </dl>

      {lead ? (
        <section aria-label={lead.label} className="max-w-[46rem] border-l-2 border-border-strong pl-5">
          <p className="label-mono mb-2 text-subtle">{lead.label}</p>
          <p className="text-body-lg leading-relaxed whitespace-pre-line text-foreground">{lead.text}</p>
        </section>
      ) : null}

      {citations.length ? (
        <section aria-labelledby="cite-h" className="grid gap-2">
          <h2 id="cite-h" className="label-mono text-subtle">
            Citations
          </h2>
          <ul className="grid gap-1.5">
            {citations.map((c) => (
              <li key={c.href} className="min-w-0">
                <a href={c.href} target="_blank" rel="noreferrer" className="inline-flex max-w-full items-center gap-1.5 font-mono text-xs break-all text-muted underline-offset-4 hover:text-foreground hover:underline">
                  {c.label}
                  <ArrowUpRight className="size-3 shrink-0" aria-hidden />
                  <span className="sr-only">(opens in a new tab)</span>
                </a>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section aria-labelledby="fields-h" className="grid gap-3">
        <h2 id="fields-h" className="text-h4">
          Record
        </h2>
        <p className="text-xs text-subtle">Every field of the source record, in file order.</p>
        <EntryFields fields={rest} knownIds={ids} />
      </section>

      {data.related.length ? (
        <section aria-labelledby="rel-h" className="grid gap-2">
          <h2 id="rel-h" className="text-h4">
            Related entries
          </h2>
          <ul className="border-t border-border">
            {data.related.map((r) => (
              <li key={r.id} className="border-b border-hairline">
                <Link href={`/research/${encodeURIComponent(r.id)}`} className="grid gap-x-5 gap-y-0.5 py-2.5 hover:bg-surface/60 sm:grid-cols-[132px_minmax(0,1fr)_auto] sm:px-2">
                  <span className="font-mono text-xs text-muted">{r.id}</span>
                  <span className="truncate text-sm">{r.title}</span>
                  <StatusMark status={r.status} />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </article>
  );
}
