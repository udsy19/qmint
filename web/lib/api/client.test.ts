import { describe, expect, it, vi } from "vitest";
import { ApiError, apiGet, apiPost } from "./client";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("api client", () => {
  it("returns typed JSON on 200", async () => {
    const fetchImpl = vi.fn(async () => json(200, { ok: true }));
    const res = await apiGet("/api/v1/health", { fetchImpl, baseUrl: "" });
    expect(res).toEqual({ ok: true });
    expect(fetchImpl).toHaveBeenCalledWith("/api/v1/health", expect.objectContaining({ method: "GET" }));
  });

  it("maps the ApiError body and 422 to kind=validation", async () => {
    const fetchImpl = vi.fn(async () => json(422, { error: { code: "validation_error", message: "n_qubits must be ≤ 8" } }));
    const err = await apiPost("/api/v1/lab/mint", { protocol_id: "wiesner_ideal", n_qubits: 9, seed: 1 } as never, { fetchImpl, baseUrl: "" }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.kind).toBe("validation");
    expect(err.code).toBe("validation_error");
    expect(err.message).toContain("≤ 8");
  });

  it("times out with kind=timeout", async () => {
    const fetchImpl = vi.fn(
      (_url: string | URL | Request, init?: RequestInit) =>
        new Promise<Response>((_, reject) => init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")))),
    );
    const err = await apiGet("/api/v1/meta", { fetchImpl: fetchImpl as typeof fetch, baseUrl: "", timeoutMs: 10 }).catch((e) => e);
    expect(err.kind).toBe("timeout");
  });

  it("reports caller aborts as kind=aborted", async () => {
    const ctrl = new AbortController();
    ctrl.abort();
    const fetchImpl = vi.fn(
      (_url: string | URL | Request, init?: RequestInit) =>
        new Promise<Response>((_, reject) => (init?.signal?.aborted ? reject(new DOMException("aborted", "AbortError")) : undefined)),
    );
    const err = await apiGet("/api/v1/meta", { fetchImpl: fetchImpl as typeof fetch, baseUrl: "", signal: ctrl.signal }).catch((e) => e);
    expect(err.kind).toBe("aborted");
  });
});
