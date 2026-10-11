import { CodeBlock } from "../code-block";
import { C, Callout, P, RefTable } from "../prose";

/**
 * Every command on this page was run on this checkout on 2026-10-11 (exit 0); timings are wall-clock on the
 * development machine and only indicate scale. Outputs are written to a directory you choose — nothing here writes
 * into the repository unless you point --out there.
 */
export const content = {
  doctor: (
    <>
      <CodeBlock code={`$ qmint doctor
$ qmint sources list --type paper | head -n 3`} />
      <P>
        <C>doctor</C> prints dependency status, lane entrypoints (<C>PRESENT</C> or <C>NOT_AVAILABLE</C>) and ends with{" "}
        <C>status: OK</C>. <C>sources list</C> prints one JSON object per row of <C>research/PRIOR_ART_MATRIX.csv</C> (24
        papers).
      </P>
    </>
  ),
  "reproduce-bounds": (
    <>
      <CodeBlock code={`$ python -m qmint.proofs.reproduce --out /tmp/qmint-proofs`} />
      <P>
        Recomputes every numerical example quoted by the registered sources and compares it with the paper (under a second,
        about one second). Each line reads <C>[ok] name: paper=… qmint=…</C>. Examples:
      </P>
      <RefTable
        head={["Check", "Paper", "QMint"]}
        rows={[
          ["W1 min length for ε ≤ 1e-9", "73", "73"],
          ["W1_CV min length for ε ≤ 1e-9", "273", "273"],
          ["S1 min length for ε ≤ 1e-9", "131", "131"],
          ["P_noqub at μ = 0.09 (Kent 2022)", "0.0038", "0.003815"],
          ["W1 n=2 SDP, certified upper bound vs exact dual", "0.562500000007276", "9/16"],
        ]}
        mono={[1, 2]}
      />
      <P>
        It writes <C>reproduction_v1.json</C> and example certificates checked by lane D&apos;s independent checker. Those
        are worked examples of the certificate format for the stated hypothetical parameters, not claims about a deployed
        system.
      </P>
    </>
  ),
  "attack-report": (
    <>
      <CodeBlock code={`$ python -m qmint.attacks.report --out /tmp/qmint-attacks.json --trials 2000 --seed 7`} />
      <P>
        Runs the lane C attack suite (about 20 s at 2 000 trials): heuristic counterfeiters as Monte Carlo lower bounds,
        the n = 1 and n = 2 W1 SDPs (<C>NUMERICAL_SDP</C>), and exact rational dual certificates (<C>CERTIFIED_NUMERIC</C>, for
        example 3/4 ≤ OPT₁ ≤ 0.750000000003638). Add <C>--clarabel-n2</C> for the Clarabel cross-check at n = 2, which needs
        about 6.5 GB of memory.
      </P>
    </>
  ),
  classical: (
    <>
      <CodeBlock code={`$ python -m qmint.classical.run_baselines --out /tmp/qmint-classical --pqc-reps 1`} />
      <P>
        Runs the classical comparators H0–H6 as deterministic state machines and writes 23 C6 <C>BenchmarkRecord</C>s
        (<C>MODELLED_LATENCY</C>), ML-DSA timings and <C>comparability_matrix.csv</C>, which states where quantum and classical
        rows are not comparable.
      </P>
    </>
  ),
  "core-run": (
    <>
      <CodeBlock code={`$ python scripts/run_core.py --offline --seed 42 --out /tmp/qmint-core`} />
      <P>
        Network is denied for the whole run. Stages whose lane has no <C>entrypoints</C> module yet are reported as{" "}
        <C>SKIPPED</C> with the reason; on this checkout that is every lane except L, so the run ends with{" "}
        <C>PASS=2 FAIL=0 SKIPPED=9</C> and a verified manifest. Use <C>--require-all</C> to turn skips into failures.
      </P>
      <Callout title="Why most stages skip">
        Lanes are merged as libraries and module CLIs (above); the uniform <C>qmint.&lt;lane&gt;.entrypoints</C> wrappers are
        being added by the integration lane. Until then <C>qmint simulate</C>, <C>qmint attacks</C> and the other lane commands
        print <C>NOT_AVAILABLE</C> and exit 3.
      </Callout>
    </>
  ),
  "api-calls": (
    <>
      <CodeBlock
        code={`$ curl -s localhost:8787/api/v1/meta/tracker | jq '.data.gates[] | [.gate_id, .status]'
$ curl -s localhost:8787/api/v1/research/sources/T-MVW12-THM1 | jq '.data.entry.title'
$ curl -s -X POST localhost:8787/api/v1/lab/attack \\
    -H 'content-type: application/json' \\
    -d '{"attack": "measure_resend", "n": 4, "backend": "analytic"}' | jq '.status, .data.theorem_bound.value'`}
      />
      <P>
        The attack call returns the MVW bound (3/4)⁴ = 0.31640625 as <C>PUBLISHED_THEOREM</C> and the exact
        measure-and-resend both-pass value (5/8)⁴ = 0.152587890625, each as a labelled <C>Quantity</C>. Its <C>status</C> and{" "}
        <C>reason</C> say which lane computed it.
      </P>
    </>
  ),
};
