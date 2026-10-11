"""Real-data checks against Zenodo 7979319 (PHOTON_EXPERIMENT). Skipped if the cache is absent."""

from __future__ import annotations

import pytest

from qmint.core.contracts import Basis
from qmint.photonics.calibration import analyze_archive, summarize
from qmint.photonics.schiansky2023 import ARCHIVE_UPSTREAM_MD5, default_archive
from qmint.photonics.zenodo import verify_upstream_checksum

pytestmark = pytest.mark.realdata

ARCHIVE = default_archive()


@pytest.fixture(scope="module")
def runs():
    if not ARCHIVE.exists():
        pytest.skip(f"real dataset not in cache: {ARCHIVE}")
    verify_upstream_checksum(ARCHIVE, ARCHIVE_UPSTREAM_MD5)
    return analyze_archive(ARCHIVE)


def test_archive_integrity_and_pairing(runs):
    assert len(runs) == 22
    assert all(r.pairing_violations == 0 and r.rematch_identical for r in runs)
    assert all(r.decode_status["ok"] == 2 * r.n_pairs for r in runs)


def test_exact_counts(runs):
    sz, sx = summarize(runs, Basis.Z), summarize(runs, Basis.X)
    assert (sz.n_pairs, sz.n_sifted, sz.n_errors) == (4394577, 2183822, 31231)
    assert (sx.n_pairs, sx.n_sifted, sx.n_errors) == (4570301, 2294692, 75417)


def test_reproduces_published_error_rates(runs):
    # Paper (Nat. Commun. 14, 3849): 1.45 +/- 0.01 % (H/V), 3.28 +/- 0.01 % (D/A)
    assert round(summarize(runs, Basis.Z).qber_state_avg * 100, 2) == 1.45
    assert round(summarize(runs, Basis.X).qber_state_avg * 100, 2) == 3.28
