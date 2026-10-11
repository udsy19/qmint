# Datasets

Raw data are never committed. They live in a shared cache outside every worktree:
`/Users/udsy/PycharmProjects/qmint-data-cache/` (override with `QMINT_DATA_CACHE`). Only
manifests (here) and small derived outputs (`reports/data_working/`) are versioned.

| Dataset | Manifest | Use in QMint | Evidence kind |
|---|---|---|---|
| Schiansky et al. 2023 timetags, Zenodo 7979319 (v1) / 7997998 (v2, latest) | `manifests/zenodo_7979319.yaml` (+ `.json`) | Coincidence counts, QBER per basis, TTP basis bias, calibration records (`experiment_family="schiansky_2023"`) | `PHOTON_EXPERIMENT` |
| Authors' analysis code, Zenodo 8020667 (+ 7985331, 7997961) | `manifests/zenodo_8020667.yaml` | Read for methodology only (license conflict, AGPL-3.0 file); no code copied | n/a |

## Manifest formats

- **YAML** (`manifests/*.yaml`, human-curated): full provenance per Zenodo version. A dataset manifest
  declares `experiment_family`; that binds every archive `sha256` in it to one calibration family.
  `qmint.photonics.zenodo.registered_datasets()` reads this table, and the proof engine
  (`qmint.proofs.assumption_check.check_calibration`) accepts a `PHOTON_EXPERIMENT` calibration only
  if its `dataset_sha256` is registered here with the same family, `n_events >= 1000` and
  `confidence_level >= 0.95`. Code-only records (`zenodo_8020667.yaml`) declare no family.
- **JSON** (`manifests/<same stem>.json`): the C6 `EvidenceManifest` consumed by
  `scripts/run_all.py` (`qmint.core.pipeline.realdata_preflight`). It lists the primary input only
  (v1 `Archive.zip`) at the run_all cache path `datasets/cache/zenodo_7979319/Archive.zip`, so run_all
  re-hashes it before running. Point `datasets/cache` at the shared cache (e.g. a symlink of the whole
  directory) to satisfy it. Regenerate after editing a YAML with
  `zenodo.dataset_evidence_manifest(yaml, git_sha=..., created_utc=...)`;
  `tests/unit/photonics/test_photonics_confidence_zenodo.py` fails if the two drift apart.

## Reproduce

```bash
PY=/Users/udsy/PycharmProjects/Qollab-QMint/.venv/bin/python
# 1. download + verify (Zenodo MD5 checked, local SHA-256 recorded)
$PY -c "from qmint.photonics.zenodo import *; [download(f, data_cache_dir()/f'zenodo_{r}') for r in (7979319, 7997998) for f in record_files(fetch_record(r))]"
# 2. analyse (streams from the ZIPs; nothing is extracted to disk)
$PY -m qmint.photonics.schiansky2023 --out reports/data_working/schiansky2023
# 3. real-data tests (skip automatically if the cache is missing)
$PY -m pytest tests/unit/photonics -m realdata
```

Disk: v1 is 146 MiB and v2 is 277 MiB compressed. The analysis keeps at most about 26 M raw events in
memory (around 0.5 GB, for the v2 raw cross-check). Skip that step with `--no-raw`.

## Scope rule

These records describe the 2023 entangled-photon, 641 m fiber, quantum-digital-payment setup.
`qmint.photonics.calibration.check_consumer` rejects them for every protocol except
`schiansky_payment_2023`. They must not calibrate S-money (Kent et al. 2022) or Wiesner proofs.
`basis_bias_interval` is the bias |p_Z − ½| of the TTP's passive basis split (≈0.003), the quantity
Kent et al. call β_PB. It is not the Z fraction (≈0.497).

Per-run error rates are overdispersed / heterogeneous across runs (χ²/dof ≈ 10 in both bases,
driven by single outlier runs). There is no evidence of monotone drift: a run-level Welch test of the
contiguous halves gives p = 0.33 (D/A) and 0.59 (H/V). The earlier "non-stationarity" reading
(p = 0.003) came from a pooled two-proportion test that treats every pair as iid, which is invalid at
this dispersion; it is kept in `summary.json` only as `pooled_iid_p_value`. The calibration intervals
stay widened by the run/block bootstrap hull.

Synthetic timetag archives (`qmint.photonics.synthetic`, used by tests and the run_core stage) carry a
`SYNTHETIC` README tag, and calibration records built from them are labelled `SYNTHETIC`, never
`PHOTON_EXPERIMENT`.

Detection efficiency, loss and multiphoton probability can't be observed from the archive (it
holds coincidence-filtered tags only), so they stay `null`. The paper's own values are kept apart
under `PUBLISHED_AGGREGATE`.
