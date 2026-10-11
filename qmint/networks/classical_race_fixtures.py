"""TEST FIXTURES ONLY -- minimal classical race-world actors for exercising the engine.

These are *not* lane H's classical baselines (``qmint/classical/``). They exist so lane G
can test the engine's race semantics before H's state machines are integrated; the lead
replaces them with H's implementations at integration and then deletes this module.
They are intentionally minimal and must not be used for benchmark numbers.

* ``FixtureH0Bearer``   -- copyable bearer token, independent offline verifiers: two sites
  accept the same token concurrently (negative control).
* ``FixtureH1Ledger`` + ``FixtureH1Merchant`` -- online atomic spent ledger with
  compare-and-set and idempotency keys; merchants pay a coordination round trip; a
  timeout turns an unreachable ledger into an *availability* failure (reject), never into
  a double acceptance.
* ``FixtureH3Escrow``   -- token pre-assigned to one site at issuance; accepted locally
  there, rejected locally at any unassigned site (loss of late location choice).

All verifiers receive presentations as ``LocalRequest(kind="local_validation_start")``
with payload ``{"token_id": ..., "request_id": ...}``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from qmint.core.contracts import TransactionTrace
from qmint.networks.causality import assert_causal
from qmint.networks.events import Effect, LocalRequest, Message, Record, Send, SetTimer
from qmint.networks.s_money_sites import IssuerHQ
from qmint.networks.simulator import Partition, SimulationResult, Simulator
from qmint.networks.topology import TopologyCase


def _result(token_id: str, accepted: bool, site: str, **extra: object) -> Record:
    return Record("verification_result_available_local", {"token_id": token_id, "accepted": accepted,
                                                          "site": site, **extra})


@dataclass
class FixtureH0Bearer:
    actor_id: str
    site_id: str
    hq: str
    proc_ns: float = 0.0

    def on_local_request(self, request: LocalRequest, now_ns: float) -> list[Effect]:
        tok = request.payload["token_id"]
        return [
            Record("verification_result_available_local", {"token_id": tok, "accepted": True, "site": self.site_id},
                   after_ns=self.proc_ns),
            Send(self.hq, {"type": "outcome", "token_id": tok, "accepted": True, "site": self.site_id},
                 after_ns=self.proc_ns),
        ]

    def on_message(self, msg: Message, now_ns: float) -> list[Effect]:
        return []


@dataclass
class FixtureH1Ledger:
    actor_id: str
    site_id: str
    spent: dict[str, str] = field(default_factory=dict)  # token_id -> winning idempotency key

    def on_local_request(self, request: LocalRequest, now_ns: float) -> list[Effect]:
        return []

    def on_message(self, msg: Message, now_ns: float) -> list[Effect]:
        if msg.payload.get("type") != "spend":
            return []
        tok, key = msg.payload["token_id"], msg.payload["idem_key"]
        is_new = tok not in self.spent
        winner = self.spent.setdefault(tok, key)  # atomic compare-and-set (single-threaded actor)
        ok = winner == key  # a retry with the same key is idempotent
        out: list[Effect] = [Send(msg.src, {"type": "spend_reply", "token_id": tok, "idem_key": key, "ok": ok})]
        if is_new:
            out.append(Record("issuer_aware_of_spend", {"token_id": tok, "idem_key": key}))
            out.append(Record("bank_settlement_final", {"token_id": tok, "rule": "ledger CAS commit"}))
        return out


@dataclass
class FixtureH1Merchant:
    actor_id: str
    site_id: str
    ledger: str
    timeout_ns: float
    pending: dict[str, str] = field(default_factory=dict)  # idem_key -> token_id

    def on_local_request(self, request: LocalRequest, now_ns: float) -> list[Effect]:
        tok = request.payload["token_id"]
        key = f"{self.actor_id}:{request.request_id}"
        self.pending[key] = tok
        return [
            Send(self.ledger, {"type": "spend", "token_id": tok, "idem_key": key}),
            SetTimer(self.timeout_ns, {"type": "timeout", "idem_key": key}),
        ]

    def on_message(self, msg: Message, now_ns: float) -> list[Effect]:
        t = msg.payload.get("type")
        key = msg.payload.get("idem_key")
        if key not in self.pending:
            return []  # late reply after timeout, or duplicate
        tok = self.pending.pop(key)
        if t == "spend_reply":
            return [_result(tok, bool(msg.payload["ok"]), self.site_id,
                            reason=None if msg.payload["ok"] else "already_spent")]
        if t == "timeout":
            return [Record("reject", {"token_id": tok, "reason": "ledger_unreachable_timeout", "site": self.site_id})]
        return []


@dataclass
class FixtureH3Escrow:
    actor_id: str
    site_id: str
    assigned: frozenset[str]  # tokens pre-allocated to this site at issuance
    spent: set[str] = field(default_factory=set)

    def on_local_request(self, request: LocalRequest, now_ns: float) -> list[Effect]:
        tok = request.payload["token_id"]
        if tok not in self.assigned:
            return [Record("reject", {"token_id": tok, "reason": "not_preassigned_here", "site": self.site_id})]
        if tok in self.spent:
            return [Record("reject", {"token_id": tok, "reason": "already_spent_locally", "site": self.site_id})]
        self.spent.add(tok)
        return [_result(tok, True, self.site_id)]

    def on_message(self, msg: Message, now_ns: float) -> list[Effect]:
        return []


@dataclass(frozen=True)
class RaceRun:
    result: SimulationResult
    trace: TransactionTrace


Presentation = tuple[str, float]  # (site_id, coordinate time ns)


def _run(case: TopologyCase, actors: list, verifier_of: dict[str, str], presentations: Sequence[Presentation],
         token_id: str, protocol_id: str, rule: str, partitions: Sequence[Partition], seed: int) -> RaceRun:
    sim = Simulator(case.network, actors, case.link_runtime, partitions=partitions, seed=seed)
    for i, (site, t) in enumerate(presentations):
        sim.schedule(LocalRequest(f"p{i}", verifier_of[site], t, kind="local_validation_start",
                                  payload={"token_id": token_id}))
    res = sim.run()
    trace = res.to_transaction_trace(
        trace_id=f"{protocol_id}-{case.network.network_id}-seed{seed}",
        token_id=token_id,
        protocol_id=protocol_id,
        irrevocability_rule=rule,
        double_spend_accepted=res.double_spend_accepted(token_id),
    )
    assert_causal(trace, case.network)
    return RaceRun(res, trace)


def run_h0(case: TopologyCase, presentations: Sequence[Presentation], token_id: str = "tok-h0",
           seed: int = 0) -> RaceRun:
    sites = case.site_ids
    vs = [FixtureH0Bearer(f"V_{s}", s, "HQ") for s in sites]
    hq = IssuerHQ("HQ", sites[0], n_sites=len(sites))
    return _run(case, [*vs, hq], {v.site_id: v.actor_id for v in vs}, presentations, token_id,
                "classical_h0_bearer", "TEST FIXTURE: HQ settles after all sites report; double spend only "
                "detected ex post", (), seed)


def run_h1(case: TopologyCase, presentations: Sequence[Presentation], ledger_site: str | None = None,
           timeout_ns: float | None = None, partitions: Sequence[Partition] = (), token_id: str = "tok-h1",
           seed: int = 0) -> RaceRun:
    sites = case.site_ids
    ledger_site = ledger_site or sites[0]
    if timeout_ns is None:  # generous: 10x the slowest round trip the runtime models allow
        timeout_ns = 10 * 2 * max(lk.propagation_lower_bound_ns for lk in case.network.links) + 1e7
    ledger = FixtureH1Ledger("LEDGER", ledger_site)
    ms = [FixtureH1Merchant(f"M_{s}", s, "LEDGER", timeout_ns) for s in sites]
    return _run(case, [ledger, *ms], {m.site_id: m.actor_id for m in ms}, presentations, token_id,
                "classical_h1_online_ledger", "TEST FIXTURE: ledger compare-and-set commit is settlement",
                partitions, seed)


def run_h3(case: TopologyCase, presentations: Sequence[Presentation], assigned_site: str,
           token_id: str = "tok-h3", seed: int = 0) -> RaceRun:
    vs = [FixtureH3Escrow(f"E_{s}", s, frozenset({token_id}) if s == assigned_site else frozenset())
          for s in case.site_ids]
    return _run(case, vs, {v.site_id: v.actor_id for v in vs}, presentations, token_id,
                "classical_h3_preallocated_escrow", "TEST FIXTURE: local acceptance at pre-assigned site",
                (), seed)
