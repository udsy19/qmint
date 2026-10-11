# Lead decisions log

- **D-001 (2026-10-11) Repository location.** The dedicated repo is `/Users/udsy/PycharmProjects/Qollab-QMint`
  (fresh `git init`, contains only the QMint package). Remote `origin` = https://github.com/udsy19/qmint
  (public, empty). No push without explicit human approval.
- **D-002 Shared environment.** Disk has ~9 GB free, so one shared `.venv` (Python 3.12, uv) in the main
  repo serves all worktrees; `requirements.lock` is the `uv pip compile` lock of `pyproject.toml[all]`.
  The `uv.lock` project lock in the plan is replaced by this pip-style lock (decision: lighter, no
  project install needed in worktrees).
- **D-003 PQC library.** liboqs C library not installed; H4 uses `dilithium-py` (pure-Python FIPS 204
  ML-DSA reference) as the standardized-signature baseline. Its timings are NOT representative of
  optimized implementations; recorded as such. liboqs may be added later.
- **D-004 Contracts frozen** at the bootstrap commit; schema hashes in `schemas/v1/SCHEMA_HASHES.json`.
- **D-005 Concurrency.** Lanes run as background Claude Code subagents in separate git worktrees under
  `/Users/udsy/PycharmProjects/qmint-worktrees/`. Each lane covers all its waves in its own branch;
  cross-lane consumers (I, K, M, N) are dispatched after their inputs are merged.
- **D-006 bootstrap/** stays until lane D's `qmint/proofs/ideal_bounds.py` supersedes it; lead deletes it at
  that merge (no dead code).
- **D-007 (2026-10-11) Website scope added to lane K** (user request): Next.js App Router site in `web/`
  (pnpm, hard-linked store to conserve disk), FastAPI research API in `qmint/api/` that wraps merged lane
  modules (no second backend), design docs in `docs/design/`. Static wave-1 workbench (`qmint/ui` HTML
  renderer, `app/site`) is superseded by `web/` and must be deleted once its views are covered; reusable
  evidence-badge/claim logic moves behind the API. Sub-agents work in worktrees `K-web-*` with disjoint
  subtrees of `web/`.
