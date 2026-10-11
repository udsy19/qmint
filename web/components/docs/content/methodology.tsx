import Link from "next/link";
import { EvidenceLabel } from "@/components/ui/evidence-label";
import { EVIDENCE_LABELS, type LabelGroup } from "@/lib/evidence";
import { C, P, RefTable, UL } from "../prose";

/** Quantity.method values (qmint/api/schemas.py) with the meaning stated in the source comments. */
const METHODS: [string, string][] = [
  ["closed_form", "a transcribed or derived formula evaluated exactly"],
  ["exact_enumeration", "exact model value from enumerating outcomes or Kraus operators"],
  ["aer_sampling", "shot-sampled local Aer simulation; carries a confidence interval"],
  ["event_simulation", "lane G discrete-event timing simulation"],
  ["published_value", "a number quoted from a paper"],
  ["measured_dataset", "a statistic of a committed real measurement dataset"],
  ["not_available", "no value; shown as text, never as 0"],
];

function LabelTable({ group }: { group: LabelGroup }) {
  const rows = EVIDENCE_LABELS.filter((l) => l.group === group);
  return (
    <RefTable
      head={["Label", "Key", "Meaning"]}
      rows={rows.map((l) => [<EvidenceLabel key={l.key} kind={l.key} group={group} showTooltip={false} />, l.key, l.title])}
      mono={[1]}
    />
  );
}

export const content = {
  principles: (
    <UL>
      <li>
        <strong>Every number carries an evidence kind.</strong> A theorem value, an SDP output, a Monte Carlo estimate and a
        photon measurement are never interchangeable and never shown without their label.
      </li>
      <li>
        <strong>Monte Carlo is a lower bound</strong> on worst-case attack success, always with its interval. It is never
        presented as an upper bound or a proof.
      </li>
      <li>
        <strong>Numerical SDP is not a proof</strong> unless residuals are rigorously accounted (that is{" "}
        <C>CERTIFIED_NUMERIC</C>, re-verified in exact arithmetic by lane D).
      </li>
      <li>
        <strong>Simulation is not physical security.</strong> No QPU result exists in this build (gate G6 is skipped).
      </li>
      <li>
        <strong>Unknown is null, never 0.</strong> An unknown bound is <C>null</C> / <C>UNCERTIFIED</C> and renders as text.
      </li>
      <li>
        <strong>No theorem crosses games.</strong> W1 ≠ W1_CV ≠ W2 ≠ S1 ≠ S2 ≠ D1 ≠ A1. ε is a maximum adversary win probability,
        never an error bar.
      </li>
      <li>
        <strong>Sources are cited to an anchor</strong> (URL plus theorem, equation or table). If a primary source could not be
        read, the entry says so instead of reconstructing it from memory.
      </li>
    </UL>
  ),
  "evidence-kinds": (
    <>
      <P>
        The glyph shape encodes origin — theory ■, numeric ◩, simulated □, measured ●, none ×, API ◇ — and its colour encodes
        tone. The table is generated from <C>qmint/ui/evidence_badges.py</C> via <C>pnpm gen:api</C>, the same source the
        API uses.
      </P>
      <LabelTable group="evidence_kind" />
    </>
  ),
  "certificate-statuses": (
    <>
      <P>
        Only <C>CERTIFIED</C> is shown in mint, and only when the frozen C5 contract allows it: assumptions met, proof
        reference, checker id, evidence hashes and every target bounded.
      </P>
      <LabelTable group="certificate_status" />
    </>
  ),
  "api-statuses": (
    <>
      <P>
        Every API response has a <C>status</C>. <C>OK</C> means a merged lane&apos;s code path produced it. The other two
        always carry a <C>reason</C>:
      </P>
      <LabelTable group="api_status" />
    </>
  ),
  methods: (
    <>
      <P>
        <C>Quantity.method</C> disambiguates how a value was computed — for example an exact analytic value that the frozen
        contract labels <C>SIMULATOR_IDEAL</C>.
      </P>
      <RefTable head={["Method", "Meaning"]} rows={METHODS.map((r) => [...r])} />
    </>
  ),
  verification: (
    <P>
      Research-library entries keep the verification status from their own file — <C>VERIFIED_FROM_SOURCE</C> and{" "}
      <C>NOT_VERIFIED</C> per transcribed theorem field, <C>FULL_TEXT_READ</C> / <C>ABSTRACT_READ</C> / <C>METADATA_ONLY</C> per
      paper, proof statuses such as <C>PUBLISHED_REPRODUCED</C> per obligation. Definitions and their source files are listed
      under “Verification status definitions” in the{" "}
      <Link href="/research" className="text-foreground underline decoration-border-strong underline-offset-4">
        research library
      </Link>
      .
    </P>
  ),
};
