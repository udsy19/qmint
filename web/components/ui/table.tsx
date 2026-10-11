import * as React from "react";
import { cn } from "@/lib/utils";

/** Dense data table. Numbers: add `numeric` to Th/Td for right-aligned tabular mono figures. */
export function Table({ className, ...props }: React.ComponentProps<"table">) {
  return (
    <div data-slot="table-container" className="relative w-full overflow-x-auto">
      <table className={cn("w-full caption-bottom border-collapse text-sm", className)} {...props} />
    </div>
  );
}
export function THead({ className, ...props }: React.ComponentProps<"thead">) {
  return <thead className={cn("[&_tr]:border-b [&_tr]:border-border", className)} {...props} />;
}
export function TBody({ className, ...props }: React.ComponentProps<"tbody">) {
  return <tbody className={cn("[&_tr:last-child]:border-0", className)} {...props} />;
}
export function Tr({ className, ...props }: React.ComponentProps<"tr">) {
  return (
    <tr
      className={cn(
        "border-b border-hairline transition-colors duration-[var(--duration-instant)] hover:bg-surface/60 data-[state=selected]:bg-surface-raised",
        className,
      )}
      {...props}
    />
  );
}
export function Th({ className, numeric, ...props }: React.ComponentProps<"th"> & { numeric?: boolean }) {
  return (
    <th
      scope="col"
      className={cn("label-mono h-8 px-3 text-left align-middle font-medium text-subtle first:pl-0 last:pr-0", numeric && "text-right", className)}
      {...props}
    />
  );
}
export function Td({ className, numeric, ...props }: React.ComponentProps<"td"> & { numeric?: boolean }) {
  return (
    <td
      className={cn("h-10 px-3 align-middle text-foreground first:pl-0 last:pr-0", numeric && "tnum text-right font-mono text-[0.8125rem]", className)}
      {...props}
    />
  );
}
export function TableCaption({ className, ...props }: React.ComponentProps<"caption">) {
  return <caption className={cn("mt-3 text-left text-xs text-subtle", className)} {...props} />;
}
