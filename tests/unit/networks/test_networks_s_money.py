"""Two-site S-money event scenario: timing reproduction, locality preconditions, privacy."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from qmint.networks.causality import is_spacelike
from qmint.networks.events import SETTLEMENT_LADDER
from qmint.networks.s_money_sites import run_s_money
from qmint.networks.simulator import Partition
from qmint.networks.topology import jiang2024_intercity, jiang2024_intracity, synthetic_two_site


@pytest.mark.parametrize("b", [0, 1])
def test_reproduces_jiang_intracity_transaction_time(b):
    """Model dT = dT_proc + L/c_fibre = 1.507 + 13.830 us vs published mean 15.34 +/- 0.01 us."""
    run = run_s_money(jiang2024_intracity(), b=b)
    assert run.transaction_time_ns == pytest.approx(15_337.0)
    assert abs(run.transaction_time_ns - 15_340.0) <= 10.0


@pytest.mark.parametrize("b", [0, 1])
def test_reproduces_jiang_intercity_transaction_time(b):
    run = run_s_money(jiang2024_intercity(), b=b)
    assert abs(run.transaction_time_ns - 304_200.0) <= 10.0


def test_local_validation_needs_no_synchronous_cross_site_message_when_preconditions_met():
    run = run_s_money(jiang2024_intracity(), b=1, predistribute=True)
    assert run.local_round_trips == ()
    assert run.result.accepted_sites("tok-s-0") == ["L1"]


def test_missing_predistribution_rejects_locally_instead_of_validating():
    run = run_s_money(jiang2024_intracity(), b=1, predistribute=False)
    assert run.transaction_time_ns is None
    rej = run.result.first("reject", site_id="L1")
    assert rej is not None and rej.detail["reason"] == "precondition_missing:record"
    assert run.result.accepted_sites("tok-s-0") == []


def test_query_home_negative_control_is_flagged_as_round_trip():
    case = jiang2024_intracity()
    good = run_s_money(case, b=1, predistribute=True)
    bad = run_s_money(case, b=1, predistribute=False, fallback="query_home")
    assert bad.local_round_trips  # detector catches the synchronous query
    assert bad.transaction_time_ns > good.transaction_time_ns


def test_settlement_ladder_events_are_distinct_and_ordered():
    run = run_s_money(jiang2024_intercity(), b=1, settlement_ns=5_000.0)
    t = {}
    for kind in SETTLEMENT_LADDER[:3]:
        ev = run.result.first(kind, accepted=True) if kind == SETTLEMENT_LADDER[0] else run.result.first(kind)
        assert ev is not None, kind
        t[kind] = ev.time_ns
    assert t["verification_result_available_local"] < t["issuer_aware_of_spend"] <= t["bank_settlement_final"]
    # issuer at Yiyuan cannot learn of a Mazhan spend before light could carry it
    lc = run.result.network.links[0].propagation_lower_bound_ns
    assert t["issuer_aware_of_spend"] - t["verification_result_available_local"] >= lc


def test_two_local_results_are_spacelike():
    run = run_s_money(jiang2024_intercity(), b=0)
    r = [e.to_trace_event() for e in run.result.of_kind("verification_result_available_local")]
    assert len(r) == 2 and r[0].site_id != r[1].site_id
    assert is_spacelike(r[0], r[1], run.result.network)


def test_branch_hidden_from_bank_until_presentation():
    run = run_s_money(jiang2024_intracity(), b=1, z=1)
    present_t = min(e.time_ns for e in run.result.of_kind("local_validation_start"))
    for e in run.result.events:
        if e.actor_id.startswith("B") or e.actor_id == "HQ":
            if e.time_ns < present_t:
                assert "b" not in e.detail, e


def test_partition_costs_availability_not_safety():
    case = jiang2024_intracity()
    p = Partition(0.0, 1e12, frozenset({"L0"}), frozenset({"L1"}))
    run = run_s_money(case, b=1, partitions=(p,))
    assert run.transaction_time_ns is None  # unavailable
    assert not run.trace.double_spend_accepted
    assert {lk.propagation_lower_bound_ns for lk in run.result.network.links} == {
        lk.propagation_lower_bound_ns for lk in case.network.links
    }


@settings(max_examples=30, deadline=None)
@given(st.sampled_from([1.0, 10.0, 100.0, 1000.0]), st.integers(0, 1), st.integers(0, 1),
       st.floats(1e6, 1e9), st.floats(0, 1e4))
def test_synthetic_transaction_time_equals_one_way_plus_proc(km, b, z, t_choice, proc):
    case = synthetic_two_site(km)
    run = run_s_money(case, b=b, z=z, t_choice_ns=t_choice, proc_ns=proc)
    one_way = case.link_runtime[case.site_ids].latency.delay_ns
    assert run.transaction_time_ns == pytest.approx(one_way + proc, rel=1e-9, abs=1e-3)
    assert run.local_round_trips == () and not run.trace.double_spend_accepted


def _bank_view_before_presentation(run):
    first = min(e.time_ns for e in run.result.of_kind("local_validation_start"))
    return [(e.actor_id, e.kind, round(e.time_ns, 6), sorted((k, repr(v)) for k, v in e.detail.items()))
            for e in run.result.events if (e.actor_id.startswith("B") or e.actor_id == "HQ") and e.time_ns < first]


def _commitment(run):
    return next(e.detail["c"] for e in run.result.of_kind("message_receive")
                if e.actor_id == "B0" and e.detail.get("type") == "commitment")


def test_default_z_is_uniform_and_bank_view_independent_of_choice():
    """M-G1 (Kent 2022 Table I: z is Alice's private uniform bit): with the default z, c = b XOR z is uniform over
    seeds for each b, and for every seed Bob's pre-presentation view is identical for b = 0 and b = 1."""
    case = jiang2024_intracity()
    cs = {0: [], 1: []}
    for seed in range(40):
        runs = {b: run_s_money(case, b=b, seed=seed) for b in (0, 1)}
        assert _bank_view_before_presentation(runs[0]) == _bank_view_before_presentation(runs[1])
        for b in (0, 1):
            cs[b].append(_commitment(runs[b]))
    assert cs[0] == cs[1]
    assert 10 <= sum(cs[0]) <= 30  # both values occur (uniform; 40 seeded draws)
    with pytest.raises(ValueError):
        run_s_money(case, b=0, z=2)
