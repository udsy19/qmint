"""Lane M red team: lane G causal engine, clock skew and choice leakage (DATA_LEAKAGE_REVIEW)."""

from __future__ import annotations

import pytest

from qmint.networks.causality import CausalityViolation
from qmint.networks.s_money_sites import run_s_money
from qmint.networks.simulator import Empirical, LinkRuntime, Simulator
from qmint.networks.topology import TopologyCase, jiang2024_intracity, synthetic_two_site

BOB = {"B0", "B1", "HQ"}


def _bob_view(run):
    evs = run.result.events
    first = min(e.time_ns for e in evs if e.kind == "local_validation_start")
    return [(e.actor_id, e.kind, round(e.time_ns, 6), tuple(sorted((k, repr(v)) for k, v in e.detail.items())))
            for e in evs if e.actor_id in BOB and e.time_ns < first]


def _presentations(run):
    return sorted((e.actor_id, round(e.time_ns, 6)) for e in run.result.events
                  if e.kind == "message_receive" and e.detail.get("type") == "present")


# --------------------------------------------------------------- controls (pass)
@pytest.mark.parametrize("case", [jiang2024_intracity(), synthetic_two_site(100.0)], ids=lambda c: c.network.network_id)
def test_presentation_timing_independent_of_choice(case):
    """Timing-metadata attack: presentation arrival times at B0/B1 do not depend on b."""
    assert _presentations(run_s_money(case, b=0)) == _presentations(run_s_money(case, b=1))


@pytest.mark.parametrize("case", [jiang2024_intracity(), synthetic_two_site(100.0)], ids=lambda c: c.network.network_id)
def test_bob_view_distribution_independent_of_choice_when_z_uniform(case):
    v = {b: sorted(repr(_bob_view(run_s_money(case, b=b, z=z))) for z in (0, 1)) for b in (0, 1)}
    assert v[0] == v[1]


def test_clock_offset_beyond_declared_bound_refused():
    case = synthetic_two_site(10.0, clock_error_bound_ns=1.0)
    with pytest.raises(ValueError):
        Simulator(case.network, [], case.link_runtime, clock_offsets_ns={case.site_ids[0]: 5.0})


def test_superluminal_empirical_latency_raises():
    case = synthetic_two_site(100.0)
    a, b = case.site_ids[:2]
    fast = {**case.link_runtime, (a, b): LinkRuntime(latency=Empirical((1.0,), source="m-redteam"))}
    with pytest.raises(CausalityViolation):
        run_s_money(TopologyCase(case.network, fast, case.provenance), b=1)


# --------------------------------------------------------------- M-G1: default z leaks b (FIXED, lane FGH)
@pytest.mark.parametrize("case", [jiang2024_intracity()], ids=lambda c: c.network.network_id)
def test_default_run_hides_choice_from_bank(case):
    assert _bob_view(run_s_money(case, b=0)) == _bob_view(run_s_money(case, b=1))
