/**
 * Evidence label registry. Source of truth is Python (qmint/ui/evidence_badges.py + API statuses),
 * exported by `pnpm gen:api` to lib/api/evidence-labels.json. Do not hand-edit labels here.
 */
import data from "@/lib/api/evidence-labels.json";

export type LabelGroup = "evidence_kind" | "certificate_status" | "api_status";
export type Origin = "theory" | "numeric" | "simulated" | "measured" | "none" | "api";
export type Tone = "ok" | "info" | "neutral" | "warn" | "danger";

export interface EvidenceLabelSpec {
  key: string;
  group: LabelGroup;
  label: string;
  css: string;
  origin: Origin;
  tone: Tone;
  title: string;
}

export const EVIDENCE_LABELS: readonly EvidenceLabelSpec[] = (data as { labels: EvidenceLabelSpec[] }).labels;

const BY_KEY = new Map<string, EvidenceLabelSpec>();
for (const l of EVIDENCE_LABELS) BY_KEY.set(`${l.group}:${l.key}`, l);

/** Look up a label. Evidence kinds and certificate statuses share keys (UNCERTIFIED), so the group matters. */
export function getEvidenceLabel(key: string, group: LabelGroup = "evidence_kind"): EvidenceLabelSpec {
  const spec = BY_KEY.get(`${group}:${key}`);
  if (!spec) throw new Error(`unknown evidence label ${group}:${key} — regenerate with pnpm gen:api`);
  return spec;
}
