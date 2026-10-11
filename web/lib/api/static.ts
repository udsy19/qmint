/**
 * Static-snapshot mode (GitHub Pages build, NEXT_PUBLIC_QMINT_STATIC=1).
 *
 * There is no API server: every response was precomputed by `scripts/build_static_site.py` with the real
 * FastAPI app and written to `public/snapshot/<method>/<path>/<sha256(canonical body)>.json`.
 * The key derivation here must match `canonical_json` / `snapshot_key` in that script byte-for-byte
 * (sorted keys, no whitespace, ECMAScript number formatting). Nothing is ever computed or fabricated
 * client-side: a request that was not precomputed fails with `SNAPSHOT_MISS_MESSAGE`.
 */

export const STATIC_SNAPSHOT = process.env.NEXT_PUBLIC_QMINT_STATIC === "1";
/** URL prefix of the exported site (next.config sets it from QMINT_BASE_PATH, default /qmint). */
export const STATIC_BASE_PATH = process.env.NEXT_PUBLIC_QMINT_BASE_PATH ?? "";
/** Git sha recorded in snapshot/meta.json at build time (next.config injects it). */
export const SNAPSHOT_GIT_SHA = process.env.NEXT_PUBLIC_QMINT_SNAPSHOT_SHA ?? "unknown";

export const SNAPSHOT_MISS_MESSAGE =
  "Static snapshot: this exact configuration wasn't precomputed — run QMint locally for live experiments";

/** Canonical JSON: object keys sorted, no whitespace, `undefined` members dropped (as JSON.stringify does). */
export function canonicalJson(value: unknown): string {
  if (value === null || typeof value !== "object") {
    if (typeof value === "number" && !Number.isFinite(value)) throw new TypeError("non-finite number in request body");
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return `[${value.map((v) => (v === undefined ? "null" : canonicalJson(v))).join(",")}]`;
  const entries = Object.entries(value as Record<string, unknown>)
    .filter(([, v]) => v !== undefined)
    .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0));
  return `{${entries.map(([k, v]) => `${JSON.stringify(k)}:${canonicalJson(v)}`).join(",")}}`;
}

export async function sha256Hex(text: string): Promise<string> {
  const digest = await globalThis.crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

/** Snapshot file for one request, relative to the snapshot root. GET keys hash the query object ({} if none). */
export async function snapshotPath(method: "GET" | "POST", path: string, payload: unknown): Promise<string> {
  const clean = path.replace(/^\/+/, "").replace(/\/+$/, "");
  const segments = clean.split("/").map((s) => encodeURIComponent(decodeURIComponent(s)));
  return `${method.toLowerCase()}/${segments.join("/")}/${await sha256Hex(canonicalJson(payload ?? {}))}.json`;
}

type NodeFs = { readFile(path: string, enc: "utf8"): Promise<string> };
type NodePath = { join(...p: string[]): string };

/**
 * Read one snapshot file. Server (build-time prerender): from `public/snapshot` on disk, via
 * `process.getBuiltinModule` so no bundler tries to resolve `fs` for the browser. Browser: same-origin fetch.
 * Resolves to null when the file does not exist.
 */
export async function readSnapshot(rel: string, fetchImpl: typeof fetch = fetch, signal?: AbortSignal): Promise<unknown | null> {
  if (typeof window === "undefined") {
    const proc = globalThis.process as unknown as { getBuiltinModule(id: string): unknown; cwd(): string };
    const fs = (proc.getBuiltinModule("node:fs") as { promises: NodeFs }).promises;
    const p = proc.getBuiltinModule("node:path") as NodePath;
    try {
      return JSON.parse(await fs.readFile(p.join(proc.cwd(), "public", "snapshot", ...rel.split("/").map(decodeURIComponent)), "utf8"));
    } catch (e) {
      if ((e as { code?: string }).code === "ENOENT") return null;
      throw e;
    }
  }
  const res = await fetchImpl(`${STATIC_BASE_PATH}/snapshot/${rel}`, { signal, headers: { Accept: "application/json" } });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`snapshot ${rel}: HTTP ${res.status}`);
  return res.json();
}
