# SDP derivation and certification — game W1 (lane C)

Primary source, read in full for Sections 1–4: A. Molina, T. Vidick, J. Watrous, *Optimal counterfeiting
attacks and generalizations for Wiesner's quantum money*, arXiv:1202.4010v1 (17 Feb 2012),
https://arxiv.org/abs/1202.4010 (PDF fetched 2026-10-11). Anchors:

| Item | Anchor |
|---|---|
| Theorem 1, optimal simple counterfeiting = (3/4)^n | p.2 |
| Theorem 2, classical-verification variant = (3/4 + √2/8)^n | p.3 |
| Choi operator J(Φ) = Σ Φ(\|i⟩⟨j\|) ⊗ \|i⟩⟨j\|, CP ⇔ J ⪰ 0, TP ⇔ Tr_Y J = 1_X, eq. (1) | Sec. 2.2, p.5 |
| SDP primal/dual pair and Slater's theorem (Thm 3) | Sec. 2.3, p.5–6 |
| Success probability (2) and counterfeiting SDP with Q = Σ p_k ψ_k⊗ψ_k⊗ψ̄_k (projector) | Sec. 3, 3.1, p.6–7 |
| n=1 value 3/4: primal channel A0, A1 (with 1/√12), dual Y = (3/8)1, ‖Q‖ = 3/8 | Sec. 3.2, p.7–8 |
| Six-state / Bužek–Hillery value 2/3 | Sec. 3.3, p.8 |
| Parallel repetition: value α^n using W_π and A ≥ B ≥ 0 ⇒ A^{⊗n} ≥ B^{⊗n} | Sec. 3.4, p.9–10 |
| Threshold variant R, eq. (4) | Sec. 3.5, p.10–11 |
| Classical verification, block-diagonal reduction, Lemma 5 | Sec. 4.1–4.2, p.13–14 |

## 1. Game W1 (exactly what is optimised)

The bank picks s uniformly from {0,1,+,−} independently for each of n positions (C7 labels:
(Z,0)=|0⟩, (Z,1)=|1⟩, (X,0)=|+⟩, (X,1)=|−⟩). The counterfeiter gets the single note
ρ_s = ⊗_i ρ_{s_i}, applies any CPTP map Φ: L(C^{2^n}) → L(C^{2^n} ⊗ C^{2^n}), and wins iff both
outputs independently pass the projective test {ρ_s, 1−ρ_s} applied to every position. No access to
any verification oracle. Win probability:

  P(Φ) = 4^{-n} Σ_s Tr[(ρ_s ⊗ ρ_s) Φ(ρ_s)].

## 2. Choi ordering used in code (differs from MVW's by a factor permutation)

QMint ordering is **(input, out1, out2)**, each register big-endian over its n qubits:

  J = Σ_{i,j} |i⟩⟨j| ⊗ Φ(|i⟩⟨j|),   Φ(ρ) = Tr_in[(ρ^T ⊗ 1) J],   Tr[A Φ(ρ)] = Tr[J (ρ^T ⊗ A)].

(Proof of the last identity: Tr[J(ρ^T⊗A)] = Σ_ij ⟨j|ρ^T|i⟩ Tr[A Φ(|i⟩⟨j|)] = Σ_ij ρ_ij Tr[AΦ(|i⟩⟨j|)] = Tr[AΦ(ρ)].)
Hence P(Φ) = Tr[G_n J] with

  G_n = 4^{-n} Σ_s ρ_s^T ⊗ ρ_s ⊗ ρ_s .

MVW order the spaces (Y, Z, X) = (out1, out2, input) and put ψ̄ (complex conjugate = transpose for a
projector) on X; G_n is MVW's W_π Q^{⊗n} W_π^* with the factors cyclically moved so the input comes first.
CP ⇔ J ⪰ 0 and TP ⇔ Tr_{out1,out2} J = 1_{in} carry over unchanged (MVW Sec. 2.2).

**Primal** max ⟨G, J⟩ s.t. J ⪰ 0, Tr_out J = 1_{din}.
**Dual** (Lagrangian with multiplier Y for the equality): L = ⟨G,J⟩ + ⟨Y, 1 − Tr_out J⟩ =
Tr Y + ⟨G − Y⊗1_{dout}, J⟩; bounded over J ⪰ 0 iff Y⊗1 ⪰ G, giving min Tr(Y) s.t. Y⊗1_{dout} ⪰ G.
Weak duality: for feasible J, Y: Tr Y − ⟨G,J⟩ = ⟨Y⊗1 − G, J⟩ ≥ 0. Strong duality holds by Slater
(J = 1/dout·1 strictly feasible; Y = c·1 for large c strictly dual feasible; MVW Sec. 3.1).

Two independent constructions of G_n are asserted equal (`tests/unit/attacks/test_attacks_sdp.py`):
NumPy `kron` over all 4^n labels, and QuTiP (`tensor` of the single-qubit Q, then `Qobj.permute` to
regroup (in_1,o1_1,o2_1,in_2,…) into (in_*, o1_*, o2_*), i.e. MVW's W_π). Max abs difference:
0 (n=1), 3.5e-18 (n=2). A third construction, exact rationals (`certify.exact_w1_objective`), also matches.

## 3. Numerical results (NUMERICAL_SDP; CVXPY 1.9.3, complex Hermitian variables)

| n | solver | primal | dual | gap | status P/D | λmin(J) | ‖Tr_out J − 1‖_F | λmin(Y⊗1−G) | time P+D (s) | peak RSS |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | SCS (eps 1e-9) | 0.7500000000000013 | 0.7500000000000002 | −1.1e-15 | optimal/optimal | −4.2e-15 | 2.7e-15 | +1.8e-16 | 0.01 | ~0.17 GB |
| 1 | Clarabel | 0.7500000000003952 | 0.7499999996197124 | −3.8e-10 | optimal/optimal | −7.0e-11 | 2.5e-15 | −4.0e-10 | 0.02 | ~0.17 GB |
| 2 | SCS (eps 1e-9) | 0.562499999999955 | 0.5624999999999998 | +4.5e-14 | optimal/optimal | −6.8e-16 | 6.4e-15 | −2.9e-16 | 0.21 | ~0.19 GB |
| 2 | Clarabel | 0.5625000002258056 | 0.56249999894657 | −1.3e-9 | **optimal_inaccurate**/optimal | −2.2e-10 | 2.4e-13 | −3.4e-10 | 23.9 | **~6.5 GB** |

Peak RSS is process-wide `ru_maxrss` after each solve (monotone; the Clarabel n=2 row dominates; whole
evidence run peak footprint 6.8 GB). Negative gaps and slightly negative eigenvalues show that the
floating-point iterates are **not** exactly feasible — which is why they are not proofs. n=3 (Choi
dimension 512) is refused by a size guard (`SDPSizeUnsupported`) instead of attempted; the general-n
value (3/4)^n is MVW Sec. 3.4 (cited theorem, not computed here).

## 4. Certified dual bound (CERTIFIED_NUMERIC)

Weak duality is exact, so any Y' with Y'⊗1 − G ⪰ 0 verified *exactly* gives a rigorous upper bound
Tr Y' on the W1 n-qubit SDP optimum, i.e. on every CPTP 1→2 attack in this game.

Procedure (`qmint/attacks/certify.py`):

1. **Realification.** G_n is real symmetric (BB84 states are real). If Y is feasible then so is Ȳ
   (conjugate the PSD constraint), so Re Y = (Y+Ȳ)/2 is feasible with the same trace. We keep the real
   symmetric part (the dropped imaginary part is reported; it is irrelevant to rigour because feasibility
   is re-verified from scratch in step 3).
2. **Rational rounding.** Y_r = entries rounded to multiples of 2^-40, exactly symmetrised.
3. **Shift.** Floating-point λ̂ = λmin(Y_r⊗1 − G). By Weyl, adding δ·1 to Y raises every eigenvalue of
   Y⊗1 − G by exactly δ (since (δ1)⊗1 = δ1), so δ ≥ max(0, −λmin) + pad suffices in exact arithmetic.
   δ is chosen as the dyadic ceiling of max(0, −λ̂) + 10^-12. The float λ̂ is only a *guess*; it is not
   trusted.
4. **Exact verification.** M = (Y_r + δ1)⊗1 − G is formed in `fractions.Fraction` arithmetic (G rebuilt
   exactly from rational BB84 projectors with entries in {0, ±1/2, 1}) and tested by LDL^T Gaussian
   elimination without pivoting. A real symmetric matrix is positive definite iff all LDL^T pivots are
   > 0 (Sylvester's criterion / inertia), and elimination with exact rationals has no rounding error.
   If any pivot is ≤ 0 the pad is multiplied by 10 and step 4 repeats (never needed in practice: 1 attempt).
5. **Bound.** Tr(Y_r + δ1) is an exact rational; it is reported as that fraction and as the next
   double ≥ it.

Lower side: MVW's channel (Sec. 3.2) has Kraus operators B_k/√12 with integer B_k, so its Choi matrix is
rational and ⟨G_1, J⟩ = 3/4 exactly (also computed in Fractions); for n=2 the product channel gives 9/16
exactly. Together:

| n | from solver | certified upper bound (≥ exact) | exact achieving value | δ |
|---|---|---|---|---|
| 1 | SCS | 0.750000000003638 | 3/4 | 1.8e-12 |
| 1 | Clarabel | 0.7500000004183676 | 3/4 | 4.0e-10 |
| 2 | SCS | 0.562500000007276 | 9/16 | 1.8e-12 |
| 2 | Clarabel | 0.5625000002919478 | 9/16 | 3.4e-10 |

So 3/4 ≤ OPT_1 ≤ 0.750000000003638 and 9/16 ≤ OPT_2 ≤ 0.562500000007276, rigorously (modulo correctness
of the ~40-line exact LDL^T routine and of the model — it certifies the SDP for the stated
finite-dimensional game W1, nothing about physical devices, noise, loss or oracles).

Scope of "CERTIFIED_NUMERIC": this is a machine check of a dual certificate in exact arithmetic, not a
formally verified proof (no proof assistant); a second reviewer (lane D/M) should re-run
`certify.is_positive_definite_exact` with an independent implementation. Status in records:
`evidence_kind = CERTIFIED_NUMERIC`, `dual_feasibility_residual = 0.0` (exactly verified PD).

## 5. W1_CV (classical verification), n=1

MVW Sec. 4.1: Q is block-diagonal in (a1,a2,c1,c2), so the SDP reduces to one POVM {X^{c}_{a}} per
challenge pair c=(c1,c2) — i.e. the counterfeiter's measurement may depend jointly on both
challenges, as in MVW eq. (8) (consistent with lane A's registry note) — with objective (1/4)Σ_c Σ_a Tr(X^c_a B^c_a), B^c_a = Σ_k p_k [a1 valid for
(c1,k) and a2 valid for (c2,k)] ρ_k, valid iff basis ≠ challenge or answer = bit (Sec. 4.2, d=2).
Dual: min Σ_c Tr Y_c s.t. Y_c ⪰ B^c_a/4 ∀a. Numerical (SCS): primal 0.9267766952901, dual
0.9267766953948; certified upper bound (same exact procedure) 0.9267766955417756; theorem value
3/4 + √2/8 = 0.9267766952966369. Only n=1 computed; general n is MVW Lemma 5 + Sec. 3.4 (cited).

## 6. Negative controls (master plan §3.3)

| control | SDP value | reference | outcome |
|---|---|---|---|
| transpose omitted, BB84 | 0.75 | 0.75 | **undetectable** — ρ^T = ρ for real states; G unchanged |
| transpose omitted, six-state ensemble | 0.5 | 2/3 (MVW Sec. 3.3) | detected |
| MVW (Y,Z,X) operator fed as (X,Y,Z), n=1 | 0.75 | 0.75 | **undetectable** — G_1 invariant under permuting its 3 factors for BB84 |
| Q⊗Q without W_π, n=2 | 0.375 | 0.5625 | detected |
| verifier reads qubits in reversed order, n=2 | 0.5625 | 0.5625 | SDP invariant (attacker absorbs SWAP); flagged by honest acceptance = 0.375 ≠ 1 |
| per-note threshold (≥1 of 2 per note), n=2 | 1.0 | 0.5625 | detected; game is W2-type, W1 bound refused by game guard |
| MVW Sec. 3.5 R operator, t=1, n=2 | 0.9375 | eq.(4)=15/16 | matches MVW eq. (4) (cross-check) |
| attacker given secret basis | 1.0 | 0.75 | detected; OUT_OF_MODEL |

Lessons: (i) on the W1 ensemble two classic bugs are invisible to the n=1 golden value, so the six-state
and n=2 controls are required to give the test oracle power; (ii) relabelling bugs (bit order, |±⟩ swap)
cannot be caught by an optimal-attack value at all, because the optimum is invariant under unitary
relabelling of outputs — they must be caught by honest-acceptance checks.

Threshold note: MVW's R counts positions in which **both** copies pass; two *independent* per-note
threshold verifications accept a strictly larger event (e.g. n=2, t=1: give the original qubit 1 to note A
and qubit 2 to note B → both accepted with probability 1). Eq. (4) therefore must not be used as a bound for
per-note threshold verifiers (W2), consistent with the master plan's "no closed form assumed for W2".
