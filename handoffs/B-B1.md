# B-B1 Wiesner (ideal + noisy) -- lane B handoff

- Code: `qmint/protocols/{register,common,wiesner}.py`; tests `tests/unit/protocols/test_protocols_wiesner.py`.
- `WiesnerChallenger` (bank) holds the `IssuerSecret`s. The wallet gets a `RegisterHandle` (public `TokenRecord` with the serial only). Modes: EXACT, SHOTS and SYMBOLIC. Lane C's attacks plug in through `RegisterHandle.split(kraus, joint=...)`, which turns one note into two candidate notes, followed by `verify_pair` or `pair_acceptance_probability`.
- `wiesner_noisy` (game W2) applies a depolarizing or bit-flip channel inside the verifier and accepts when the error count is at most t. Honest acceptance equals binomial survival. For bit-flip noise it is Bin(n_Z, p), because X-basis states are immune to X flips.
- Lifecycle: serial collision check, spend-once, replay refusal, remint. `leak_secret_TEST_ONLY` lets a trivial forger win 50/50 trials (OUT_OF_MODEL).
- Correction to the work order: Z measure-resend gives 3/4 per qubit for a single copy, but the W1 event (both copies valid) is 5/8 per qubit.
- Contract gap: `IssuerSecret` can be deep-copied, because pydantic's own deepcopy bypasses the pickle guard. A migration is proposed. Challengers refuse copy and pickle via `SecretHolder`.
- Tests: `pytest tests/contracts tests/unit/protocols` exits 0 with 135 passed. Ruff is clean.
