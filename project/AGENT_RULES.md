# QMint agent rules (binding on every worker)

Repo: `/Users/udsy/PycharmProjects/Qollab-QMint` (branch `main`, lead-only).
Worktrees: `/Users/udsy/PycharmProjects/qmint-worktrees/<lane>` on branch `feat/<lane>-<task>`.
Shared Python env (DO NOT create another venv — disk is ~9 GB free):
`/Users/udsy/PycharmProjects/Qollab-QMint/.venv/bin/python` (numpy, scipy, cvxpy+SCS/Clarabel,
qiskit, qiskit-aer, qutip 5, pydantic 2, dilithium-py, requests, matplotlib, pandas, pytest, hypothesis, ruff).
Run tests from your worktree root: `$PY -m pytest tests/unit/<lane> tests/contracts -q`
(pytest `pythonpath=["."]` ensures your worktree's `qmint/` is imported).

1. Edit ONLY your owned paths (see your work order). Never edit `main`, `schemas/`, `qmint/core/contracts.py`,
   `qmint/core/serialization.py`, `qmint/core/interfaces.py`, `project/`, `pyproject.toml`, `requirements.lock`,
   root README, or another lane's files. Need a dependency or contract change? Write it in your handoff under
   `interfaces_changed` / `blockers` as a concrete proposal. Do not `uv pip install` into the shared venv
   unless your work order explicitly permits a named package.
2. Commit to your own branch with scoped `git add <your paths>`; never `git add -A`, never push, never
   force, never rebase/merge other branches, never delete unknown files.
3. No secrets, no paid hardware/credits, no real payments, no publication.
4. Evidence discipline: every number carries an `EvidenceKind`. Monte Carlo = lower bound on worst-case
   attack success. Numerical SDP ≠ proof unless residuals are rigorously accounted. Simulation ≠ physical
   security. Unknown bound = `None`/`UNCERTIFIED`, never 0. Never transfer a theorem across games
   (W1 ≠ W1_CV ≠ W2 ≠ S1 ≠ S2 ≠ D1 ≠ A1).
5. Sources: cite URL + theorem/equation/table anchor. If you could not read the primary source, say so
   and mark BLOCKED instead of reconstructing from memory. Do not copy third-party code without verifying
   its license; record attribution.
6. No bloat: reuse `qmint.core` contracts/serialization; no duplicate helpers; delete superseded code.
7. Handoff: write `handoffs/<lane>-<task>.json` + `.md` in your branch with fields: lane, task,
   input_contract_sha, branch, starting_commit_sha, final_commit_sha, changed_paths, commands_run,
   test_exit_codes, evidence_files, assumptions_verified, performance_numbers_with_sources, blockers,
   known_limitations, interfaces_changed, whether_paid_jobs_run. Report failures honestly.
