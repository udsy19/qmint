"""Classical race world (TEST FIXTURE actors): H0 double accept, H1 single success, H3 escrow."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from qmint.networks.causality import synchronous_cross_site_round_trips
from qmint.networks.classical_race_fixtures import FixtureH1Ledger, run_h0, run_h1, run_h3
from qmint.networks.events import Message
from qmint.networks.simulator import Partition
from qmint.networks.topology import jiang2024_intracity, synthetic_two_site


def test_h0_both_sites_accept_concurrently():
    case = synthetic_two_site(100.0)
    run = run_h0(case, [("L0", 1000.0), ("L1", 1000.0)])
    assert run.result.accepted_sites("tok-h0") == ["L0", "L1"]
    assert run.trace.double_spend_accepted is True
    settle = run.result.first("bank_settlement_final")
    acc = run.result.of_kind("verification_result_available_local")
    assert settle is not None and settle.time_ns > max(e.time_ns for e in acc)  # detected only ex post


@settings(max_examples=60, deadline=None)
@given(st.sampled_from([1.0, 10.0, 100.0, 1000.0]), st.floats(0, 1e7), st.floats(0, 1e7),
       st.sampled_from(["L0", "L1"]), st.integers(0, 1000))
def test_h1_exactly_one_success_under_concurrency(km, t0, t1, ledger_site, seed):
    case = synthetic_two_site(km)
    run = run_h1(case, [("L0", t0), ("L1", t1)], ledger_site=ledger_site, seed=seed)
    assert len(run.result.accepted_sites("tok-h1")) == 1
    assert not run.trace.double_spend_accepted
    results = run.result.of_kind("verification_result_available_local")
    assert len(results) == 2  # the loser gets a definite 'already_spent'


def test_h1_remote_merchant_pays_coordination_round_trip():
    case = jiang2024_intracity()
    run = run_h1(case, [("L1", 0.0)], ledger_site="L0")
    pres = run.result.first("local_validation_start", site_id="L1")
    res = run.result.first("verification_result_available_local", site_id="L1")
    fiber = case.link_runtime[("L1", "L0")].latency.delay_ns
    assert res.time_ns - pres.time_ns >= 2 * fiber  # 27.66 us on the Jinan fibre
    evs = [e.to_trace_event() for e in run.result.events]
    assert synchronous_cross_site_round_trips(evs, res.event_id, pres.event_id)


def test_h1_partition_changes_availability_not_physics():
    case = synthetic_two_site(10.0)
    base = run_h1(case, [("L0", 0.0), ("L1", 0.0)], ledger_site="L0")
    part = run_h1(case, [("L0", 0.0), ("L1", 0.0)], ledger_site="L0",
                  partitions=[Partition(0.0, 1e12, frozenset({"L0"}), frozenset({"L1"}))])
    assert base.result.accepted_sites("tok-h1") and part.result.accepted_sites("tok-h1") == ["L0"]
    rej = part.result.first("reject", site_id="L1")
    assert rej is not None and rej.detail["reason"] == "ledger_unreachable_timeout"
    assert not part.trace.double_spend_accepted
    # physics unchanged: same lower bounds; every delivered message identical in delay
    assert part.result.network == base.result.network

    def delays(r):
        s = {e.message_id: e.time_ns for e in r.result.events if e.kind == "message_send"}
        return {round(e.time_ns - s[e.message_id], 6) for e in r.result.events if e.kind == "message_receive"}

    assert delays(part) <= delays(base)


def test_h1_ledger_idempotent_retry():
    led = FixtureH1Ledger("LEDGER", "L0")
    m = lambda key: Message("m", "M", "LEDGER", 0.0, {"type": "spend", "token_id": "t", "idem_key": key})  # noqa: E731
    first = led.on_message(m("k1"), 0.0)
    again = led.on_message(m("k1"), 1.0)
    other = led.on_message(m("k2"), 2.0)
    assert first[0].payload["ok"] and again[0].payload["ok"] and not other[0].payload["ok"]
    assert sum(1 for e in first + again + other if getattr(e, "kind", None) == "issuer_aware_of_spend") == 1


def test_h3_rejects_at_unassigned_site_and_accepts_locally_at_assigned():
    case = synthetic_two_site(1000.0)
    run = run_h3(case, [("L0", 0.0), ("L1", 0.0)], assigned_site="L0")
    assert run.result.accepted_sites("tok-h3") == ["L0"]
    rej = run.result.first("reject", site_id="L1")
    assert rej is not None and rej.detail["reason"] == "not_preassigned_here"
    acc = run.result.first("verification_result_available_local", site_id="L0")
    assert acc.time_ns == 0.0 and not run.result.of_kind("message_send")  # local, no coordination
