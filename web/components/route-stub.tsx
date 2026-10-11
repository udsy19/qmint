import Link from "next/link";

/**
 * Phase-1 placeholder. Each phase-2 agent replaces the stub for its routes (see
 * docs/design/WEB_OWNERSHIP.md); agent F deletes this file once no route imports it.
 */
export function RouteStub({ route, title, owner, summary }: { route: string; title: string; owner: string; summary: string }) {
  return (
    <main id="main" className="container-content grid min-h-dvh content-center gap-6 py-24">
      <p className="label-mono text-subtle">
        {route} · under construction by {owner}
      </p>
      <h1 className="font-pixel text-h1 text-foreground">{title}</h1>
      <p className="max-w-prose text-body-lg text-muted">{summary}</p>
      <nav aria-label="Phase 1 routes" className="flex flex-wrap gap-x-5 gap-y-2 text-sm text-muted">
        {["/", "/app", "/lab/mint", "/lab/attack", "/benchmarks", "/certificates", "/research", "/docs", "/design-system"].map((r) => (
          <Link key={r} href={r} className="font-mono underline-offset-4 hover:text-foreground hover:underline">
            {r}
          </Link>
        ))}
      </nav>
    </main>
  );
}
