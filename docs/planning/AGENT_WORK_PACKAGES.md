# QMint: Parallel Agent Work Orders
## Ready-to-dispatch task descriptions for Claude Code agents or independent coding sessions

**Read before dispatch:** `QMINT_MASTER_RESEARCH_PLAN.md` is authoritative. `CLAUDE_CODE_ORCHESTRATOR_PROMPT.md` controls integration. These are **agents to be dispatched by the user's actual Claude Code environment**, not agents already running as a result of generating this document.

## Universal worker contract (prefix to every agent's task)

You are an isolated research/coding worker. Your assigned worktree was created from a frozen bootstrap SHA; you own only the paths in your task brief. Read the complete master plan's relevant sections and JSON contracts C0–C7. Never edit `main`, `schemas/v1/`, the central tracker, global dependency lock, shared root README or another agent's files. Do not push, force-push, remove unknown files, change unrelated repos, expose credentials, incur paid compute/hardware charges or submit real financial transactions. Verify research source/license before copying code. Create independent tests and commit only your own path changes. Document assumptions, source URLs and page/equation anchors. If an input contract is wrong, stop and report a concrete proposed schema migration; never silently redefine it. Use `set -euo pipefail` for scripts. Hand off: (a) branch and commit hash, (b) exact changed paths, (c) tests and exit codes, (d) evidence produced, (e) numerical results only if executed, (f) remaining blockers and (g) any theorem/model limitations. A passing toy demo is not a physical security proof.

**Standard done-format:** create `handoffs/<lane>-<task>.json` with fields from §11 of the master plan and a matching short `handoffs/<lane>-<task>.md`. If the worker cannot write handoff paths because of worktree ownership rule, output these records in a designated per-agent handoff path approved by the lead. Report failure honestly; don't conceal test failures.

---

## Agent A — Literature, novelty and licensing (researcher)

**Own:** `research/` and `licenses/REFERENCE_AUDIT.md`. **Wave:** 1. **Gate:** G0, G3, G7.

**Mission:** Prevent QMint from accidentally claiming someone else's quantum-money theorem or replicating a published system and calling it new. Audit the primary papers from §2, *including theorem statements and supplemental methods*, plus more recent literature up to execution date. Map Wiesner 2012 vs S-money 2019/2022/2024 vs Schiansky 2023 vs Google 2025 vs 2026 hardware challenges. Search explicitly for pre-existing software that **optimizes security parameters using measured quantum optical data** and for SDP packages for counterfeiting. Use exact first-party publications rather than blogs when possible.

**Actions:** create `PRIOR_ART_MATRIX.csv`, `THEOREM_REGISTRY_SEED.yaml`, `DATASOURCE_REGISTER.yaml`, `NOVELTY_HYPOTHESES.md`, `LICENSE_AND_PATENT_RISKS.md`, `CORRECTIONS.md`. For every paper: game, attacker, theorem's epsilon, source assumptions, source versions, corrections, code/data and license. Inspect 2023 author's correction; do not infer its significance without reading. Audit QMoney repo for private-key vs public key. Distinguish existing security proof from new optimization claims. Record access problems explicitly.

**Validation:** another agent can reproduce each result's bibliographic identifier and theorem/game match. At least 5 explicit disallowed false statements and 5 highest-risk novelty conflicts. A source register that points to unverified speculative links is not acceptable.

**Do NOT:** implement the protocol as an intuition-only variant, claim first quantum payments, or assume paper code license equals paper Creative Commons license.

---

## Agent B — Protocol reference implementation (builder)

**Own:** `qmint/protocols/` and protocol-only unit fixtures under `tests/unit/protocols/`. **Wave:** 1 then 2. **Gate:** G1, G2.

**Mission:** Implement *paper-faithful* cryptographic state machines with a strict challenge/attacker/verifier boundary. Start Wiesner exactly; add S-money and 2023 quantum-digital cryptograms as **separate** protocols.

**Actions:** implement `wiesner.py` (BB84 prep, secret verifier, serial, note lifecycle), `kent_smoney_2022.py` (ideal two-site Table 1 then noisy 2022 versions), `schiansky_payment_2023.py` (real issuer-client-merchant-provider flow; authenticated merchant-binding and bank verification), independent reference test vectors. Document where an event occurs in spacetime and which hidden information a party receives. Expose interface defined by C0/C1/C4; no protocols hold default unrestricted secret basis in a public token object.

**Independent tests:** honest W1 accepts ideal; Z/X preparation mapping; forged copy if secret exposed in a deliberately unsafe control; S-money local validation causal ordering; distinct honest choice paths; privacy until specified commitment/reveal; double-site acceptance under adversarial experiment is scored by the proper game. Inject a mistaken variant to prove test suite flags it.

**Blockers:** missing precise S-money table or correction; mark blocked rather than substitute a homemade BB84 two-merchant protocol.

**Do NOT:** claim that combining S-money+Wiesner+anonymous protocols inherits all their theorems.

---

## Agent C — Quantum attackers and optimal SDP (mathematician/security engineer)

**Own:** `qmint/attacks/`, `tests/unit/attacks/`, `audits/SDP_DERIVATION.md`. **Wave:** 1 onward. **Gate:** G1, G5.

**Mission:** Model attackers at least as rigorously as defenders. The central deliverable is a 1→2 arbitrary CPTP-channel attack formulated as an SDP in the correct BB84 verification game, with independently tested primal and dual constraints.

**Actions:** implement classical guessing/measure-resend, optimal-classical strategy if derived correctly, simple cloning/channel attack, loss reporting attacks, adversary capability restriction and Choi SDP. For W1 n=1 use Hermitian 8×8 Choi matrix `J`; objective `G=1/4 Σ rho_s^T ⊗ rho_s ⊗ rho_s`, constraints `J>=0`, `Tr_out J=I_2`; dual `min Tr(Y)` with `Y⊗I_4>=G`. Verify numerical optimum ~0.75 with solver-specific declared tolerance. Include input/output subsystem order documentation and independent NumPy and QuTiP matrix constructors. Report primal/dual feasibility residuals and max eigenvalue violations, not simply `prob.value`.

**Tests:** n=1 published theorem recovered; duality gap small; CPTP trace preservation; wrong-transpose and secret-exposure negative controls; confidence intervals for Monte Carlo attacks; exact game IDs reject W2 and S-money unsupported bounds. For n>1 test only feasible instances with memory footprint checked in advance. For error-tolerant games, optimize the *actual threshold verifier* at tractable sizes if math permits; otherwise say not solved.

**Do NOT:** turn a Monte Carlo attack result into an adversary upper bound, use a heuristic cloner as “optimal”, or treat floating-point SDP dual slack as certified rigorous proof without residual accounting.

---

## Agent D — Proof system and finite-key analysis (formal-methods engineer)

**Own:** `qmint/proofs/`, `proofs/`, `tests/unit/proofs/`. **Wave:** 1 then 2. **Gate:** G1, G2, G5.

**Mission:** Implement the mathematical validity boundary between empirical data and statements about unlimited adversaries. The proof engine must be more conservative than an enthusiastic user interface.

**Actions:** machine-readable theorem registry, ideal W1 and S1 bounds, separate W variant bound, published 2022 realistic S-money lemmas and thresholds, published 2023 paper's applicable security curve and source assumptions, confidence propagation interface, theorem precondition checker, source anchors, `SecurityCertificate` with `UNCERTIFIED` default, certificate checker distinct from optimization. Derive no new theorem by analogy. Create human-readable proof dossiers, including quantifiers and accepted physical model. Support numerical SDP certificates only when independent residual/dual bounds justify them.

**Tests:** ideal W1 and S1 values with log-space stability; invalid protocol-family transfer blocked; unknown/unchecked noise source blocked; independent checker rejects optimistic source parameters and invalid rounding; missing privacy theorem does not become epsilon=0; mixed-up epsilon directions fail. Recompute paper's published example numerical bound at paper's parameter tuple when exact equations and assumptions are known.

**Do NOT:** quote “information-theoretic” for device models with unverified entropy/randomness or finite-key assumptions as a product certification.

---

## Agent E — Empirical photonics and calibration (data scientist)

**Own:** `qmint/photonics/`, `datasets/manifests/`, `tests/unit/photonics/`, `reports/data_working/`. **Wave:** 1 then 2. **Gate:** G3.

**Mission:** Replace invented quantum-noise numbers with responsibly analyzed real optical measurements.

**Sources:** Zenodo https://doi.org/10.5281/zenodo.7979319 real event timetags; authors' analysis-code DOI https://doi.org/10.5281/zenodo.8020667; Nature Communications 2023 paper + its published 21-Aug correction; published aggregate parameters from 2022/2024 **separately tagged**.

**Actions:** verify metadata/license/version, download without secret auth if possible, hash inputs, stream parse exact archived event format, map channels and bases, preserve original times, validate coincidence selection window from paper, account for drift/time offsets, reconstruct count/error plots, do proper uncertainty and time-contiguous holdouts. Inspect authors' code if accessible and legally reusable; independent reconstruction if not. Do not invent missing generation counts or optical efficiency. Generate calibration record with confidence method and physical assumptions. Pin exact event units. If network unavailable, write robust download+validate scripts and test on small synthetic **tagged** fixtures.

**Tests:** known-epoch timetagger fixture, no double-counting coincidence pairs, channel swaps detected, 3-ns boundary tie handling, corrupted archive failure, deterministic output hash, full source provenance, correct rejection of inapplicable data-to-protocol transfer.

**Do NOT:** pass 2023 photonic calibration to 2022 S-money proof just because both mention BB84.

---

## Agent F — Circuit implementation and independent state physics (quantum engineer)

**Own:** `qmint/quantum/` excluding IonQ and Qollab files; `tests/unit/quantum/`. **Wave:** 1. **Gate:** G1, G6.

**Mission:** Build a small trustworthy circuit experiment for real quantum state preparation, measurement disturbance and controlled attacker approximations.

**Actions:** Qiskit/Aer ideal/noisy and QuTiP alternate reference for BB84 Z/X states, 1–8 qubit circuits (resource-controlled), deterministic prep test vector, probability/measurement analysis, noise channels, resource counts, structured backend provenance. Implement an optional small approximate cloner attack circuit only if the mathematical map and physical resource width are derivable; otherwise focus on known attack classes and label them. Do not construct n=128 full statevectors; large n is supported via analytic/theorem/symbolic modes only. Simulated photonic loss must be separate from trapped-ion gate/readout noise.

**Tests:** correct basis outcome distributions, Bloch/density-matrix overlaps, CPTP trace preservation, physical qubit indexing; high-shot empirical check with binomial CI; exact local simulator crosscheck. Hardware backend runs delegated to J.

**Do NOT:** claim a Qiskit simulator has no-cloning protection at the software object level. Its wavefunction is classical data and can be copied by the host.

---

## Agent G — Relativistic networking and event correctness (distributed-systems engineer)

**Own:** `qmint/networks/`, `tests/unit/networks/`. **Wave:** 1 then 2. **Gate:** G2, G4.

**Mission:** Formalize what transaction “instant” means in relativistic distributed verification. You must be able to make an apples-to-apples space-time diagram from actual event traces.

**Actions:** actor model and event DAG for user agents, issuer agents, two sites, pre-distribution, honest merchant, malicious simultaneous redeemer. Enforce causal lower bounds and explicit clock uncertainties. Add ideal propagation topology, synthetic queueing/partition scenarios, and RIPE Atlas public RTT adapter with source probe/measurement IDs. Define local validation, issuer confirmation and irrevocable settlement as separate events. Implement receipt choice timing and preallocated branch constraints. Emit comparability-relevant site details for H and I.

**Tests:** no retrocausal message; disallow spending information propagating faster than configured bound; under H0 simultaneous sites can accept without coordinating; under bank online atomic H1 only one redeem succeeds; S-money branch selection hidden up to specified point; classical escrow requires prior allocation; network partition changes availability not physics.

**Do NOT:** treat a single measured RTT as an information-theoretic physical lower bound; do not call local authorization final settlement.

---

## Agent H — Strong classical comparison protocols (cryptography/fintech engineer)

**Own:** `qmint/classical/`, `tests/unit/classical/`, `reports/classical_baseline_notes/`. **Wave:** 1 then 2. **Gate:** G4.

**Mission:** Be a skeptical classical-systems engineer whose goal is to defeat inflated quantum-advantage claims.

**Actions:** build H0 copyable bearer negative control; H1 atomic online spent ledger; H2 quorum/regional coordination; H3 preallocated/escrow branch with late-choice restrictions; H4 ML-DSA-signed bearer authorization via actual standardized library; H5 tamper-resistant secure hardware *trust model*, realistically modeled not simulated as “unbreakable”; optionally H6 anonymous offline e-cash and ex post double-spend detection with referenced construction. Each protocol emits the same `BenchmarkRecord` and works on G's causal topology. Implement idempotency, retries, concurrent requests, and replay attacks. Preserve keygen/sign/verify overhead, bytes, storage and security assumptions. No real finance credentials.

**Tests:** atomic spent ledger linearization under concurrent threads/events; legitimate retry idempotency; escrow rejected at wrong site; signatures validate and do not alone prevent double spend; additional trusted hardware assumptions reflected in fairness matrix. Document best classical construction for each scenario rather than pick a deliberately slow strawman.

**Do NOT:** claim post-quantum crypto signatures are crackable by Shor's algorithm or that classical physical hardware cannot resist cloning under a different trust model.

---

## Agent I — Resource-optimal, independently checked certificates (optimization researcher)

**Own:** `qmint/compiler/`, `tests/unit/compiler/`, `reports/optimizer_working/`. **Wave:** 2 after schema/ideal bounds. **Gate:** G5.

**Mission:** Build the proposed novel research artifact: certificate-producing optimal configuration search. Target a reproducible reduction in required photons or issuance latency **at equal or stronger bound-qualified security**, not a guessed percentage.

**Actions:** bound-aware feasible search over N, error/loss thresholds, source bias, reporting strategy, sites and privacy requirements; multiobjective Pareto frontier; fixed published baseline, naive sizing, exhaustive oracle, robust optimizer. All candidate tests use D's proof evaluator and E's uncertainty records; independent read-back verifier checks candidates. Use monotonicity pruning only with documented proof or tested condition. Include infeasible certificates explaining which constraint failed and how assumption data are missing. Cache by canonical model+calibration+proof version. Record solver runtime and memory. Optional surrogate/ML only if it improves an expensive proof oracle *and* exact checker remains final authority.

**Tests:** brute-force small-grid agreement, duplicate domination removal, invalid privacy/correctness/game rejected, null bound returns UNCERTIFIED, interval worst-case rather than cherry-picked mean, mutation tests for reversed inequalities, numerical accuracy. Publish fixed pre-registered scenarios before hyperparameter tuning; holdout untouched until selection frozen.

**Do NOT:** use a neural network's low predicted cheating probability as a cryptographic theorem.

---

## Agent J — Qollab/IonQ and genuine backend provenance (quantum cloud engineer)

**Own:** `qmint/quantum/ionq.py`, `qmint/quantum/qollab.py`, `qollab/`, `tests/unit/ionq/`. **Wave:** 1 probe / 3 optional actual run. **Gate:** G6.

**Mission:** Demonstrate that a small primitive can run on a real quantum-computing stack while being explicit that it is not a physical photonic money network.

**Actions:** backend probe: Qiskit version, qiskit-ionq, authentication via env only, simulator/noise models, width/shots, memory, supported mid-circuit measurement, pricing. Provide a standalone one-qubit or small n BB84 prepare/verify circuit and optional approximate attack, ideal/noisy simulator counts with correct bit order. Adapt to Qollab's verified capabilities rather than assuming files can be installed. For paid hardware, output a dry-run resource/cost/shot estimate and request explicit approval; do not submit without it. Record job IDs, backend name, time, error, shots and transpiled native gate counts only if actual job completed.

**Tests:** mocks and test-vector parsing, no secret env logging, no paid calls, no silent fallback from real device to noisy simulator, unavailable job produces SKIPPED rather than fake success.

**Do NOT:** claim a few gate-based qubits constitute an unclonable banknote deployed to users.

---

## Agent K — Evidence-first dashboard and UX (product engineer)

**Own:** `qmint/ui/`, `app/`, `tests/unit/ui/`. **Wave:** 1 typed mock / 3 integrated. **Gate:** G7.

**Mission:** Build an impressive yet epistemically honest research interface, not an investment/wallet product.

**Views:** (1) choose genuine protocol family and security game; (2) mint/test unknown BB84 state; (3) adversary attack with primal/dual and attack win CI; (4) upload/open verified real photon data and source identifier; (5) visualize spacetime choice and classical cross-check; (6) set epsilon and constraints, calculate Pareto resources and validate certificate; (7) evidence ledger and links to paper; (8) hardware primer and experimental provenance. Source labels unmistakable: THEOREM, NUMERICAL, SYNTHETIC, PHOTON-EXPERIMENT, QPU, MODELLED-LATENCY, UNCERTIFIED. Red warning on incomplete assumptions; no default green security badge. Every figure downloadable with experiment manifest. Accessibility and mobile-ready view optional.

**Tests:** no missing bound displays zero; uncited number can't enter claim panel; simulated and measured curves cannot share origin badge; adverse case clearly displayed; unknown job counts marked not run.

**Do NOT:** implement a tradable cryptocurrency dashboard or imply tokens have monetary value.

---

## Agent L — Build/CI/integration infrastructure (senior SWE)

**Own:** `qmint/core/`, `qmint/cli.py`, `scripts/`, `pyproject.toml`, dependency lock, CI, `tests/contracts/`, `tests/integration/`. **Wave:** 0 with lead; 1 onward. **Gate:** all.

**Mission:** Be ruthless about module boundary, scientific provenance and clean-room execution.

**Actions:** project skeleton, Pydantic schema validators based on frozen contracts, types/time units, project doctor command, low-memory dataset handling, evidence manifest hashing, typed CLI, centralized config, structured logs, reproducible seeds, optional extras, hardware disabled by default, CI with fixtures, security scanning of env leaks, integration tasks/entrypoints. Keep dependencies lean and compatible with user's platform. Optional libraries should fail gracefully. Implement `run_core.py` that can execute completely offline and `run_all.py` that explicitly requires public real data when needed. Confirm every test's exit status; avoid catch-all exception handling that turns missing dependencies into synthetic evidence.

**Tests:** clean install, executable CLI, strict serializer default, schema hash matches fixture, secret leakage regression, network denied mode, irreproducible stochastic result flagged, fail if source type absent, deterministic plot input manifests, hidden isolated worktree not staged as nested repo.

**Do NOT:** stage entire monorepo parent or overwrite an active agent-org.

---

## Agent M — Independent adversarial auditor (skeptical red team)

**Own:** `audits/`, `tests/adversarial/`. **Wave:** 2 and 3. **Gate:** G5, G7.

**Mission:** Try to falsify every security and systems assertion without destroying the main codebase. Treat all other agents' success messages as untrusted until reproduced.

**Attacks:** observe whether user token objects reveal BB84 state descriptors; tamper with SDP transpose/subsystem order; insert a proof for the wrong game; change a realistic noise threshold while retaining ideal bound; poison dataset calibration; force timestamp drift; make classical preassignment unexpectedly beat S-money latency; forge/duplicate transaction IDs; race two sites; leak issuer's chosen site through timing metadata; forge figures by injecting synthetic records without origin flag; suggest a hardware-TEE comparison. Document counterexamples and exact repro scripts. Where insufficient proof exists, state assumption/uncertainty instead of claiming security broken.

**Tests:** every critical finding includes a failing regression and expected safe behavior, or an explicit infeasible-theorem-domain argument. Produce `audits/CRYPTOGRAPHIC_REVIEW.md`, `audits/DATA_LEAKAGE_REVIEW.md`, `audits/CLASSICAL_FAIRNESS_REVIEW.md`, `audits/CLAIMS_AUDIT.md`, with severity, remedy, acceptance status, review SHA.

**Do NOT:** run against live third-party financial systems; the test target is only local research code.

---

## Agent N — Research manuscript and reproducibility (technical writer + research engineer)

**Own:** `qmint/evaluation/`, `reports/`, `figures/`, `docs/paper/`, `tests/unit/evaluation/`. **Wave:** 2 scaffolding / 4 manuscript. **Gate:** G7.

**Mission:** Turn actual data, proofs and code into a skeptical-reviewer-ready paper and open research asset. You are not marketing.

**Actions:** implement experiment record warehouse and 10 figure scripts from master §9. Build trust/comparability tables, statistical CI routines, raw-data and published-aggregate source labels, run manifests, paper LaTeX/Markdown and appendix with theorem-to-implementation mapping. Keep all figures regenerable and never manual-copy agent numeric claims. Highlight strongest *classical* baselines, the cost of calibration uncertainty, negative findings, and when simulated IonQ does not imply a physical money system. Present limitations prominently. Require review SHA from M and novelty matrix from A. Generate `FINAL_RESEARCH_REPORT.md`, `BENCHMARK_RESULTS.md`, `SECURITY_PROOFS.md`, `NOVELTY_AUDIT.md`, `REPRODUCE.md`, `NEGATIVE_RESULTS.md` only with citations to real experiment record IDs.

**Tests:** every numeric figure caption has a valid source manifest, stale cached plots are rejected when dependencies/data SHA change, theorem/Monte Carlo/real-photon plot styles distinguish evidence, missing final result is marked PENDING or BLOCKED, all tables match frozen experiment CSV.

**Do NOT:** invent positive results, paper acceptance, simulator/hardware access or publication timeline.

---

## Lead integration checklist and dispatch order

1. Read current `project/TRACKER.yaml` and `git worktree list --porcelain`. Avoid colliding with active unrelated agents.
2. Pre-freeze C0–C7 + smoke tests; create milestone commit. Share exact SHA to workers.
3. Dispatch Wave 1 tasks with path ownership. Limit concurrency based on actual runtime capacity and conflict matrix.
4. Each agent reports unit tests; lead fetches/merges **only its branch** after checking diff and handoff. Run CI on merged code.
5. After B-Wiesner + C-SDP + D-ideal + F circuit evidence, mark **G1 only if independent checks pass**. Then expand B/G/H/D.
6. E's experimental data should remain immutable, with a separate versioned derived calibration, and must not be consumed across protocols without compatibility proof.
7. Freeze test configurations and pre-register uncertainty treatment before optimizing; no retroactive holdout tuning.
8. Publish a clear current status: implemented / tested / reproduced / conjectural / real-data blocked / hardware blocked.
9. Stop generating extra branches when integration burden exceeds progress. The user wants one working research platform, not 14 unmerged prototypes.
10. No public submission, publication, branch push or hardware credit use without explicit authorization from the human lead.

**How to judge agents:** scientific falsifiability and complete integration, not lines written. **How to judge QMint:** an independent researcher can match each result to a precisely stated security game, theorem, device source and classical comparator.
