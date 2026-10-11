/**
 * Typed client for the QMint research API (qmint/api, FastAPI, /api/v1).
 * Types are generated: `pnpm gen:api` → lib/api/openapi.json → lib/api/schema.d.ts. Never hand-edit those.
 * All requests go same-origin to /api/* (Next rewrites to :8787), with a timeout and abort support.
 */
import type { components, paths } from "./schema";

export type Schemas = components["schemas"];
export type Quantity = Schemas["Quantity"];
export type ApiStatus = Schemas["MetaResponse"]["status"];

type JsonOf<T> = T extends { content: { "application/json": infer J } } ? J : never;
type GetPaths = { [P in keyof paths]: paths[P] extends { get: object } ? P : never }[keyof paths];
type PostPaths = { [P in keyof paths]: paths[P] extends { post: object } ? P : never }[keyof paths];
type Ok<Op> = Op extends { responses: { 200: infer R } } ? JsonOf<R> : never;
type Body<Op> = Op extends { requestBody: infer B } ? JsonOf<B> : Op extends { requestBody?: infer B } ? JsonOf<B> : never;
type Query<Op> = Op extends { parameters: { query?: infer Q } } ? Q : never;

export type GetResponse<P extends GetPaths> = Ok<paths[P]["get"]>;
export type PostResponse<P extends PostPaths> = Ok<paths[P]["post"]>;
export type PostBody<P extends PostPaths> = Body<paths[P]["post"]>;

export type ApiErrorKind = "http" | "validation" | "timeout" | "aborted" | "network" | "parse";

/** Every failure is an ApiError with a discriminating `kind`; UIs map kind → ErrorState copy. */
export class ApiError extends Error {
  constructor(
    readonly kind: ApiErrorKind,
    message: string,
    readonly status?: number,
    readonly code?: string,
    readonly detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export const DEFAULT_TIMEOUT_MS = 15_000;

export interface RequestOptions {
  signal?: AbortSignal;
  timeoutMs?: number;
  /** Absolute origin for server-side calls (RSC); browser calls stay same-origin. */
  baseUrl?: string;
  fetchImpl?: typeof fetch;
}

function baseUrl(opts: RequestOptions): string {
  if (opts.baseUrl) return opts.baseUrl;
  if (typeof window === "undefined") return process.env.QMINT_API_ORIGIN ?? "http://127.0.0.1:8787";
  return "";
}

async function request<T>(method: "GET" | "POST", path: string, opts: RequestOptions & { body?: unknown; query?: object }): Promise<T> {
  const timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const ctrl = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    ctrl.abort();
  }, timeoutMs);
  const onAbort = () => ctrl.abort();
  opts.signal?.addEventListener("abort", onAbort, { once: true });
  if (opts.signal?.aborted) ctrl.abort();

  let url = `${baseUrl(opts)}${path}`;
  if (opts.query) {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(opts.query)) if (v !== undefined && v !== null) qs.set(k, String(v));
    const s = qs.toString();
    if (s) url += `?${s}`;
  }

  let res: Response;
  try {
    res = await (opts.fetchImpl ?? fetch)(url, {
      method,
      signal: ctrl.signal,
      headers: { Accept: "application/json", ...(opts.body !== undefined ? { "Content-Type": "application/json" } : {}) },
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      cache: "no-store",
    });
  } catch (e) {
    if (timedOut) throw new ApiError("timeout", `${method} ${path} timed out after ${timeoutMs} ms`);
    if (ctrl.signal.aborted) throw new ApiError("aborted", `${method} ${path} was cancelled`);
    throw new ApiError("network", `${method} ${path} failed: ${(e as Error).message}`);
  } finally {
    clearTimeout(timer);
    opts.signal?.removeEventListener("abort", onAbort);
  }

  let payload: unknown;
  try {
    payload = await res.json();
  } catch {
    throw new ApiError("parse", `${method} ${path}: response was not JSON`, res.status);
  }
  if (!res.ok) {
    const err = (payload as Partial<Schemas["ApiError"]>)?.error;
    throw new ApiError(res.status === 422 ? "validation" : "http", err?.message ?? `HTTP ${res.status}`, res.status, err?.code, err?.detail);
  }
  return payload as T;
}

export function apiGet<P extends GetPaths>(path: P, opts: RequestOptions & { query?: Query<paths[P]["get"]> } = {}) {
  return request<GetResponse<P>>("GET", path, opts);
}

export function apiPost<P extends PostPaths>(path: P, body: PostBody<P>, opts: RequestOptions = {}) {
  return request<PostResponse<P>>("POST", path, { ...opts, body });
}
