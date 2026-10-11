# Datasets

Raw data are never committed. They live in a shared cache outside every worktree:
`/Users/udsy/PycharmProjects/qmint-data-cache/` (override with `QMINT_DATA_CACHE`). Only
manifests (here) and small derived outputs (`reports/data_working/`) are versioned.

| Dataset | Manifest | Use in QMint | Evidence kind |
|---|---|---|---|
| Schiansky et al. 2023 timetags, Zenodo 7979319 (v1) / 7997998 (v2, latest) | `manifests/zenodo_7979319.yaml` | Coincidence counts, QBER per basis, TTP basis split, calibration records (`experiment_family="schiansky_2023"`) | `PHOTON_EXPERIMENT` |
| Authors' analysis code, Zenodo 8020667 (+ 7985331, 7997961) | `manifests/zenodo_8020667.yaml` | Read for methodology only (license conflict, AGPL-3.0 file); no code copied | n/a |

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
Detection efficiency, loss and multiphoton probability can't be observed from the archive (it
holds coincidence-filtered tags only), so they stay `null`. The paper's own values are kept apart
under `PUBLISHED_AGGREGATE`.
