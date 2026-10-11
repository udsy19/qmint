# L-L1: build/CI/CLI/integration infrastructure

Branch `feat/L-infra`, from `ece05ef`. Code commit `234d3c3`; this handoff is in the commit after it.

## Delivered
- `qmint/core/config.py`: central config. Network and paid hardware are **denied by default** (`QMINT_ALLOW_NETWORK`, `QMINT_ALLOW_PAID_HARDWARE`). Also `derive_seed`/`make_rng` and `network_guard`, which blocks sockets.
- `qmint/core/logging.py`: JSON-lines logs with redaction. Covers credential and issuer-secret keys, `IssuerSecret` objects (including inside models), credential env-var values and Bearer tokens.
- `qmint/core/manifest.py` + `scripts/verify_manifest.py`: C6 EvidenceManifest builder. It pins the git sha, a dirty flag, `sha256(requirements.lock)` and the seeds. The verifier exits 1 on a mismatch or missing file and 2 if it finds no manifest.
- `qmint/core/records.py`: append-only `experiments/run_registry.jsonl` + `experiments/results/<id>.json`. Payloads are validated against the frozen contracts. Records are rejected if they lack an evidence kind or provenance, or if they contain a secret. Records are flagged `IRREPRODUCIBLE_STOCHASTIC_RESULT`, `REPRODUCIBILITY_UNCHECKED` or `NO_SEED` when those apply.
- `qmint/core/doctor.py` + `qmint doctor`: dependency report. Missing optional deps show as SKIPPED with the extra to install. Also reports lock drift, disk space, flags, lane availability and credential presence (booleans only).
- `qmint/core/lanes.py`, `qmint/cli.py`: all master-plan section 6 commands. Lanes that are not merged print `NOT_AVAILABLE: lane X module ... not merged` and exit 3. A module that exists but fails to import exits 4 (BROKEN).
- `qmint/core/pipeline.py`, `scripts/run_core.py`, `scripts/run_all.py`: a strict stage runner. A FAIL halts the run, a missing lane is SKIPPED with a reason, and a broken lane is FAIL. The run ends with a status table, a status JSON and a manifest that is checked by re-hashing. `run_all` refuses to run without verified real data and never substitutes fixtures.
- `.github/workflows/ci.yml` (uv, lock install, ruff, pytest without network/realdata, doctor, run_core + verify). Not pushed.
- `docs/REPRODUCIBILITY.md`.

## Tests
`$PY -m pytest tests -m "not network and not realdata"` exits 0 with 86 passed and 1 strict xfail. `ruff check qmint scripts tests` exits 0.

## Critical finding (frozen code, not edited)
The frozen `canonical_json` writes out IssuerSecret bases and bits when the secret sits inside an `Any` field of a contract model, such as `SecurityCertificate.parameters`. I worked around it in RecordStore and the logger. The fix is proposed in the JSON under `interfaces_changed`, and a strict-xfail regression test tracks it.

## Blockers / limitations
- The whole-repo `ruff check .` (and so CI) fails on 2 lint issues in the lead-owned `bootstrap/`.
- No lane entrypoints are merged yet, so run_core runs 2 stages and skips 9.
- The run_all real-data convention (`datasets/manifests/*.json`) still needs lane E to agree to it.
