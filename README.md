# QMint — proof-carrying quantum money benchmarks

[![ci](https://github.com/udsy19/qmint/actions/workflows/ci.yml/badge.svg)](https://github.com/udsy19/qmint/actions/workflows/ci.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](pyproject.toml)

**This effort is supported by Qollab & IonQ.**

**Website:** https://udsy19.github.io/qmint/ (static snapshot) ·
**Run it on Qollab:** https://qollab.xyz/u/udsy/qmint-proof-carrying-quantum-m ·
**Demo video (2:32):** https://drive.google.com/file/d/1Q91bDAflNIMsbsbJLyPn0Bf0A6DAJHqJ/view?usp=sharing

QMint is an open-source research platform that asks one question carefully: *when does quantum money actually beat a
well-engineered classical payment system, and how do we prove it rather than claim it?* It reproduces published
quantum-token security results, attacks them with optimal adversaries, checks them against real photon data, and
compares them with strong classical baselines on identical networks. Every number carries an evidence label
(published theorem, certified numeric, Monte Carlo, simulator, real photon experiment, modelled latency), and negative
results are reported as prominently as positive ones.

> **Research platform, not money.** Nothing here is a deployable banknote, a payment service, or a security
> certification of any device. A simulator copying a statevector is not "cloning".

## Key results

| Result | Value | Evidence |
|---|---|---|
| Optimal 1→2 Wiesner counterfeiting (game W1), n = 1 | SDP 0.75; exact certified bracket 3/4 ≤ OPT ≤ 0.750000000003638, re-verified in a separate exact-rational code path | `CERTIFIED_NUMERIC` (reproduces Molina–Vidick–Watrous 2012) |
| Same, n = 2 | 9/16 ≤ OPT ≤ 0.562500000007276 | `CERTIFIED_NUMERIC` |
| Real photon data, Schiansky et al. 2023 (Zenodo 10.5281/zenodo.7979319) | 8.96 M coincidences; QBER 1.4491 % (H/V) and 3.2787 % (D/A) vs published 1.45 % / 3.28 % | `PHOTON_EXPERIMENT` |
| Qollab run, n = 3, built-in simulator | honest 1.000; MVW optimal cloner 0.4135 [0.392, 0.435] vs bound (3/4)³ = 0.4219 | `SIMULATOR_IDEAL` |
| Qollab run, n = 3, IonQ Forte 1 noise model (free) | honest 0.9995; MVW cloner 0.2530 [0.234, 0.273] | `SIMULATOR_NOISY` |
| S-money vs classical, matched topologies | S-money's only latency edge is one round trip over designs that consult a remote online ledger (27.66 µs on the 2.766 km Jinan link); **none** over a classical private late-commit escrow | `MODELLED_LATENCY` |

### Negative results and corrections (kept deliberately)

1. The tested basis-guess measure-and-resend attack wins **(5/8)ⁿ** — an attack-specific value, not a bound. The bound
   over all strategies is the published (3/4)ⁿ, which the optimal cloner attains.
2. Ideal S-money is not coordination-free (a bank relay precedes presentation, Kent et al. 2022 Table I). What remains for
   quantum is information-theoretic vs computational security, not speed.
3. **Unresolved reproducibility finding (not an invalidation):** the 2023 paper's 5.9×10⁻⁴⁵ bound reproduces only with
   N = 4.2×10⁶, and we could not confirm that its Chernoff step meets that bound's stated hypothesis. QMint does not
   certify it.
4. Kent et al. 2022's experimental tuple lies outside its own Theorem 1, as the paper says.
5. Photon runs are overdispersed (χ²/dof ≈ 10): run-to-run heterogeneity, not drift (run-level Welch test p = 0.33 / 0.59).
6. The certificate compiler's apparent photon savings **do not survive calibration uncertainty**; it passes the
   pre-registered bar only on hypothetical devices.
7. An exact-match Wiesner verifier is fragile: 1–2 % readout error drops honest acceptance to 0.14 at n = 128.

Full ledger: [`reports/paper/table4_negative_results.md`](reports/paper/table4_negative_results.md) ·
red-team audit: [`audits/`](audits/).

## What is in the repository

| Path | Contents |
|---|---|
| `qmint/protocols` | Wiesner money; Kent et al. 2022 S-money (IQT1/IQT2/QT1/QT2); Schiansky et al. 2023 quantum-digital payments — each with a strict challenger/adversary secret boundary |
| `qmint/attacks` | Counterfeiting SDP (CVXPY) with certified dual bounds, heuristic attacks (Monte Carlo lower bounds), negative controls |
| `qmint/proofs` | Theorem registry with page/equation anchors, log-space ideal bounds, Kent 2022 finite-size bounds, independent checker (the only path to `CERTIFIED`) |
| `qmint/photonics` | Zenodo download + checksum, streaming parser, coincidence matching, calibration with widened intervals |
| `qmint/quantum` | Qiskit / Aer / QuTiP / NumPy cross-checked BB84 circuits, noise channels, photonic source model, IonQ provenance (dry-run only) |
| `qmint/networks`, `qmint/classical` | Causal discrete-event simulator; classical baselines H0–H6 (ledger, quorum, escrow, ML-DSA, secure hardware, e-cash) |
| `qmint/compiler` | Pre-registered certificate compiler vs published/naive/exhaustive selectors |
| `qmint/api`, `web/` | FastAPI research API and the Next.js website/workbench |
| `qmint/core`, `schemas/v1` | Frozen data contracts C0–C7, canonical serialization, evidence manifests, CLI |
| `qollab/` | Self-contained one-circuit `main.py` that runs on Qollab (Pyodide) |
| `research/`, `proofs/`, `audits/`, `figures/`, `reports/` | Prior-art register, proof dossiers, red-team audit, generated figures and tables |
| `docs/` | Reproducibility, design system, static site, and the original [research plan](docs/planning/QMINT_MASTER_RESEARCH_PLAN.md) |

## Quick start

Requirements: Python 3.12, [uv](https://docs.astral.sh/uv/), Node ≥ 20 with pnpm (website only).

```bash
git clone https://github.com/udsy19/qmint && cd qmint
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.lock
uv pip install --python .venv/bin/python --no-deps -e .

.venv/bin/python -m pytest -q -m "not network and not realdata and not slow"   # test suite
.venv/bin/qmint doctor                                                          # environment report
.venv/bin/qmint proofs verify --game W1 --n 1 --method sdp --primal-dual        # optimal-attack SDP
.venv/bin/python -m qmint.proofs.reproduce                                      # paper reproductions
.venv/bin/python scripts/run_core.py --offline --seed 42                        # deterministic pipeline
```

Real photon data (optional, ~153 MB): `QMINT_ALLOW_NETWORK=1 .venv/bin/qmint data fetch zenodo:7979319`, then
`.venv/bin/python -m pytest -m realdata`.

### Website and API

```bash
.venv/bin/python -m uvicorn qmint.api.app:app --port 8787    # research API
cd web && pnpm install && pnpm dev                            # http://localhost:3000 (proxies /api to :8787)
```

The public site is a static export with precomputed API responses — see [`docs/STATIC_SITE.md`](docs/STATIC_SITE.md).
Rebuild and deploy with `scripts/build_static_site.py` and `pnpm build:static` (or the manual `pages` workflow).

### On Qollab

Open the [Qollab project](https://qollab.xyz/u/udsy/qmint-proof-carrying-quantum-m), press **Run**, choose `n_qubits`,
`shots`, `seed` and a free backend (built-in simulator or IonQ noise models). Locally:
`cd qollab && python -c "import main; main.main(3, 2000, 7)"`.

## Scope and limitations

No physical quantum hardware was run (free IonQ noise-model simulators only; paid jobs are refused in code). S-money
double spending is not simulated in the network model; scenarios have two sites; RIPE latency data covers one hour and
three probes; the post-quantum signature baseline uses the pure-Python `dilithium-py` reference. Lower-severity red-team
items remain open as strict expected-failure tests. See [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md) and the
website's Limitations page.

## Citing, contributing, security

- Cite with [`CITATION.cff`](CITATION.cff). Prior work reproduced: Molina, Vidick & Watrous 2012; Kent et al. 2022;
  Schiansky et al. 2023 (and its Zenodo dataset); Jiang et al. 2024; Bruß et al. 2000.
- Contributions: [`CONTRIBUTING.md`](CONTRIBUTING.md). Security reports: [`SECURITY.md`](SECURITY.md).
- Disclosure of starting material and AI assistance: [`DISCLOSURE.md`](DISCLOSURE.md).

## License

MIT — see [`LICENSE`](LICENSE). Third-party datasets and papers keep their own licences
([`datasets/DATA_LICENSES.md`](datasets/DATA_LICENSES.md)).

This effort is supported by Qollab & IonQ.
