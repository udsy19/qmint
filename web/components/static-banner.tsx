import { SNAPSHOT_GIT_SHA, STATIC_SNAPSHOT } from "@/lib/api/static";

/** Site-wide notice in the static GitHub Pages export; renders nothing in the normal (live API) build. */
export function StaticBanner() {
  if (!STATIC_SNAPSHOT) return null;
  return (
    <div role="note" className="border-b border-border bg-surface px-4 py-1.5 text-center font-mono text-xs text-muted">
      Static snapshot of QMint (git {SNAPSHOT_GIT_SHA.slice(0, 12)}) — live experiments run locally
    </div>
  );
}
