"""Calibration / QBER / scope tests on SYNTHETIC fixtures with known error counts."""

from __future__ import annotations

import numpy as np
import pytest

from qmint.core.contracts import Basis, CalibrationRecord, EvidenceKind, Interval, Unit
from qmint.core.serialization import canonical_hash, file_sha256
from qmint.photonics.calibration import (
    EXPERIMENT_FAMILY,
    InapplicableCalibration,
    analyze_archive,
    analyze_run,
    bias_interval,
    calibration_record,
    check_consumer,
    published_aggregate_record,
    summarize,
)
from qmint.photonics.channels import ChannelMappingError, detect_channel_swap
from qmint.photonics.parser import TagBlock
from qmint.photonics.synthetic import standard_archive, synth_pairs


def _blk(ch, t):
    n = len(ch)
    return TagBlock(np.asarray(ch, np.uint8), np.asarray(t, float), np.arange(n), np.zeros(n, np.uint8))


def test_qber_known_counts_and_denominators():
    tc, tt, cc, ct = synth_pairs(400, client_basis="Z", n_errors_by_state={2: 3, 3: 5}, seed=0)
    r = analyze_run(_blk(tc, tt), _blk(cc, ct), "linear", 0)
    assert r.n_pairs == 400
    assert r.n_sifted == 200  # only TTP H/V rows count in the Z denominator
    assert r.n_errors == 8
    assert r.n_ttp_z == 200
    assert r.pairing_violations == 0 and r.rematch_identical
    assert r.table[0].tolist() == [3, 97] and r.table[1].tolist() == [95, 5]


def test_channel_swap_detected():
    tc, tt, cc, ct = synth_pairs(400, client_basis="X", n_errors_by_state={4: 2}, seed=1)
    swapped = np.where(cc == 2, 4, 2).astype(np.uint8)  # client detectors swapped
    with pytest.raises(ChannelMappingError, match="swapped"):
        analyze_run(_blk(tc, tt), _blk(swapped, ct), "diagonal", 0)
    with pytest.raises(ChannelMappingError):
        detect_channel_swap(0, 0)


def test_unmapped_channel_rejected():
    tc, tt, cc, ct = synth_pairs(40, client_basis="Z", n_errors_by_state={}, seed=2)
    tc = tc.copy()
    tc[0] = 7
    with pytest.raises(ChannelMappingError, match="unmapped"):
        analyze_run(_blk(tc, tt), _blk(cc, ct), "linear", 0)


def test_unpaired_rows_rejected():
    tc, tt, cc, ct = synth_pairs(40, client_basis="Z", n_errors_by_state={}, seed=2)
    with pytest.raises(ValueError, match="row counts"):
        analyze_run(_blk(tc, tt), _blk(cc[:-1], ct[:-1]), "linear", 0)


def test_archive_summary_and_record(tmp_path):
    p = standard_archive(tmp_path / "s.zip")
    runs = analyze_archive(p)
    sz, sx = summarize(runs, Basis.Z), summarize(runs, Basis.X)
    assert (sz.n_errors, sz.n_sifted) == (8, 400)
    assert (sx.n_errors, sx.n_sifted) == (6, 400)
    assert sz.qber == 8 / 400
    # paper's estimator: mean over states of P(err | state) = mean(3/200, 5/200)
    assert sz.error_given_state == {"H": 3 / 200, "V": 5 / 200}
    assert sz.qber_state_avg == pytest.approx(0.02)
    sha = file_sha256(p)
    rec = calibration_record(sz, dataset_sha256=sha, dataset_tag="synthetic", runs=runs)
    assert rec.experiment_family == EXPERIMENT_FAMILY
    assert rec.data_origin == EvidenceKind.SYNTHETIC and rec.dataset_sha256 == sha  # README carries the tag
    assert rec.qber_interval.lo <= sz.qber <= rec.qber_interval.hi
    assert rec.loss_interval is None and rec.detection_efficiency_interval is None  # never invented
    assert rec.multiphoton_interval is None
    assert rec.n_events == 800


def test_origin_label_follows_the_archive(tmp_path):
    """Synthetic archives yield SYNTHETIC records; only untagged (real) archives yield PHOTON_EXPERIMENT."""
    runs = analyze_archive(standard_archive(tmp_path / "s.zip"))
    assert all(r.synthetic for r in runs)
    for r in runs:
        r.synthetic = False  # stand-in for a real archive (no SYNTHETIC README)
    rec = calibration_record(summarize(runs, Basis.Z), dataset_sha256="c" * 64, dataset_tag="t", runs=runs)
    assert rec.data_origin == EvidenceKind.PHOTON_EXPERIMENT


@pytest.mark.parametrize(("lo", "hi", "point", "want"), [
    (0.49, 0.51, 0.497, (0.0, 0.01, 0.003)),      # straddles 1/2 -> bias interval starts at 0
    (0.40, 0.45, 0.42, (0.05, 0.10, 0.08)),        # entirely below 1/2
    (0.52, 0.60, 0.55, (0.02, 0.10, 0.05)),        # entirely above 1/2
])
def test_bias_interval_is_distance_from_half(lo, hi, point, want):
    b = bias_interval(Interval(lo=lo, hi=hi, unit=Unit.FRACTION, point=point))
    assert (b.lo, b.hi, b.point) == pytest.approx(want)


def test_record_basis_bias_is_a_bias_not_a_fraction(tmp_path):
    """KE finding: basis_bias_interval = |p_Z - 1/2| (Kent beta_PB semantics), not p_Z (~0.5)."""
    runs = analyze_archive(standard_archive(tmp_path / "s.zip"))
    s = summarize(runs, Basis.Z)
    rec = calibration_record(s, dataset_sha256="c" * 64, dataset_tag="t", runs=runs)
    bb = rec.basis_bias_interval
    assert 0.0 <= bb.lo <= bb.point <= bb.hi < 0.5
    assert bb.point == pytest.approx(abs(s.ttp_z_frac - 0.5))
    assert bb.hi == pytest.approx(max(abs(x - 0.5) for x in (*s.ttp_z_frac_cp, *s.ttp_z_frac_boot_runs)))


def test_photon_experiment_requires_hash():
    with pytest.raises(ValueError):
        CalibrationRecord(calibration_id="x", device_id="d", experiment_family=EXPERIMENT_FAMILY,
                          data_origin=EvidenceKind.PHOTON_EXPERIMENT, n_events=1, confidence_level=0.95,
                          interval_method="m", independence_assumptions=["a"])


def test_inapplicable_transfer_rejected(tmp_path):
    runs = analyze_archive(standard_archive(tmp_path / "s.zip"))
    rec = calibration_record(summarize(runs, Basis.X), dataset_sha256="b" * 64, dataset_tag="t", runs=runs)
    check_consumer(rec, "schiansky_payment_2023")
    for pid in ("s_money_kent_2022_realistic", "s_money_kent_2022_ideal_2site", "wiesner_noisy"):
        with pytest.raises(InapplicableCalibration):
            check_consumer(rec, pid)


def test_published_aggregate_is_separately_tagged():
    r = published_aggregate_record()
    assert r.data_origin == EvidenceKind.PUBLISHED_AGGREGATE
    assert r.loss_interval.point == pytest.approx(0.224)
    assert r.dataset_sha256 is None


def test_deterministic_output_hash(tmp_path):
    hashes = []
    for i in range(2):
        p = standard_archive(tmp_path / f"s{i}.zip")
        runs = analyze_archive(p)
        recs = [calibration_record(summarize(runs, b), dataset_sha256=file_sha256(p), dataset_tag="synthetic",
                                   runs=runs) for b in (Basis.Z, Basis.X)]
        hashes.append((file_sha256(p), canonical_hash(recs)))
    assert hashes[0] == hashes[1]
