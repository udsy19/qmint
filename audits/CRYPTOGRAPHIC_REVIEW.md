# Cryptographic review (lane M, red team)

- **Review SHA:** `9a4e8a9368e75d3e8e329231020e1992bc7f04ea`. This is the base of `feat/M-redteam`, with lanes A–H, J and L merged; its code is identical to main `4c04f53`.
- **Also checked against:** main `7130c1fa9b844ea23d1dffd842d47fe4eca03fd3` (after GH/X and K-web phase 1 merged). Every finding below still reproduces there (run against a `git archive main` snapshot: 34 passed, 26 xfailed).
- **Repro prefix:** `PY=/Users/udsy/PycharmProjects/Qollab-QMint/.venv/bin/python`, run from the worktree root. Each finding has a strict-xfail regression test, and `--runxfail` shows the live failure.
- **Severity scale:**
  - HIGH: a certificate or "prevented" result is wrong for an in-model request.
  - MEDIUM: an integrity gap that needs an extra mistake or an unusual deployment to bite.
  - LOW: a narrow or presentation issue.
  - INFO: context only.
- **Evidence discipline:** every claim below is backed by a test or an exact computation. Where I could not build an exploit, I say so rather than claiming a break.

## Summary

| id | sev | owner | finding | status |
|---|---|---|---|---|
| M-D1 | HIGH | D | Ideal theorems (W1, S1) issue CERTIFIED certificates for requests that carry realistic noise, loss or threshold parameters, because the engine and checker only deny 6 specific key names | OPEN |
| M-D2 | HIGH | D | The CERTIFIED_NUMERIC (SDP) checker path skips the ideal-noise check, the required declarations and the proof-reference/claim match | OPEN |
| M-B1 | HIGH | B | `copy.deepcopy` or a pickle round trip of a `RegisterHandle` makes a perfect counterfeit; the W1 pair is accepted with probability 1.0 | OPEN |
| M-B2 | MEDIUM | B (+C, I) | In-process introspection reaches the exact BB84 states (Wiesner handle) and Bob's `IssuerSecret` plus t,u (the Kent session handed to Alice) | OPEN (design) |
| M-B3 | MEDIUM | B | `WiesnerChallenger.redeem` verifies against `record.token_id` but spends `public_metadata['serial']`, which are not bound together. A note presented under a victim's serial is accepted, and the victim then gets "replay" | OPEN |
| M-D3 | LOW | D | The proof-reference check is `startswith(claim_id)`, so a W1 certificate citing `P-W1CV` is accepted | OPEN |
| M-D4 | MEDIUM | D/E | The calibration gate checks only the family string and the origin. An unregistered `dataset_sha256`, `n_events=1` and `confidence_level=0.05` are all accepted | OPEN |
| M-B4 | LOW | B/G | The S1 harness does not enforce that the two presentations are spacelike separated. Bob's per-site `errors`/`delta_size` are readable by Alice-side code before her second presentation. No beating strategy was found (see below) | OPEN (uncertain impact) |
| M-S1 | MEDIUM (claims) | D/N | Schiansky 2023's p_d = 5.9e-45 rests on applying a {0,1} Chernoff bound to a {0,1,6.83}-valued mishap sum. An iid cheater on the paper's own fitted boundary has an exact tail of 7.0e-9 | MITIGATED in code (D1 never certified); manuscript guard needed |
| M-C0 | INFO | C/D | Attempts to tamper with the SDP transpose and subsystem order: harmless for BB84 by construction. Lowering the claimed optimum is refused by D's exact checker | NO FINDING |

## Findings

### M-D1 (HIGH): noisy or lossy requests certified under ideal theorems
- **Attack ("change the realistic noise threshold while retaining the ideal bound").** A W1 request with `{"n": 73, "threshold": 5}` gets status CERTIFIED with ε_unf = 7.6e-10. So do:
  - W1 with `noise={"kind": "depolarizing", "p": 0.05}`;
  - W1 with `max_errors=3, qber=0.03`;
  - S1 with `gamma_det=0.018, P_det=0.019` (Kent's own lossy tuple);
  - S1 with `e_h/l_h`.
- **Why it happens.** Both `assumption_check.check_noise_free` and `checker._ideal` use the denylist `("error_threshold","gamma_err","loss_tolerance","loss_threshold","E","P_noqub")`, so any other spelling passes. The required declarations (e.g. `ideal_no_loss_no_error`) are self-attested strings, so contradicting them costs nothing.
- **Impact.** These are exactly the cross-game transfers the master plan forbids. Lane C's A06 already shows loss reporting gives success 1.0 in a lossy W2 toy, so the certified bound is not valid for the request.
- **Repro:** `$PY -m pytest tests/adversarial/test_m_proof_gates.py -k unknown_noise --runxfail -q`
- **Expected safe behaviour:** an ideal-game request with any parameter outside a per-game allowlist is OUT_OF_MODEL/UNCERTIFIED.
- **Remedy:** replace the denylist with an allowlist, in both the evaluator and the checker:
  - W1/W1_CV: `{n, declared_assumptions, verifier, verification_oracle_queries}`;
  - S1: `{N, M, declared_assumptions, ...}`.
  The checker must refuse unknown keys by itself, not rely on the engine.

### M-D2 (HIGH): the SDP certificate path skips the model gates
- **What is missing.** `IndependentProofChecker._check_sdp` never calls `_ideal`'s noise test or `required_declarations`, and only checks that `proof_reference` is non-empty.
- **Effect.** A W1 CERTIFIED_NUMERIC certificate is CERTIFIED in each of these cases:
  - with `error_threshold=1`;
  - with no declarations;
  - citing `P-S1`.
- **Repro:** `$PY -m pytest tests/adversarial/test_m_proof_gates.py -k sdp_certificate_re --runxfail -q`
- **Expected safe behaviour:** the same model gates as the published path, plus `proof_reference` ∈ {`P-W1`, `P-W2/sdp`}, compared exactly.
- **Remedy:** factor the gate checks into one checker function that both paths call.

### M-B1 (HIGH): copying a token handle clones the quantum state
- `copy.deepcopy(note)` and `pickle.loads(pickle.dumps(note))` both succeed. `WiesnerChallenger.pair_acceptance_probability(note, twin)` then returns 0.99999999999999 at n = 8.
- `register.py` says "Deep-copying a handle is a simulator artefact, NOT cloning". Nothing enforces that, though, and the challenger cannot tell the copy apart.
- **Impact.** Any attack harness, notebook or API route that copies a handle (even by accident, e.g. in a multiprocessing pool) produces an IN_MODEL MONTE_CARLO "attack" that beats (3/4)^n.
- **Repro:** `$PY -m pytest tests/adversarial/test_m_protocol_boundary.py -k "deepcopy or pickle" --runxfail -q`
- **Expected safe behaviour:** `RegisterHandle` and `FactorizedRegister` refuse `__copy__`, `__deepcopy__` and `__reduce_ex__`, the same way `SecretHolder` does.
- **Remedy:** the challenger's analysis copy (`_exact_count_distribution`, noisy branch) uses a private `_clone_for_analysis()` instead of `copy.deepcopy`.

### M-B2 (MEDIUM, design): in-process introspection
- **Wiesner handle.** `note._register.reduced_state([q])` returns the exact projector for every qubit, which recovers (basis, bit) exactly (tested against `leak_secret_TEST_ONLY`).
- **Kent session.** Dishonest Alice calls the same `KentSMoneySession` object that stores `_secret: IssuerSecret` and `_bob["B0"]["t"]`. Reading them wins S1 with certainty (`test_kent_introspection_attack_wins_s1_with_certainty`).
- **What is not at issue.** Serialization is sound: `canonical_json`, `model_dump(_json)`, pickle and deepcopy of an `IssuerSecret`, including one nested in a certificate, are all refused (lane L's earlier finding is fixed at the review SHA). Attribute access (`secret.bits`, `vars(secret)`) remains open, which is inherent in Python.
- **What the code does right.** Lane C's attack modules never access private attributes of handles (grep-verified), and lane C's own harness has a test against reading `_positions`.
- **Expected safe behaviour:** the adversary-facing object graph reaches no `IssuerSecret` and no state matrices (`tests/adversarial/_reach.py`).
- **Remedy, by owner:**
  - B: split the Kent session into a Bob-side object and an Alice-facing proxy with no reference to it.
  - B/I: run challengers in a subprocess for any experiment that produces attack evidence (pipe or queue API).
  - C: add an AST policy test over `qmint/attacks/**` that forbids `_`-prefixed attribute access on foreign objects and the `gc`, `inspect`, `ctypes` and `pickle` imports.
- **Note:** until this is fixed, attack results are only as trustworthy as the attack code's adherence to the API.

### M-B3 (MEDIUM): serial and token id are not bound together at redemption
- **How it works.** The attacker sets `mine.record.public_metadata = {"serial": victim_serial}` (the record is mutable). The bank verifies the qubits against `mine`'s secret (found via `token_id`) and marks the *victim's* serial spent. The attacker's genuine note is accepted, and the victim's genuine note is then refused as `replay`.
- **Effect.** Value moves to whoever presents first. Combined with a W1 success at probability ≤ (3/4)^n, it turns a counterfeit into a redemption charged to a third party.
- **Repro:** `$PY -m pytest tests/adversarial/test_m_protocol_boundary.py::test_redeem_binds_serial_to_token --runxfail -q`
- **Remedy:** the bank keys everything by its own (serial → token_id) map, refuses a mismatch, and freezes the record (no `validate_assignment` mutation after mint).

### M-D3 (LOW): proof-reference prefix match
- `"P-W1CV".startswith("P-W1")` is true, so a W1 certificate citing the W1_CV theorem is accepted. The bound value is still the correct W1 value, so only the citation is wrong.
- **Remedy:** compare exactly against the claim id, or require `claim_id + "/"` as the prefix.
- **Test:** `test_w1_certificate_citing_w1cv_is_refused`.

### M-D4 (MEDIUM): calibration poisoning
- **What is checked.** `check_calibration` checks only `experiment_family ∈ claim.calibration_families`, `data_origin ∈ {PHOTON_EXPERIMENT, PUBLISHED_AGGREGATE}` and that `independence_assumptions` is non-empty.
- **What gets through.** A record that claims `experiment_family="kent_2022"`, `dataset_sha256="0"*64` and `n_events=1`, with a 1e-4-wide QBER interval at `confidence_level=0.05`, gives an S2 certificate that is CERTIFIED.
- **Defences that did work:**
  - A real Schiansky record relabelled as Kent is refused only if the label is honest (the family-mismatch control passes).
  - `merge_calibration` takes the hull, so a calibration can never make a certificate more optimistic than parameters supplied explicitly.
- **Remedy (D, with E):**
  - Bind families to registered dataset hashes. E's record hash `ef73667f…0130` equals `sha256(zenodo_7979319/Archive.zip)`, which I verified.
  - Set a confidence floor (≥ 0.95).
  - Whitelist the interval methods.
  - Require `n_events` ≥ some minimum.

### M-B4 (LOW, uncertain): the S1 harness is not a spacelike game
- **What is missing.** `KentSMoneySession.present(i, x, t)` takes caller-supplied times with no geometry, so presentations at Q0 and Q1 need not be spacelike. `present()` returns the outcome, and `session.events` exposes B_i's `delta_size`/`errors` immediately.
- **Why it matters.** Lemma 1 is proven for spacelike-separated presentations. In this harness, an adaptive Alice can condition her Q1 presentation on Q0's result.
- **What I tried.** I worked through N = 1 under IQT2 with a quantum memory. The adaptive strategies I tried reach 3/4, which is below the Breidbart value 0.854. **I did not find a strategy that beats Lemma 1, so I do not claim a break.**
- **Remedy:** route S1 runs through G's engine, where the two presentations are spacelike-checked (`is_spacelike`) and B_i outcomes are not visible to Alice's agents before the other presentation.
- No regression test was written. A meaningful test needs G/B integration; this falls under the work order's "explicit argument" clause.

### M-S1 (MEDIUM, claims): Schiansky 2023 Chernoff on weighted mishaps
- **Primary sources** (read by me via a sub-agent; quotes in `handoffs/M-M1.md`):
  - SI Note 1C, Eqs. (7)–(8): "N random variables X_i, which can each take the value 1 with probability p_i and 0 with probability 1 − p_i". That is, {0,1}-valued variables.
  - SI Eqs. (18)–(22) then plug M(e,l) = (4+2√2)e + l in as the mean. They never define per-state summands and never rescale.
- **Counterexample under the paper's own iid model.** Take a cheater with zero declared loss and per-state error indicator q = 0.48495/6.828 = 0.07102, which puts her on the fitted boundary M(e,0) = ½(1−p_m/2).
  - Exact lower tail: `binom.cdf(⌊0.99·N·q⌋, N, q)` = **6.96e-9** at N = 4.2e6.
  - Published bound: 5.9e-45.
  - Rescaled [0,1] Chernoff bound: 3.3e-7. The exact tail respects this one, so D's rescaled value is a valid generic bound.
- **Caveat.** This assumes the cheating channel can reach the (e≈0.071, l≈0) end of the fitted boundary. The fit is not proven tight there, so the conclusion is "the published value is unsupported, and is violated if the boundary is attainable at l→0", not "proved false".
- **Repro:** `$PY -m pytest tests/adversarial/test_m_claims.py -k chernoff -q` (passes; it documents the finding).
- **Status.** D never certifies D1 (verified: `test_d1_is_never_certified`). Lane N must not quote 5.9e-45 as a security level without this caveat.

### M-C0 (INFO): SDP tamper attempts (lanes C and D)
- **Transpose omission.** Every C7 BB84 projector is real symmetric (ρᵀ = ρ, tested), so omitting the transpose cannot change any BB84 W1 value at any n. Lane C's claim that it is "invisible on BB84" is correct and also holds for every n.
- **Subsystem permutation.** D's exact check of the scalar dual Y = (3/8)ⁿ·1 is invariant under any qubit permutation P, because P(Y⊗1 − G)Pᵀ = Y⊗1 − PGPᵀ. So the order bug cannot produce a wrong *bound* through that path. It would matter only for a supplied non-scalar `dual_matrix_rational`, which D checks against its own G.
- **Lower-than-true claims.** Claimed optima of 0.70 (n=1) and 0.375 (n=2, lane C's "missing W_π" value) are refused by the checker (`test_sdp_claim_below_true_optimum_is_refused`).
- **Relabelling.** A W1 bound relabelled as W1_CV is refused.
- **Reproduced:** C's report regenerates in 91 s with identical values (n=1: 0.75 by SCS and Clarabel; certified bounds 3/4 ≤ OPT₁ ≤ 0.750000000003638 and 9/16 ≤ OPT₂ ≤ 0.562500000007276). D's exact duals give 3/4 and 9/16, and W1_CV ≤ 0.9267766953053069.
- **Cross-lane result (new):** lane F's MVW channel run against **lane B's** challenger gives exactly 0.75ⁿ for n = 1, 2, 3, and lane C's Z measure-resend gives 0.625ⁿ. Lanes B and C had never been run against each other.

## Re-audit after the in-flight lanes merge
- **Q (dedupe of protocols, attacks and proofs):** the tests import `qmint.protocols.{wiesner,kent_smoney_2022,register}`, `qmint.proofs.{engine,checker,registry}`, `qmint.attacks.heuristic.a01_kraus` and `qmint.quantum.cloner.cloner_kraus`. Update the imports, and keep every xfail **strict** so that a dedupe which silently fixes or reintroduces a bug is noticed.
- **I (compiler):** check that the compiler consumes only `IndependentProofChecker` verdicts and cannot reach M-D1 or M-D2 by optimising over parameter names. Mutation-test the constraint directions (T7).
- **GH (merged on main at 7130c1f after the review SHA):** `engine_adapter` / `matched_topology` re-host H on G's engine. M-H1, M-H2 and M-H3 still reproduce there (see CLASSICAL_FAIRNESS_REVIEW).
- **K-web (`qmint/api/routes/lab.py`, merged on main):**
  - The teaching demo deliberately reveals note secrets derived from a *client-supplied seed*. Confirm that no `/lab/attack` result is ever recorded as IN_MODEL evidence, and that no endpoint returns a `RegisterHandle` or a challenger.
