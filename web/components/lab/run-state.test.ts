import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import { initialRunState, QUEUED_MS, runReducer, toFailure, useLabRun, validationMessages, type RunState } from "./run-state";

type S = RunState<string, number>;
const reduce = (s: S, a: Parameters<typeof runReducer<string, number>>[1]) => runReducer<string, number>(s, a);

describe("runReducer", () => {
  it("walks idle → queued → running → done and keeps the request that produced the data", () => {
    let s: S = initialRunState();
    s = reduce(s, { type: "submit", runId: 1, request: "a", at: 10 });
    expect(s.phase).toBe("queued");
    s = reduce(s, { type: "start", runId: 1 });
    expect(s.phase).toBe("running");
    s = reduce(s, { type: "succeed", runId: 1, data: 42, at: 30 });
    expect(s).toMatchObject({ phase: "done", data: 42, dataRequest: "a", startedAt: 10, finishedAt: 30 });
  });

  it("ignores actions from a superseded run and keeps previous data while re-running", () => {
    let s: S = reduce(initialRunState(), { type: "submit", runId: 1, request: "a", at: 0 });
    s = reduce(s, { type: "succeed", runId: 1, data: 1, at: 1 });
    s = reduce(s, { type: "submit", runId: 2, request: "b", at: 2 });
    expect(s.data).toBe(1);
    s = reduce(s, { type: "succeed", runId: 1, data: 99, at: 3 }); // stale
    expect(s).toMatchObject({ phase: "queued", data: 1 });
    s = reduce(s, { type: "fail", runId: 2, failure: { kind: "timeout", message: "t" }, at: 4 });
    expect(s.phase).toBe("timeout");
    expect(s.data).toBe(1);
  });

  it("maps validation and error failures to the error phase, cancel only while active", () => {
    let s: S = reduce(initialRunState(), { type: "submit", runId: 1, request: "a", at: 0 });
    s = reduce(s, { type: "fail", runId: 1, failure: { kind: "validation", message: "v" }, at: 1 });
    expect(s.phase).toBe("error");
    expect(reduce(s, { type: "cancel", runId: 1, at: 2 }).phase).toBe("error");
    s = reduce(s, { type: "submit", runId: 2, request: "b", at: 3 });
    expect(reduce(s, { type: "cancel", runId: 2, at: 4 }).phase).toBe("cancelled");
    expect(reduce(s, { type: "start", runId: 3 }).phase).toBe("queued");
  });
});

describe("toFailure", () => {
  it("classifies ApiError kinds; aborts are not failures", () => {
    expect(toFailure(new ApiError("aborted", "x"))).toBeNull();
    expect(toFailure(new ApiError("timeout", "x"))?.kind).toBe("timeout");
    expect(toFailure(new ApiError("http", "deadline", 504, "timeout"))?.kind).toBe("timeout");
    expect(toFailure(new ApiError("validation", "bad", 422, "validation_error", []))?.kind).toBe("validation");
    expect(toFailure(new ApiError("network", "down"))?.kind).toBe("error");
    expect(toFailure(new Error("boom"))).toEqual({ kind: "error", message: "boom" });
  });

  it("summarises pydantic validation details", () => {
    expect(validationMessages([{ loc: ["body", "n"], msg: "too big" }, { msg: "bad" }])).toEqual(["n: too big", "bad"]);
    expect(validationMessages("nope")).toEqual([]);
  });
});

describe("useLabRun", () => {
  it("resolves to done, and cancel aborts the in-flight request", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let seen: AbortSignal | undefined;
    const runner = vi.fn((req: string, signal: AbortSignal) => {
      seen = signal;
      return req === "slow"
        ? new Promise<number>((_, reject) => signal.addEventListener("abort", () => reject(new ApiError("aborted", "x"))))
        : Promise.resolve(7);
    });
    const { result } = renderHook(() => useLabRun<string, number>(runner));
    act(() => result.current.run("fast"));
    await waitFor(() => expect(result.current.state.phase).toBe("done"));
    expect(result.current.state.data).toBe(7);

    act(() => result.current.run("slow"));
    act(() => {
      vi.advanceTimersByTime(QUEUED_MS + 1);
    });
    expect(result.current.state.phase).toBe("running");
    act(() => result.current.cancel());
    expect(seen?.aborted).toBe(true);
    expect(result.current.state.phase).toBe("cancelled");
    expect(result.current.state.data).toBe(7);
    vi.useRealTimers();
  });
});
