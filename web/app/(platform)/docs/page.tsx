import { ArrowRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { CodeBlock } from "@/components/docs/code-block";
import { DOC_GROUPS, DOCS } from "@/components/docs/registry";

export const metadata: Metadata = { title: "Documentation" };

export default function DocsIndex() {
  return (
    <main id="main" className="container-content grid gap-10 py-8 lg:py-12">
      <header className="grid max-w-[46rem] gap-3">
        <p className="label-mono text-subtle">Docs</p>
        <h1 className="text-h1 max-sm:text-h2">Developer documentation</h1>
        <p className="text-body-lg text-muted">
          Run QMint locally, call its research API, reproduce the published bounds and read how every number on this site is
          labelled.
        </p>
      </header>

      <section aria-labelledby="quick-h" className="grid max-w-[46rem] gap-3">
        <h2 id="quick-h" className="label-mono text-subtle">
          Quick start
        </h2>
        <CodeBlock
          code={`$ uv venv && uv pip install -r requirements.lock && uv pip install --no-deps -e .
$ python -m uvicorn qmint.api.app:app --port 8787
$ cd web && pnpm install && pnpm dev`}
        />
      </section>

      <div className="grid gap-10 md:grid-cols-3 md:gap-8">
        {DOC_GROUPS.map((g) => (
          <section key={g} aria-labelledby={`g-${g}`} className="grid content-start gap-2">
            <h2 id={`g-${g}`} className="label-mono border-b border-border pb-2 text-subtle">
              {g}
            </h2>
            <ul className="grid">
              {DOCS.filter((d) => d.group === g).map((d) => (
                <li key={d.slug} className="border-b border-hairline">
                  <Link href={`/docs/${d.slug}`} className="group grid gap-1 py-3">
                    <span className="flex items-center justify-between gap-2 text-sm text-foreground">
                      {d.title}
                      <ArrowRight className="size-3.5 text-subtle transition-transform duration-[var(--duration-fast)] group-hover:translate-x-0.5 group-hover:text-foreground" aria-hidden />
                    </span>
                    <span className="text-xs leading-relaxed text-muted">{d.description}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>

      <p className="max-w-[46rem] text-sm text-muted">
        QMint is MIT-licensed; see{" "}
        <Link href="/docs/getting-started#support-license" className="text-foreground underline decoration-border-strong underline-offset-4">
          support, license and disclosure
        </Link>
        .
      </p>
    </main>
  );
}
