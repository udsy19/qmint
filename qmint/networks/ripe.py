"""RIPE Atlas public REST adapter -> empirical latency models (MEASURED_LATENCY).

Data source: RIPE Atlas REST API v2, https://atlas.ripe.net/docs/apis/rest-api-reference/
(public measurement results need no API key). We use the *anchoring mesh* ping
measurements, whose source probes and target anchors have published coordinates.

Explicit modelling assumptions (all flagged in every case's provenance):

* ``ONE_WAY_ASSUMPTION``: one-way delay ~= RTT / 2. Ping measures a round trip; forward and
  return paths may differ (asymmetric routing), and the RTT includes host/ICMP processing
  and queueing at both ends. One-way delays derived this way are *estimates*, not
  measurements of one-way delay.
* An RTT sample is never a physical lower bound. The C4 ``propagation_lower_bound_ns`` of a
  RIPE-derived link is the light-cone bound between the declared probe coordinates (chord
  through a spherical Earth / c); the empirical sample is only the runtime latency model.
* Probe/anchor coordinates are as published by RIPE Atlas (operator-declared, typically
  city-level accuracy for probes); we only build a site pair when the measurement's source
  probe and target anchor are exactly those endpoints.
"""

from __future__ import annotations

import json
import math
import statistics
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qmint.core.contracts import EvidenceKind, Link, Site, SpacetimeNetwork, TopologySource
from qmint.networks.causality import lightcone_delay_ns
from qmint.networks.simulator import Empirical, LinkRuntime
from qmint.networks.topology import EARTH_RADIUS_M, TopologyCase, haversine_m

API_BASE = "https://atlas.ripe.net/api/v2"
ECEF_FRAME = "earth_centered_spherical_R6371008.8m"
ONE_WAY_ASSUMPTION = (
    "one_way_ns = RTT/2: assumes symmetric forward/return paths; RTT includes end-host "
    "processing and queueing; NOT a physical lower bound and NOT a one-way measurement"
)
REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "datasets" / "fixtures" / "ripe"
DEFAULT_FIXTURE = FIXTURE_DIR / "anchor_mesh_ping_hel_tmp_fra_sample.json"


@dataclass(frozen=True)
class PingSample:
    msm_id: int
    prb_id: int
    timestamp: int  # unix seconds (RIPE result timestamp)
    src_addr: str
    dst_addr: str
    rtts_ms: tuple[float, ...]  # successful replies only
    sent: int
    rcvd: int

    @property
    def min_rtt_ms(self) -> float | None:
        return min(self.rtts_ms) if self.rtts_ms else None


def parse_ping_results(raw: Iterable[Mapping[str, Any]]) -> list[PingSample]:
    """Parse RIPE ping result objects; timeouts (``{"x": "*"}``) and errors are skipped."""
    out = []
    for r in raw:
        if r.get("type") != "ping":
            continue
        rtts = tuple(float(x["rtt"]) for x in r.get("result", []) if isinstance(x, Mapping) and "rtt" in x)
        out.append(
            PingSample(
                msm_id=int(r["msm_id"]),
                prb_id=int(r["prb_id"]),
                timestamp=int(r["timestamp"]),
                src_addr=str(r.get("src_addr", r.get("from", ""))),
                dst_addr=str(r.get("dst_addr", "")),
                rtts_ms=rtts,
                sent=int(r.get("sent", 0)),
                rcvd=int(r.get("rcvd", len(rtts))),
            )
        )
    return out


def one_way_samples_ns(samples: Sequence[PingSample]) -> tuple[float, ...]:
    """Every successful RTT reply converted with the flagged RTT/2 assumption."""
    return tuple(rtt * 1e6 / 2.0 for s in samples for rtt in s.rtts_ms)


def percentiles_ns(values: Sequence[float]) -> dict[str, float]:
    if not values:
        raise ValueError("no samples")
    v = sorted(values)
    q = statistics.quantiles(v, n=100, method="inclusive") if len(v) > 1 else [v[0]] * 99
    return {"n": float(len(v)), "min": v[0], "p05": q[4], "p50": q[49], "p95": q[94], "max": v[-1]}


# --------------------------------------------------------------------------- #
# Network access
# --------------------------------------------------------------------------- #


class RipeAtlasClient:
    """Minimal read-only client for public RIPE Atlas data (no API key)."""

    def __init__(self, base_url: str = API_BASE, timeout_s: float = 30.0, session: Any = None) -> None:
        import requests  # optional 'data' extra; imported lazily

        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.session = session or requests.Session()

    def get(self, path: str, **params: Any) -> Any:
        url = f"{self.base_url}/{path.strip('/')}/"
        params = {"format": "json", **{k: v for k, v in params.items() if v is not None}}
        r = self.session.get(url, params=params, timeout=self.timeout_s)
        r.raise_for_status()
        return r.json()

    def measurement(self, msm_id: int) -> dict[str, Any]:
        return self.get(f"measurements/{msm_id}")

    def results(
        self, msm_id: int, start: int, stop: int, probe_ids: Sequence[int] | None = None
    ) -> list[dict[str, Any]]:
        ids = ",".join(str(p) for p in probe_ids) if probe_ids else None
        return self.get(f"measurements/{msm_id}/results", start=start, stop=stop, probe_ids=ids)

    def probe(self, probe_id: int) -> dict[str, Any]:
        return self.get(f"probes/{probe_id}")

    def anchor_probe_id(self, fqdn: str) -> int:
        res = self.get("anchors", search=fqdn.split(".")[0])["results"]
        match = [a for a in res if a["fqdn"] == fqdn]
        if len(match) != 1:
            raise LookupError(f"cannot uniquely resolve anchor {fqdn!r}")
        return int(match[0]["probe"])


_MSM_KEEP = ("id", "type", "af", "description", "target", "target_ip", "target_asn", "interval", "packets",
             "size", "is_public", "tags")
_PROBE_KEEP = ("id", "is_anchor", "country_code", "asn_v4", "address_v4", "geometry", "description")


def build_fixture(
    client: RipeAtlasClient,
    blocks: Sequence[tuple[int, Sequence[int]]],
    start: int,
    stop: int,
) -> dict[str, Any]:
    """Fetch ``[(msm_id, source_probe_ids), ...]`` in ``[start, stop)`` plus endpoint metadata."""
    measurements = []
    probe_ids: set[int] = set()
    for msm_id, src_ids in blocks:
        meta = client.measurement(msm_id)
        target_probe = client.anchor_probe_id(meta["target"])
        raw = client.results(msm_id, start, stop, src_ids)
        measurements.append(
            {
                "msm_id": msm_id,
                "measurement": {k: meta.get(k) for k in _MSM_KEEP},
                "target_probe_id": target_probe,
                "source_probe_ids": list(src_ids),
                "results_url": f"{client.base_url}/measurements/{msm_id}/results/?start={start}&stop={stop}"
                f"&probe_ids={','.join(map(str, src_ids))}&format=json",
                "results": raw,
            }
        )
        probe_ids |= {target_probe, *src_ids}
    probes = {str(p): {k: client.probe(p).get(k) for k in _PROBE_KEEP} for p in sorted(probe_ids)}
    return {
        "source": "RIPE Atlas REST API v2 (public measurement results)",
        "api_base": client.base_url,
        "retrieved_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "window_unix_s": [start, stop],
        "one_way_assumption": ONE_WAY_ASSUMPTION,
        "evidence_kind": EvidenceKind.MEASURED_LATENCY.value,
        "probes": probes,
        "measurements": measurements,
    }


def load_fixture(path: str | Path = DEFAULT_FIXTURE) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Fixture -> SpacetimeNetwork + empirical latency
# --------------------------------------------------------------------------- #


def _ecef(lon_deg: float, lat_deg: float) -> tuple[float, float, float]:
    lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    r = EARTH_RADIUS_M
    return (r * math.cos(lat) * math.cos(lon), r * math.cos(lat) * math.sin(lon), r * math.sin(lat))


def probe_site(probe: Mapping[str, Any], clock_error_bound_ns: float, trust_domain: str = "bank") -> Site:
    lon, lat = probe["geometry"]["coordinates"]
    x, y, z = _ecef(lon, lat)
    return Site(
        site_id=f"prb{probe['id']}",
        frame=ECEF_FRAME,
        x_m=x,
        y_m=y,
        z_m=z,
        trust_domain=trust_domain,
        clock_error_bound_ns=clock_error_bound_ns,
    )


@dataclass(frozen=True)
class DirectedSample:
    msm_id: int
    src_probe: int
    dst_probe: int
    samples: tuple[PingSample, ...]

    @property
    def one_way_ns(self) -> tuple[float, ...]:
        return one_way_samples_ns(self.samples)


def directed_samples(fixture: Mapping[str, Any]) -> list[DirectedSample]:
    out = []
    for block in fixture["measurements"]:
        parsed = parse_ping_results(block["results"])
        for src in block["source_probe_ids"]:
            mine = tuple(s for s in parsed if s.prb_id == src)
            if mine:
                out.append(DirectedSample(int(block["msm_id"]), int(src), int(block["target_probe_id"]), mine))
    return out


def ripe_two_site_case(
    fixture: Mapping[str, Any],
    probe_a: int,
    probe_b: int,
    clock_error_bound_ns: float = 1_000.0,  # NTP-class; declared assumption, not measured
) -> TopologyCase:
    """Two-site network keyed to two real RIPE endpoints with measured runtime latency.

    Requires at least one measured direction between exactly these probes. If only one
    direction was measured, the reverse link reuses it (symmetric-RTT assumption flagged).
    """
    probes = fixture["probes"]
    sites = [probe_site(probes[str(probe_a)], clock_error_bound_ns), probe_site(probes[str(probe_b)], clock_error_bound_ns)]
    by_dir = {(d.src_probe, d.dst_probe): d for d in directed_samples(fixture)}
    measured = [k for k in ((probe_a, probe_b), (probe_b, probe_a)) if k in by_dir]
    if not measured:
        raise LookupError(f"no RIPE measurement between probes {probe_a} and {probe_b} in fixture")
    lc = lightcone_delay_ns(sites[0], sites[1])

    links, runtime, prov_dirs = [], {}, {}
    for src, dst in ((probe_a, probe_b), (probe_b, probe_a)):
        d = by_dir.get((src, dst)) or by_dir[measured[0]]
        ow = d.one_way_ns
        if min(ow) < lc:
            raise ValueError(
                f"RTT/2 sample {min(ow):.0f} ns below light-cone {lc:.0f} ns: endpoint coordinates "
                f"do not match the measurement (msm {d.msm_id})"
            )
        tag = f"ripe:{d.msm_id}:prb{d.src_probe}->prb{d.dst_probe}"
        links.append(
            Link(
                src=f"prb{src}",
                dst=f"prb{dst}",
                propagation_lower_bound_ns=lc,
                latency_model=tag + ":rtt/2",
                latency_evidence=EvidenceKind.MEASURED_LATENCY,
                authenticated=True,
            )
        )
        runtime[(f"prb{src}", f"prb{dst}")] = LinkRuntime(latency=Empirical(samples_ns=ow, source=tag))
        prov_dirs[f"prb{src}->prb{dst}"] = {
            "msm_id": d.msm_id,
            "measured_direction": f"prb{d.src_probe}->prb{d.dst_probe}",
            "reused_reverse_direction": (d.src_probe, d.dst_probe) != (src, dst),
            "n_results": len(d.samples),
            "first_timestamp": min(s.timestamp for s in d.samples),
            "last_timestamp": max(s.timestamp for s in d.samples),
            "one_way_ns_percentiles": percentiles_ns(ow),
        }
    net = SpacetimeNetwork(
        network_id=f"ripe-prb{probe_a}-prb{probe_b}",
        topology_source=TopologySource.MEASURED_RIPE,
        sites=sites,
        links=links,
    )
    pa, pb = probes[str(probe_a)], probes[str(probe_b)]
    prov = {
        "source": fixture["source"],
        "retrieved_utc": fixture["retrieved_utc"],
        "window_unix_s": fixture["window_unix_s"],
        "one_way_assumption": ONE_WAY_ASSUMPTION,
        "evidence_kind": EvidenceKind.MEASURED_LATENCY.value,
        "probe_ids": [probe_a, probe_b],
        "probe_coordinates_lonlat": [pa["geometry"]["coordinates"], pb["geometry"]["coordinates"]],
        "great_circle_m": haversine_m(*pa["geometry"]["coordinates"][::-1], *pb["geometry"]["coordinates"][::-1]),
        "lightcone_ns": lc,
        "directions": prov_dirs,
        "clock_error_bound_ns_assumed": clock_error_bound_ns,
    }
    return TopologyCase(network=net, link_runtime=runtime, provenance=prov)


# Fixture used in the repo: anchoring-mesh pings, IPv4.
#   msm 7714918  : target anchor fi-tmp-as719 (Tampere, probe 6251); sources 6330 (Helsinki
#                  anchor fi-hel-as203296) and 6979 (Frankfurt anchor de-fra-as12008)
#   msm 10683825 : target anchor fi-hel-as203296 (probe 6330); source 6251 (reverse direction)
FIXTURE_BLOCKS: tuple[tuple[int, tuple[int, ...]], ...] = ((7714918, (6330, 6979)), (10683825, (6251,)))
FIXTURE_WINDOW_UNIX_S = (1791579600, 1791583200)  # 2026-10-09T07:00Z .. 08:00Z


def main(argv: Sequence[str] | None = None) -> int:  # pragma: no cover - network
    """Regenerate the committed fixture: ``python -m qmint.networks.ripe [out.json]``."""
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    out = Path(args[0]) if args else DEFAULT_FIXTURE
    fx = build_fixture(RipeAtlasClient(), FIXTURE_BLOCKS, *FIXTURE_WINDOW_UNIX_S)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(fx, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out} ({sum(len(m['results']) for m in fx['measurements'])} results)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
