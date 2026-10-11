import { cn } from "@/lib/utils";

/** Editorial section shell: Pixel numeral + mono kicker on a 3-column rail, headline on the remaining 9. */
export function Section({
  id,
  index,
  kicker,
  title,
  lead,
  children,
  className,
}: {
  id: string;
  index: string;
  kicker: string;
  title: React.ReactNode;
  lead?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className={cn("border-t border-border py-24 md:py-32 xl:py-40", className)}>
      <div className="container-wide">
        <header className="grid gap-6 md:grid-cols-12 md:gap-8">
          <div className="flex items-baseline gap-4 md:col-span-3 md:flex-col md:gap-3">
            <span aria-hidden className="font-pixel text-[2.5rem] leading-none text-foreground md:text-[3.5rem]">
              {index}
            </span>
            <span className="label-mono text-subtle">{kicker}</span>
          </div>
          <div className="grid gap-5 md:col-span-9">
            <h2 id={`${id}-title`} className="max-w-[20ch] text-h1 text-balance md:text-display">
              <span className="sr-only">{index}. </span>
              {title}
            </h2>
            {lead ? <p className="max-w-[60ch] text-body-lg text-muted">{lead}</p> : null}
          </div>
        </header>
        <div className="mt-16 md:mt-20">{children}</div>
      </div>
    </section>
  );
}
