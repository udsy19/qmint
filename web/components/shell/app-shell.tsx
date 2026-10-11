"use client";

import { ChevronRight, Menu, PanelLeftClose, PanelLeftOpen, Search, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Dialog as D } from "radix-ui";
import * as React from "react";
import { docBySlug } from "@/components/docs/registry";
import { DialogOverlay } from "@/components/ui/dialog";
import { Kbd } from "@/components/ui/kbd";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { PaletteProvider, usePalette } from "./command-palette";
import { crumbsFor, isActive, NAV, type NavItem } from "./nav";
import { DISCLOSURE_URL, LICENSE_URL, SUPPORT_LINE } from "./support";

const COLLAPSE_KEY = "qmint.sidebar.collapsed";
const collapseListeners = new Set<() => void>();
let memoryCollapsed: boolean | null = null;

function readCollapsed(): boolean {
  try {
    return window.localStorage.getItem(COLLAPSE_KEY) === "1";
  } catch {
    return false;
  }
}

function writeCollapsed(v: boolean) {
  try {
    window.localStorage.setItem(COLLAPSE_KEY, v ? "1" : "0");
  } catch {
    /* storage unavailable (private mode): state still toggles for this page view */
  }
  memoryCollapsed = v;
  collapseListeners.forEach((l) => l());
}

function useCollapsed(): [boolean, (v: boolean) => void] {
  const value = React.useSyncExternalStore(
    (cb) => {
      collapseListeners.add(cb);
      return () => collapseListeners.delete(cb);
    },
    () => memoryCollapsed ?? readCollapsed(),
    () => false,
  );
  return [value, writeCollapsed];
}

function isTypingTarget(t: EventTarget | null): boolean {
  const el = t as HTMLElement | null;
  return !!el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
}

/** Platform shell: compact sidebar (collapsible to a rail), 48px header with breadcrumbs, mobile sheet, global ⌘K. */
export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <PaletteProvider>
      <ShellFrame>{children}</ShellFrame>
    </PaletteProvider>
  );
}

function ShellFrame({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() ?? "/";
  const [collapsed, setCollapsed] = useCollapsed();
  const previous = React.useRef(pathname);

  // Focus management: after client-side navigation (not on first load, and idempotent under StrictMode's
  // double effects) move focus to the new page's <main id="main"> so keyboard and screen-reader users start there.
  React.useEffect(() => {
    if (previous.current === pathname) return;
    previous.current = pathname;
    if (window.location.hash) return; // in-page anchor links keep their own target
    const main = document.getElementById("main");
    if (main) {
      if (!main.hasAttribute("tabindex")) main.setAttribute("tabindex", "-1");
      main.classList.add("outline-none");
      main.focus({ preventScroll: true });
    }
  }, [pathname]);

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "[" && !e.metaKey && !e.ctrlKey && !e.altKey && !isTypingTarget(e.target)) {
        setCollapsed(!collapsed);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [collapsed, setCollapsed]);

  return (
    <div className="flex min-h-dvh">
      <aside
        aria-label="Platform"
        data-collapsed={collapsed || undefined}
        className={cn(
          "sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-border bg-background lg:flex",
          "transition-[width] duration-[var(--duration-base)] ease-out",
          collapsed ? "w-[var(--sidebar-w-collapsed)]" : "w-[var(--sidebar-w)]",
        )}
      >
        <div className={cn("flex h-[var(--header-h)] shrink-0 items-center border-b border-border", collapsed ? "justify-center" : "justify-between pr-2 pl-4")}>
          {collapsed ? null : <Wordmark />}
          <CollapseButton collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
        </div>
        <SidebarSearch collapsed={collapsed} />
        <NavList pathname={pathname} collapsed={collapsed} />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <Header pathname={pathname} />
        <div className="min-w-0 flex-1">{children}</div>
        <ShellFooter />
      </div>
    </div>
  );
}

function Wordmark() {
  return (
    <Link href="/" className="font-pixel text-[1.0625rem] leading-none tracking-tight text-foreground" aria-label="QMint home">
      QMint
    </Link>
  );
}

function CollapseButton({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const label = collapsed ? "Expand sidebar" : "Collapse sidebar";
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          onClick={onToggle}
          aria-label={label}
          aria-expanded={!collapsed}
          className="grid size-8 place-items-center rounded-sm text-subtle transition-colors duration-[var(--duration-instant)] hover:bg-surface-hover hover:text-foreground"
        >
          {collapsed ? <PanelLeftOpen className="size-4" aria-hidden /> : <PanelLeftClose className="size-4" aria-hidden />}
        </button>
      </TooltipTrigger>
      <TooltipContent side="right">
        {label} <Kbd className="ml-1">[</Kbd>
      </TooltipContent>
    </Tooltip>
  );
}

function SidebarSearch({ collapsed }: { collapsed: boolean }) {
  const { setOpen } = usePalette();
  if (collapsed) {
    return (
      <div className="flex justify-center py-2">
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              onClick={() => setOpen(true)}
              aria-label="Open command palette"
              className="grid size-8 place-items-center rounded-sm text-subtle hover:bg-surface-hover hover:text-foreground"
            >
              <Search className="size-4" aria-hidden />
            </button>
          </TooltipTrigger>
          <TooltipContent side="right">
            Search <Kbd className="ml-1">⌘K</Kbd>
          </TooltipContent>
        </Tooltip>
      </div>
    );
  }
  return (
    <div className="px-3 pt-3 pb-1">
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex h-8 w-full items-center gap-2 rounded-sm border border-border bg-surface px-2.5 text-left text-sm text-subtle transition-colors duration-[var(--duration-instant)] hover:border-border-strong hover:text-muted"
      >
        <Search className="size-3.5" aria-hidden />
        <span className="flex-1">Search…</span>
        <Kbd aria-label="Command K">⌘K</Kbd>
      </button>
    </div>
  );
}

function NavList({ pathname, collapsed, onNavigate }: { pathname: string; collapsed?: boolean; onNavigate?: () => void }) {
  return (
    <nav aria-label="Platform sections" className="flex-1 overflow-y-auto px-2 py-2">
      {NAV.map((group, gi) => (
        <div key={group.label ?? gi} className={cn(gi > 0 && "mt-4")}>
          {group.label && !collapsed ? <p className="label-mono px-2 pb-1 text-subtle">{group.label}</p> : null}
          {group.label && collapsed ? <div className="mx-auto mb-2 h-px w-5 bg-border" aria-hidden /> : null}
          <ul className="grid gap-px">
            {group.items.map((item) => (
              <li key={item.href}>
                <NavLink item={item} active={isActive(pathname, item.href)} collapsed={!!collapsed} onNavigate={onNavigate} />
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}

function NavLink({ item, active, collapsed, onNavigate }: { item: NavItem; active: boolean; collapsed: boolean; onNavigate?: () => void }) {
  const link = (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      aria-label={collapsed ? item.label : undefined}
      className={cn(
        "flex h-8 items-center gap-2.5 rounded-sm text-sm transition-colors duration-[var(--duration-instant)]",
        collapsed ? "mx-auto w-8 justify-center" : "px-2",
        active ? "bg-surface-raised text-foreground" : "text-muted hover:bg-surface-hover hover:text-foreground",
      )}
    >
      <item.icon className={cn("size-4 shrink-0", active ? "text-foreground" : "text-subtle")} aria-hidden />
      {collapsed ? null : <span className="truncate">{item.label}</span>}
    </Link>
  );
  if (!collapsed) return link;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{link}</TooltipTrigger>
      <TooltipContent side="right">{item.label}</TooltipContent>
    </Tooltip>
  );
}

function resolveCrumb(href: string, segment: string): string | undefined {
  if (href.startsWith("/docs/")) return docBySlug(segment)?.title;
  return undefined;
}

export function Breadcrumbs({ pathname }: { pathname: string }) {
  const crumbs = crumbsFor(pathname, resolveCrumb);
  if (!crumbs.length) return null;
  return (
    <nav aria-label="Breadcrumb" className="min-w-0">
      <ol className="flex min-w-0 items-center gap-1 text-sm">
        {crumbs.map((c, i) => {
          const last = i === crumbs.length - 1;
          return (
            <li key={`${c.label}-${i}`} className={cn("flex min-w-0 items-center gap-1", !last && "hidden shrink-0 sm:flex")}>
              {i > 0 ? <ChevronRight className="hidden size-3.5 shrink-0 text-subtle sm:block" aria-hidden /> : null}
              {last ? (
                <span aria-current="page" className="truncate text-foreground">
                  {c.label}
                </span>
              ) : c.href ? (
                <Link href={c.href} className="truncate text-muted transition-colors hover:text-foreground">
                  {c.label}
                </Link>
              ) : (
                <span className="truncate text-subtle">{c.label}</span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function Header({ pathname }: { pathname: string }) {
  const { setOpen } = usePalette();
  return (
    <header className="sticky top-0 z-header flex h-[var(--header-h)] shrink-0 items-center gap-2 border-b border-border bg-background px-[var(--gutter)] lg:px-6">
      <MobileNav pathname={pathname} />
      <span className="font-pixel text-[0.9375rem] leading-none text-foreground lg:hidden" aria-hidden>
        QMint
      </span>
      <span className="mx-1 h-4 w-px bg-border lg:hidden" aria-hidden />
      <Breadcrumbs pathname={pathname} />
      <div className="ml-auto flex items-center gap-1">
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Open command palette"
          className="flex h-8 items-center gap-2 rounded-sm px-2 text-sm text-subtle transition-colors duration-[var(--duration-instant)] hover:bg-surface-hover hover:text-foreground"
        >
          <Search className="size-4" aria-hidden />
          <Kbd className="hidden sm:inline-flex">⌘K</Kbd>
        </button>
      </div>
    </header>
  );
}

function MobileNav({ pathname }: { pathname: string }) {
  const [open, setOpen] = React.useState(false);
  const { setOpen: setPalette } = usePalette();
  return (
    <D.Root open={open} onOpenChange={setOpen}>
      <D.Trigger asChild>
        <button
          type="button"
          aria-label="Open navigation"
          className="-ml-1.5 grid size-9 place-items-center rounded-sm text-muted hover:bg-surface-hover hover:text-foreground lg:hidden"
        >
          <Menu className="size-4.5" aria-hidden />
        </button>
      </D.Trigger>
      <D.Portal>
        <DialogOverlay />
        <D.Content
          aria-describedby={undefined}
          className="fixed inset-y-0 left-0 z-modal flex w-[min(300px,86vw)] flex-col border-r border-border bg-background shadow-overlay outline-none data-[state=open]:animate-[qm-fade-in_var(--duration-base)_var(--ease-out)]"
        >
          <div className="flex h-[var(--header-h)] shrink-0 items-center justify-between border-b border-border pr-2 pl-4">
            <D.Title asChild>
              <span className="font-pixel text-[1.0625rem] leading-none">QMint</span>
            </D.Title>
            <D.Close asChild>
              <button type="button" aria-label="Close navigation" className="grid size-9 place-items-center rounded-sm text-muted hover:bg-surface-hover hover:text-foreground">
                <X className="size-4" aria-hidden />
              </button>
            </D.Close>
          </div>
          <div className="px-3 pt-3 pb-1">
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                setPalette(true);
              }}
              className="flex h-10 w-full items-center gap-2 rounded-sm border border-border bg-surface px-3 text-left text-sm text-subtle"
            >
              <Search className="size-4" aria-hidden />
              Search pages, docs, research
            </button>
          </div>
          <NavList pathname={pathname} onNavigate={() => setOpen(false)} />
        </D.Content>
      </D.Portal>
    </D.Root>
  );
}

function ShellFooter() {
  return (
    <footer className="border-t border-border">
      <div className="flex flex-col gap-2 px-[var(--gutter)] py-4 text-xs text-subtle sm:flex-row sm:items-center sm:justify-between lg:px-6">
        <p data-testid="support-line" className="text-muted">
          {SUPPORT_LINE}
        </p>
        <ul className="flex flex-wrap items-center gap-x-4 gap-y-1">
          <li>Research platform · not a payment service</li>
          <li>
            <a href={LICENSE_URL} className="underline-offset-4 hover:text-foreground hover:underline" rel="noreferrer">
              MIT License
            </a>
          </li>
          <li>
            <a href={DISCLOSURE_URL} className="underline-offset-4 hover:text-foreground hover:underline" rel="noreferrer">
              Disclosure
            </a>
          </li>
        </ul>
      </div>
    </footer>
  );
}
