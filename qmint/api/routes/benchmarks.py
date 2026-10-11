"""GET /benchmarks -- transaction-latency rows from lane G (``qmint.networks``).

Modelled (MODELLED_LATENCY, lane-G event simulation) next to the published aggregates of
Jiang et al. 2024 (PUBLISHED_AGGREGATE) and the committed RIPE Atlas fixture (MEASURED_LATENCY,
one-way = RTT/2 assumption flagged). These rows are NOT a matched quantum-vs-classical benchmark:
classical baselines (lane H) are NOT_AVAILABLE until that lane merges.
"""

from __future__ import annotations

import statistics
from functools import lru_cache
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from qmint.core.contracts import PROTOCOL_GAMES, EvidenceKind, Unit
from qmint.networks import ripe
from qmint.networks.s_money_sites import run_s_money
from qmint.networks.topology import JIANG2024_URL, TopologyCase, jiang2024_intercity, jiang2024_intracity

from ..common import lane_merged, provenance
from ..schemas import ConfidenceInterval, Envelope, Quantity

RIPE_SEEDS = range(20)


class BenchmarkRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    family: Literal["quantum", "classical"]
    protocol_id: str
    status: Literal["OK", "DEMO_ADAPTER", "NOT_AVAILABLE"]
    reason: str | None = None
    quantities: list[Quantity]
    assumptions: list[str]
    reproduce: str | None
    sources: list[str]


class BenchmarksData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rows: list[BenchmarkRow]
    comparability_note: str


class BenchmarksResponse(Envelope):
    data: BenchmarksData


COMPARABILITY = (
    "Rows are not a matched benchmark: trust model, privacy, processing and security assumptions differ "
    "between the S-money timing model and any classical system. Fair classical baselines (lane H) are "
    "not merged yet."
)
SMONEY_ASSUMPTIONS = [
    "timing/causality model only; says nothing about security",
    "dT_tran = dT_proc + L_fibre / c_fibre (Jiang et al. 2024, Methods eq. (10)-(11))",
    "secret validation record pre-distributed to the remote bank agent",
]


def _lightcone(case: TopologyCase) -> float:
    return case.network.links[0].propagation_lower_bound_ns


def _paper_row(row_id: str, title: str, case: TopologyCase, classical_key: str, classical_label: str) -> BenchmarkRow:
    prov = case.provenance
    run = run_s_money(case, b=1)
    pub = float(prov["published_mean_transaction_time_ns"])
    cite = f"Jiang et al. 2024, {JIANG2024_URL} ({prov['anchors']})"
    q = [
        Quantity(
            id="smoney_modelled", label="S-money transaction time (modelled)", value=run.transaction_time_ns,
            unit=Unit.NANOSECOND, evidence_kind=EvidenceKind.MODELLED_LATENCY, method="event_simulation",
            source="qmint.networks.s_money_sites.run_s_money", formula="dT_proc + L_fibre / c_fibre",
        ),
        Quantity(
            id="smoney_published", label="Published mean transaction time", value=pub, unit=Unit.NANOSECOND,
            evidence_kind=EvidenceKind.PUBLISHED_AGGREGATE, method="published_value",
            interval=ConfidenceInterval(lo=pub - 10.0, hi=pub + 10.0, confidence=None, method="published_plus_minus"),
            source=cite,
        ),
        Quantity(
            id=classical_key, label=classical_label, value=float(prov[f"published_{classical_key}_ns"]),
            unit=Unit.NANOSECOND, evidence_kind=EvidenceKind.PUBLISHED_AGGREGATE, method="published_value",
            source=cite, note="reference quoted by the paper, not a QMint classical baseline",
        ),
        Quantity(
            id="lightcone_bound", label="Light-cone lower bound (straight line / c)", value=_lightcone(case),
            unit=Unit.NANOSECOND, evidence_kind=EvidenceKind.MODELLED_LATENCY, method="closed_form",
            source="qmint.networks.causality.lightcone_delay_ns", formula="D / c",
        ),
    ]
    return BenchmarkRow(
        id=row_id, title=title, family="quantum", protocol_id=run.trace.protocol_id, status="OK", quantities=q,
        assumptions=[*SMONEY_ASSUMPTIONS, f"fibre {prov['fiber_length_m']:.0f} m at {prov['fiber_velocity_m_per_s']:.3g} m/s"],
        reproduce="$PY -m pytest tests/unit/networks/test_networks_s_money.py -q", sources=[cite],
    )


def _ripe_row(probe_a: int, probe_b: int, title: str) -> BenchmarkRow:
    fx = ripe.load_fixture()
    case = ripe.ripe_two_site_case(fx, probe_a, probe_b)
    prov = case.provenance
    d = next(iter(prov["directions"].values()))
    pct = d["one_way_ns_percentiles"]
    src = f"RIPE Atlas msm {d['msm_id']} ({prov['source']}), retrieved {prov['retrieved_utc']}"
    times = [run_s_money(case, b=1, t_choice_ns=1e8, seed=s).transaction_time_ns for s in RIPE_SEEDS]
    q = [
        Quantity(
            id="one_way_p50", label="One-way delay p50 (RTT/2)", value=pct["p50"], unit=Unit.NANOSECOND,
            evidence_kind=EvidenceKind.MEASURED_LATENCY, method="measured_dataset",
            interval=ConfidenceInterval(lo=pct["p05"], hi=pct["p95"], confidence=None, method="p05_p95"),
            source=src, note=ripe.ONE_WAY_ASSUMPTION,
        ),
        Quantity(
            id="lightcone_bound", label="Light-cone lower bound (chord / c)", value=prov["lightcone_ns"],
            unit=Unit.NANOSECOND, evidence_kind=EvidenceKind.MODELLED_LATENCY, method="closed_form",
            source="qmint.networks.causality.lightcone_delay_ns", formula="chord(D) / c",
        ),
    ]
    if all(t is not None for t in times):
        q.insert(1, Quantity(
            id="smoney_modelled_median", label=f"S-money transaction time, median of {len(times)} seeds",
            value=statistics.median(t for t in times if t is not None), unit=Unit.NANOSECOND,
            evidence_kind=EvidenceKind.MODELLED_LATENCY, method="event_simulation",
            source="qmint.networks.s_money_sites.run_s_money with ripe.Empirical latency",
            note="modelled on measured RTT/2 samples; not a measured transaction",
        ))
    return BenchmarkRow(
        id=f"ripe-prb{probe_a}-prb{probe_b}", title=title, family="quantum", protocol_id="s_money_kent_2022_ideal_2site",
        status="OK", quantities=q,
        assumptions=[*SMONEY_ASSUMPTIONS, ripe.ONE_WAY_ASSUMPTION,
                     f"clock error bound {prov['clock_error_bound_ns_assumed']:.0f} ns assumed (NTP-class)"],
        reproduce="$PY -m pytest tests/unit/networks/test_networks_ripe.py -q", sources=[src],
    )


@lru_cache(maxsize=1)
def _rows() -> tuple[BenchmarkRow, ...]:
    rows = [
        _paper_row("jiang2024-intracity", "Jinan intra-city, 2.766 km fibre", jiang2024_intracity(),
                   "classical_crosscheck", "Published classical cross-check (2 L / c_fibre)"),
        _paper_row("jiang2024-intercity", "Yiyuan-Mazhan inter-city, 60.54 km fibre", jiang2024_intercity(),
                   "classical_free_space", "Published classical free-space reference (2 D / c)"),
        _ripe_row(6330, 6251, "RIPE Atlas Helsinki -> Tampere"),
        _ripe_row(6979, 6251, "RIPE Atlas Frankfurt -> Tampere"),
    ]
    h_merged, h_detail = lane_merged("H")
    for pid in sorted(p for p in PROTOCOL_GAMES if p.startswith("classical_")):
        rows.append(
            BenchmarkRow(
                id=pid, title=pid.removeprefix("classical_").replace("_", " "), family="classical", protocol_id=pid,
                status="NOT_AVAILABLE",
                reason="lane H (classical baselines) not merged" if not h_merged else "lane H adapter not wired yet",
                quantities=[], assumptions=[], reproduce=None, sources=[],
            )
        )
    return tuple(rows)


router = APIRouter(tags=["benchmarks"])


@router.get("/benchmarks", response_model=BenchmarksResponse)
def benchmarks() -> BenchmarksResponse:
    return BenchmarksResponse(
        status="OK",
        evidence_kind=EvidenceKind.MODELLED_LATENCY,
        provenance=provenance("qmint.networks (lane G)", seed=0, notes="RIPE rows: seeds 0..19"),
        data=BenchmarksData(rows=list(_rows()), comparability_note=COMPARABILITY),
    )
