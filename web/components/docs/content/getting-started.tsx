import Link from "next/link";
import { DISCLOSURE_URL, LICENSE_URL, REPO_URL, SUPPORT_LINE } from "@/components/shell/support";
import { CodeBlock } from "../code-block";
import { A, C, Callout, P, UL } from "../prose";

export const content = {
  "what-qmint-is": (
    <>
      <P>
        QMint is an open-source research platform for quantum money and quantum payment security. It reproduces published
        bounds (Molina–Vidick–Watrous 2012, Kent et al. 2022, Schiansky et al. 2023), runs attack simulations, analyses a
        public photon dataset and compares quantum protocols with classical baselines. Every number it shows carries an
        evidence label that says where it came from.
      </P>
      <Callout title="Research platform, not a payment system">
        QMint does not issue money, run payments or provide a deployable quantum currency. Simulations are not hardware
        results, and a Monte Carlo attack rate is a lower bound on the worst case, not a security proof.
      </Callout>
    </>
  ),
  prerequisites: (
    <UL>
      <li>
        <strong>Python 3.11–3.13</strong> (<C>requires-python</C> in <C>pyproject.toml</C>) and{" "}
        <A href="https://docs.astral.sh/uv/">uv</A> for the environment.
      </li>
      <li>
        <strong>Node.js ≥ 20.9</strong> and <strong>pnpm 9</strong> for the web app. Use pnpm only; the lockfile is{" "}
        <C>web/pnpm-lock.yaml</C>.
      </li>
      <li>No API keys. Network access and paid hardware are off by default.</li>
    </UL>
  ),
  python: (
    <>
      <P>
        Dependencies are pinned in <C>requirements.lock</C>. Install them into a fresh virtual environment, then install
        the package itself without re-resolving dependencies.
      </P>
      <CodeBlock
        title="repository root"
        code={`$ uv venv
$ uv pip install -r requirements.lock
$ uv pip install --no-deps -e .
$ qmint doctor`}
      />
      <P>
        <C>qmint doctor</C> reports required and optional dependencies, drift from the lock, which lane entrypoints are
        present, and whether credential variables are set (booleans only, never values).
      </P>
    </>
  ),
  api: (
    <>
      <P>
        The website reads everything from one FastAPI service in <C>qmint/api</C>. It wraps the merged research lanes and
        labels every response with a status and an evidence kind.
      </P>
      <CodeBlock title="repository root" code={`$ python -m uvicorn qmint.api.app:app --port 8787`} />
      <P>
        Open <C>http://127.0.0.1:8787/docs</C> for FastAPI&apos;s interactive explorer, or read the{" "}
        <Link href="/docs/api" className="text-foreground underline decoration-border-strong underline-offset-4">
          API reference
        </Link>{" "}
        here.
      </P>
    </>
  ),
  web: (
    <>
      <CodeBlock
        title="web/"
        code={`$ pnpm install
$ pnpm dev
# http://localhost:3000 — /api/* is rewritten to the API on :8787`}
      />
      <P>
        Point the web app at another API with <C>QMINT_API_ORIGIN</C> (for example <C>QMINT_API_ORIGIN=http://127.0.0.1:8782 pnpm dev -p 3002</C>).
        Server components call the API directly; the browser always calls same-origin <C>/api/*</C>.
      </P>
      <P>
        After changing an API model, regenerate the typed client with <C>pnpm gen:api</C>. It rewrites{" "}
        <C>lib/api/openapi.json</C>, <C>schema.d.ts</C> and <C>evidence-labels.json</C>; never edit those by hand.
      </P>
    </>
  ),
  tests: (
    <>
      <CodeBlock
        title="repository root"
        code={`$ python -m pytest tests/contracts tests/unit -q
$ python -m pytest tests/unit/api -q
$ python -m ruff check qmint tests`}
      />
      <CodeBlock
        title="web/"
        code={`$ pnpm typecheck
$ pnpm lint
$ pnpm test
$ pnpm build
$ pnpm e2e`}
      />
      <P>
        Tests marked <C>slow</C>, <C>network</C> or <C>realdata</C> need large solvers, public network access or the
        downloaded Zenodo archive; see <C>pyproject.toml</C> for the markers.
      </P>
    </>
  ),
  "support-license": (
    <>
      <p className="border-l-2 border-border-strong pl-4 text-body-lg text-foreground">{SUPPORT_LINE}</p>
      <UL>
        <li>
          <strong>License.</strong> QMint&apos;s own code is MIT-licensed: <A href={LICENSE_URL}>LICENSE</A>. Third-party
          dependencies keep their own licences; no third-party source is vendored.
        </li>
        <li>
          <strong>Disclosure.</strong> <A href={DISCLOSURE_URL}>DISCLOSURE.md</A> lists the starting material, the
          published research that is reproduced (not invented here), the dependencies, and how AI assistance (Claude Code)
          was used under the human author&apos;s direction and review.
        </li>
        <li>
          <strong>Source.</strong> <A href={REPO_URL}>{REPO_URL.replace("https://", "")}</A>
        </li>
      </UL>
    </>
  ),
};
