import type { Schemas } from "@/lib/api/client";

export type EntryKind = Schemas["ResearchEntry"]["kind"];

export const KIND_ORDER: EntryKind[] = ["paper", "theorem", "obligation", "dataset", "correction", "novelty"];

export const KIND_LABEL: Record<EntryKind, string> = {
  paper: "Papers",
  theorem: "Theorems",
  obligation: "Proof obligations",
  dataset: "Datasets",
  correction: "Corrections",
  novelty: "Novelty audit",
};

/** Singular label used as an eyebrow on detail pages. */
export const KIND_SINGULAR: Record<EntryKind, string> = {
  paper: "Paper",
  theorem: "Theorem",
  obligation: "Proof obligation",
  dataset: "Dataset",
  correction: "Correction",
  novelty: "Novelty audit",
};

export function isEntryKind(v: string | undefined): v is EntryKind {
  return !!v && (KIND_ORDER as string[]).includes(v);
}
