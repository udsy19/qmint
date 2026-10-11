import * as React from "react";
import { Button } from "@/components/ui/button";
import { ErrorState, StateMessage } from "@/components/ui/state";
import { validationMessages, type RunFailure, type RunPhase } from "./run-state";

/** Error / timeout / cancelled copy: what happened, why, what to do next. */
export function RunFailurePanel({ phase, failure, onRetry }: { phase: RunPhase; failure?: RunFailure; onRetry: () => void }) {
  if (phase === "cancelled") {
    return (
      <StateMessage
        kind="empty"
        title="Run cancelled"
        description="The request was aborted in the browser. The server may finish its current computation, but the result is discarded."
        action={<Button size="sm" onClick={onRetry}>Run again</Button>}
      />
    );
  }
  if (!failure) return null;
  if (failure.kind === "timeout") {
    return (
      <ErrorState
        timeout
        title="The experiment took too long"
        description="Each run has a 20 s compute budget on a single quantum worker. Reduce qubits, shots or trials and try again."
        detail={failure.message}
        action={<Button size="sm" onClick={onRetry}>Retry</Button>}
      />
    );
  }
  if (failure.kind === "validation") {
    const msgs = validationMessages(failure.detail);
    return (
      <ErrorState
        title="The API rejected these parameters"
        description={msgs.length ? <span className="grid gap-0.5">{msgs.map((m) => <span key={m}>{m}</span>)}</span> : failure.message}
        detail={`HTTP ${failure.status ?? 422} · validation_error`}
      />
    );
  }
  return (
    <ErrorState
      title="The lab API could not run this experiment"
      description="Check that the research API is running (python -m uvicorn qmint.api.app:app) and retry."
      detail={`${failure.status ? `HTTP ${failure.status} · ` : ""}${failure.message}`}
      action={<Button size="sm" onClick={onRetry}>Retry</Button>}
    />
  );
}
