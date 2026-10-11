"""Host lane-H classical state machines on lane-G's discrete-event engine (the only H<->G glue).

Lane H writes every party as a pure node ``handle(Message, now_ns) -> list[Message]`` with a
declared ``processing_ns`` (:class:`qmint.classical.common.ProtocolNode`). Lane G's engine
(:mod:`qmint.networks.simulator`) hosts :class:`qmint.networks.events.Actor` objects that
return ``Send | Record | SetTimer`` effects. This module maps one onto the other:

* :class:`NodeActor` wraps one node. Every output message leaves after the node's
  ``processing_ns`` (as a G ``Send``), so cross-site delivery is subject to the engine's
  light-cone / link lower bound and runtime latency model (fibre, RIPE, queueing, loss,
  partitions). Retry timers: a node exposing ``on_timeout(idem_key, now_ns)`` and
  ``retry_timeout_ns`` (H1 ``MerchantTerminal``) arms a G ``SetTimer`` for every outgoing
  request that carries an ``idem_key``; when it fires the engine calls ``on_timeout``.
  No engine change was needed: G's ``SetTimer`` already redelivers to the same actor.
* :class:`PresentationPoint` is the user's agent / till at one site. It injects H messages
  (presentations, Stage-II commits), answers interactive challenges through ``react``
  (H5 device, H6 wallet), records the C4 ``verification_result_available_local`` event when
  a ``Result`` arrives, and can report the outcome to a G ``IssuerHQ`` (one-way, exactly
  like the S-money bank agents do) so issuer awareness / settlement are measured the same way.

``run_hosted`` builds a :class:`~qmint.networks.simulator.Simulator`, schedules injections
and returns the G ``SimulationResult``; the trace exporter and causality checker are G's.
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from qmint.classical.common import Decision, ProtocolNode
from qmint.classical.common import Message as HMessage
from qmint.core.contracts import SpacetimeNetwork
from qmint.networks.events import Effect, LocalRequest, Message, Record, Send, SetTimer
from qmint.networks.simulator import LinkRuntime, Partition, SimulationResult, Simulator

React = Callable[[HMessage], list[HMessage]]


def wrap(m: HMessage) -> dict[str, Any]:
    """Engine payload carrying one H message (deep-copied: nodes never share mutable state). H's
    process-global ``msg_id`` is dropped; the engine's deterministic message id replaces it."""
    return {"h_kind": m.kind, "body": copy.deepcopy(dict(m.payload))}


def unwrap(msg: Message) -> HMessage:
    p = msg.payload
    return HMessage(kind=p["h_kind"], src=msg.src, dst=msg.dst, payload=copy.deepcopy(dict(p["body"])),
                    msg_id=msg.msg_id)


@dataclass
class NodeActor:
    """G ``Actor`` hosting one H ``ProtocolNode``."""

    node: ProtocolNode
    followup: React | None = None  # extra messages after a Result leaves (e.g. H6 merchant deposit)
    annotate: Callable[[HMessage], list[Record]] | None = None  # C4 trace events implied by an output

    @property
    def actor_id(self) -> str:
        return self.node.node_id

    @property
    def site_id(self) -> str:
        return self.node.site_id

    def on_local_request(self, request: LocalRequest, now_ns: float) -> list[Effect]:
        """Out-of-band operator action at the node (e.g. issuance): send the injected messages."""
        return _sends(request)

    def on_message(self, msg: Message, now_ns: float) -> list[Effect]:
        if msg.is_timer:
            return self._effects(self.node.on_timeout(msg.payload["idem_key"], now_ns), 0.0)  # type: ignore[attr-defined]
        return self._effects(self.node.handle(unwrap(msg), now_ns), self.node.processing_ns)

    def _effects(self, outs: Iterable[HMessage], after_ns: float) -> list[Effect]:
        retry = getattr(self.node, "retry_timeout_ns", None) if hasattr(self.node, "on_timeout") else None
        eff: list[Effect] = []
        for m in outs:
            eff.append(Send(m.dst, wrap(m), after_ns=after_ns))
            if retry is not None and "idem_key" in m.payload:
                eff.append(SetTimer(after_ns + retry, {"idem_key": m.payload["idem_key"]}))
            if self.followup is not None and m.kind == "Result":
                eff += [Send(f.dst, wrap(f), after_ns=after_ns) for f in self.followup(m)]
            if self.annotate is not None:
                eff += [Record(r.kind, r.detail, after_ns=after_ns) for r in self.annotate(m)]
        return eff


@dataclass
class PresentationPoint:
    """User agent + till at one site (G ``Actor``).

    Local requests carry ``{"send": [wrapped H messages]}`` (sent immediately) and/or
    ``{"report_null": True}`` (tell the issuer HQ nothing was presented here). A ``"go"``
    message from a choice agent presents ``present`` (genuine) or reports null (dummy),
    mirroring S-money's A_b / A_(1-b) presentations.
    """

    actor_id: str
    site_id: str
    token_id: str
    react: React | None = None
    hq: str | None = None
    present: Sequence[HMessage] = ()

    def _report(self, accepted: bool) -> list[Effect]:
        if self.hq is None:
            return []
        return [Send(self.hq, {"type": "outcome", "token_id": self.token_id, "accepted": accepted,
                               "site": self.site_id})]

    def on_local_request(self, request: LocalRequest, now_ns: float) -> list[Effect]:
        eff = _sends(request)
        if request.payload.get("report_null"):
            eff += self._report(False)
        return eff

    def on_message(self, msg: Message, now_ns: float) -> list[Effect]:
        if msg.payload.get("type") == "go":
            if not msg.payload["genuine"]:
                return self._report(False)
            return [Record("local_validation_start", {"token_id": self.token_id, "site": self.site_id}),
                    *(Send(m.dst, wrap(m)) for m in self.present)]
        h = unwrap(msg)
        if h.kind == "Result":
            decision = h.payload["decision"]
            accepted = decision == Decision.ACCEPT.value
            return [Record("verification_result_available_local",
                           {"token_id": self.token_id, "accepted": accepted, "decision": decision,
                            "site": self.site_id, "verifier": h.src}),
                    *self._report(accepted)]
        if self.react is None:
            return []
        return [Send(m.dst, wrap(m)) for m in self.react(h)]


def inject(msgs: Sequence[HMessage]) -> dict[str, Any]:
    """LocalRequest payload that makes the requested actor send ``msgs`` now."""
    return {"send": [{"dst": m.dst, "msg": wrap(m)} for m in msgs]}


def _sends(request: LocalRequest) -> list[Effect]:
    return [Send(w["dst"], w["msg"]) for w in request.payload.get("send", ())]


def wire_bytes(result: SimulationResult, actors: Iterable[str] | None = None) -> int:
    """Canonical-JSON bytes of every H message sent (optionally only by ``actors``)."""
    keep = None if actors is None else set(actors)
    return sum(
        HMessage(e.detail["h_kind"], e.actor_id, e.detail["dst"], e.detail["body"]).size_bytes()
        for e in result.of_kind("message_send")
        if "h_kind" in e.detail and (keep is None or e.actor_id in keep)
    )


@dataclass
class Injection:
    time_ns: float
    msg: HMessage
    kind: str = "local_validation_start"  # C4 kind recorded for the injection itself
    site: str | None = None  # where a new PresentationPoint for msg.src lives (default: msg.dst's site)


@dataclass
class HostedRun:
    result: SimulationResult
    clients: dict[str, PresentationPoint] = field(default_factory=dict)

    def decisions(self) -> dict[str, tuple[str, float]]:
        """First local decision per client actor: ``{client_id: (decision, time_ns)}``."""
        out: dict[str, tuple[str, float]] = {}
        for e in self.result.of_kind("verification_result_available_local"):
            out.setdefault(e.actor_id, (str(e.detail["decision"]), e.time_ns))
        return out


def run_hosted(
    network: SpacetimeNetwork,
    nodes: Iterable[ProtocolNode | NodeActor],
    injections: Sequence[Injection],
    *,
    token_id: str = "tok",
    reacts: Mapping[str, React] | None = None,
    link_runtime: Mapping[tuple[str, str], LinkRuntime] | None = None,
    partitions: Sequence[Partition] = (),
    clock_offsets_ns: Mapping[str, float] | None = None,
    seed: int = 0,
) -> HostedRun:
    """Run H nodes on G's engine. A PresentationPoint is created for every injection source that is
    not a hosted node, at ``Injection.site`` or else co-located with the node its first message targets."""
    actors = [n if isinstance(n, NodeActor) else NodeActor(n) for n in nodes]
    site_of = {a.actor_id: a.site_id for a in actors}
    clients: dict[str, PresentationPoint] = {}
    for inj in injections:
        src = inj.msg.src
        if src not in clients and src not in site_of:
            clients[src] = PresentationPoint(src, inj.site or site_of[inj.msg.dst], token_id, (reacts or {}).get(src))
    sim = Simulator(network, [*actors, *clients.values()], link_runtime, partitions=partitions,
                    clock_offsets_ns=clock_offsets_ns, seed=seed)
    for i, inj in enumerate(injections):
        sim.schedule(LocalRequest(f"inj{i}", inj.msg.src, inj.time_ns, kind=inj.kind, payload=inject([inj.msg])))
    return HostedRun(sim.run(), clients)
