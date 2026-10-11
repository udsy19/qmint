# Reproducing QMint figures and tables (DRAFT, lane N phase 1)

Status: draft for the lead. The root `REPRODUCE.md` is finalised at gate G7. These commands were
written against branch `feat/N-paper`, which includes lanes A-H, J and L. Commands that need the
network or a paid account are marked; nothing here submits a hardware job.

## 0. Clean-room environment

```bash
git clone <repo> qmint && cd qmint
uv venv && uv pip install -r requirements.lock && uv pip install --no-deps -e .
python -m qmint.cli doctor            # dependency report; network and paid hardware are off by default
```

## 1. Offline checks (no network)

```bash
python -m pytest tests -m "not network and not realdata and not slow"
python -m ruff check qmint scripts tests
python scripts/run_core.py --offline --seed 42     # strict stage runner; writes a verified manifest
```

## 2. Regenerate figures and tables from committed evidence

```bash
python -m qmint.evaluation.make_figures --check                      # FRESH / STALE / PENDING per figure
python -m qmint.evaluation.make_figures --out figures --tables-out reports/paper
python scripts/verify_manifest.py figures                            # re-hash every pinned input/output
```

- Each figure writes `figures/<id>_<slug>.{svg,png,csv,caption.json,manifest.json}`. The manifest
  pins every input file, every executed module, every output, the git sha and `sha256(requirements.lock)`.
- A figure is rebuilt only when it is stale, meaning a pinned hash changed or the spec changed.
  `--force` rebuilds everything. Builds are byte-deterministic for fixed library versions.
- PENDING figures (6-9) are placeholders without numbers. They become real figures only when
  non-SYNTHETIC records exist in the lane-L record store `experiments/`.

## 3. Regenerate the upstream evidence the figures read

| Evidence | Command | Notes |
|---|---|---|
| Fig. 2/3 attacks + SDP (`handoffs/C-C1-evidence.json`) | `python -m qmint.attacks.report --out handoffs/C-C1-evidence.json [--clarabel-n2]` | ~110 s; Clarabel n=2 needs several GB of RAM |
| Fig. 5 Kent reproduction + certificates (`proofs/certificates/`) | `python -m qmint.proofs.reproduce --out proofs/certificates` | deterministic, offline |
| Fig. 10 circuits (`handoffs/F-F1_evidence.json`) | `python -m qmint.quantum.evidence handoffs/F-F1_evidence.json <git-sha>` | local Aer only |
| Fig. 10 8-qubit runs (`qollab/evidence/`) | `python -m qmint.quantum.ionq --out qollab/evidence` | local Aer + dry run; never submits |
| Fig. 4 photon data (`reports/data_working/schiansky2023/`) | **network:** download Zenodo 7979319 (and 7997998 for the raw cross-check) with `qmint.photonics.zenodo`, then `python -m qmint.photonics.schiansky2023` | checks the archive's upstream md5; sha256 recorded in the manifest |

After regenerating any of these, re-run step 2. `--check` will report the dependent figures as
STALE until they are rebuilt.

## 4. What this does not reproduce

- No QPU result exists. Lane J's procedure for an authorized human run is in `qmint/quantum/ionq.py`
  (`HUMAN_RUN_PROCEDURE`).
- Figures 6-9 are pending lanes GH (matched spacetime/latency records) and I (compiler).
- Figure 1 (protocol schematic) is not part of this harness yet.
