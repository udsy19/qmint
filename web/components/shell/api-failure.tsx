import { ErrorState } from "@/components/ui/state";

/** Shown when a server component cannot reach the research API. Says what failed and how to start it. */
export function ApiFailure({ what, kind, message }: { what: string; kind: string; message: string }) {
  return (
    <ErrorState
      timeout={kind === "timeout"}
      title={`Could not load ${what}`}
      description="The research API did not answer. Start it from the repository root, then reload this page."
      detail={
        <>
          {kind}: {message}
          <br />$ python -m uvicorn qmint.api.app:app --port 8787
        </>
      }
    />
  );
}
