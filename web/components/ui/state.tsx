import { AlertTriangle, CircleDashed, Clock, Unplug } from "lucide-react";
import * as React from "react";
import { cn } from "@/lib/utils";

type Kind = "empty" | "error" | "timeout" | "unavailable";

const ICON: Record<Kind, React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>> = {
  empty: CircleDashed,
  error: AlertTriangle,
  timeout: Clock,
  unavailable: Unplug,
};

/**
 * Empty / error / timeout / not-available states. Quiet, left-aligned inside panels, centred in pages.
 * Copy must say what happened, why, and what the user can do — and for NOT_AVAILABLE, which lane/
 * capability is missing. Errors use role="alert"; the rest role="status".
 */
export function StateMessage({
  kind,
  title,
  description,
  action,
  detail,
  align = "start",
  className,
}: {
  kind: Kind;
  title: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactNode;
  /** Technical detail (error code, request id) shown in mono. */
  detail?: React.ReactNode;
  align?: "start" | "center";
  className?: string;
}) {
  const Icon = ICON[kind];
  const isError = kind === "error" || kind === "timeout";
  return (
    <div
      role={isError ? "alert" : "status"}
      data-state-kind={kind}
      className={cn(
        "flex flex-col gap-3 py-8",
        align === "center" ? "items-center text-center" : "items-start",
        className,
      )}
    >
      <Icon className={cn("size-5", isError ? "text-danger" : kind === "unavailable" ? "text-warn" : "text-subtle")} aria-hidden />
      <div className="grid max-w-md gap-1">
        <p className="text-sm font-medium text-foreground">{title}</p>
        {description ? <p className="text-sm text-muted">{description}</p> : null}
        {detail ? <p className="mt-1 font-mono text-xs break-all text-subtle">{detail}</p> : null}
      </div>
      {action ? <div className="mt-1">{action}</div> : null}
    </div>
  );
}

export function EmptyState(props: Omit<React.ComponentProps<typeof StateMessage>, "kind">) {
  return <StateMessage kind="empty" {...props} />;
}
export function ErrorState(props: Omit<React.ComponentProps<typeof StateMessage>, "kind"> & { timeout?: boolean }) {
  const { timeout, ...rest } = props;
  return <StateMessage kind={timeout ? "timeout" : "error"} {...rest} />;
}
export function UnavailableState(props: Omit<React.ComponentProps<typeof StateMessage>, "kind">) {
  return <StateMessage kind="unavailable" {...props} />;
}
