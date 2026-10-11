"use client";

import { Search, X } from "lucide-react";
import Link from "next/link";
import * as React from "react";
import { StatusMark, statusTone, type StatusTone } from "@/components/shell/status-mark";
import { cn } from "@/lib/utils";
import type { Schemas } from "@/lib/api/client";
import { KIND_LABEL, KIND_ORDER, type EntryKind } from "./kinds";

type Entry = Schemas["ResearchEntry"];

export interface Filters {
  q: string;
  kind: EntryKind | "all";
  game: string;
  tone: StatusTone | "all";
}

const TONE_LABEL: Record<StatusTone, string> = {
  done: "Verified / reproduced",
  partial: "Partial",
  open: "Not verified / open",
  skipped: "Unsupported",
  danger: "Conflict / disallowed",
};

export function matches(e: Entry, f: Filters): boolean {
  if (f.kind !== "all" && e.kind !== f.kind) return false;
  if (f.game && !e.games.includes(f.game)) return false;
  if (f.tone !== "all" && statusTone(e.status) !== f.tone) return false;
  const q = f.q.trim().toLowerCase();
  if (!q) return true;
  const hay = [e.id, e.title, e.subtitle ?? "", e.summary, e.status, e.anchor ?? "", ...e.games, ...e.dois].join(" ").toLowerCase();
  return q.split(/\s+/).every((t) => hay.includes(t));
}

function writeUrl(f: Filters) {
  const p = new URLSearchParams();
  if (f.q) p.set("q", f.q);
  if (f.kind !== "all") p.set("kind", f.kind);
  if (f.game) p.set("game", f.game);
  if (f.tone !== "all") p.set("status", f.tone);
  const s = p.toString();
  window.history.replaceState(null, "", s ? `?${s}` : window.location.pathname);
}

/** Searchable, filterable research index. Filters live in the URL so a filtered view can be shared. */
export function ResearchIndex({ entries, initial }: { entries: Entry[]; initial: Filters }) {
  const [f, setF] = React.useState<Filters>(initial);
  const searchRef = React.useRef<HTMLInputElement>(null);
  const update = (patch: Partial<Filters>) => {
    const next = { ...f, ...patch };
    setF(next);
    writeUrl(next);
  };

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (e.key === "/" && !(t && (t.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName)))) {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const results = entries.filter((e) => matches(e, f));
  const games = Array.from(new Set(entries.flatMap((e) => e.games))).sort();
  const kindCounts = new Map<string, number>();
  for (const e of entries) if (matches(e, { ...f, kind: "all" })) kindCounts.set(e.kind, (kindCounts.get(e.kind) ?? 0) + 1);
  const filtered = f.q || f.kind !== "all" || f.game || f.tone !== "all";
  const groups = KIND_ORDER.map((k) => ({ kind: k, items: results.filter((e) => e.kind === k) })).filter((g) => g.items.length);

  return (
    <div className="grid gap-6 lg:grid-cols-[200px_minmax(0,1fr)] lg:gap-10">
      <div className="grid content-start gap-5 lg:sticky lg:top-[calc(var(--header-h)+24px)]">
        <label className="relative block">
          <span className="sr-only">Search the research library</span>
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-subtle" aria-hidden />
          <input
            ref={searchRef}
            type="search"
            value={f.q}
            onChange={(e) => update({ q: e.target.value })}
            placeholder="Search id, title, DOI…"
            className="h-9 w-full rounded-sm border border-border-strong bg-surface pr-8 pl-8 text-sm text-foreground outline-none placeholder:text-subtle focus-visible:border-ring"
          />
          <kbd className="pointer-events-none absolute top-1/2 right-2 hidden -translate-y-1/2 rounded-xs border border-border-strong px-1 font-mono text-[0.625rem] text-subtle sm:block">/</kbd>
        </label>

        <fieldset className="grid gap-1">
          <legend className="label-mono mb-1.5 text-subtle">Kind</legend>
          <div className="-mx-1 flex gap-1 overflow-x-auto px-1 pb-1 lg:grid lg:overflow-visible lg:pb-0">
            {(["all", ...KIND_ORDER] as const).map((k) => {
              const n = k === "all" ? Array.from(kindCounts.values()).reduce((a, b) => a + b, 0) : (kindCounts.get(k) ?? 0);
              const active = f.kind === k;
              return (
                <button
                  key={k}
                  type="button"
                  aria-pressed={active}
                  onClick={() => update({ kind: k })}
                  className={cn(
                    "flex h-8 shrink-0 items-center justify-between gap-3 rounded-sm px-2.5 text-sm whitespace-nowrap transition-colors duration-[var(--duration-instant)]",
                    active ? "bg-surface-raised text-foreground" : "text-muted hover:bg-surface-hover hover:text-foreground",
                  )}
                >
                  <span>{k === "all" ? "All entries" : KIND_LABEL[k]}</span>
                  <span className="tnum font-mono text-xs text-subtle">{n}</span>
                </button>
              );
            })}
          </div>
        </fieldset>

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-1">
          <label className="grid gap-1.5">
            <span className="label-mono text-subtle">Game</span>
            <select
              value={f.game}
              onChange={(e) => update({ game: e.target.value })}
              className="h-8 rounded-sm border border-border-strong bg-surface px-2 font-mono text-xs text-foreground"
            >
              <option value="">Any game</option>
              {games.map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-1.5">
            <span className="label-mono text-subtle">Verification</span>
            <select
              value={f.tone}
              onChange={(e) => update({ tone: e.target.value as Filters["tone"] })}
              className="h-8 rounded-sm border border-border-strong bg-surface px-2 text-xs text-foreground"
            >
              <option value="all">Any status</option>
              {(Object.keys(TONE_LABEL) as StatusTone[]).map((t) => (
                <option key={t} value={t}>
                  {TONE_LABEL[t]}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div className="min-w-0">
        <div className="flex min-h-8 items-center justify-between gap-4 border-b border-border pb-2 text-xs text-subtle" aria-live="polite">
          <span>
            <span className="tnum font-mono text-foreground">{results.length}</span> of <span className="tnum font-mono">{entries.length}</span> entries
          </span>
          {filtered ? (
            <button
              type="button"
              onClick={() => update({ q: "", kind: "all", game: "", tone: "all" })}
              className="inline-flex items-center gap-1 rounded-sm px-1.5 py-1 text-muted hover:bg-surface-hover hover:text-foreground"
            >
              <X className="size-3" aria-hidden /> Clear filters
            </button>
          ) : null}
        </div>

        {groups.length === 0 ? (
          <div role="status" className="py-12 text-sm text-muted">
            No entry matches these filters.{" "}
            <button type="button" className="text-foreground underline underline-offset-4" onClick={() => update({ q: "", kind: "all", game: "", tone: "all" })}>
              Clear filters
            </button>
          </div>
        ) : null}

        {groups.map((g) => (
          <section key={g.kind} aria-labelledby={`grp-${g.kind}`}>
            <h2 id={`grp-${g.kind}`} className="label-mono sticky top-[var(--header-h)] z-sticky flex justify-between bg-background pt-5 pb-2 text-subtle">
              <span>{KIND_LABEL[g.kind]}</span>
              <span className="tnum">{g.items.length}</span>
            </h2>
            <ul className="border-t border-border">
              {g.items.map((e) => (
                <EntryRow key={e.id} e={e} />
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}

function EntryRow({ e }: { e: Entry }) {
  return (
    <li className="border-b border-hairline">
      <Link
        href={`/research/${encodeURIComponent(e.id)}`}
        className="group grid gap-x-5 gap-y-1 py-3 transition-colors duration-[var(--duration-instant)] hover:bg-surface/60 sm:grid-cols-[132px_minmax(0,1fr)_auto] sm:px-2"
      >
        <span className="flex items-center justify-between gap-3 sm:block">
          <span className="font-mono text-xs text-muted group-hover:text-foreground">{e.id}</span>
          <StatusMark status={e.status} className="sm:hidden" />
        </span>
        <span className="grid min-w-0 gap-0.5">
          <span className="text-sm text-foreground">{e.title}</span>
          {e.summary && e.summary !== e.title ? <span className="line-clamp-2 text-xs leading-relaxed text-muted">{e.summary}</span> : null}
          <span className="flex min-w-0 flex-wrap gap-x-3 font-mono text-[0.6875rem] text-subtle">
            {e.games.length ? <span>{e.games.join(" · ")}</span> : null}
            {e.year ? <span>{e.year}</span> : null}
            {e.dois[0] ? <span className="truncate">doi:{e.dois[0]}</span> : null}
          </span>
        </span>
        <span className="hidden sm:block sm:pt-0.5">
          <StatusMark status={e.status} />
        </span>
      </Link>
    </li>
  );
}
