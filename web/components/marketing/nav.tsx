"use client";

import { ArrowUpRight, Menu, X } from "lucide-react";
import Link from "next/link";
import * as React from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { REPO_URL } from "./site";
import { Wordmark } from "./wordmark";

export const NAV_LINKS = [
  { href: "/app", label: "Product" },
  { href: "/research", label: "Research" },
  { href: "/benchmarks", label: "Benchmarks" },
  { href: "/docs", label: "Documentation" },
] as const;

/**
 * Marketing nav: 56px, sticky (the landing page is long and the Lab CTA should stay one click away).
 * Opaque background, no blur; the hairline appears once the page scrolls. < md: links in a sheet.
 */
export function MarketingNav() {
  const [open, setOpen] = React.useState(false);
  const [scrolled, setScrolled] = React.useState(false);

  React.useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <header
      className={cn(
        "sticky top-0 z-header border-b bg-background transition-colors duration-[var(--duration-base)]",
        scrolled || open ? "border-border" : "border-transparent",
      )}
    >
      <nav aria-label="Primary" className="container-wide flex h-[var(--nav-h)] items-center justify-between gap-6">
        <Link href="/" aria-label="QMint home" className="-m-1 rounded-xs p-1">
          <Wordmark />
        </Link>

        <ul className="hidden items-center gap-1 md:flex">
          {NAV_LINKS.map((l) => (
            <li key={l.href}>
              <Link
                href={l.href}
                className="rounded-sm px-2.5 py-1.5 text-sm text-muted transition-colors duration-[var(--duration-instant)] hover:text-foreground"
              >
                {l.label}
              </Link>
            </li>
          ))}
          <li>
            <a
              href={REPO_URL}
              className="inline-flex items-center gap-1 rounded-sm px-2.5 py-1.5 text-sm text-muted transition-colors duration-[var(--duration-instant)] hover:text-foreground"
            >
              GitHub <ArrowUpRight className="size-3.5 text-subtle" aria-hidden />
            </a>
          </li>
          <li aria-hidden className="mx-2 h-4 w-px bg-border" />
          <li>
            <Button asChild variant="primary" size="md">
              <Link href="/app">Launch Lab</Link>
            </Button>
          </li>
        </ul>

        <Button
          variant="ghost"
          size="icon"
          className="md:hidden"
          aria-expanded={open}
          aria-controls="marketing-menu"
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((o) => !o)}
        >
          {open ? <X /> : <Menu />}
        </Button>
      </nav>

      {open ? (
        <div id="marketing-menu" className="border-t border-border bg-background md:hidden">
          <ul className="container-wide grid py-2">
            {NAV_LINKS.map((l) => (
              <li key={l.href}>
                <Link href={l.href} onClick={() => setOpen(false)} className="flex h-11 items-center text-[0.9375rem] text-muted hover:text-foreground">
                  {l.label}
                </Link>
              </li>
            ))}
            <li>
              <a href={REPO_URL} className="flex h-11 items-center gap-1 text-[0.9375rem] text-muted hover:text-foreground">
                GitHub <ArrowUpRight className="size-3.5" aria-hidden />
              </a>
            </li>
            <li className="pt-2 pb-3">
              <Button asChild variant="primary" size="lg" className="w-full">
                <Link href="/app" onClick={() => setOpen(false)}>
                  Launch Lab
                </Link>
              </Button>
            </li>
          </ul>
        </div>
      ) : null}
    </header>
  );
}
