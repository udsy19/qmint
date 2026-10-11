"use client";

import { Check, Copy } from "lucide-react";
import * as React from "react";
import { toast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";

/**
 * Code block with a copy button. `code` is copied verbatim; lines starting with "$ " are shown with a quiet
 * prompt and copied without it, so copying a command never pastes the prompt.
 */
export function CodeBlock({ code, title, lang, className }: { code: string; title?: string; lang?: string; className?: string }) {
  const [copied, setCopied] = React.useState(false);
  const lines = code.replace(/\n$/, "").split("\n");
  const copyText = lines.map((l) => (l.startsWith("$ ") ? l.slice(2) : l)).join("\n");

  async function copy() {
    try {
      await navigator.clipboard.writeText(copyText);
      setCopied(true);
      toast("Copied to clipboard");
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      toast.error("Clipboard unavailable — select the text instead");
    }
  }

  return (
    <figure data-slot="code-block" className={cn("group/code relative min-w-0 overflow-hidden rounded-md border border-border bg-surface", className)}>
      {title || lang ? (
        <figcaption className="flex h-8 items-center justify-between border-b border-border pr-10 pl-3 font-mono text-[0.6875rem] text-subtle">
          <span className="truncate">{title}</span>
          {lang ? <span className="uppercase">{lang}</span> : null}
        </figcaption>
      ) : null}
      <pre className="overflow-x-auto px-3 py-2.5 font-mono text-[0.8125rem] leading-relaxed text-foreground">
        <code>
          {lines.map((l, i) => (
            <span key={i} className="block min-h-[1lh]">
              {l.startsWith("$ ") ? (
                <>
                  <span className="text-subtle select-none" aria-hidden>
                    ${" "}
                  </span>
                  {l.slice(2)}
                </>
              ) : l.startsWith("# ") ? (
                <span className="text-subtle">{l}</span>
              ) : (
                l
              )}
            </span>
          ))}
        </code>
      </pre>
      <button
        type="button"
        onClick={copy}
        aria-label={copied ? "Copied" : "Copy code"}
        className="absolute top-1 right-1 grid size-7 place-items-center rounded-sm text-subtle transition-colors duration-[var(--duration-instant)] hover:bg-surface-hover hover:text-foreground"
      >
        {copied ? <Check className="size-3.5" aria-hidden /> : <Copy className="size-3.5" aria-hidden />}
      </button>
    </figure>
  );
}
