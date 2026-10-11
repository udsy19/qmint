"""RIPE Atlas adapter: committed fixture (offline) + a live smoke test (network)."""

from __future__ import annotations

import copy

import pytest

from qmint.core.contracts import EvidenceKind, TopologySource
from qmint.networks.ripe import (
    FIXTURE_BLOCKS,
    ONE_WAY_ASSUMPTION,
    RipeAtlasClient,
    directed_samples,
    load_fixture,
    one_way_samples_ns,
    parse_ping_results,
    percentiles_ns,
    ripe_two_site_case,
)
from qmint.networks.s_money_sites import run_s_money


@pytest.fixture(scope="module")
def fx():
    return load_fixture()


def test_fixture_provenance(fx):
    assert fx["one_way_assumption"] == ONE_WAY_ASSUMPTION
    assert {m["msm_id"] for m in fx["measurements"]} == {b[0] for b in FIXTURE_BLOCKS}
    for m in fx["measurements"]:
        assert m["measurement"]["is_public"] is True and m["measurement"]["type"] == "ping"
        assert all(r["msm_id"] == m["msm_id"] for r in m["results"])
        assert all(fx["window_unix_s"][0] <= r["timestamp"] < fx["window_unix_s"][1] for r in m["results"])
    for p in fx["probes"].values():
        assert p["is_anchor"] is True and len(p["geometry"]["coordinates"]) == 2


def test_parse_skips_timeouts():
    raw = [{"type": "ping", "msm_id": 1, "prb_id": 2, "timestamp": 3, "result": [{"x": "*"}, {"rtt": 4.0}],
            "sent": 2, "rcvd": 1}]
    (s,) = parse_ping_results(raw)
    assert s.rtts_ms == (4.0,) and one_way_samples_ns([s]) == (2_000_000.0,)


def test_directed_samples_cover_both_directions(fx):
    dirs = {(d.src_probe, d.dst_probe) for d in directed_samples(fx)}
    assert {(6330, 6251), (6251, 6330), (6979, 6251)} <= dirs


def test_helsinki_tampere_case(fx):
    case = ripe_two_site_case(fx, 6330, 6251)
    net = case.network
    assert net.topology_source is TopologySource.MEASURED_RIPE
    assert all(lk.latency_evidence is EvidenceKind.MEASURED_LATENCY for lk in net.links)
    lc = case.provenance["lightcone_ns"]
    assert all(lk.propagation_lower_bound_ns == lc for lk in net.links)  # bound is physics, not RTT
    for d in case.provenance["directions"].values():
        assert d["reused_reverse_direction"] is False
        assert d["one_way_ns_percentiles"]["min"] > lc  # data consistent with geometry
    assert 140_000 < case.provenance["great_circle_m"] < 170_000


def test_one_direction_only_is_flagged(fx):
    case = ripe_two_site_case(fx, 6979, 6251)
    flags = {k: v["reused_reverse_direction"] for k, v in case.provenance["directions"].items()}
    assert flags == {"prb6979->prb6251": False, "prb6251->prb6979": True}


def test_coordinates_inconsistent_with_rtt_are_refused(fx):
    bad = copy.deepcopy(fx)
    bad["probes"]["6330"]["geometry"]["coordinates"] = [-122.0, 37.0]  # California: RTT/2 < light cone
    with pytest.raises(ValueError, match="below light-cone"):
        ripe_two_site_case(bad, 6330, 6251)


def test_unmeasured_pair_refused(fx):
    with pytest.raises(LookupError):
        ripe_two_site_case(fx, 6330, 6979)


def test_percentiles():
    p = percentiles_ns([1.0, 2.0, 3.0, 4.0, 5.0])
    assert p["min"] == 1.0 and p["max"] == 5.0 and p["p50"] == 3.0


def test_s_money_on_measured_topology(fx):
    run = run_s_money(ripe_two_site_case(fx, 6330, 6251), b=1, t_choice_ns=1e8)
    assert run.trace.latency_evidence is EvidenceKind.MEASURED_LATENCY
    assert run.transaction_time_ns is not None and run.local_round_trips == ()


@pytest.mark.network
def test_live_ripe_fetch_small_sample():
    c = RipeAtlasClient(timeout_s=30)
    meta = c.measurement(7714918)
    assert meta["is_public"] and meta["type"] == "ping"
    import time

    stop = int(time.time()) - 3600
    raw = c.results(7714918, stop - 600, stop, [6330])
    samples = parse_ping_results(raw)
    assert samples and all(s.prb_id == 6330 and s.msm_id == 7714918 for s in samples)
