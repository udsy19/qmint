import { ArrowLeft, ArrowRight, Link2 } from "lucide-react";
import Link from "next/link";
import * as React from "react";
import { Disclosure } from "@/components/ui/disclosure";
import { DocsNav } from "./docs-nav";
import { docNeighbours, type DocPageMeta } from "./registry";
import { Toc } from "./toc";

/** Three-column documentation page: docs nav · 680px prose · on-this-page rail (collapses to one column). */
export function DocPage({ doc, content }: { doc: DocPageMeta; content: Record<string, React.ReactNode> }) {
  const { prev, next } = docNeighbours(doc.slug);
  return (
    <div className="mx-auto grid w-full max-w-[1280px] gap-8 px-[var(--gutter)] py-8 lg:grid-cols-[200px_minmax(0,1fr)] lg:gap-10 lg:py-10 xl:grid-cols-[200px_minmax(0,1fr)_180px]">
      <aside className="hidden lg:block">
        <div className="sticky top-[calc(var(--header-h)+32px)]">
          <DocsNav />
        </div>
      </aside>

      <main id="main" className="min-w-0">
        <div className="mb-6 lg:hidden">
          <Disclosure title="Documentation menu">
            <DocsNav />
          </Disclosure>
        </div>
        <article className="mx-auto grid max-w-[46rem] gap-12">
          <header className="grid gap-3">
            <p className="label-mono text-subtle">Docs · {doc.group}</p>
            <h1 className="text-h1 max-sm:text-h2">{doc.title}</h1>
            <p className="text-body-lg text-muted">{doc.description}</p>
          </header>
          {doc.sections.map((s) => (
            <section key={s.id} id={s.id} aria-labelledby={`${s.id}-h`} className="grid scroll-mt-[calc(var(--header-h)+16px)] gap-4">
              <h2 id={`${s.id}-h`} className="group flex items-center gap-2 text-h3">
                {s.title}
                <a href={`#${s.id}`} className="text-subtle opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100" aria-label={`Link to ${s.title}`}>
                  <Link2 className="size-4" aria-hidden />
                </a>
              </h2>
              {content[s.id]}
            </section>
          ))}
          <nav aria-label="Previous and next" className="grid grid-cols-2 gap-4 border-t border-border pt-6">
            {prev ? (
              <Link href={`/docs/${prev.slug}`} className="group grid gap-1 text-sm">
                <span className="flex items-center gap-1 text-xs text-subtle">
                  <ArrowLeft className="size-3" aria-hidden /> Previous
                </span>
                <span className="text-muted group-hover:text-foreground">{prev.title}</span>
              </Link>
            ) : (
              <span />
            )}
            {next ? (
              <Link href={`/docs/${next.slug}`} className="group grid justify-items-end gap-1 text-right text-sm">
                <span className="flex items-center gap-1 text-xs text-subtle">
                  Next <ArrowRight className="size-3" aria-hidden />
                </span>
                <span className="text-muted group-hover:text-foreground">{next.title}</span>
              </Link>
            ) : null}
          </nav>
        </article>
      </main>

      <aside className="hidden xl:block">
        <div className="sticky top-[calc(var(--header-h)+32px)]">
          <Toc sections={doc.sections} />
        </div>
      </aside>
    </div>
  );
}
