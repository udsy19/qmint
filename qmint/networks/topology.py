"""SpacetimeNetwork builders: paper-sourced, synthetic and (via ripe.py) measured cases.

Every builder returns a :class:`TopologyCase`: the frozen C4 ``SpacetimeNetwork`` plus the
runtime latency models for the simulator and a provenance record. In every network the C4
``Link.propagation_lower_bound_ns`` is the *physical* light-cone bound between the two
sites (straight-line distance / c); the realistic delay (fibre, measured RTT/2, ...) is a
separate runtime model. The two are never interchanged.

Paper-sourced cases (EvidenceKind of the inputs: PUBLISHED_AGGREGATE)
-------------------------------------------------------------------
Jiang et al., "Experimental practical quantum tokens with transaction time advantage",
arXiv:2408.13063v2 (19 Sep 2024), https://arxiv.org/abs/2408.13063 -- PDF read
2026-10-11, sha256 a5a4242882c4a265738dbcf84a58f41acd345dfa51eb0dcf40537df7dec5deb4.

* Intra-city (Jinan, Shandong): two labs "separated by 426 m and connected by 2.766 km
  of optical fibre" (main text, PDF p.6; Fig. 2(a) caption says "around 425 m"; SI p.39
  says 425 m). The abstract rounds the fibre to 2.77 km. Measured mean transaction time
  15.34 +/- 0.01 us; classical cross-check reference 2 L/c_fibre = 27.66 us (SI, Table S2).
* Inter-city: Yiyuan (36 10'50.4"N, 118 12'10"E) to Mazhan (36 0'19"N, 118 42'35"E),
  "separated by 51.60 km and connected by a 60.54 km field-deployable optical fibre"
  (main text p.6; Methods p.15). Measured mean 304.20 +/- 0.01 us; classical free-space
  reference 2D/c = 344 us with c = 3e8 m/s (SI, Table S3).
* Methods eqs. (10)-(15): dT_tran = dT_proc + L_fibre/c_fibre, c_fibre ~= 2e8 m/s,
  dT_proc ~= 1.5 us (SI: measured average 1.507 us).

Verification note (not a correction of the paper): the haversine distance between the two
published inter-city coordinates (R = 6371.0088 km) is ~49.55 km, not 51.60 km. The paper
does not state how D was obtained; we use the stated D = 51.60 km for the PAPER case and
record the discrepancy (``provenance["coordinate_distance_check_m"]``).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from qmint.core.contracts import EvidenceKind, Link, Site, SpacetimeNetwork, TopologySource
from qmint.networks.causality import lightcone_delay_ns
from qmint.networks.simulator import FIBER_VELOCITY_FRACTION, Fiber, LinkRuntime

FLAT_FRAME = "flat_local_approx"  # Minkowski approx over a local tangent plane; GR effects ignored
JIANG2024_URL = "https://arxiv.org/abs/2408.13063"
JIANG2024_PDF_SHA256 = "a5a4242882c4a265738dbcf84a58f41acd345dfa51eb0dcf40537df7dec5deb4"
JIANG2024_FIBER_VELOCITY_M_PER_S = 2.0e8  # Methods eq. (11): c_fibre ~= 2 x 10^8 m/s
JIANG2024_PROC_NS = 1507.0  # SI: measured average dT_proc = 1.507 us
EARTH_RADIUS_M = 6_371_008.8  # IUGG mean radius; spherical-Earth approximation


@dataclass(frozen=True)
class TopologyCase:
    network: SpacetimeNetwork
    link_runtime: Mapping[tuple[str, str], LinkRuntime]
    provenance: Mapping[str, Any] = field(default_factory=dict)

    @property
    def site_ids(self) -> tuple[str, ...]:
        return tuple(s.site_id for s in self.network.sites)


def haversine_m(lat1_deg: float, lon1_deg: float, lat2_deg: float, lon2_deg: float) -> float:
    p1, p2 = math.radians(lat1_deg), math.radians(lat2_deg)
    dp, dl = p2 - p1, math.radians(lon2_deg - lon1_deg)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def _dms(d: float, m: float, s: float) -> float:
    return d + m / 60 + s / 3600


def lightcone_links(
    sites: Sequence[Site],
    latency_model: str,
    latency_evidence: EvidenceKind,
    authenticated: bool = True,
    message_cost_bytes: int = 0,
) -> list[Link]:
    """All ordered pairs, each with the physical light-cone lower bound."""
    out = []
    for a in sites:
        for b in sites:
            if a.site_id != b.site_id:
                out.append(
                    Link(
                        src=a.site_id,
                        dst=b.site_id,
                        propagation_lower_bound_ns=lightcone_delay_ns(a, b),
                        latency_model=latency_model,
                        latency_evidence=latency_evidence,
                        authenticated=authenticated,
                        message_cost_bytes=message_cost_bytes,
                    )
                )
    return out


def two_site_case(
    network_id: str,
    distance_m: float,
    topology_source: TopologySource,
    fiber_length_m: float | None = None,
    fiber_velocity_m_per_s: float | None = None,
    clock_error_bound_ns: float = 1.0,
    site_ids: tuple[str, str] = ("L0", "L1"),
    trust_domain: str = "bank",
    provenance: Mapping[str, Any] | None = None,
) -> TopologyCase:
    """Two sites on a line, ``distance_m`` apart, joined by a fibre runtime model."""
    if distance_m <= 0:
        raise ValueError("distance must be > 0")
    fiber_length_m = distance_m if fiber_length_m is None else fiber_length_m
    if fiber_length_m < distance_m:
        raise ValueError("fibre cannot be shorter than the straight-line distance")
    v = fiber_velocity_m_per_s or FIBER_VELOCITY_FRACTION * 299_792_458.0
    sites = [
        Site(site_id=site_ids[0], frame=FLAT_FRAME, x_m=0.0, y_m=0.0, trust_domain=trust_domain,
             clock_error_bound_ns=clock_error_bound_ns),
        Site(site_id=site_ids[1], frame=FLAT_FRAME, x_m=distance_m, y_m=0.0, trust_domain=trust_domain,
             clock_error_bound_ns=clock_error_bound_ns),
    ]
    fiber = Fiber(length_m=fiber_length_m, velocity_m_per_s=v)
    net = SpacetimeNetwork(
        network_id=network_id,
        topology_source=topology_source,
        sites=sites,
        links=lightcone_links(sites, latency_model=fiber.name, latency_evidence=EvidenceKind.MODELLED_LATENCY),
    )
    rt = {(a, b): LinkRuntime(latency=fiber) for a in site_ids for b in site_ids if a != b}
    prov = {
        "distance_m": distance_m,
        "fiber_length_m": fiber_length_m,
        "fiber_velocity_m_per_s": v,
        "lower_bound_semantics": "propagation_lower_bound_ns = straight-line distance / c (physics)",
        **(provenance or {}),
    }
    return TopologyCase(network=net, link_runtime=rt, provenance=prov)


# --------------------------------------------------------------------------- #
# PAPER cases (Jiang et al. 2024)
# --------------------------------------------------------------------------- #


def jiang2024_intracity() -> TopologyCase:
    """Jinan intra-city link: D = 426 m straight line, 2.766 km fibre (paper rounds to 2.77 km)."""
    return two_site_case(
        "paper-jiang2024-jinan-2.766km-fibre",
        distance_m=426.0,
        topology_source=TopologySource.PAPER,
        fiber_length_m=2766.0,
        fiber_velocity_m_per_s=JIANG2024_FIBER_VELOCITY_M_PER_S,
        provenance={
            "source_url": JIANG2024_URL,
            "source_pdf_sha256": JIANG2024_PDF_SHA256,
            "anchors": "main text p.6 ('426 m', '2.766 km'); Fig.2(a) caption ('around 425 m'); "
            "Methods eq.(10)-(13); SI Table S2",
            "input_evidence": EvidenceKind.PUBLISHED_AGGREGATE.value,
            "straight_line_note": "main text 426 m vs caption/SI 425 m; 426 m used",
            "published_mean_transaction_time_ns": 15_340.0,
            "published_classical_crosscheck_ns": 27_660.0,  # 2 L_fibre / c_fibre
            "published_quantum_advantage_ns": 12_320.0,
            "published_proc_ns": JIANG2024_PROC_NS,
        },
    )


def jiang2024_intercity() -> TopologyCase:
    """Yiyuan-Mazhan inter-city link: D = 51.60 km straight line, 60.54 km fibre."""
    yiyuan = (_dms(36, 10, 50.4), _dms(118, 12, 10))
    mazhan = (_dms(36, 0, 19), _dms(118, 42, 35))
    return two_site_case(
        "paper-jiang2024-yiyuan-mazhan-60.54km-fibre",
        distance_m=51_600.0,
        topology_source=TopologySource.PAPER,
        fiber_length_m=60_540.0,
        fiber_velocity_m_per_s=JIANG2024_FIBER_VELOCITY_M_PER_S,
        site_ids=("Yiyuan", "Mazhan"),
        provenance={
            "source_url": JIANG2024_URL,
            "source_pdf_sha256": JIANG2024_PDF_SHA256,
            "anchors": "main text p.6; Fig.2(b) caption; Methods eq.(14)-(15) p.15; SI Table S3",
            "input_evidence": EvidenceKind.PUBLISHED_AGGREGATE.value,
            "coordinates_deg": {"Yiyuan": yiyuan, "Mazhan": mazhan},
            "coordinate_distance_check_m": round(haversine_m(*yiyuan, *mazhan), 1),
            "coordinate_distance_note": "haversine of published coordinates ~49.55 km != stated 51.60 km; "
            "stated D used",
            "published_mean_transaction_time_ns": 304_200.0,
            "published_classical_free_space_ns": 344_000.0,  # 2D/c with c = 3e8 m/s
            "published_comparative_advantage_ns": 39_800.0,
            "published_proc_ns": JIANG2024_PROC_NS,
        },
    )


# --------------------------------------------------------------------------- #
# SYNTHETIC cases
# --------------------------------------------------------------------------- #

SYNTHETIC_DISTANCES_KM: tuple[float, ...] = (1.0, 10.0, 100.0, 1000.0)


def synthetic_two_site(distance_km: float, clock_error_bound_ns: float = 1.0) -> TopologyCase:
    """Hypothetical straight fibre (length = distance) at 2/3 c. SYNTHETIC, not a deployment."""
    return two_site_case(
        f"synthetic-2site-{distance_km:g}km",
        distance_m=distance_km * 1000.0,
        topology_source=TopologySource.SYNTHETIC,
        clock_error_bound_ns=clock_error_bound_ns,
        provenance={
            "input_evidence": EvidenceKind.SYNTHETIC.value,
            "assumption": "straight fibre equal to site separation at 2/3 c; hypothetical scenario",
        },
    )


def synthetic_cases() -> list[TopologyCase]:
    return [synthetic_two_site(d) for d in SYNTHETIC_DISTANCES_KM]
