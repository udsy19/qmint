import { ApiError, apiGet } from "@/lib/api/client";

type GetPath = Parameters<typeof apiGet>[0];
type Result<P extends GetPath> = Awaited<ReturnType<typeof apiGet<P>>>;

export type Loaded<T> = { ok: true; body: T } | { ok: false; kind: string; message: string };

/** Server-side GET that never throws: pages render an explicit error state instead of a 500. */
export async function load<P extends GetPath>(path: P, timeoutMs = 10_000): Promise<Loaded<Result<P>>> {
  try {
    return { ok: true, body: await apiGet(path, { timeoutMs }) };
  } catch (e) {
    const err = e instanceof ApiError ? e : new ApiError("network", (e as Error).message);
    return { ok: false, kind: err.kind, message: err.message };
  }
}
