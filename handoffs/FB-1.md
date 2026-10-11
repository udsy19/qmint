# Handoff FB-1: lane B protocol-boundary fixes (M-B1..M-B4)

- **Branch:** `feat/FB-fixes`, from main `02aeab1`. Code commit `5e4f16a`.
- **Findings fixed:** M-B1 (HIGH), M-B2, M-B3, M-B4 (LOW). Five strict-xfail markers removed from `tests/adversarial/test_m_protocol_boundary.py`; no assertion changed.
- **Tests:** `$PY -m pytest tests -q -m "not network and not slow" -o addopts=""` exit 0: 996 passed, 21 xfailed (baseline 983 passed, 26 xfailed). `ruff check` clean on owned paths.

## What changed
- **M-B1 (no-cloning boundary).** `RegisterHandle` (via the new `NonCopyable` mixin in `qmint/protocols/common.py`) refuses `copy.copy`, `copy.deepcopy`, `pickle` at every protocol, `__reduce__` and `__getstate__`, raising `CapabilityBoundaryError`. A handle rebuilt by a `copyreg`/`dispatch_table` reducer or `object.__new__` + `__dict__` copy is unbound and every operation on it is refused. The public `TokenRecord` can still be `model_copy`'d: that copies a serial, not the state.
- **M-B2 (introspection).** New `PrivateVault`: a simulator-side store keyed by a random opaque id and bound (by weakref identity) to exactly one owner object, dropped on GC.
  - `RegisterHandle` holds only `{record, consumed, _cap_key}`. The register and qubit ids live in the vault.
  - `KentSMoneySession` (Alice-facing) holds no `IssuerSecret`, `t`/`u`, Bob agents' memories or Bob's RNG. They live in a separate `_BobSide` party object in a vault.
  - Lane C's `split`/`measure`/`n_qubits` API, the contracts tests and `tests/integration/test_q_*` are unchanged and pass.
- **M-B3 (serial binding).** `WiesnerChallenger` records the serial each token id was minted under. `redeem` returns `serial_mismatch` for a note presented under another serial, without measuring it and without spending either serial. The victim still redeems.
- **M-B4 (S1 precondition).** `KentSMoneySession` takes an optional `network: SpacetimeNetwork` and `enforce_spacelike`.
  - `s1_presentation_status()` returns `IN_MODEL` only when a network is declared and the two presentation events are certainly spacelike (`qmint.networks.causality.is_spacelike`, clock bounds included). Otherwise it returns `OUT_OF_MODEL`, or `INCOMPLETE` before the second presentation.
  - With `enforce_spacelike=True`, a non-spacelike second presentation raises `SpacelikeViolation` before Bob validates.

## Limitations
- **API boundary only.** This is enforcement at the API boundary of a single-process simulator, **not physics**. Importing the vaults, walking the gc, or calling the private accessors still reaches amplitudes and secrets, and that is OUT_OF_MODEL.
- **Private accessors kept on purpose.** The private accessors `_register`/`_qubits`/`_bob` remain as properties because lane M's two *passing* M-B2 documentation tests use them, and this lane may not edit those tests.
- **Proposal to lane M.** Re-point those tests at the vault; FB then removes the properties.
- **M-B4 is a label/guard, not a re-host.** Bob's per-site outcomes remain readable in-process. The auditor's fuller remedy (run S1 through lane G's engine) is not done.
- **Constructor aliasing.** The `RegisterHandle(register, qubits, record)` constructor can still alias live qubits for code that already holds a register. That is aliasing, not cloning, and reaching the register needs out-of-model introspection.

## Interface notes
- **New reason value.** `RedemptionResult.reason` gains `serial_mismatch`.
- **Kent changes.** `KentSMoneySession` drops its `_secret`/`_rng` attributes; Bob's side is reached via `_bank()`. It gains `network`, `enforce_spacelike` and `s1_presentation_status()`.
- **C1 v2 proposal (not applied).** Handles are non-copyable and non-picklable, as M-M1 proposed.
- **API lab route.** `qmint/api/routes/lab.py` is unaffected (its tests pass), so no edit is needed.
- **Paid jobs:** none.
