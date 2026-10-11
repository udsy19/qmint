import { ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { apiGet } from "@/lib/api/client";
import { DISCLOSURE_URL, LICENSE_URL, REPO_URL, SUPPORT_LINE } from "./site";
import { Wordmark } from "./wordmark";

const COLUMNS = [
  {
    head: "Platform",
    links: [
      { href: "/app", label: "Overview" },
      { href: "/lab/mint", label: "Mint lab" },
      { href: "/lab/attack", label: "Attack lab" },
      { href: "/certificates", label: "Certificates" },
      { href: "/benchmarks", label: "Benchmarks" },
    ],
  },
  {
    head: "Research",
    links: [
      { href: "/research", label: "Library" },
      { href: "/docs", label: "Documentation" },
      { href: "/#proof", label: "Evidence" },
    ],
  },
  {
    head: "Source",
    links: [
      { href: REPO_URL, label: "GitHub" },
      { href: LICENSE_URL, label: "MIT License" },
      { href: DISCLOSURE_URL, label: "AI assistance disclosure" },
    ],
  },
] as const;

async function loadMeta() {
  try {
    const r = await apiGet("/api/v1/meta", { timeoutMs: 3000 });
    return { apiVersion: r.data.api_version, gitSha: r.data.git_sha };
  } catch {
    return null;
  }
}

export async function MarketingFooter() {
  const meta = await loadMeta();
  return (
    <footer className="border-t border-border">
      <div className="container-wide grid gap-12 py-16 md:grid-cols-12 md:gap-8">
        <div className="grid content-start gap-4 md:col-span-5">
          <Wordmark />
          <p className="text-sm text-foreground">{SUPPORT_LINE}</p>
        </div>
        <nav aria-label="Footer" className="grid grid-cols-2 gap-8 sm:grid-cols-3 md:col-span-7">
          {COLUMNS.map((c) => (
            <div key={c.head} className="grid content-start gap-3">
              <p className="label-mono text-subtle">{c.head}</p>
              <ul className="grid gap-2">
                {c.links.map((l) => (
                  <li key={l.label}>
                    {l.href.startsWith("http") ? (
                      <a href={l.href} className="inline-flex items-center gap-1 text-sm text-muted transition-colors hover:text-foreground">
                        {l.label} <ArrowUpRight className="size-3 text-subtle" aria-hidden />
                      </a>
                    ) : (
                      <Link href={l.href} className="text-sm text-muted transition-colors hover:text-foreground">
                        {l.label}
                      </Link>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
      </div>
      <div className="border-t border-border">
        <div className="container-wide flex flex-col gap-2 py-5 font-mono text-[0.6875rem] text-subtle sm:flex-row sm:items-center sm:justify-between">
          <span>Research demonstrations · not a payment service · MIT License</span>
          <span className="tnum">
            {meta ? (
              <>
                API {meta.apiVersion} · git {meta.gitSha.slice(0, 7)}
              </>
            ) : (
              "API offline: build metadata unavailable"
            )}
          </span>
        </div>
      </div>
    </footer>
  );
}
