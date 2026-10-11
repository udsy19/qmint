import Link from "next/link";
import { Disclosure } from "@/components/ui/disclosure";
import type { Schemas } from "@/lib/api/client";

type Field = Schemas["EntryField"];

/** Field keys shown as the lead statement of an entry (first match wins). */
export const LEAD_FIELDS = ["statement_verbatim", "statement_summary", "precise_theorem", "source_and_theorem", "observation", "text"];

const LONG_CODE_LINES = 10;

/**
 * Renders a research record field-by-field: label column + value column on wide screens, stacked on
 * mobile. LaTeX is shown as source (Mono) and labelled as such — no renderer is bundled, and
 * a mis-rendered formula would be worse than readable source.
 */
export function EntryFields({ fields, knownIds = [] }: { fields: Field[]; knownIds?: string[] }) {
  const ids = new Set(knownIds);
  if (!fields.length) return <p className="text-sm text-subtle">No further fields.</p>;
  return (
    <dl className="grid border-t border-border">
      {fields.map((f) => (
        <div key={f.key} className="grid gap-x-8 gap-y-1.5 border-b border-hairline py-3.5 md:grid-cols-[200px_minmax(0,1fr)]">
          <dt className="text-xs text-subtle md:pt-0.5">
            <span className="text-muted">{f.label}</span>
            <span className="block font-mono text-[0.625rem] text-subtle">{f.key}</span>
          </dt>
          <dd className="min-w-0">
            <FieldValue f={f} ids={ids} />
          </dd>
        </div>
      ))}
    </dl>
  );
}

function FieldValue({ f, ids }: { f: Field; ids: Set<string> }) {
  if (f.kind === "text" && f.text && ids.has(f.text.trim())) {
    return (
      <Link href={`/research/${encodeURIComponent(f.text.trim())}`} className="font-mono text-sm text-foreground underline decoration-border-strong underline-offset-4 hover:decoration-foreground">
        {f.text.trim()}
      </Link>
    );
  }
  if (f.kind === "list") {
    return (
      <ul className="grid max-w-[46rem] gap-1.5 text-sm leading-relaxed text-foreground">
        {(f.items ?? []).map((it, i) => (
          <li key={i} className="grid grid-cols-[12px_minmax(0,1fr)]">
            <span className="text-subtle" aria-hidden>
              –
            </span>
            <span className="break-words">{it}</span>
          </li>
        ))}
      </ul>
    );
  }
  if (f.kind === "latex") {
    return (
      <figure className="grid gap-1">
        <pre className="overflow-x-auto rounded-sm border border-border bg-surface px-3 py-2.5 font-mono text-[0.8125rem] leading-relaxed whitespace-pre-wrap text-foreground">{f.text}</pre>
        <figcaption className="label-mono text-subtle">LaTeX source</figcaption>
      </figure>
    );
  }
  if (f.kind === "code") {
    const text = f.text ?? "";
    const pre = (
      <pre className="overflow-x-auto rounded-sm border border-border bg-surface px-3 py-2.5 font-mono text-xs leading-relaxed text-muted">{text}</pre>
    );
    if (text.split("\n").length <= LONG_CODE_LINES) return pre;
    return (
      <Disclosure title="Show structured value" meta={`${text.split("\n").length} lines`} className="border-t-0">
        {pre}
      </Disclosure>
    );
  }
  return <p className="max-w-[46rem] text-sm leading-relaxed break-words whitespace-pre-line text-foreground">{f.text}</p>;
}
