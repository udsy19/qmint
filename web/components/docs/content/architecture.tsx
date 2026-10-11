import Link from "next/link";
import { C, P, RefTable, UL } from "../prose";

const LANES: [string, string, string, string][] = [
  ["A", "research/", "Literature, theorem registry seed, prior-art matrix, corrections, novelty audit", "files"],
  ["B", "qmint.protocols", "Wiesner, Kent 2022 S-money and Schiansky 2023 payment state machines", "simulate"],
  ["C", "qmint.attacks", "Adversaries, Monte Carlo attacks, W1 Choi-matrix SDP with certified duals", "attacks"],
  ["D", "qmint.proofs", "Proof obligations, ideal and finite-size bounds, independent checker", "proofs"],
  ["E", "qmint.photonics", "Zenodo 7979319 photon timetags, QBER reproduction, calibration", "data"],
  ["F", "qmint.quantum", "BB84 circuits, noise channels, cloners, Qiskit/QuTiP cross-checks", "—"],
  ["G", "qmint.networks", "Discrete-event causal simulator, Jiang 2024 topologies, RIPE Atlas latency", "—"],
  ["H", "qmint.classical", "Classical double-spend baselines H0–H6 and the comparability matrix", "baselines"],
  ["I", "qmint.compiler", "Resource-optimised certificate compiler (in flight)", "compiler"],
  ["J", "qmint.quantum.ionq", "IonQ / Qollab hardware path (dry-run only)", "qollab"],
  ["K", "qmint.api · web/", "Research API and this website", "—"],
  ["L", "qmint.core", "Frozen contracts, records, configuration, pipeline", "doctor"],
  ["N", "qmint.evaluation", "Figures, benchmark plan, paper (in flight)", "figures · paper"],
];

const CONTRACTS: [string, string, string][] = [
  ["C0", "ProtocolSpec", "protocol_id must be registered in PROTOCOL_GAMES; the game must be one of that protocol's games"],
  ["C1", "TokenRecord, IssuerSecret", "public metadata rejects secret-like keys; IssuerSecret refuses serialisation and is redacted in repr"],
  ["C2", "MeasurementEvent, PhotonEvent, CalibrationRecord", "PHOTON_EXPERIMENT calibration requires a dataset SHA-256; fractions in [0, 1]; experiment family must match the consumer"],
  ["C3", "AttackResult", "successes ≤ trials; Monte Carlo requires a CI; SDP evidence requires primal, dual and dual residual"],
  ["C4", "SpacetimeNetwork, TransactionTrace", "links reference known sites; no retrocausal edges; local validation, settlement and irrevocability are distinct events"],
  ["C5", "SecurityCertificate, BoundRequest, BoundResult", "default UNCERTIFIED with null bounds; CERTIFIED only with met assumptions, proof ref, checker id, evidence hashes and every target bounded"],
  ["C6", "BenchmarkRecord, EvidenceManifest", "quantum/classical flag consistent with protocol id; every record carries evidence kind, git sha and environment lock"],
  ["C7", "enums, Interval, Unit", "BB84 (Z,0)=|0⟩ (Z,1)=|1⟩ (X,0)=|+⟩ (X,1)=|−⟩; no implicit little-endian decoding; time in ns; ε is a maximum adversary win probability, never an error bar"],
];

const GAMES: [string, string, string][] = [
  ["W1", "Molina–Vidick–Watrous 2012 simple 1→2 counterfeiting, exact verifier", "(3/4)^n"],
  ["W1_CV", "MVW classical-verification variant", "(3/4 + √2/8)^n"],
  ["W2", "Noisy / threshold Wiesner", "no closed form"],
  ["S1", "Kent et al. 2022 ideal two-site S-token", "(1/2 + 1/(2√2))^N"],
  ["S2", "Kent et al. 2022 realistic noisy/lossy S-token", "finite-size lemmas"],
  ["D1", "Schiansky et al. 2023 quantum-digital payment", "never certified"],
  ["A1", "Gavinsky et al. 2025 anonymity / issuer tracking", "not verified"],
  ["C1", "Classical double-spend systems game", "no theorem"],
];

export const content = {
  lanes: (
    <>
      <P>
        QMint is built by parallel research lanes, each owning one package or directory and merging through the lead. The
        live status of every lane and gate is on the{" "}
        <Link href="/app" className="text-foreground underline decoration-border-strong underline-offset-4">
          overview
        </Link>{" "}
        (read from <C>project/TRACKER.yaml</C>).
      </P>
      <RefTable head={["Lane", "Package", "Scope", "CLI"]} rows={LANES.map(([l, p, s, c]) => [l, p, s, c])} mono={[0, 1, 3]} />
    </>
  ),
  contracts: (
    <>
      <P>
        Lanes communicate only through frozen Pydantic v2 contracts in <C>qmint/core/contracts.py</C> (schema 1.0.0). JSON
        Schemas live in <C>schemas/v1/</C>, and their hashes are enforced by <C>tests/contracts</C>. Changes go to{" "}
        <C>schemas/v2/</C> through a lead-approved migration.
      </P>
      <RefTable head={["Contract", "Models", "Key invariants"]} rows={CONTRACTS.map((r) => [...r])} mono={[0]} />
    </>
  ),
  games: (
    <>
      <P>
        A bound is valid only for its own game. QMint never moves a theorem across games: W1 ≠ W1_CV ≠ W2 ≠ S1 ≠ S2 ≠ D1 ≠ A1.
        The registry with theorem anchors is at <C>GET /api/v1/games</C>.
      </P>
      <RefTable head={["Game", "Definition", "Bound"]} rows={GAMES.map((r) => [...r])} mono={[0, 2]} />
    </>
  ),
  "evidence-flow": (
    <>
      <P>A number reaches the screen through four steps, and keeps its label at each one:</P>
      <UL>
        <li>
          A lane computes it and wraps it in a contract (for example an <C>AttackResult</C> with <C>MONTE_CARLO</C> evidence and a
          Clopper–Pearson interval).
        </li>
        <li>
          The API turns it into a <C>Quantity</C>: value, unit, evidence kind, method, source and optional interval. A{" "}
          <C>null</C> value means “not available”, never 0.
        </li>
        <li>
          The response envelope adds <C>status</C> (<C>OK</C>, <C>DEMO_ADAPTER</C>, <C>NOT_AVAILABLE</C>), <C>reason</C> and{" "}
          <C>provenance</C> (git sha, time, seed, software versions).
        </li>
        <li>
          The web app renders the value next to its <C>EvidenceLabel</C>, generated from the same Python table.
        </li>
      </UL>
    </>
  ),
  web: (
    <>
      <P>
        The site is a Next.js App Router application in <C>web/</C>. The marketing route group serves <C>/</C>; the platform group
        wraps <C>/app</C>, <C>/lab/*</C>, <C>/benchmarks</C>, <C>/certificates</C>, <C>/research</C> and <C>/docs</C> in one
        shell (sidebar, breadcrumbs, ⌘K palette). Design tokens are in <C>app/globals.css</C>; primitives in{" "}
        <C>components/ui</C>; the typed client in <C>lib/api</C>.
      </P>
    </>
  ),
};
