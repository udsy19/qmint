"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { DOC_GROUPS, DOCS } from "./registry";

/** Left documentation navigation (desktop rail; rendered inside a disclosure on small screens). */
export function DocsNav({ className }: { className?: string }) {
  const pathname = usePathname() ?? "";
  return (
    <nav aria-label="Documentation" className={cn("grid content-start gap-5", className)}>
      {DOC_GROUPS.map((g) => (
        <div key={g} className="grid gap-1">
          <p className="label-mono px-2 text-subtle">{g}</p>
          <ul className="grid gap-px">
            {DOCS.filter((d) => d.group === g).map((d) => {
              const active = pathname === `/docs/${d.slug}`;
              return (
                <li key={d.slug}>
                  <Link
                    href={`/docs/${d.slug}`}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex h-8 items-center rounded-sm px-2 text-sm transition-colors duration-[var(--duration-instant)]",
                      active ? "bg-surface-raised text-foreground" : "text-muted hover:bg-surface-hover hover:text-foreground",
                    )}
                  >
                    {d.title}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}
