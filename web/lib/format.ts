/**
 * Number formatting for scientific readouts. Mirrors qmint/ui/claims.py::fmt_number so the web and
 * Python surfaces agree: never turns a tiny probability into "0"; null renders as text, never 0.
 */
export const NO_BOUND = "no applicable bound";
export const NOT_REPORTED = "not reported";

export function formatNumber(v: number, opts: { sig?: number } = {}): string {
  const sig = opts.sig ?? 6;
  if (!Number.isFinite(v)) throw new Error("non-finite value reached a display surface");
  if (Number.isInteger(v) && Math.abs(v) < 1e6) return String(v);
  if (v === 0) return "0";
  const a = Math.abs(v);
  if (a < 1e-3 || a >= 1e6) {
    const [m, e] = v.toExponential(3).split("e");
    return `${m}e${Number(e) < 0 ? "−" : ""}${Math.abs(Number(e))}`;
  }
  return String(Number(v.toPrecision(sig)));
}

export function formatValue(v: number | null | undefined, missing: string = NOT_REPORTED): string {
  return v === null || v === undefined ? missing : formatNumber(v);
}

export function formatInterval(lo: number, hi: number): string {
  return `[${formatNumber(lo)}, ${formatNumber(hi)}]`;
}
