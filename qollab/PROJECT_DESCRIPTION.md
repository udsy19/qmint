# QMint — Proof-Carrying Quantum Money Benchmarks

**This effort is supported by Qollab & IonQ.**

**Demo video (2:32):** https://drive.google.com/file/d/1Q91bDAflNIMsbsbJLyPn0Bf0A6DAJHqJ/view?usp=sharing · **Website (static snapshot):** https://udsy19.github.io/qmint/ · **Code:** https://github.com/udsy19/qmint

QMint is an open-source research platform that asks a sharp question: *when does quantum money actually beat a well-engineered classical payment system — and how do we prove it, rather than claim it?* It reproduces the published security results for quantum tokens, attacks them with optimal adversaries, checks them against real photon data, and compares them with strong classical baselines. Every number carries an evidence label (theorem, certified numeric, Monte Carlo, simulator, real photon experiment), and negative results are reported as seriously as positive ones.

> Research platform, not money. Nothing here is a deployable banknote or a payment service, and a simulator copying a statevector is not "cloning".

## What this Qollab project runs (`main.py`)

One circuit, three experiments on a freshly minted Wiesner (BB84) banknote of *n* qubits:

| Block | What happens | Counterfeiter wins if |
|---|---|---|
| A. Honest note | The bank measures the untouched note in its secret bases | — (should always pass) |
| B. Phase-covariant cloner (Bruß et al. 2000) | One note → two notes, bank checks **both** | both copies pass |
| C. MVW optimal cloner (Molina–Vidick–Watrous 2012, §3.2) | Same game, with the provably optimal channel | both copies pass |

For each block the run prints the **measured** rate from the selected backend (with a 95% Wilson interval), the **exact model** value computed in NumPy, and the **published theorem bound** (3/4)^n (MVW 2012, Thm 1, game W1). The width is 7n qubits (n ≤ 3 on the 24-qubit built-in simulator, n ≤ 4 on IonQ's 29-qubit noise-model simulators).

**Run form:** `n_qubits` (1–4), `shots`, `seed`. Choose any backend: the built-in simulator (ideal) or IonQ Aria/Forte noise-model simulators (free).

### Results from Qollab runs

| Backend | n | Honest accepted | Phase-cov. both pass (exact) | MVW both pass (exact) | Bound (3/4)^n |
|---|---|---|---|---|---|
| Built-in simulator (ideal), 2000 shots, seed 7 | 3 | 1.0000 [0.9981, 1] | 0.3850 [0.3639, 0.4065] (0.3867) | 0.4135 [0.3921, 0.4352] (0.4219) | 0.4219 |
| IonQ Forte 1 noise-model simulator (free), 2000 shots, seed 7 | 3 | 0.9995 [0.9972, 0.9999] | 0.2075 [0.1903, 0.2258] (0.3867 ideal) | 0.2530 [0.2344, 0.2725] (0.4219 ideal) | 0.4219 |

On the ideal simulator the optimal cloner reaches the theorem bound (within shot noise) and nothing exceeds it. On IonQ's Forte 1 noise model the honest note, which needs single-qubit gates only, is still accepted 99.95% of the time. The cloners' entangling circuits, however, are degraded to roughly 60% of their ideal success. Under realistic gate noise the counterfeiter is hurt far more than the honest user. That is a property of this *circuit implementation*, not a security proof: the theorem bound is the only adversary guarantee, and in our full platform an exact-match verifier with many qubits becomes fragile once preparation/channel noise acts on the honest note itself.

## The problem it explores

A classical file can always be copied. Whether a copied token can be **spent twice** depends on trust, coordination and the verifier, not on the bits. Quantum states cannot be cloned perfectly, but no-cloning is only the start of a security proof: real protocols must handle noise, loss, finite statistics, verifier leakage, timing and insiders. QMint builds an auditable bridge from the theorems to concrete payment-security claims, and tests where quantum really helps.

## What the full platform does (github.com/udsy19/qmint)

- **Protocols:** Wiesner money; Kent et al. 2022 S-money (all four schemes from Tables 1–3); Schiansky et al. 2023 quantum-digital payments. Each has a strict challenger/adversary secret boundary.
- **Optimal attacks:** the 1→2 counterfeiting SDP (CVXPY) gives **0.75 at n=1 and 9/16 at n=2**, with an exact-rational certified bracket 3/4 ≤ OPT ≤ 0.750000000003638. That bracket was independently re-verified in a separate code path. Heuristic attacks are reported as Monte Carlo lower bounds with CIs.
- **Proof engine:** theorem registry with page/equation anchors, log-space bounds, Kent 2022 finite-size bounds, assumption checks. An independent checker is the only path to a "CERTIFIED" status.
- **Real photon data:** we decoded the Schiansky et al. 2023 Zenodo dataset (10.5281/zenodo.7979319): 8.96 M coincidences. We reproduce the paper's error rates: **1.449% (H/V) vs 1.45%** and **3.279% (D/A) vs 3.28%**.
- **Classical baselines (H0–H6):** copyable bearer token, atomic online ledger, sharded quorum, pre-allocated escrow, ML-DSA (FIPS 204) signed tokens, a secure-hardware trust model, and Chaum–Fiat–Naor e-cash. These run on a causal spacetime event simulator with paper-sourced (2.766 km / 60.54 km fibre) and real RIPE Atlas latencies.
- **Evidence-first web workbench** and FastAPI backend.

### Honest findings (including negative ones)

1. The specific basis-guess measure-and-resend attack we tested wins **(5/8)^n** (our own plan wrongly assumed (3/4)^n for it). This is an attack-specific probability, not a security bound: the bound over *all* counterfeiting strategies in game W1 is the published (3/4)^n (MVW 2012, Thm 1), which the optimal cloner attains.
2. Ideal S-money is **not coordination-free**: a bank relay precedes presentation (Kent 2022, Table I). A classical private late-commit escrow matches its local latency under computational assumptions. On matched topologies S-money has **no latency advantage** over that escrow; its only edge is one round trip over designs that consult an online ledger at the other site. What remains for quantum is information-theoretic (vs computational) security, not speed.
3. **Unresolved reproducibility finding (not an invalidation of the original work):** the 2023 paper's 5.9×10⁻⁴⁵ bound reproduces only with N = 4.2×10⁶ (the SI table lists 4,482,440), and we could not confirm that its Chernoff step, applied to a weighted error+loss sum, meets that bound's stated hypothesis (a conservatively rescaled version gives 3.3×10⁻⁷). We therefore do not certify it; the question is open for review by the authors and independent experts.
4. The published experimental tuple of Kent 2022 lies outside its own Theorem 1, as the paper says.
5. Real photon error rates are heterogeneous across runs (overdispersed, χ²/dof ≈ 10, driven by a few outlier runs; no evidence of monotone drift), so calibration intervals must be widened.
6. Our proposed contribution, a security-certificate compiler, matches an exhaustive oracle and passes an independent checker, but its apparent photon savings **do not survive calibration uncertainty**; it clears our pre-registered bar only on hypothetical devices.

## How to run it

- **On Qollab:** press **Run**, choose `n_qubits`, `shots`, `seed` and a backend. No setup needed.
- **Locally:** `pip install qiskit numpy` then `python -c "import main; main.main(3, 2000, 7)"`. With no Qollab `backend` it falls back to Qiskit's BasicSimulator.
- **Full platform:**
  ```bash
  git clone https://github.com/udsy19/qmint && cd qmint
  uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.lock
  .venv/bin/python -m pytest -q -m "not network and not realdata"   # full test suite
  .venv/bin/python -m qmint.proofs.reproduce                         # paper reproductions
  .venv/bin/python scripts/run_core.py --offline --seed 42           # deterministic pipeline
  ```

## How to reproduce or extend it

- Change `seed` and `n_qubits` to test other notes; compare measured vs exact vs bound.
- Add your own cloner: write its 8×2 isometry next to `bruss_isometry()` and append a block. The theorem guarantees you cannot beat (3/4)^n. If you seem to, check the statistics first.
- Swap the verifier for a threshold rule (the noisy game W2). The (3/4)^n theorem then **no longer applies**. The full platform shows a loss-reporting attacker winning outright, which marks the boundary of the published proof.
- Everything else (SDP, photon data, classical baselines, proofs) is reproducible from the GitHub repo; see `REPRODUCE`/`docs/REPRODUCIBILITY.md`.

## Disclosure, licence and credits

- **License:** MIT (`LICENSE` in the repo).
- **AI assistance:** code, tests, documents and website were written by Anthropic's Claude (Claude Code) as an orchestrator plus parallel sub-agents, directed and reviewed by the author. Starting material was a written research plan; no templates or forks were used; no third-party code was copied. See `DISCLOSURE.md`.
- **Prior work reproduced:** Molina, Vidick & Watrous 2012; Kent et al. 2022; Schiansky et al. 2023 (and its Zenodo dataset); Jiang et al. 2024; Bruß et al. 2000.

This effort is supported by Qollab & IonQ.
