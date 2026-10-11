"""Streaming decoders for the Schiansky et al. 2023 timetag archives (Zenodo 7979319 / 7997998).

Format established BY INSPECTION of the archives (not assumed from the record text):

* ``{linear,diagonal}/{ttp,client}_chunkNN.tsv`` -- ASCII text, LF line endings, one header
  line ``channel\\ttag``, then ``<int channel>\\t<decimal float tag_ns>`` per line. The Zenodo
  description "<uint8 c>\\t<double t>" names the column *types*; the records are NOT binary,
  so there is no endianness or fixed record size. Values are already in nanoseconds
  (offset/drift corrected by the authors; they are not raw TTM ticks).
* ``tagfile_example/{SG,BG}.txt`` (v2 record 7997998 only) -- raw AIT TTM8000 text export,
  CRLF, four space-separated integers ``<1> <channel> <1> <tick>``; the authors' prep script
  (Zenodo 8020667, ``01_a_prepdata2.py``) reads columns 1 and 3 and converts ticks with
  82.3045 ps/tick. That constant is quoted from the authors' script, not independently
  verified against TTM8000 documentation (unavailable).

Everything streams from the ZIP member (``zipfile`` + bounded line blocks); nothing is
extracted to disk. Per-record ``decode_status`` follows C2 ``PhotonEvent``.
"""

from __future__ import annotations

import io
import itertools
import re
import zipfile
import zlib
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from qmint.core.contracts import PhotonEvent

ARCHIVE_TSV_HEADER = "channel\ttag"
TTM8000_TICK_NS = 0.0823045  # authors' 01_a_prepdata2.py: "*82.3045/1000" (ps -> ns)

STATUS_CODES: tuple[str, ...] = ("ok", "malformed", "duplicate", "out_of_range")
OK, MALFORMED, DUPLICATE, OUT_OF_RANGE = range(4)

_MEMBER_RE = re.compile(r"^(linear|diagonal)/(ttp|client)_chunk(\d+)\.tsv$")


class CorruptArchiveError(RuntimeError):
    """ZIP container or member failed integrity checks (CRC, deflate stream, structure)."""


@dataclass(frozen=True)
class TagBlock:
    """Column-oriented decoded records. ``t_ns`` is NaN and ``channel`` 0 for malformed rows."""

    channel: np.ndarray  # uint8
    t_ns: np.ndarray  # float64, as recorded (never rescaled except TTM ticks -> ns)
    record_index: np.ndarray  # int64, 0-based data-line index within the member (header excluded)
    status: np.ndarray  # uint8 codes into STATUS_CODES

    def __len__(self) -> int:
        return int(self.channel.shape[0])

    def ok(self) -> TagBlock:
        m = self.status == OK
        return TagBlock(self.channel[m], self.t_ns[m], self.record_index[m], self.status[m])

    def status_counts(self) -> dict[str, int]:
        c = np.bincount(self.status, minlength=len(STATUS_CODES))
        return {s: int(c[i]) for i, s in enumerate(STATUS_CODES)}

    @staticmethod
    def concat(blocks: Iterable[TagBlock]) -> TagBlock:
        bl = list(blocks)
        if not bl:
            return TagBlock(
                np.empty(0, np.uint8), np.empty(0, np.float64), np.empty(0, np.int64), np.empty(0, np.uint8)
            )
        return TagBlock(*(np.concatenate([getattr(b, f) for b in bl]) for f in TagBlock.__dataclass_fields__))


@dataclass(frozen=True)
class MemberKey:
    basis_folder: str  # "linear" | "diagonal"
    side: str  # "ttp" | "client"
    chunk: int


def parse_member_name(name: str) -> MemberKey | None:
    m = _MEMBER_RE.match(name)
    return MemberKey(m.group(1), m.group(2), int(m.group(3))) if m else None


def open_archive(path: str | Path) -> zipfile.ZipFile:
    """Open a ZIP, raising :class:`CorruptArchiveError` on a damaged container."""
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError, EOFError) as exc:
        raise CorruptArchiveError(f"{path}: {exc}") from exc
    return zf


def archive_members(zf: zipfile.ZipFile) -> dict[MemberKey, str]:
    """Map recognised data members (ignoring __MACOSX, README, LICENSE, tagfile_example)."""
    out = {}
    for n in zf.namelist():
        k = parse_member_name(n)
        if k is not None:
            out[k] = n
    return out


def _classify(
    channel: np.ndarray,
    t: np.ndarray,
    status: np.ndarray,
    allowed_channels: frozenset[int] | None,
    prev: tuple[int, float] | None,
) -> tuple[int, float] | None:
    """Assign duplicate / out_of_range codes in-place, sequentially against the last ok record."""
    ok = status == OK
    if allowed_channels is not None:
        bad = ok & ~np.isin(channel, np.fromiter(allowed_channels, dtype=np.int64))
        status[bad] = OUT_OF_RANGE
        ok &= ~bad
    idx = np.flatnonzero(ok)
    if idx.size == 0:
        return prev
    tc, cc = t[idx], channel[idx].astype(np.int64)
    prev_t = np.concatenate([[prev[1] if prev else -np.inf], tc[:-1]])
    prev_c = np.concatenate([[prev[0] if prev else -1], cc[:-1]])
    dup = (tc == prev_t) & (cc == prev_c)
    # time going backwards relative to the previous accepted record: out_of_range
    back = tc < prev_t
    status[idx[dup]] = DUPLICATE
    status[idx[back & ~dup]] = OUT_OF_RANGE
    # NOTE: comparison is with the immediately preceding ok-classified line (single pass,
    # deterministic). Archives inspected so far contain zero such records.
    return int(cc[-1]), float(tc[-1])


def _decode_lines(
    lines: list[str], first_index: int, ncols: int, chan_col: int, tag_col: int, sep: str | None,
    tick_ns: float | None,
) -> TagBlock:
    """Fast vectorised parse; on any malformed line fall back to per-line parsing for this block."""
    n = len(lines)
    arr = np.full((n, ncols), np.nan)
    try:
        parsed = np.loadtxt(io.StringIO("".join(lines)), delimiter=sep, dtype=np.float64, ndmin=2)
        if parsed.shape != (n, ncols):
            raise ValueError("ragged block")
        arr = parsed
    except ValueError:
        for i, line in enumerate(lines):
            row = _parse_row(line, sep, ncols)
            if row is not None:
                arr[i] = row
    ch, tag = arr[:, chan_col], arr[:, tag_col]
    valid = np.isfinite(tag) & np.isfinite(ch) & (ch >= 0) & (ch <= 255) & (ch == np.floor(ch))
    channel = np.zeros(n, np.uint8)
    t = np.full(n, np.nan)
    channel[valid] = ch[valid].astype(np.uint8)
    t[valid] = tag[valid] * tick_ns if tick_ns else tag[valid]
    status = np.where(valid, OK, MALFORMED).astype(np.uint8)
    return TagBlock(channel, t, np.arange(first_index, first_index + n, dtype=np.int64), status)


def _parse_row(line: str, sep: str | None, ncols: int) -> np.ndarray | None:
    parts = line.strip().split(sep)
    if len(parts) != ncols:
        return None
    try:
        return np.array([float(p) for p in parts])
    except ValueError:
        return None


def _iter_text(zf: zipfile.ZipFile, member: str) -> Iterator[str]:
    try:
        with zf.open(member) as raw:
            yield from io.TextIOWrapper(raw, encoding="ascii", errors="replace", newline=None)
    except (zipfile.BadZipFile, zlib.error, EOFError) as exc:
        raise CorruptArchiveError(f"member {member!r}: {exc}") from exc


def _iter_blocks(lines: Iterator[str], block_lines: int, decode, allowed, start_index: int = 0) -> Iterator[TagBlock]:
    prev = None
    idx = start_index
    while True:
        chunk = [ln for ln in itertools.islice(lines, block_lines)]
        if not chunk:
            return
        blk = decode(chunk, idx)
        prev = _classify(blk.channel, blk.t_ns, blk.status, allowed, prev)
        idx += len(chunk)
        yield blk


def iter_tsv_member(
    zf: zipfile.ZipFile,
    member: str,
    *,
    block_lines: int = 200_000,
    allowed_channels: frozenset[int] | None = None,
) -> Iterator[TagBlock]:
    """Stream an archived ``channel\\ttag`` TSV member in bounded blocks."""
    lines = _iter_text(zf, member)
    header = next(lines, None)
    if header is None or header.strip() != ARCHIVE_TSV_HEADER:
        raise CorruptArchiveError(f"member {member!r}: unexpected header {header!r}")

    def dec(chunk: list[str], i0: int) -> TagBlock:
        return _decode_lines(chunk, i0, 2, 0, 1, "\t", None)

    yield from _iter_blocks(lines, block_lines, dec, allowed_channels)


def read_tsv_member(zf: zipfile.ZipFile, member: str, **kw) -> TagBlock:
    return TagBlock.concat(iter_tsv_member(zf, member, **kw))


def iter_ttm8000_member(
    zf: zipfile.ZipFile,
    member: str,
    *,
    block_lines: int = 500_000,
    tick_ns: float = TTM8000_TICK_NS,
    allowed_channels: frozenset[int] | None = None,
    max_lines: int | None = None,
) -> Iterator[TagBlock]:
    """Stream a raw TTM8000 text export (``1 <ch> 1 <tick>``); ticks converted to ns."""
    lines: Iterator[str] = _iter_text(zf, member)
    if max_lines is not None:
        lines = itertools.islice(lines, max_lines)

    def dec(chunk: list[str], i0: int) -> TagBlock:
        return _decode_lines(chunk, i0, 4, 1, 3, None, tick_ns)

    yield from _iter_blocks(lines, block_lines, dec, allowed_channels)


def to_photon_events(
    block: TagBlock,
    *,
    dataset_id: str,
    file_hash: str,
    channel_mapping_version: str,
    coincidence_ids: list[str | None] | None = None,
) -> list[PhotonEvent]:
    """Materialise C2 ``PhotonEvent`` records (use on small slices; one pydantic object per row)."""
    out = []
    for i in range(len(block)):
        st = STATUS_CODES[int(block.status[i])]
        t = float(block.t_ns[i])
        out.append(
            PhotonEvent(
                dataset_id=dataset_id,
                file_hash=file_hash,
                record_index=int(block.record_index[i]),
                raw_channel=int(block.channel[i]),
                arrival_ns=t if np.isfinite(t) else 0.0,  # malformed rows carry no time; status says so
                channel_mapping_version=channel_mapping_version,
                coincidence_id=coincidence_ids[i] if coincidence_ids else None,
                decode_status=st,
            )
        )
    return out
