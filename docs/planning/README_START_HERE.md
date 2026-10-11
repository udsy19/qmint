# Start here: QMint research & Claude Code multi-agent package

**Created:** 11 October 2026. **What this is:** an extensive execution-ready research plan and verified initial analytical-reference tests. **What it is not:** a completed quantum-payment security implementation, a new theorem or evidence of actual physical money.

## Contents

| File | Role |
|---|---|
| `QMINT_MASTER_RESEARCH_PLAN.md` | **Full technical science plan**, 16 sections: novel hypothesis, proofs, trust games, exact SDP, empirical data, fair classical competition, contracts, 18 benchmarks, 16-week roadmap, 14-lane organization, quality gates, paper and limitations |
| `CLAUDE_CODE_ORCHESTRATOR_PROMPT.md` | **Copy-and-paste primary prompt** to instruct Claude Code to build the project and launch agents safely |
| `AGENT_WORK_PACKAGES.md` | Full independent work orders and acceptance tests for agents A–N |
| `project/TRACKER_TEMPLATE.yaml` | Initial task/quality-gate truth tracker: everything starts OPEN, no false completion |
| `qmint/proofs/ideal_bounds.py` | Published ideal-model theorem bounds (supersedes the original `bootstrap/` reference, removed 2026-10-11) |
| `references/genqai-implementation-plan.md` | Your supplied GenQAI plan, preserved as organizational-format inspiration |

## Recommended way to use it with Claude Code

1. Create a new folder/repository for `qmint-research`, separate from ongoing QC-TRADE/GenQAI/Qollab/ECHO agents. Unzip this package into it.
2. Open Claude Code with this project folder as working directory.
3. Paste the **entire** contents of `CLAUDE_CODE_ORCHESTRATOR_PROMPT.md` in the same Claude Code session.
4. Let the lead freeze shared contracts and create a bootstrap SHA before it dispatches parallel agents from `AGENT_WORK_PACKAGES.md`. The lead owns merging; agent branches/worktrees stay isolated.
5. Review results at G0–G7, especially proof validity, actual dataset provenance, fair classical baselines, and whether the proposed compiler result survives independent checking.
6. Do not authorize paid hardware, remote pushes, publication or transactions unless you have checked the intended scope.

### Short terminal check (works without installing external packages)

```bash
python -m qmint.proofs.reproduce
python -m pytest tests/unit/proofs -q
```

Example **theoretical ideal-model** minimum lengths for `epsilon <= 10^-9` (not hardware security):

- Original Wiesner simple two-forgery game W1: **73** qubits, using `(3/4)^n`.
- Distinct Wiesner classical-verification variant: **273** qubits, using `(3/4 + sqrt(2)/8)^n`.
- Two-site ideal S-money S1: **131** qubits, using `(1/2 + 1/(2 sqrt(2)))^N`.

These are three **different game/protocol** targets; numbers are not interchangeable and must not be used to certify any realistic noisy/photonic implementation. They are a useful basic sanity test of the proof-registry architecture.

## Strongest verified research anchors

- Molina–Vidick–Watrous paper: https://arxiv.org/abs/1202.4010
- Kent et al. practical S-money: https://www.nature.com/articles/s41534-022-00524-4
- 2023 quantum payment experiment: https://www.nature.com/articles/s41467-023-39519-w
- Actual experimental photon data: https://doi.org/10.5281/zenodo.7979319
- Authors' published code DOI: https://doi.org/10.5281/zenodo.8020667
- 2024 experimental transaction-time advantage: https://arxiv.org/abs/2408.13063
- 2025 anonymous tokens with classical verification: https://arxiv.org/abs/2510.06212
- 2026 practical quantum token survey: https://arxiv.org/abs/2602.10621

**Research honesty:** This package contains a verified analytical-reference smoke program and detailed source-backed research instructions. It has **not** trained new cryptographic models, executed SDP attacks, downloaded the raw photon dataset, run QPU hardware, experimentally proved new security properties, or produced a real quantum-money system. Those are assigned future research tasks for the user's Claude Code environment.
