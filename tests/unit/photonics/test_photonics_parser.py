"""Parser tests on SYNTHETIC tagged fixtures."""

from __future__ import annotations

import zipfile

import numpy as np
import pytest

from qmint.photonics.parser import (
    TTM8000_TICK_NS,
    CorruptArchiveError,
    MemberKey,
    TagBlock,
    archive_members,
    iter_tsv_member,
    iter_ttm8000_member,
    open_archive,
    read_tsv_member,
    to_photon_events,
)
from qmint.photonics.synthetic import standard_archive, synth_pairs, tsv_bytes

SHA = "a" * 64


def _zip_with(tmp_path, name, data: bytes):
    p = tmp_path / "a.zip"
    with zipfile.ZipFile(p, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name, data)
    return p


def test_known_epoch_roundtrip(tmp_path):
    tc, tt, cc, ct = synth_pairs(1000, client_basis="Z", n_errors_by_state={}, seed=7)
    z = open_archive(standard_archive(tmp_path / "s.zip"))
    m = archive_members(z)
    assert set(m) >= {MemberKey("linear", "ttp", 0), MemberKey("diagonal", "client", 1)}
    p = _zip_with(tmp_path, "linear/ttp_chunk00.tsv", tsv_bytes(tc, tt))
    blk = read_tsv_member(open_archive(p), "linear/ttp_chunk00.tsv")
    assert len(blk) == 1000
    np.testing.assert_array_equal(blk.channel, tc)
    np.testing.assert_allclose(blk.t_ns, np.round(tt, 7), rtol=0, atol=1e-6)
    np.testing.assert_array_equal(blk.record_index, np.arange(1000))
    assert blk.status_counts() == {"ok": 1000, "malformed": 0, "duplicate": 0, "out_of_range": 0}


def test_streaming_blocks_equal_whole(tmp_path):
    tc, tt, _, _ = synth_pairs(1001, client_basis="Z", n_errors_by_state={}, seed=1)
    p = _zip_with(tmp_path, "linear/ttp_chunk00.tsv", tsv_bytes(tc, tt))
    z = open_archive(p)
    small = TagBlock.concat(iter_tsv_member(z, "linear/ttp_chunk00.tsv", block_lines=97))
    big = read_tsv_member(z, "linear/ttp_chunk00.tsv")
    for f in ("channel", "t_ns", "record_index", "status"):
        np.testing.assert_array_equal(getattr(small, f), getattr(big, f))


def test_malformed_duplicate_out_of_range(tmp_path):
    body = (
        "channel\ttag\n"
        "2\t10.0\n"
        "2\t10.0\n"  # exact duplicate of previous record
        "x\t11.0\n"  # malformed channel
        "3\tnan\n"  # non-finite time -> malformed
        "9\t12.0\n"  # channel not in mapping -> out_of_range
        "4\t5.0\n"  # time goes backwards -> out_of_range
        "300\t13.0\n"  # > uint8 -> malformed
        "5\t14.0\n"
        "5\n"  # missing column -> malformed
    )
    p = _zip_with(tmp_path, "linear/ttp_chunk00.tsv", body.encode())
    blk = read_tsv_member(open_archive(p), "linear/ttp_chunk00.tsv", allowed_channels=frozenset({2, 3, 4, 5}))
    codes = [("ok", "duplicate", "malformed", "malformed", "out_of_range", "out_of_range", "malformed", "ok",
              "malformed")]
    from qmint.photonics.parser import STATUS_CODES

    assert [STATUS_CODES[s] for s in blk.status] == list(codes[0])
    assert blk.ok().channel.tolist() == [2, 5]


def test_bad_header_rejected(tmp_path):
    p = _zip_with(tmp_path, "linear/ttp_chunk00.tsv", b"time\tchan\n1\t2\n")
    with pytest.raises(CorruptArchiveError, match="header"):
        read_tsv_member(open_archive(p), "linear/ttp_chunk00.tsv")


def test_corrupted_archive_fails(tmp_path):
    p = standard_archive(tmp_path / "s.zip")
    raw = bytearray(p.read_bytes())
    # flip bytes inside the first data member's compressed stream
    z = zipfile.ZipFile(p)
    info = z.getinfo("diagonal/client_chunk00.tsv")
    start = info.header_offset + 30 + len(info.filename) + len(info.extra) + 50
    for i in range(start, start + 40):
        raw[i] ^= 0xFF
    bad = tmp_path / "bad.zip"
    bad.write_bytes(bytes(raw))
    with pytest.raises(CorruptArchiveError):
        read_tsv_member(open_archive(bad), "diagonal/client_chunk00.tsv")


def test_truncated_archive_fails(tmp_path):
    p = standard_archive(tmp_path / "s.zip")
    bad = tmp_path / "trunc.zip"
    bad.write_bytes(p.read_bytes()[:-200])
    with pytest.raises(CorruptArchiveError):
        open_archive(bad)


def test_ttm8000_raw_format(tmp_path):
    body = b"1 4 1 58270270\r\n1 2 1 151225632\r\n1 4 1 151827645\r\n"
    p = _zip_with(tmp_path, "tagfile_example/BG.txt", body)
    blk = TagBlock.concat(iter_ttm8000_member(open_archive(p), "tagfile_example/BG.txt"))
    assert blk.channel.tolist() == [4, 2, 4]
    np.testing.assert_allclose(blk.t_ns, np.array([58270270, 151225632, 151827645]) * TTM8000_TICK_NS)


def test_photon_events_contract(tmp_path):
    p = _zip_with(tmp_path, "linear/ttp_chunk00.tsv", b"channel\ttag\n2\t1.5\nbad\n")
    blk = read_tsv_member(open_archive(p), "linear/ttp_chunk00.tsv")
    ev = to_photon_events(blk, dataset_id="synthetic:fixture", file_hash=SHA, channel_mapping_version="v")
    assert [e.decode_status for e in ev] == ["ok", "malformed"]
    assert ev[0].arrival_ns == 1.5 and ev[0].raw_channel == 2 and ev[0].record_index == 0
