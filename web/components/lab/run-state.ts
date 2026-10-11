"use client";

/**
 * Lab run state machine (pure reducer + hook).
 *
 *   idle ──submit──▶ queued ──(request still open after QUEUED_MS)──▶ running ──▶ done
 *                      │                                               ├──▶ error    (HTTP / validation / network)
 *                      │                                               ├──▶ timeout  (client timeout or HTTP 504)
 *                      └──────────────── cancel ───────────────────────┴──▶ cancelled
 *
 * "queued" means the request has been sent and is waiting for the API's single quantum worker; the
 * API has no progress channel, so the queued → running hand-off is a client-side estimate (QUEUED_MS)
 * and the copy says so. Every action carries the run id; actions from a superseded run are ignored,
 * so a slow response can never overwrite a newer one. The last successful result is kept while a new
 * run is in flight (shown dimmed) so the page never flashes empty.
 */
import * as React from "react";
import { ApiError } from "@/lib/api/client";

export type RunPhase = "idle" | "queued" | "running" | "done" | "error" | "timeout" | "cancelled";

export interface RunFailure {
  kind: "error" | "validation" | "timeout";
  message: string;
  status?: number;
  detail?: unknown;
}

export interface RunState<Req, Res> {
  phase: RunPhase;
  runId: number;
  request?: Req;
  /** Latest successful response (kept across later runs until replaced). */
  data?: Res;
  /** Request that produced `data`. */
  dataRequest?: Req;
  failure?: RunFailure;
  startedAt?: number;
  finishedAt?: number;
}

export type RunAction<Req, Res> =
  | { type: "submit"; runId: number; request: Req; at: number }
  | { type: "start"; runId: number }
  | { type: "succeed"; runId: number; data: Res; at: number }
  | { type: "fail"; runId: number; failure: RunFailure; at: number }
  | { type: "cancel"; runId: number; at: number };

export const QUEUED_MS = 250;
/** Server compute deadline is 20 s plus up to 25 s waiting for the single worker. */
export const CLIENT_TIMEOUT_MS = 50_000;

export function isActive(phase: RunPhase): boolean {
  return phase === "queued" || phase === "running";
}

export function initialRunState<Req, Res>(): RunState<Req, Res> {
  return { phase: "idle", runId: 0 };
}

export function runReducer<Req, Res>(state: RunState<Req, Res>, action: RunAction<Req, Res>): RunState<Req, Res> {
  if (action.type === "submit") {
    return { ...state, phase: "queued", runId: action.runId, request: action.request, failure: undefined, startedAt: action.at, finishedAt: undefined };
  }
  if (action.runId !== state.runId) return state; // stale run
  switch (action.type) {
    case "start":
      return state.phase === "queued" ? { ...state, phase: "running" } : state;
    case "succeed":
      if (!isActive(state.phase)) return state;
      return { ...state, phase: "done", data: action.data, dataRequest: state.request, finishedAt: action.at };
    case "fail":
      if (!isActive(state.phase)) return state;
      return { ...state, phase: action.failure.kind === "timeout" ? "timeout" : "error", failure: action.failure, finishedAt: action.at };
    case "cancel":
      if (!isActive(state.phase)) return state;
      return { ...state, phase: "cancelled", finishedAt: action.at };
  }
}

/** Map any thrown value to a RunFailure (null = the user cancelled; not a failure). */
export function toFailure(e: unknown): RunFailure | null {
  if (e instanceof ApiError) {
    if (e.kind === "aborted") return null;
    if (e.kind === "timeout" || e.status === 504) return { kind: "timeout", message: e.message, status: e.status };
    if (e.kind === "validation") return { kind: "validation", message: e.message, status: e.status, detail: e.detail };
    return { kind: "error", message: e.message, status: e.status, detail: e.detail };
  }
  return { kind: "error", message: e instanceof Error ? e.message : String(e) };
}

/** Human summary of a FastAPI/pydantic validation `detail` list. */
export function validationMessages(detail: unknown): string[] {
  if (!Array.isArray(detail)) return [];
  return detail.map((d) => {
    const item = d as { loc?: unknown[]; msg?: string };
    const loc = (item.loc ?? []).filter((x) => x !== "body").join(".");
    return loc ? `${loc}: ${item.msg ?? "invalid"}` : (item.msg ?? "invalid");
  });
}

export function useLabRun<Req, Res>(runner: (req: Req, signal: AbortSignal) => Promise<Res>) {
  const [state, dispatch] = React.useReducer(runReducer<Req, Res>, undefined, initialRunState<Req, Res>);
  const ctrl = React.useRef<AbortController | null>(null);
  const seq = React.useRef(0);
  const runnerRef = React.useRef(runner);
  React.useEffect(() => {
    runnerRef.current = runner;
  });

  const run = React.useCallback((request: Req) => {
    ctrl.current?.abort();
    const c = new AbortController();
    ctrl.current = c;
    const runId = ++seq.current;
    dispatch({ type: "submit", runId, request, at: performance.now() });
    const timer = setTimeout(() => dispatch({ type: "start", runId }), QUEUED_MS);
    runnerRef.current(request, c.signal)
      .then((data) => dispatch({ type: "succeed", runId, data, at: performance.now() }))
      .catch((e: unknown) => {
        const failure = toFailure(e);
        if (failure) dispatch({ type: "fail", runId, failure, at: performance.now() });
      })
      .finally(() => clearTimeout(timer));
  }, []);

  const cancel = React.useCallback(() => {
    ctrl.current?.abort();
    dispatch({ type: "cancel", runId: seq.current, at: performance.now() });
  }, []);

  React.useEffect(() => () => ctrl.current?.abort(), []);

  return { state, run, cancel };
}
