/**
 * Certificate Studio form model: converts between the API request and editable text fields.
 * Pure (unit-tested). It never computes a bound — only qmint.proofs on the API does.
 */
import type { Schemas } from "@/lib/api/client";

export type CertRequest = Schemas["CertificateRequest"];
export type CertData = Schemas["CertificateData"];
export type Catalog = Schemas["CatalogData"];
export type GameEntry = Schemas["GameEntry"];
export type GameId = Schemas["GameId"];
export type Axis = Schemas["SecurityAxis"];
export type CalibrationSource = CertRequest["calibration"];
export type NoiseSource = NonNullable<CertRequest["noise_source"]>;

export const AXES: { key: Axis; label: string; symbol: string }[] = [
  { key: "epsilon_unf", label: "Unforgeability", symbol: "ε_unf" },
  { key: "epsilon_cor", label: "Correctness", symbol: "ε_cor" },
  { key: "epsilon_rob", label: "Robustness", symbol: "ε_rob" },
  { key: "epsilon_priv", label: "Privacy", symbol: "ε_priv" },
];

/** Parameters that must stay integers (sizes, site exponent, pair count). */
export const INTEGER_PARAMS = new Set(["n", "N", "M", "C"]);

export interface ParamField {
  mode: "point" | "interval";
  value: string;
  lo: string;
  hi: string;
}

export interface FormState {
  game: GameId;
  protocolId: string | null;
  targets: Record<Axis, string>;
  params: Record<string, ParamField>;
  honestError: string;
  declared: string[];
  noiseSource: NoiseSource | "";
  calibration: CalibrationSource;
}

const num = (v: number) => String(v);

export function emptyField(): ParamField {
  return { mode: "point", value: "", lo: "", hi: "" };
}

/** Parameter names the editor shows for a game: the theorem's own parameters, else a size. */
export function paramNames(entry: GameEntry | undefined, current: Record<string, ParamField> = {}): string[] {
  const base = entry?.theorem ? Object.keys(entry.theorem.parameters) : ["n"];
  return [...base, ...Object.keys(current).filter((k) => !base.includes(k))];
}

export function fromRequest(req: CertRequest): FormState {
  const params: Record<string, ParamField> = {};
  for (const [k, v] of Object.entries(req.parameters ?? {})) {
    params[k] = typeof v === "number" ? { mode: "point", value: num(v), lo: "", hi: "" } : { mode: "interval", value: "", lo: num(v.lo), hi: num(v.hi) };
  }
  const t = req.targets ?? {};
  return {
    game: req.game,
    protocolId: req.protocol_id ?? null,
    targets: {
      epsilon_unf: t.epsilon_unf != null ? num(t.epsilon_unf) : "",
      epsilon_cor: t.epsilon_cor != null ? num(t.epsilon_cor) : "",
      epsilon_rob: t.epsilon_rob != null ? num(t.epsilon_rob) : "",
      epsilon_priv: t.epsilon_priv != null ? num(t.epsilon_priv) : "",
    },
    params,
    honestError: req.honest_error_tolerance != null ? num(req.honest_error_tolerance) : "",
    declared: [...(req.declared_assumptions ?? [])],
    noiseSource: req.noise_source ?? "",
    calibration: req.calibration ?? "none",
  };
}

/** Defaults when switching game: the first preset for that game, else an empty theorem form. */
export function defaultsForGame(game: GameId, catalog: Catalog): FormState {
  const preset = catalog.presets.find((p) => p.request.game === game);
  if (preset) return fromRequest(preset.request);
  const entry = catalog.games.find((g) => g.game === game);
  const params: Record<string, ParamField> = {};
  for (const k of paramNames(entry)) params[k] = emptyField();
  return {
    game,
    protocolId: null,
    targets: { epsilon_unf: "1e-9", epsilon_cor: "", epsilon_rob: "", epsilon_priv: "" },
    params,
    honestError: "",
    declared: [],
    noiseSource: "",
    calibration: "none",
  };
}

function parseNumber(s: string): number | null {
  const t = s.trim().replace(/−/g, "-").replace(/×\s*10\^?/g, "e");
  if (!t) return null;
  const v = Number(t);
  return Number.isFinite(v) ? v : NaN;
}

export type FieldErrors = Record<string, string>;

/** Build the API request; returns field errors instead when an input is not a valid number. */
export function toRequest(s: FormState): { request: CertRequest; errors: FieldErrors } {
  const errors: FieldErrors = {};
  const targets: NonNullable<CertRequest["targets"]> = {};
  for (const a of AXES) {
    const v = parseNumber(s.targets[a.key]);
    if (v === null) continue;
    if (Number.isNaN(v) || !(v > 0 && v < 1)) errors[`target.${a.key}`] = "a probability strictly between 0 and 1";
    else targets[a.key] = v;
  }
  const parameters: NonNullable<CertRequest["parameters"]> = {};
  for (const [k, f] of Object.entries(s.params)) {
    if (f.mode === "point") {
      const v = parseNumber(f.value);
      if (v === null) continue;
      if (Number.isNaN(v)) errors[`param.${k}`] = "not a number";
      else if (INTEGER_PARAMS.has(k) && !Number.isInteger(v)) errors[`param.${k}`] = "must be an integer";
      else parameters[k] = v;
    } else {
      const lo = parseNumber(f.lo);
      const hi = parseNumber(f.hi);
      if (lo === null && hi === null) continue;
      if (lo === null || hi === null || Number.isNaN(lo) || Number.isNaN(hi)) errors[`param.${k}`] = "interval needs a numeric lo and hi";
      else if (lo > hi) errors[`param.${k}`] = "lo must not exceed hi";
      else parameters[k] = { lo, hi };
    }
  }
  const tol = parseNumber(s.honestError);
  if (tol !== null && (Number.isNaN(tol) || tol < 0 || tol >= 0.5)) errors.honestError = "a fraction in [0, 0.5)";
  const request: CertRequest = {
    game: s.game,
    protocol_id: s.protocolId,
    targets,
    parameters,
    honest_error_tolerance: tol === null || Number.isNaN(tol) ? null : tol,
    declared_assumptions: s.declared,
    noise_source: s.noiseSource || null,
    calibration: s.calibration,
  };
  return { request, errors };
}

/** Preview of the API's calibration check (the API decides): ideal games admit no measured noise at all. */
export function calibrationPreview(entry: GameEntry | undefined, family: string | null | undefined): "none" | "match" | "mismatch" | "ideal" {
  if (!family) return "none";
  if (entry?.sizing_available) return "ideal";
  return entry?.theorem?.calibration_families.includes(family) ? "match" : "mismatch";
}
