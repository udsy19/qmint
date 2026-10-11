"""Engine tests: bounds, determinism, clocks, loss/retry, partitions, queueing (T6)."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from qmint.core.contracts import EvidenceKind, Link, Site, SpacetimeNetwork, TopologySource, TransactionTrace
from qmint.networks.causality import (
    CausalityViolation,
    assert_causal,
    lightcone_delay_ns,
    link_lower_bound_ns,
)
from qmint.networks.events import TRACE_EVENT_KINDS, LocalRequest, Message, Record, Send
from qmint.networks.simulator import (
    Empirical,
    Fiber,
    Lightcone,
    LinkRuntime,
    Partition,
    Simulator,
)
from qmint.networks.topology import FLAT_FRAME, lightcone_links


def make_net(coords, clock=5.0, net_id="t"):
    sites = [Site(site_id=f"S{i}", frame=FLAT_FRAME, x_m=x, y_m=y, trust_domain="bank",
                  clock_error_bound_ns=clock) for i, (x, y) in enumerate(coords)]
    return SpacetimeNetwork(network_id=net_id, topology_source=TopologySource.SYNTHETIC, sites=sites,
                            links=lightcone_links(sites, "lightcone", EvidenceKind.MODELLED_LATENCY))


@dataclass
class Chatter:
    """Test actor: on request, sends to targets; on receipt, optionally replies once."""

    actor_id: str
    site_id: str
    reply: bool = True
    seen_local_clock: list = field(default_factory=list)

    def on_local_request(self, request, now_ns):
        self.seen_local_clock.append(now_ns)
        return [Send(t, {"hop": 0}) for t in request.payload["targets"]]

    def on_message(self, msg, now_ns):
        self.seen_local_clock.append(now_ns)
        if self.reply and msg.payload.get("hop", 0) < 2:
            return [Send(msg.src, {"hop": msg.payload["hop"] + 1}, after_ns=10.0), Record("other", {"got": msg.msg_id})]
        return []


coords_st = st.lists(
    st.tuples(st.floats(-1e6, 1e6, allow_nan=False), st.floats(-1e6, 1e6, allow_nan=False)),
    min_size=2, max_size=4, unique=True,
)


@st.composite
def scenario(draw):
    coords = draw(coords_st)
    net = make_net(coords)
    sites = {s.site_id: s for s in net.sites}
    rt = {}
    for a in sites:
        for b in sites:
            if a == b:
                continue
            lc = lightcone_delay_ns(sites[a], sites[b])
            kind = draw(st.sampled_from(["lightcone", "fiber", "empirical"]))
            if kind == "fiber":
                lat = Fiber(length_m=lc * 0.299792458 * draw(st.floats(1.0, 3.0)))
            elif kind == "empirical":
                lat = Empirical(tuple(lc + draw(st.floats(0, 1e6)) for _ in range(3)), source="test")
            else:
                lat = Lightcone()
            rt[(a, b)] = LinkRuntime(latency=lat, service_time_ns=draw(st.sampled_from([0.0, 100.0])),
                                     loss_prob=draw(st.sampled_from([0.0, 0.3])), max_attempts=3,
                                     retry_timeout_ns=draw(st.floats(0, 1e5)))
    parts = []
    if draw(st.booleans()):
        parts.append(Partition(0.0, draw(st.floats(1.0, 1e7)), frozenset({"S0"}), frozenset(sites) - {"S0"}))
    reqs = draw(st.lists(st.tuples(st.sampled_from(sorted(sites)), st.floats(0, 1e7)), min_size=1, max_size=6))
    return net, rt, parts, reqs, draw(st.integers(0, 2**31))


def run_scenario(net, rt, parts, reqs, seed):
    actors = [Chatter(f"a_{s.site_id}", s.site_id) for s in net.sites]
    sim = Simulator(net, actors, rt, partitions=parts, seed=seed)
    ids = [a.actor_id for a in actors]
    for i, (site, t) in enumerate(reqs):
        sim.schedule(LocalRequest(f"r{i}", f"a_{site}", t, payload={"targets": [x for x in ids if x != f"a_{site}"]}))
    return sim.run()


@settings(max_examples=60, deadline=None)
@given(scenario())
def test_arrivals_never_precede_bounds(sc):
    net, rt, parts, reqs, seed = sc
    res = run_scenario(net, rt, parts, reqs, seed)
    sends = {e.message_id: e for e in res.events if e.kind == "message_send"}
    for e in res.events:
        if e.kind == "message_receive":
            s = sends[e.message_id]
            assert e.time_ns - s.time_ns >= link_lower_bound_ns(net, s.site_id, e.site_id) - 1e-6
    trace = res.to_transaction_trace("t", "tok", "classical_h0_bearer", "none", False)
    assert isinstance(trace, TransactionTrace)
    assert_causal(trace, net)


@settings(max_examples=20, deadline=None)
@given(scenario())
def test_seeded_determinism(sc):
    net, rt, parts, reqs, seed = sc
    a = run_scenario(net, rt, parts, reqs, seed)
    b = run_scenario(net, rt, parts, reqs, seed)
    assert a.events == b.events and a.dropped == b.dropped


def test_too_fast_latency_model_is_rejected_not_clamped():
    net = make_net([(0, 0), (300_000, 0)])  # 1.0007 ms light cone
    rt = {("S0", "S1"): LinkRuntime(latency=Empirical((500_000.0,), source="bogus"))}
    sim = Simulator(net, [Chatter("a0", "S0"), Chatter("a1", "S1")], rt)
    sim.schedule(LocalRequest("r", "a0", 0.0, payload={"targets": ["a1"]}))
    with pytest.raises(CausalityViolation):
        sim.run()


def test_fiber_shorter_than_distance_is_rejected():
    net = make_net([(0, 0), (10_000, 0)])
    rt = {("S0", "S1"): LinkRuntime(latency=Fiber(length_m=5_000))}
    sim = Simulator(net, [Chatter("a0", "S0"), Chatter("a1", "S1")], rt)
    sim.schedule(LocalRequest("r", "a0", 0.0, payload={"targets": ["a1"]}))
    with pytest.raises(CausalityViolation):
        sim.run()


def test_superluminal_declared_link_bound_rejected():
    sites = make_net([(0, 0), (10_000, 0)]).sites
    net = SpacetimeNetwork(network_id="bad", topology_source=TopologySource.SYNTHETIC, sites=sites, links=[
        Link(src="S0", dst="S1", propagation_lower_bound_ns=1.0, latency_model="x",
             latency_evidence=EvidenceKind.MODELLED_LATENCY, authenticated=True)])
    with pytest.raises(CausalityViolation):
        Simulator(net, [])


def test_clock_offsets_bounded_and_seen_by_actors():
    net = make_net([(0, 0), (1000, 0)], clock=50.0)
    with pytest.raises(ValueError):
        Simulator(net, [], clock_offsets_ns={"S0": 51.0})
    a0 = Chatter("a0", "S0", reply=False)
    sim = Simulator(net, [a0, Chatter("a1", "S1", reply=False)], clock_offsets_ns={"S0": 40.0, "S1": -40.0})
    sim.schedule(LocalRequest("r", "a0", 1000.0, payload={"targets": ["a1"]}))
    res = sim.run()
    assert a0.seen_local_clock == [1040.0]
    ev = res.first("other")
    assert ev is not None and ev.local_clock_ns == 1040.0 and ev.time_ns == 1000.0
    # sampled offsets also respect bounds
    s2 = Simulator(net, [], seed=7)
    assert all(abs(v) <= 50.0 for v in s2.clock_offsets_ns.values())


def test_equal_time_tie_break_is_scheduling_order():
    net = make_net([(0, 0), (1000, 0)])
    order = []

    @dataclass
    class Logger:
        actor_id: str
        site_id: str

        def on_local_request(self, request, now_ns):
            order.append(request.request_id)
            return []

        def on_message(self, msg, now_ns):
            return []

    sim = Simulator(net, [Logger("l", "S0")])
    for rid in ["z", "a", "m"]:
        sim.schedule(LocalRequest(rid, "l", 5.0))
    sim.run()
    assert order == ["z", "a", "m"]


def _pair(rt=None, parts=()):
    net = make_net([(0, 0), (30_000, 0)])  # ~100 us light cone
    a0, a1 = Chatter("a0", "S0", reply=False), Chatter("a1", "S1", reply=False)
    return net, Simulator(net, [a0, a1], rt or {}, partitions=parts)


def test_total_loss_drops_after_retries():
    _, sim = _pair({("S0", "S1"): LinkRuntime(loss_prob=1.0, max_attempts=4, retry_timeout_ns=10.0)})
    sim.schedule(LocalRequest("r", "a0", 0.0, payload={"targets": ["a1"]}))
    res = sim.run()
    assert len(res.dropped) == 1 and res.dropped[0].attempts == 4 and res.dropped[0].reason == "loss"
    assert not res.of_kind("message_receive")


def test_retry_after_partition_heals_delivers_later():
    parts = [Partition(0.0, 1_000.0, frozenset({"S0"}), frozenset({"S1"}))]
    net, sim = _pair({("S0", "S1"): LinkRuntime(max_attempts=5, retry_timeout_ns=400.0)}, parts)
    sim.schedule(LocalRequest("r", "a0", 0.0, payload={"targets": ["a1"]}))
    res = sim.run()
    rcv = res.first("message_receive")
    assert rcv is not None and rcv.detail["attempts"] == 4  # 0, 400, 800 blocked; 1200 ok
    assert rcv.time_ns == pytest.approx(1200.0 + link_lower_bound_ns(net, "S0", "S1"))


def test_partition_without_retry_drops():
    parts = [Partition(0.0, 1e9, frozenset({"S0"}), frozenset({"S1"}))]
    _, sim = _pair(parts=parts)
    sim.schedule(LocalRequest("r", "a0", 0.0, payload={"targets": ["a1"]}))
    res = sim.run()
    assert res.dropped[0].reason == "partition"


def test_fifo_queueing_serialises_messages():
    net, sim = _pair({("S0", "S1"): LinkRuntime(service_time_ns=1_000.0)})
    sim.schedule(LocalRequest("r", "a0", 0.0, payload={"targets": ["a1", "a1"]}))
    res = sim.run()
    t = sorted(e.time_ns for e in res.of_kind("message_receive"))
    lb = link_lower_bound_ns(net, "S0", "S1")
    assert t == pytest.approx([lb + 1_000.0, lb + 2_000.0])


def test_trace_export_is_valid_c4_and_kinds_known():
    _, sim = _pair()
    sim.schedule(LocalRequest("r", "a0", 0.0, payload={"targets": ["a1"]}))
    res = sim.run()
    tr = res.to_transaction_trace("t", "tok", "classical_h0_bearer", "none", False)
    TransactionTrace.model_validate(tr.model_dump())
    assert {e.kind for e in tr.events} <= TRACE_EVENT_KINDS
    assert tr.latency_evidence is EvidenceKind.MODELLED_LATENCY
    recv = [e for e in tr.events if e.kind == "message_receive"][0]
    send = [e for e in tr.events if e.kind == "message_send"][0]
    assert recv.causal_parent_ids == [send.event_id] and recv.message_id == send.message_id


def test_message_payload_is_immutable():
    m = Message("m", "a", "b", 0.0, {"x": 1})
    with pytest.raises(TypeError):
        m.payload["x"] = 2  # type: ignore[index]


def test_record_rejects_unknown_kind():
    with pytest.raises(ValueError):
        Record("settled_instantly")
