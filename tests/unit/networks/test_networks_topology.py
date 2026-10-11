"""Topology builders: paper-sourced numbers (Jiang et al. 2024) and synthetic cases."""

from __future__ import annotations

import pytest

from qmint.core.contracts import TopologySource
from qmint.networks.causality import C_M_PER_NS, network_violations
from qmint.networks.topology import (
    SYNTHETIC_DISTANCES_KM,
    jiang2024_intercity,
    jiang2024_intracity,
    synthetic_cases,
)


def test_jiang_intracity_numbers_and_provenance():
    case = jiang2024_intracity()
    net = case.network
    assert net.topology_source is TopologySource.PAPER
    assert case.provenance["fiber_length_m"] == 2766.0 and case.provenance["distance_m"] == 426.0
    assert "2408.13063" in case.provenance["source_url"]
    # Physical lower bound is the straight-line light cone, NOT the fibre delay.
    assert net.links[0].propagation_lower_bound_ns == pytest.approx(426.0 / C_M_PER_NS)
    fiber = case.link_runtime[("L0", "L1")].latency
    # SI Table S2 reference: classical cross-check 2 * L/c_fibre = 27.66 us (PUBLISHED_AGGREGATE).
    assert 2 * fiber.delay_ns == pytest.approx(27_660.0, abs=0.5)
    assert network_violations(net) == []


def test_jiang_intercity_numbers_and_coordinate_check():
    case = jiang2024_intercity()
    assert case.site_ids == ("Yiyuan", "Mazhan")
    assert case.provenance["fiber_length_m"] == 60_540.0 and case.provenance["distance_m"] == 51_600.0
    # SI Table S3 reference uses c = 3e8 m/s: 2D/c = 344 us.
    assert 2 * 51_600.0 / 3.0e8 * 1e9 == pytest.approx(344_000.0)
    # Same quantity with exact c (what our light-cone bound uses): 344.24 us (vs 344 us with c=3e8).
    assert 2 * case.network.links[0].propagation_lower_bound_ns == pytest.approx(344_238.1, abs=0.5)
    # Published coordinates give ~49.55 km, not 51.60 km -- recorded, not silently "fixed".
    assert case.provenance["coordinate_distance_check_m"] == pytest.approx(49_550.0, abs=50.0)


def test_synthetic_cases_are_labelled_synthetic():
    cases = synthetic_cases()
    assert [c.provenance["distance_m"] for c in cases] == [d * 1000 for d in SYNTHETIC_DISTANCES_KM]
    for c in cases:
        assert c.network.topology_source is TopologySource.SYNTHETIC
        assert c.provenance["input_evidence"] == "SYNTHETIC"
        assert network_violations(c.network) == []
        fib = c.link_runtime[c.site_ids].latency
        assert fib.delay_ns == pytest.approx(1.5 * c.network.links[0].propagation_lower_bound_ns)
