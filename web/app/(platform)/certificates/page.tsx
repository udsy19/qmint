import type { Metadata } from "next";
import { connection } from "next/server";
import { Studio } from "@/components/certificates/studio";
import { ErrorState } from "@/components/ui/state";
import { ApiError, apiGet, type GetResponse } from "@/lib/api/client";
import { STATIC_SNAPSHOT } from "@/lib/api/static";

export const metadata: Metadata = { title: "Security Certificate Studio" };

async function load(): Promise<{ catalog?: GetResponse<"/api/v1/certificates/catalog">["data"]; error?: ApiError }> {
  try {
    return { catalog: (await apiGet("/api/v1/certificates/catalog")).data };
  } catch (e) {
    return { error: e instanceof ApiError ? e : new ApiError("network", String(e)) };
  }
}

export default async function Page() {
  if (!STATIC_SNAPSHOT) await connection(); // request-time render; the static export prerenders from the snapshot
  const { catalog, error } = await load();
  return (
    <main id="main" className="container-wide grid gap-10 py-10 md:py-14">
      <header className="grid max-w-3xl gap-4">
        <p className="label-mono text-subtle">Certificates · lane D proofs</p>
        <h1 className="text-h2 text-foreground md:text-h1">Security Certificate Studio</h1>
        <p className="text-body-lg text-muted">
          State the security you need and the conditions you can vouch for. The studio finds the published theorem that covers them, evaluates its bound, and asks an
          independent checker to re-derive every number. Only that checker can say CERTIFIED.
        </p>
      </header>
      {catalog ? (
        <Studio catalog={catalog} />
      ) : (
        <ErrorState
          timeout={error?.kind === "timeout"}
          title="The theorem catalog could not be loaded"
          description="The research API did not answer. Start it and reload."
          detail={`${error?.kind ?? "error"}: ${error?.message ?? ""} · $PY -m uvicorn qmint.api.app:app --port 8787`}
        />
      )}
    </main>
  );
}
