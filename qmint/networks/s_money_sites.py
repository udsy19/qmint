"""Two-site S-money event scenario (timing / causality model only).

What this models
----------------
The *event structure* of a two-presentation-site S-token transaction as executed by
Jiang et al. 2024 (arXiv:2408.13063, SI Fig. S3 and Methods eqs. (7)-(15)), following the
Kent et al. S-money pattern:

1. Quantum stage at L0 (``quantum_exchange``), long before the transaction.
2. Bob's agent B0 pre-distributes his secret validation record to B1 (one-way, early).
3. At ``T_begin`` Alice's agent A0 chooses the presentation site b (``branch_choice``),
   sends b to her own agent A1 over her own channel, and gives B0 the commitment
   c = z XOR b (which is independent of b for uniform z -- B learns nothing about b).
   ``run_s_money`` draws z uniformly by default (lane M finding M-G1; Kent et al. 2022 Table I:
   z is Alice's private uniform bit); a fixed z is only for explicit tests.
4. B0 forwards c to B1 (one-way). A_b presents the token x to B_b, A_(1-b) presents a dummy.
5. B_b validates *locally* from (x, its pre-distributed record, c) after ``proc_ns``:
   ``verification_result_available_local``. No query to the other site is made.
6. Both B_i report their outcome to the issuer HQ at L0: ``issuer_aware_of_spend`` on the
   first accepted report; ``bank_settlement_final`` only once HQ has both sites' outcomes
   (declared irrevocability rule; not physics, not a legal statement).

What this does NOT model: the quantum security (forgery probability is lane B/C/D's job;
``token_valid`` is a symbolic input), the actual S-token validation arithmetic, or anything
about legal finality. The transaction time it reproduces is the event-timing equation
dT_tran = dT_proc + dT_comm (Methods eq. (10)-(11)), not the physical experiment.

Preconditions for local validation (T6): B_b holds the pre-distributed record AND has
received c. Missing record -> ``fallback="reject"`` (default) rejects locally;
``fallback="query_home"`` is a deliberately *non-local* negative control that fetches the
record from B0 with a synchronous round trip, which
:func:`~qmint.networks.causality.synchronous_cross_site_round_trips` must flag.
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from qmint.core.contracts import TransactionTrace
from qmint.networks.causality import assert_causal, synchronous_cross_site_round_trips
from qmint.networks.events import Effect, LocalRequest, Message, Record, Send, SetTimer
from qmint.networks.simulator import Empirical, Fiber, Partition, SimulationResult, Simulator
from qmint.networks.topology import TopologyCase

S_MONEY_PROTOCOL_ID = "s_money_kent_2022_ideal_2site"  # event-structure stand-in; see module doc
S_MONEY_IRREVOCABILITY_RULE = (
    "bank_settlement_final when issuer HQ holds validation outcomes from every presentation "
    "site plus settlement_ns; verification_result_available_local is NOT settlement"
)


@dataclass
class SUserAgent:
    """Alice's agent A_i at site L_i (trusted by Alice)."""

    actor_id: str
    site_id: str
    index: int  # i
    bank_agent: str  # B_i at the same site
    peer: str  # A_(1-i)
    token_id: str
    present_delay_ns: float = 0.0  # A0 waits this long so both presentations are ~simultaneous
    b: int | None = None

    def on_local_request(self, request: LocalRequest, now_ns: float) -> list[Effect]:
        if request.kind == "branch_choice":
            self.b = int(request.payload["b"])
            z = int(request.payload["z"])
            c = z ^ self.b
            return [
                Send(self.peer, {"type": "branch", "b": self.b}),  # Alice's own channel
                Send(self.bank_agent, {"type": "commitment", "c": c, "token_id": self.token_id}),
                SetTimer(self.present_delay_ns, {"type": "present_now"}),
            ]
        return []

    def _present(self) -> list[Effect]:
        assert self.b is not None
        is_real = self.index == self.b
        return [Send(self.bank_agent, {"type": "present", "token_id": self.token_id, "dummy": not is_real,
                                       "token_valid": is_real})]

    def on_message(self, msg: Message, now_ns: float) -> list[Effect]:
        t = msg.payload.get("type")
        if t == "branch":
            self.b = int(msg.payload["b"])
            return self._present()
        if t == "present_now":
            return self._present()
        return []


@dataclass
class SBankAgent:
    """Bob's agent B_i at site L_i. Validates locally; never queries the other site unless
    ``fallback == "query_home"`` (negative control)."""

    actor_id: str
    site_id: str
    index: int
    peer: str  # B_(1-i)
    hq: str
    proc_ns: float
    has_record: bool = False
    fallback: str = "reject"  # or "query_home"
    commitment: int | None = None
    pending: list[Mapping[str, Any]] = field(default_factory=list)

    def on_local_request(self, request: LocalRequest, now_ns: float) -> list[Effect]:
        if request.payload.get("action") == "predistribute":
            return [Send(self.peer, {"type": "secret_record"})]
        return []

    def _validate(self, p: Mapping[str, Any]) -> list[Effect]:
        accepted = bool(p["token_valid"]) and not p["dummy"]
        out: list[Effect] = [
            Record(
                "verification_result_available_local",
                {"token_id": p["token_id"], "accepted": accepted, "dummy": p["dummy"], "site": self.site_id},
                after_ns=self.proc_ns,
            ),
            Send(self.hq, {"type": "outcome", "token_id": p["token_id"], "accepted": accepted,
                           "site": self.site_id}, after_ns=self.proc_ns),
        ]
        if accepted:
            out.append(Record("buyer_receipt", {"token_id": p["token_id"]}, after_ns=self.proc_ns))
        return out

    def _try(self) -> list[Effect]:
        out: list[Effect] = []
        if self.commitment is None:
            return out  # wait for the one-way commitment (protocol window [T, T+dT])
        while self.pending:
            p = self.pending.pop(0)
            if self.has_record:
                out += self._validate(p)
            elif self.fallback == "query_home":
                self.pending.insert(0, p)
                return [Send(self.peer, {"type": "record_query"})]
            else:
                out.append(Record("reject", {"token_id": p["token_id"], "reason": "precondition_missing:record",
                                             "site": self.site_id}))
        return out

    def on_message(self, msg: Message, now_ns: float) -> list[Effect]:
        t = msg.payload.get("type")
        if t == "secret_record":
            self.has_record = True
            return self._try()
        if t == "record_query":  # only reachable in the negative-control variant
            return [Send(msg.src, {"type": "secret_record"})] if self.has_record else []
        if t == "commitment":
            first = self.commitment is None
            self.commitment = int(msg.payload["c"])
            fwd: list[Effect] = []
            if first and msg.src != self.peer:  # B0 forwards c received from Alice to B1
                fwd = [Send(self.peer, {"type": "commitment", "c": self.commitment,
                                        "token_id": msg.payload["token_id"]})]
            return fwd + self._try()
        if t == "present":
            self.pending.append(dict(msg.payload))
            return [Record("local_validation_start", {"token_id": msg.payload["token_id"]})] + self._try()
        return []


@dataclass
class IssuerHQ:
    """Issuer headquarters: learns of spends; settles when every site has reported."""

    actor_id: str
    site_id: str
    n_sites: int
    settlement_ns: float = 0.0
    reports: dict[str, dict[str, bool]] = field(default_factory=dict)

    def on_local_request(self, request: LocalRequest, now_ns: float) -> list[Effect]:
        return []

    def on_message(self, msg: Message, now_ns: float) -> list[Effect]:
        if msg.payload.get("type") != "outcome":
            return []
        tok, site, acc = msg.payload["token_id"], msg.payload["site"], bool(msg.payload["accepted"])
        rep = self.reports.setdefault(tok, {})
        first_accept = acc and not any(rep.values())
        rep[site] = acc
        out: list[Effect] = []
        if first_accept:
            out.append(Record("issuer_aware_of_spend", {"token_id": tok, "site": site}))
        if len(rep) == self.n_sites:
            n_acc = sum(rep.values())
            out.append(Record("bank_settlement_final", {"token_id": tok, "accepted_sites": n_acc,
                                                        "double_spend_detected": n_acc >= 2},
                              after_ns=self.settlement_ns))
        return out


def nominal_one_way_ns(case: TopologyCase, src: str, dst: str) -> float:
    """Worst-case runtime one-way delay of a link (used only for A0's presentation timer)."""
    lat = case.link_runtime[(src, dst)].latency
    if isinstance(lat, Fiber):
        return lat.delay_ns
    if isinstance(lat, Empirical):
        return max(lat.samples_ns)
    raise TypeError(f"no nominal delay for {lat!r}")


@dataclass(frozen=True)
class SMoneyRun:
    result: SimulationResult
    trace: TransactionTrace
    transaction_time_ns: float | None  # branch_choice -> accepted local result at L_b
    choice_event_id: str
    local_round_trips: tuple[str, ...]  # synchronous cross-site round trips before the accept


def run_s_money(
    case: TopologyCase,
    b: int,
    z: int | None = None,
    t_choice_ns: float = 1_000_000.0,
    proc_ns: float = 1507.0,
    predistribute: bool = True,
    fallback: str = "reject",
    settlement_ns: float = 0.0,
    partitions: tuple[Partition, ...] = (),
    seed: int = 0,
    token_id: str = "tok-s-0",
) -> SMoneyRun:
    if b not in (0, 1) or z not in (None, 0, 1):
        raise ValueError("b and z are bits")
    if z is None:
        # Alice's private uniform z, seeded for reproducibility. Coupling: draw the uniform commitment
        # c from the seed and set z = c XOR b. (b, z, c) has exactly the honest joint law (z uniform and
        # independent of b), and for a fixed seed Bob's whole pre-presentation view is identical for
        # b = 0 and b = 1, i.e. the privacy property holds pathwise, not only in distribution.
        z = random.Random(f"s-money-c|{seed}").getrandbits(1) ^ b
    L0, L1 = case.site_ids[:2]
    a = [SUserAgent(f"A{i}", s, i, f"B{i}", f"A{1 - i}", token_id) for i, s in enumerate((L0, L1))]
    a[0].present_delay_ns = nominal_one_way_ns(case, L0, L1)
    # B0 generated the secret record during the quantum stage at L0; B1 only has it if pre-distributed.
    bank = [
        SBankAgent(f"B{i}", s, i, f"B{1 - i}", "HQ", proc_ns, has_record=(i == 0), fallback=fallback)
        for i, s in enumerate((L0, L1))
    ]
    hq = IssuerHQ("HQ", L0, n_sites=2, settlement_ns=settlement_ns)
    sim = Simulator(case.network, [*a, *bank, hq], case.link_runtime, partitions=partitions, seed=seed)
    sim.schedule(LocalRequest("q0", "A0", 0.0, kind="quantum_exchange", payload={"token_id": token_id}))
    if predistribute:
        sim.schedule(LocalRequest("pd0", "B0", 0.0, kind="other", payload={"action": "predistribute"}))
    sim.schedule(LocalRequest("choice", "A0", t_choice_ns, kind="branch_choice", payload={"b": b, "z": z}))
    res = sim.run()

    choice = res.first("branch_choice")
    assert choice is not None
    acc = res.first("verification_result_available_local", site_id=case.site_ids[b], accepted=True)
    rts: tuple[str, ...] = ()
    if acc is not None:
        evs = [e.to_trace_event() for e in res.events]
        rts = tuple(synchronous_cross_site_round_trips(evs, acc.event_id, _presentation_start(res, b, case)))
    tt = None if acc is None else acc.time_ns - choice.time_ns
    breakdown = {"proc_ns": proc_ns}
    if tt is not None:
        breakdown["choice_to_local_result_ns"] = tt
        breakdown["cross_site_comm_ns"] = tt - proc_ns
    trace = res.to_transaction_trace(
        trace_id=f"smoney-{case.network.network_id}-b{b}-seed{seed}",
        token_id=token_id,
        protocol_id=S_MONEY_PROTOCOL_ID,
        irrevocability_rule=S_MONEY_IRREVOCABILITY_RULE,
        double_spend_accepted=res.double_spend_accepted(token_id),
        latency_breakdown_ns=breakdown,
    )
    assert_causal(trace, case.network)
    return SMoneyRun(res, trace, tt, choice.event_id, rts)


def _presentation_start(res: SimulationResult, b: int, case: TopologyCase) -> str:
    """The receive event of the genuine presentation at L_b (trigger for round-trip analysis)."""
    ev = res.first("local_validation_start", site_id=case.site_ids[b])
    assert ev is not None
    return ev.causal_parent_ids[0]
