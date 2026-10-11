# Disclosure: starting material, dependencies and AI assistance

This effort is supported by Qollab & IonQ.

**Starting material.** The project began from a research specification package written before
implementation: `QMINT_MASTER_RESEARCH_PLAN.md`, `CLAUDE_CODE_ORCHESTRATOR_PROMPT.md`,
`AGENT_WORK_PACKAGES.md`, `project/TRACKER_TEMPLATE.yaml`, and a 70-line stdlib reference of three published
ideal bounds (later superseded by `qmint/proofs/ideal_bounds.py` and deleted). `references/genqai-implementation-plan.md`
is an organisational-format inspiration from a separate project. No templates or forks of other repositories
were used; no third-party source code was copied (see `licenses/REFERENCE_AUDIT.md`, `datasets/DATA_LICENSES.md`).

**AI assistance.** The code, tests, documents and website in this repository were written by Anthropic's Claude
(Claude Code; model Claude Opus 5.5) acting as a lead orchestrator plus parallel sub-agents working in
isolated git worktrees, under the direction and review of the human author (Udaya Tejas). Commits carry a
`Co-Authored-By: Claude` trailer. Every numerical claim is tied to an executed script, a published source,
or a real dataset, and labelled with its evidence kind; see `project/TRACKER.yaml` and `handoffs/`.

**Published research reproduced (not invented here).** Wiesner/Molina–Vidick–Watrous 2012 bounds, Kent et al. 2022
S-money, Schiansky et al. 2023 quantum-digital payments (and their Zenodo photon dataset 10.5281/zenodo.7979319,
CC-BY), Jiang et al. 2024. See `research/PRIOR_ART_MATRIX.csv`.

**Dependencies** (installed, not vendored): NumPy, SciPy, Pydantic, CVXPY/SCS/Clarabel, Qiskit, Qiskit Aer, QuTiP,
qiskit-ionq, dilithium-py, FastAPI, Next.js/React and others — each under its own open-source licence. QMint's own
code is MIT-licensed (`LICENSE`).
