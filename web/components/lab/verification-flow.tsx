import * as React from "react";
import type { Schemas } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { formatSerial } from "./token-strip";

type FlowStep = Schemas["FlowStep"];

const RESULT_TEXT: Record<FlowStep["result"], string> = {
  done: "done",
  accepted: "accepted",
  rejected: "rejected",
  refused: "refused",
  skipped: "skipped",
};

/** Bank lifecycle from lane B: mint → transmit → verify (spend once) → replay refused → remint. */
export function VerificationFlow({ steps, className }: { steps: FlowStep[]; className?: string }) {
  return (
    <ol className={cn("grid", className)} aria-label="Verification flow">
      {steps.map((s, i) => (
        <li key={s.id} className="relative grid grid-cols-[20px_1fr] gap-x-3 pb-5 last:pb-0">
          {i < steps.length - 1 ? <span aria-hidden className="absolute top-5 bottom-0 left-[9.5px] w-px bg-border" /> : null}
          <StepGlyph result={s.result} />
          <div className="grid min-w-0 gap-0.5">
            <p className="flex flex-wrap items-baseline gap-x-2 text-sm">
              <span className="text-foreground">{s.label}</span>
              <span
                className={cn(
                  "label-mono",
                  s.result === "accepted" && "text-foreground",
                  s.result === "rejected" && "text-danger",
                  s.result === "refused" && "text-warn",
                  (s.result === "done" || s.result === "skipped") && "text-subtle",
                )}
              >
                {RESULT_TEXT[s.result]}
              </span>
            </p>
            <p className="text-xs text-muted">{s.detail}</p>
            {s.serial ? <p className="font-mono text-[0.6875rem] text-subtle">{formatSerial(s.serial)}</p> : null}
          </div>
        </li>
      ))}
    </ol>
  );
}

function StepGlyph({ result }: { result: FlowStep["result"] }) {
  return (
    <svg viewBox="0 0 20 20" className="mt-0.5 size-5" aria-hidden>
      <circle cx="10" cy="10" r="5.5" className={cn("fill-background", result === "skipped" ? "stroke-border" : "stroke-border-strong")} strokeDasharray={result === "skipped" ? "2 2" : undefined} />
      {result === "accepted" ? <path d="M7.4 10.2 9.2 12l3.4-3.8" className="fill-none stroke-foreground" strokeWidth="1.4" /> : null}
      {result === "done" ? <circle cx="10" cy="10" r="2" className="fill-muted" /> : null}
      {result === "rejected" ? <path d="M7.8 7.8l4.4 4.4M12.2 7.8l-4.4 4.4" className="stroke-danger" strokeWidth="1.4" /> : null}
      {result === "refused" ? <path d="M7.2 10h5.6" className="stroke-warn" strokeWidth="1.6" /> : null}
    </svg>
  );
}
