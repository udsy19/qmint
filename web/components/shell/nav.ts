import { BookOpen, ChartColumn, CircleDot, Crosshair, FileCheck2, LayoutGrid, Library, type LucideIcon } from "lucide-react";

/** Platform navigation — the single source for the sidebar, mobile sheet, breadcrumbs and ⌘K palette. */
export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  description: string;
  keywords?: string[];
}

export interface NavGroup {
  label: string | null;
  items: NavItem[];
}

export const NAV: NavGroup[] = [
  {
    label: null,
    items: [{ href: "/app", label: "Overview", icon: LayoutGrid, description: "Gates, lanes, games and recent records", keywords: ["dashboard", "home", "status"] }],
  },
  {
    label: "Lab",
    items: [
      { href: "/lab/mint", label: "Mint", icon: CircleDot, description: "Prepare and verify a BB84 token", keywords: ["token", "qubit", "circuit", "wiesner"] },
      { href: "/lab/attack", label: "Attack", icon: Crosshair, description: "Counterfeiting and double-verification", keywords: ["counterfeit", "cloner", "adversary"] },
    ],
  },
  {
    label: "Analysis",
    items: [
      { href: "/benchmarks", label: "Benchmarks", icon: ChartColumn, description: "Quantum vs classical under matched assumptions", keywords: ["latency", "classical", "compare"] },
      { href: "/certificates", label: "Certificates", icon: FileCheck2, description: "Security certificate studio", keywords: ["bound", "epsilon", "proof"] },
    ],
  },
  {
    label: "Library",
    items: [
      { href: "/research", label: "Research", icon: Library, description: "Papers, theorems, obligations, datasets", keywords: ["papers", "citations", "doi", "theorem"] },
      { href: "/docs", label: "Docs", icon: BookOpen, description: "Developer documentation", keywords: ["api", "cli", "reference"] },
    ],
  },
];

export const NAV_ITEMS: NavItem[] = NAV.flatMap((g) => g.items);

/** Path segments that are not routes of their own (rendered as plain text, not links). */
const GROUP_SEGMENTS: Record<string, string> = { lab: "Lab" };

export function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export interface Crumb {
  /** null for grouping segments that have no page (e.g. /lab). */
  href: string | null;
  label: string;
}

/**
 * Breadcrumbs from the pathname. `resolve` names dynamic segments (doc slugs, research ids);
 * unknown segments fall back to the raw segment, decoded.
 */
export function crumbsFor(pathname: string, resolve?: (href: string, segment: string) => string | undefined): Crumb[] {
  const parts = pathname.split("/").filter(Boolean);
  const out: Crumb[] = [];
  parts.forEach((seg, i) => {
    const href = `/${parts.slice(0, i + 1).join("/")}`;
    const item = NAV_ITEMS.find((n) => n.href === href);
    if (!item && i === 0 && GROUP_SEGMENTS[seg]) {
      out.push({ href: null, label: GROUP_SEGMENTS[seg] });
      return;
    }
    const label = item?.label ?? resolve?.(href, seg) ?? decodeURIComponent(seg);
    out.push({ href, label });
  });
  return out;
}
