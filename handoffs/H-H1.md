# Handoff H-H1: classical comparators H0–H6 (lane H)

Branch `feat/H-classical`, starting at `ece05ef`. Code commit `1051ee5`; reports commit `6d40865`. The final SHA is in `git log`.

**Tests:** `pytest tests/contracts tests/unit/classical` gives 61 passed (43 lane H + 18 contracts), exit 0. `ruff` is clean.

**What was built:** pure deterministic state machines, `handle(Message, now_ns) -> list[Message]`, for:
- H0: bearer negative control.
- H1: CAS ledger with idempotency keys, HMAC-authenticated requests, retries and replay handling.
- H2: sharded f-fault quorum with a home-shard leader.
- H3: three modes — preassigned, late-commit-disclosed, and late-commit with an ideal OT (private).
- H4: ML-DSA signed tokens, alone and combined with H1 or H3.
- H5: secure-element trust model, including the broken-assumption case.
- H6: Chaum–Fiat–Naor 1988 §1 e-cash with ex-post tracing.

These produce 23 C6 BenchmarkRecords (MODELLED_LATENCY) and the X11 comparability matrix.

**Key results:**
- **Double spends:** they succeed in H0, H4-alone, H5 with the assumption violated (classified OUT_OF_MODEL) and H6 (detection, not prevention). They are prevented in H1, H2, H3, H4+H1, H4+H3 and H5 with the assumption holding.
- **Coordination is not S1's distinction:** S1 itself needs the Stage-II bit `c` relayed to both sites (Kent 2022 Table I steps 7–9). H3 with OT reproduces late choice, local acceptance and issuer-blind commit. What remains different is that the classical version is computational, while S1's ideal model is information-theoretic.

See `reports/classical_baseline_notes/README.md` and `handoffs/H-H1.json` for limitations and interface proposals.
