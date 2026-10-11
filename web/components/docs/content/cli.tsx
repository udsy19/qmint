import { CodeBlock } from "../code-block";
import { C, P, RefTable } from "../prose";

/** Mirrors qmint/cli.py and qmint/core/lanes.py::LANE_COMMANDS at the time of writing (checked by running --help). */
const LANE_COMMANDS: [string, string, string][] = [
  ["data", "E", "fetch/validate public photonic datasets"],
  ["proofs", "D", "verify published bounds / SDP primal-dual"],
  ["simulate", "B", "protocol simulations (wiesner, smoney, ...)"],
  ["attacks", "C", "attack suites"],
  ["baselines", "H", "classical baseline protocols"],
  ["compiler", "I", "certificate compiler optimize/verify"],
  ["benchmark", "N", "frozen benchmark plan"],
  ["figures", "N", "regenerate figures from records"],
  ["paper", "N", "build paper from evidence"],
  ["qollab", "J", "optional Qollab export"],
];

export const content = {
  usage: (
    <>
      <CodeBlock
        code={`$ qmint --help
usage: qmint [-h] {doctor,sources,data,proofs,simulate,attacks,baselines,compiler,benchmark,figures,paper,qollab} ...`}
      />
      <P>
        <C>qmint</C> is installed by <C>uv pip install -e .</C> (<C>[project.scripts]</C> in <C>pyproject.toml</C>);{" "}
        <C>python -m qmint.cli</C> is equivalent. <C>doctor</C> and <C>sources</C> are built in. Every other command is
        dispatched lazily to its lane&apos;s entrypoint module; nothing is fabricated when a lane is missing.
      </P>
    </>
  ),
  builtin: (
    <RefTable
      head={["Command", "Effect"]}
      rows={[
        ["qmint doctor [--json] [--report PATH]", "Environment and dependency report; exit 0 when status is OK."],
        ["qmint sources list [--type paper|dataset|all]", "One JSON object per lane A source (PRIOR_ART_MATRIX.csv, DATASOURCE_REGISTER.yaml)."],
      ]}
    />
  ),
  "lane-commands": (
    <>
      <P>
        Each command forwards its arguments, including <C>--help</C>, to <C>qmint.&lt;lane&gt;.entrypoints.cli_main</C>. On this
        checkout no lane ships that module yet, so each prints <C>NOT_AVAILABLE: lane X module … not merged</C> and exits 3; use
        the module entrypoints below instead.
      </P>
      <RefTable head={["Command", "Lane", "Purpose"]} rows={LANE_COMMANDS.map((r) => [...r])} mono={[0, 1]} />
    </>
  ),
  "exit-codes": (
    <RefTable
      head={["Code", "Meaning"]}
      rows={[
        ["0", "ok"],
        ["1", "failure (including doctor status other than OK)"],
        ["2", "usage error"],
        ["3", "NOT_AVAILABLE — the lane module is not merged"],
        ["4", "BROKEN — the lane module exists but failed to import"],
      ]}
    />
  ),
  modules: (
    <>
      <P>Merged lanes expose these runnable modules today. All are deterministic for a given seed and offline unless stated.</P>
      <RefTable
        head={["Module", "Lane", "Writes"]}
        rows={[
          ["python -m qmint.proofs.reproduce --out DIR", "D", "reproduction_v1.json + example certificates"],
          ["python -m qmint.attacks.report --out FILE [--trials N] [--seed S] [--clarabel-n2]", "C", "attack + SDP evidence JSON"],
          ["python -m qmint.classical.run_baselines --out DIR [--pqc-reps N]", "H", "23 BenchmarkRecords, PQC timings, comparability matrix"],
          ["python -m qmint.photonics.schiansky2023 --out DIR", "E", "QBER reproduction + calibration (needs the Zenodo archive in the data cache)"],
          ["python scripts/run_core.py --offline --seed 42", "L", "stage table, status JSON, verified manifest"],
          ["python scripts/verify_manifest.py PATH…", "L", "re-hashes manifests; exit 1 on mismatch"],
          ["python -m qmint.api.export [--out DIR]", "K", "openapi.json + evidence-labels.json for the web client"],
        ]}
        mono={[0, 1]}
      />
    </>
  ),
};
