# Contributing to QMint

Thanks for helping. QMint values **falsifiable, evidence-labelled claims** over impressive-sounding ones.

## Ground rules

1. **Every number carries an evidence kind** (`qmint/core/contracts.py` → `EvidenceKind`). A Monte Carlo estimate is a
   lower bound on attack success, a numerical SDP is not a proof unless residuals are rigorously accounted for, and a
   simulation is not physical security.
2. **Never transfer a theorem across games** (W1 ≠ W1_CV ≠ W2 ≠ S1 ≠ S2 ≠ D1). Unknown bounds are `None` / `UNCERTIFIED`,
   never 0.
3. **Contracts are frozen** (`schemas/v1`, hashes in `schemas/v1/SCHEMA_HASHES.json`). Changes go through a versioned
   migration, proposed in an issue.
4. **Negative results stay.** If you overturn a claim, add a failing test first, then the fix, and record it in
   `reports/paper/table4_negative_results.md` via `qmint/evaluation/tables.py`.
5. Cite primary sources with an equation/table/page anchor. Do not copy third-party code without checking its licence.

## Development

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.lock
uv pip install --python .venv/bin/python --no-deps -e .
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest -q -m "not network and not realdata and not slow"
cd web && pnpm install && pnpm typecheck && pnpm lint && pnpm test && pnpm build
```

Figures are generated, never hand-edited: `python -m qmint.evaluation.make_figures --out figures --tables-out reports/paper`
(a test fails if committed figures are stale). Regenerate the web API client with `cd web && pnpm gen:api`.

## Pull requests

Keep PRs scoped; include the test command and its output, the evidence kind of any new number, and any change to a
limitation or negative result. CI must pass.
