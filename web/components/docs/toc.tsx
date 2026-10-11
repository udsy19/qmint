"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import type { DocSectionMeta } from "./registry";

/** "On this page" with scroll-spy: the section nearest the top of the viewport is marked current. */
export function Toc({ sections }: { sections: DocSectionMeta[] }) {
  const [active, setActive] = React.useState<string | null>(sections[0]?.id ?? null);
  React.useEffect(() => {
    const els = sections.map((s) => document.getElementById(s.id)).filter((e): e is HTMLElement => !!e);
    if (!els.length || typeof IntersectionObserver === "undefined") return;
    const visible = new Map<string, number>();
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) visible.set(e.target.id, e.boundingClientRect.top);
          else visible.delete(e.target.id);
        }
        const first = sections.find((s) => visible.has(s.id));
        if (first) setActive(first.id);
      },
      { rootMargin: "-56px 0px -60% 0px" },
    );
    els.forEach((e) => io.observe(e));
    return () => io.disconnect();
  }, [sections]);

  return (
    <nav aria-label="On this page" className="grid content-start gap-2">
      <p className="label-mono text-subtle">On this page</p>
      <ul className="grid gap-px border-l border-border">
        {sections.map((s) => (
          <li key={s.id}>
            <a
              href={`#${s.id}`}
              aria-current={active === s.id ? "location" : undefined}
              className={cn(
                "-ml-px block border-l py-1 pl-3 text-xs leading-5 transition-colors duration-[var(--duration-instant)]",
                active === s.id ? "border-accent text-foreground" : "border-transparent text-subtle hover:text-foreground",
              )}
            >
              {s.title}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
