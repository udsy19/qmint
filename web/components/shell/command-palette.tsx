"use client";

import { ArrowUpRight, FileText, Hash, Home } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";
import { DOCS } from "@/components/docs/registry";
import {
  CommandDialog,
  CommandEmpty,
  CommandFooter,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { apiGet } from "@/lib/api/client";
import { NAV_ITEMS } from "./nav";

interface ResearchHit {
  id: string;
  title: string;
  kind: string;
}

type ResearchState = { state: "idle" | "loading" } | { state: "ready"; items: ResearchHit[] } | { state: "error"; message: string };

/** Open/close state shared by the header button, the mobile sheet and the ⌘K shortcut. */
export const PaletteContext = React.createContext<{ open: boolean; setOpen: (v: boolean) => void }>({
  open: false,
  setOpen: () => {},
});

export function usePalette() {
  return React.useContext(PaletteContext);
}

export function PaletteProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = React.useState(false);
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && !e.altKey && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  const value = React.useMemo(() => ({ open, setOpen }), [open]);
  return (
    <PaletteContext.Provider value={value}>
      {children}
      <CommandPalette open={open} onOpenChange={setOpen} />
    </PaletteContext.Provider>
  );
}

/**
 * Global ⌘K palette: every platform route, every docs page and section, and (fetched on first open)
 * every research-library entry. Deterministic search (cmdk), no AI.
 */
export function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const router = useRouter();
  const [research, setResearch] = React.useState<ResearchState>({ state: "idle" });

  const started = React.useRef(false);

  // Lazy one-shot load of the research index the first time the palette opens. Not aborted on close: the
  // result is cached for the rest of the session; a failure is retried on the next open.
  React.useEffect(() => {
    if (!open || started.current) return;
    started.current = true;
    setResearch({ state: "loading" });
    apiGet("/api/v1/research/sources", { timeoutMs: 8000 })
      .then((r) => setResearch({ state: "ready", items: r.data.sources.map((s) => ({ id: s.id, title: s.title, kind: s.kind })) }))
      .catch((e: Error) => {
        started.current = false; // retry on the next open
        setResearch({ state: "error", message: e.message });
      });
  }, [open]);

  const go = React.useCallback(
    (href: string) => {
      onOpenChange(false);
      router.push(href);
    },
    [onOpenChange, router],
  );

  const researchItems = research.state === "ready" ? research.items : [];
  const count = NAV_ITEMS.length + 1 + DOCS.reduce((n, d) => n + 1 + d.sections.length, 0) + researchItems.length;

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange} label="Go to page, document or research entry">
      <CommandInput placeholder="Go to page, docs or research…" aria-label="Search pages, docs and research entries" />
      <CommandList>
        <CommandEmpty>No matching page, document or entry.</CommandEmpty>
        <CommandGroup heading="Platform">
          {NAV_ITEMS.map((n) => (
            <CommandItem key={n.href} value={`${n.label} ${n.href} ${n.description} ${(n.keywords ?? []).join(" ")}`} onSelect={() => go(n.href)}>
              <n.icon aria-hidden />
              <span className="text-foreground">{n.label}</span>
              <span className="truncate text-subtle">— {n.description}</span>
            </CommandItem>
          ))}
          <CommandItem value="Home landing page /" onSelect={() => go("/")}>
            <Home aria-hidden />
            <span className="text-foreground">Home</span>
            <span className="truncate text-subtle">— public landing page</span>
          </CommandItem>
        </CommandGroup>
        <CommandSeparator />
        <CommandGroup heading="Docs">
          {DOCS.map((d) => (
            <React.Fragment key={d.slug}>
              <CommandItem value={`docs ${d.title} ${d.description}`} onSelect={() => go(`/docs/${d.slug}`)}>
                <FileText aria-hidden />
                <span className="text-foreground">{d.title}</span>
                <span className="truncate text-subtle">— Docs</span>
              </CommandItem>
              {d.sections.map((s) => (
                <CommandItem key={s.id} value={`docs ${d.title} ${s.title} ${s.id}`} onSelect={() => go(`/docs/${d.slug}#${s.id}`)}>
                  <Hash aria-hidden />
                  <span className="truncate">{s.title}</span>
                  <span className="shrink-0 truncate text-subtle">— {d.title}</span>
                </CommandItem>
              ))}
            </React.Fragment>
          ))}
        </CommandGroup>
        <CommandSeparator />
        <CommandGroup heading="Research library">
          {research.state === "loading" ? (
            <CommandItem disabled value="research loading">
              <span className="text-subtle">Loading research entries…</span>
            </CommandItem>
          ) : null}
          {research.state === "error" ? (
            <CommandItem value="research library unavailable" onSelect={() => go("/research")}>
              <ArrowUpRight aria-hidden />
              <span>Research library</span>
              <span className="truncate text-subtle">— entries could not load ({research.message})</span>
            </CommandItem>
          ) : null}
          {researchItems.map((r) => (
            <CommandItem key={r.id} value={`research ${r.id} ${r.title} ${r.kind}`} onSelect={() => go(`/research/${encodeURIComponent(r.id)}`)}>
              <span className="w-28 shrink-0 truncate font-mono text-xs text-subtle">{r.id}</span>
              <span className="truncate">{r.title}</span>
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
      <CommandFooter>
        <span className="tnum">{count} items</span>
      </CommandFooter>
    </CommandDialog>
  );
}
