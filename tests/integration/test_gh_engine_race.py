"""Lane H's real state machines hosted on lane G's engine: race semantics (replaces G's fixtures)."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from qmint.classical import matched_topology as M
from qmint.classical import scenarios as S
from qmint.classical.common import new_msg
from qmint.classical.engine_adapter import Injection, run_hosted
from qmint.networks.causality import assert_causal, synchronous_cross_site_round_trips
from qmint.networks.simulator import LinkRuntime, Partition
from qmint.networks.topology import jiang2024_intracity, synthetic_two_site


def _h1(case, ledger_site, tokens=frozenset({"tok"})):
    coord, terms = S.h1_nodes(ledger_site, tokens, case.site_ids, 0.0, 0.0)
    return coord, terms


def _present(site, tok="tok"):
    return new_msg("Present", f"cust@{site}", f"t@{site}", "s", token_id=tok)


def test_h0_double_accept_and_settlement_only_ex_post():
    case = synthetic_two_site(100.0)
    run = M.run_matched(case, "H0", 1, "jiang_dTproc_1507ns", adversary="replay")
    assert run.result.accepted_sites(run.spec.token_id) == ["L0", "L1"]
    assert run.trace.double_spend_accepted is True
    settle = run.result.first("bank_settlement_final")
    accepts = run.result.of_kind("verification_result_available_local")
    assert settle.detail["double_spend_detected"] is True
    assert settle.time_ns > max(e.time_ns for e in accepts)  # detected only after both sites accepted


@settings(max_examples=60, deadline=None)
@given(st.sampled_from([1.0, 10.0, 100.0, 1000.0]), st.floats(0, 1e7), st.floats(0, 1e7),
       st.sampled_from(["L0", "L1"]), st.integers(0, 1000))
def test_h1_engine_race_is_linearizable(km, t0, t1, ledger_site, seed):
    """Concurrent presentations at both sites: exactly one ACCEPT; the coordinator's linearization order
    equals the order in which the requests reached it on the engine; the loser gets a definite answer."""
    case = synthetic_two_site(km)
    coord, terms = _h1(case, ledger_site)
    run = run_hosted(case.network, [coord, *terms.values()],
                     [Injection(t0, _present("L0")), Injection(t1, _present("L1"))],
                     token_id="tok", link_runtime=case.link_runtime, seed=seed)
    dec = run.decisions()
    assert sorted(d for d, _ in dec.values()) == ["ACCEPT", "REJECT_DOUBLE_SPEND"]
    assert not run.result.double_spend_accepted("tok")
    arrivals = [e for e in run.result.of_kind("message_receive")
                if e.actor_id == "coord" and e.detail["h_kind"] == "SpendRequest"]
    first_merchant = arrivals[0].detail["body"]["merchant_id"]
    seq_order = [h[3] for h in sorted(coord.history)]
    assert seq_order == [a.detail["body"]["merchant_id"] for a in arrivals]  # linearization = arrival order
    assert coord.spent["tok"].merchant_id == first_merchant and sum(coord.credits.values()) == 1
    winner_site = first_merchant.split("@")[1]
    assert dec[f"cust@{winner_site}"][0] == "ACCEPT"
    assert_causal(run.result.to_transaction_trace("h1-race", "tok", "classical_h1_online_ledger", "ledger", False),
                  case.network)


def test_h1_remote_merchant_pays_coordination_round_trip_jinan():
    case = jiang2024_intracity()
    run = M.run_matched(case, "H1", 1, "zero_processing")
    fiber = case.link_runtime[("L1", "L0")].latency.delay_ns
    assert run.metrics["local_validation_ns"] == 2 * fiber  # 27.66 us = Jiang's classical 2L/c_fibre reference
    assert run.metrics["sync_cross_site_msgs_after_presentation"] == 2  # request out, response back


def test_h1_partition_changes_availability_not_physics():
    case = synthetic_two_site(10.0)

    def play(parts):
        coord, terms = _h1(case, "L0", frozenset({"a", "b"}))
        return run_hosted(case.network, [coord, *terms.values()],
                          [Injection(0.0, _present("L0", "a")), Injection(0.0, _present("L1", "b"))],
                          link_runtime=case.link_runtime, partitions=parts)

    base = play(())
    part = play([Partition(0.0, 1e12, frozenset({"L0"}), frozenset({"L1"}))])
    assert {d for d, _ in base.decisions().values()} == {"ACCEPT"}
    dec = part.decisions()
    assert dec["cust@L0"][0] == "ACCEPT" and dec["cust@L1"][0] == "REJECT_UNAVAILABLE"  # safe, unavailable
    assert len(part.result.dropped) == 3  # three attempts by the terminal's retry timer, all partitioned
    assert part.result.network == base.result.network

    def delays(r):
        s = {e.message_id: e.time_ns for e in r.result.events if e.kind == "message_send"}
        return {round(e.time_ns - s[e.message_id], 6) for e in r.result.events if e.kind == "message_receive"}

    assert delays(part) <= delays(base)  # every delivered message as fast as before: physics unchanged


def test_h1_lossy_link_retries_with_same_key_never_double_credits():
    case = synthetic_two_site(100.0)
    lossy = {**case.link_runtime, ("L1", "L0"): LinkRuntime(case.link_runtime[("L1", "L0")].latency, loss_prob=0.5)}
    outcomes = set()
    for seed in range(30):
        coord, terms = _h1(case, "L0")
        run = run_hosted(case.network, [coord, *terms.values()], [Injection(0.0, _present("L1"))],
                         link_runtime=lossy, seed=seed)
        (d, _), = run.decisions().values()
        outcomes.add(d)
        keys = {e.detail["body"]["idem_key"] for e in run.result.of_kind("message_send")
                if e.detail.get("h_kind") == "SpendRequest"}
        assert len(keys) == 1  # every retry reuses the idempotency key
        assert sum(coord.credits.values()) == (1 if d == "ACCEPT" else 0)
    assert outcomes == {"ACCEPT", "REJECT_UNAVAILABLE"}  # both branches exercised


def test_h3_wrong_site_rejected_locally_and_assigned_site_accepts_without_coordination():
    case = synthetic_two_site(1000.0)
    run = M.run_matched(case, "H3_preassigned", 0, "jiang_dTproc_1507ns", adversary="replay")
    dec = {e.site_id: e.detail["decision"] for e in run.result.of_kind("verification_result_available_local")}
    assert dec == {"L0": "ACCEPT", "L1": "REJECT_UNASSIGNED_SITE"}
    assert run.metrics["sync_cross_site_msgs_after_presentation"] == 0
    for mode in ("H3_late_commit_disclosed", "H3_late_commit_ot_private"):
        r = M.run_matched(case, mode, 1, "zero_processing", adversary="replay")
        dec = {e.site_id: e.detail["decision"] for e in r.result.of_kind("verification_result_available_local")}
        assert dec == {"L0": "REJECT_UNASSIGNED_SITE", "L1": "ACCEPT"}
        assert not r.trace.double_spend_accepted


def test_presentation_trigger_detector_matches_g():
    case = jiang2024_intracity()
    run = M.run_matched(case, "H1", 1, "jiang_dTproc_1507ns")
    acc = run.result.first("verification_result_available_local", site_id="L1")
    pres = run.result.first("local_validation_start", site_id="L1")
    assert synchronous_cross_site_round_trips(run.trace.events, acc.event_id, pres.causal_parent_ids[0])
