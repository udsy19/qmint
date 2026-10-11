"""Generic seeded discrete-event engine with relativistic delivery constraints (lane G).

The engine hosts :class:`~qmint.networks.events.Actor` objects at the sites of a C4
:class:`~qmint.core.contracts.SpacetimeNetwork` and enforces, for every cross-site
delivery::

    receive_time >= send_time + max(link.propagation_lower_bound_ns, light-cone(src, dst))

A latency model that proposes a faster delivery raises :class:`CausalityViolation`; the
engine never silently clamps (a too-fast "measurement" means the declared geometry or the
data are wrong, and that must surface).

Latency models (declared per directed link through :class:`LinkRuntime`):

* :class:`Lightcone`  -- exactly the physical bound (ideal causal geometry world).
* :class:`Fiber`      -- path length / fibre group velocity (default 2/3 c).
* :class:`Empirical`  -- i.i.d. resampling of a measured one-way delay sample (e.g. RIPE
  Atlas RTT/2, see :mod:`qmint.networks.ripe`).
* plus per-link FIFO queueing (``service_time_ns``), Bernoulli loss with sender
  retransmission (``loss_prob``/``max_attempts``/``retry_timeout_ns``), timed partitions,
  and per-site clock offsets bounded by ``Site.clock_error_bound_ns``.

Determinism: one ``random.Random(seed)``; the event heap is ordered by
``(time_ns, insertion sequence)`` so equal-time events fire in scheduling order.
"""

from __future__ import annotations

import heapq
import random
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from qmint.core.contracts import EvidenceKind, SpacetimeNetwork, TransactionTrace
from qmint.networks.causality import (
    C_M_PER_NS,
    TIME_TOL_NS,
    CausalityViolation,
    link_lower_bound_ns,
    network_violations,
)
from qmint.networks.events import (
    Actor,
    DroppedMessage,
    Effect,
    LocalRequest,
    Message,
    Record,
    Send,
    SetTimer,
    SimEvent,
)

FIBER_VELOCITY_FRACTION = 2.0 / 3.0  # declared assumption for synthetic fibre, not a measurement

# --------------------------------------------------------------------------- #
# Latency models
# --------------------------------------------------------------------------- #


class LatencyModel(Protocol):
    name: str
    evidence: EvidenceKind

    def sample_ns(self, rng: random.Random, lower_bound_ns: float) -> float: ...


@dataclass(frozen=True)
class Lightcone:
    """Delivery at exactly the causal lower bound (idealised, MODELLED_LATENCY)."""

    name: str = "lightcone"
    evidence: EvidenceKind = EvidenceKind.MODELLED_LATENCY

    def sample_ns(self, rng: random.Random, lower_bound_ns: float) -> float:
        return lower_bound_ns


@dataclass(frozen=True)
class Fiber:
    """Straight propagation through ``length_m`` of fibre at ``velocity_m_per_s``."""

    length_m: float
    velocity_m_per_s: float = FIBER_VELOCITY_FRACTION * C_M_PER_NS * 1e9
    evidence: EvidenceKind = EvidenceKind.MODELLED_LATENCY

    def __post_init__(self) -> None:
        if self.length_m < 0 or not (0 < self.velocity_m_per_s <= C_M_PER_NS * 1e9):
            raise ValueError("fibre length must be >= 0 and velocity in (0, c]")

    @property
    def name(self) -> str:
        return f"fiber:L={self.length_m:g}m,v={self.velocity_m_per_s:.6g}m/s"

    @property
    def delay_ns(self) -> float:
        return self.length_m / self.velocity_m_per_s * 1e9

    def sample_ns(self, rng: random.Random, lower_bound_ns: float) -> float:
        return self.delay_ns


@dataclass(frozen=True)
class Empirical:
    """Resample a recorded one-way delay sample (ns). ``source`` names its provenance."""

    samples_ns: tuple[float, ...]
    source: str
    evidence: EvidenceKind = EvidenceKind.MEASURED_LATENCY

    def __post_init__(self) -> None:
        if not self.samples_ns or any(s < 0 for s in self.samples_ns):
            raise ValueError("empirical latency needs a non-empty sample of non-negative delays")

    @property
    def name(self) -> str:
        return f"empirical:{self.source}"

    def sample_ns(self, rng: random.Random, lower_bound_ns: float) -> float:
        return self.samples_ns[rng.randrange(len(self.samples_ns))]


@dataclass(frozen=True)
class LinkRuntime:
    """Runtime behaviour of one directed link (beyond its C4 lower bound)."""

    latency: LatencyModel = field(default_factory=Lightcone)
    service_time_ns: float = 0.0  # FIFO serialisation/queueing per message
    loss_prob: float = 0.0  # per-attempt Bernoulli loss
    max_attempts: int = 1  # sender retransmits up to this many times
    retry_timeout_ns: float = 0.0  # sender-side retransmission timer

    def __post_init__(self) -> None:
        if not (0.0 <= self.loss_prob <= 1.0):
            raise ValueError("loss_prob must be in [0,1]")
        if self.max_attempts < 1 or self.service_time_ns < 0 or self.retry_timeout_ns < 0:
            raise ValueError("invalid link runtime parameters")


@dataclass(frozen=True)
class Partition:
    """During ``[start_ns, end_ns)`` no message crosses between ``side_a`` and ``side_b``."""

    start_ns: float
    end_ns: float
    side_a: frozenset[str]
    side_b: frozenset[str]

    def blocks(self, src_site: str, dst_site: str, t_ns: float) -> bool:
        if not (self.start_ns <= t_ns < self.end_ns):
            return False
        return (src_site in self.side_a and dst_site in self.side_b) or (
            src_site in self.side_b and dst_site in self.side_a
        )


# --------------------------------------------------------------------------- #
# Result
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SimulationResult:
    network: SpacetimeNetwork
    events: tuple[SimEvent, ...]
    dropped: tuple[DroppedMessage, ...]
    clock_offsets_ns: Mapping[str, float]
    seed: int
    latency_evidence: EvidenceKind

    def of_kind(self, kind: str, site_id: str | None = None) -> list[SimEvent]:
        return [e for e in self.events if e.kind == kind and (site_id is None or e.site_id == site_id)]

    def first(self, kind: str, site_id: str | None = None, **detail: Any) -> SimEvent | None:
        for e in self.of_kind(kind, site_id):
            if all(e.detail.get(k) == v for k, v in detail.items()):
                return e
        return None

    def accepted_sites(self, token_id: str) -> list[str]:
        """Sites with a positive ``verification_result_available_local`` for ``token_id``."""
        return sorted(
            {
                e.site_id
                for e in self.of_kind("verification_result_available_local")
                if e.detail.get("token_id") == token_id and e.detail.get("accepted") is True
            }
        )

    def double_spend_accepted(self, token_id: str) -> bool:
        return len(self.accepted_sites(token_id)) >= 2

    def to_transaction_trace(
        self,
        trace_id: str,
        token_id: str,
        protocol_id: str,
        irrevocability_rule: str,
        double_spend_accepted: bool,
        latency_breakdown_ns: Mapping[str, float] | None = None,
    ) -> TransactionTrace:
        return TransactionTrace(
            trace_id=trace_id,
            token_id=token_id,
            protocol_id=protocol_id,
            network_id=self.network.network_id,
            events=[e.to_trace_event() for e in self.events],
            irrevocability_rule=irrevocability_rule,
            double_spend_accepted=double_spend_accepted,
            latency_breakdown_ns=dict(latency_breakdown_ns or {}),
            latency_evidence=self.latency_evidence,
        )


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #

_LOCAL = LinkRuntime()  # same-site delivery: zero-duration idealisation (C4 allows it)


class Simulator:
    def __init__(
        self,
        network: SpacetimeNetwork,
        actors: Iterable[Actor],
        link_runtime: Mapping[tuple[str, str], LinkRuntime] | None = None,
        partitions: Sequence[Partition] = (),
        clock_offsets_ns: Mapping[str, float] | None = None,
        seed: int = 0,
    ) -> None:
        bad = network_violations(network)
        if bad:
            raise CausalityViolation("; ".join(bad))
        self.network = network
        self.sites = {s.site_id: s for s in network.sites}
        self.actors: dict[str, Actor] = {}
        for a in actors:
            if a.actor_id in self.actors:
                raise ValueError(f"duplicate actor_id {a.actor_id}")
            if a.site_id not in self.sites:
                raise ValueError(f"actor {a.actor_id} at unknown site {a.site_id}")
            self.actors[a.actor_id] = a
        self.link_runtime = dict(link_runtime or {})
        for (s, d) in self.link_runtime:
            if s not in self.sites or d not in self.sites:
                raise ValueError(f"link runtime for unknown sites {s}->{d}")
        self.partitions = tuple(partitions)
        self.seed = seed
        self.rng = random.Random(seed)
        self.clock_offsets_ns = self._offsets(clock_offsets_ns)
        self._heap: list[tuple[float, int, str, Any]] = []
        self._seq = 0
        self._events: list[SimEvent] = []
        self._dropped: list[DroppedMessage] = []
        self._link_busy_until: dict[tuple[str, str], float] = {}
        self._msg_counter = 0
        self._ran = False

    # ----------------------------------------------------------------- setup
    def _offsets(self, given: Mapping[str, float] | None) -> dict[str, float]:
        out: dict[str, float] = {}
        for sid, s in self.sites.items():
            if given is not None and sid in given:
                off = float(given[sid])
                if abs(off) > s.clock_error_bound_ns:
                    raise ValueError(f"clock offset {off} at {sid} exceeds bound {s.clock_error_bound_ns}")
            else:
                off = self.rng.uniform(-s.clock_error_bound_ns, s.clock_error_bound_ns)
            out[sid] = off
        return out

    def _push(self, t: float, tag: str, item: Any) -> None:
        heapq.heappush(self._heap, (t, self._seq, tag, item))
        self._seq += 1

    def schedule(self, request: LocalRequest) -> None:
        if request.actor_id not in self.actors:
            raise ValueError(f"unknown actor {request.actor_id}")
        self._push(request.time_ns, "request", request)

    def _runtime(self, src_site: str, dst_site: str) -> LinkRuntime:
        if src_site == dst_site:
            return self.link_runtime.get((src_site, dst_site), _LOCAL)
        return self.link_runtime.get((src_site, dst_site), LinkRuntime())

    @property
    def latency_evidence(self) -> EvidenceKind:
        kinds = {rt.latency.evidence for (s, d), rt in self.link_runtime.items() if s != d}
        if EvidenceKind.MEASURED_LATENCY in kinds:
            return EvidenceKind.MEASURED_LATENCY
        return EvidenceKind.MODELLED_LATENCY

    # ------------------------------------------------------------- recording
    def _record(
        self,
        actor_id: str,
        kind: str,
        t: float,
        parents: Sequence[str] = (),
        message_id: str | None = None,
        detail: Mapping[str, Any] | None = None,
    ) -> SimEvent:
        site = self.actors[actor_id].site_id
        ev = SimEvent(
            event_id=f"e{len(self._events):06d}",
            site_id=site,
            actor_id=actor_id,
            kind=kind,
            time_ns=t,
            local_clock_ns=t + self.clock_offsets_ns[site],
            causal_parent_ids=tuple(parents),
            message_id=message_id,
            detail=detail or {},
        )
        self._events.append(ev)
        return ev

    # ------------------------------------------------------------- transport
    def _transmit(self, src_actor: str, send: Send, t_send: float, send_event_id: str, msg_id: str) -> None:
        if send.dst not in self.actors:
            raise ValueError(f"message to unknown actor {send.dst}")
        src_site = self.actors[src_actor].site_id
        dst_site = self.actors[send.dst].site_id
        rt = self._runtime(src_site, dst_site)
        bound = link_lower_bound_ns(self.network, src_site, dst_site)
        msg = Message(msg_id=msg_id, src=src_actor, dst=send.dst, send_time_ns=t_send, payload=send.payload)
        reason = "loss"
        for attempt in range(rt.max_attempts):
            t_attempt = t_send + attempt * rt.retry_timeout_ns
            if any(p.blocks(src_site, dst_site, t_attempt) for p in self.partitions):
                reason = "partition"
                continue
            if rt.loss_prob > 0.0 and self.rng.random() < rt.loss_prob:
                reason = "loss"
                continue
            key = (src_site, dst_site)
            start = t_attempt
            if rt.service_time_ns > 0.0:
                start = max(t_attempt, self._link_busy_until.get(key, float("-inf")))
                self._link_busy_until[key] = start + rt.service_time_ns
            delay = rt.service_time_ns + rt.latency.sample_ns(self.rng, bound)
            t_recv = start + delay
            if t_recv - t_send + TIME_TOL_NS < bound:
                raise CausalityViolation(
                    f"latency model {rt.latency.name} delivers {msg_id} {src_site}->{dst_site} in "
                    f"{t_recv - t_send:.3f} ns < lower bound {bound:.3f} ns"
                )
            self._push(t_recv, "deliver", (msg, send_event_id, attempt + 1))
            return
        self._dropped.append(
            DroppedMessage(msg_id, src_actor, send.dst, t_send, attempts=rt.max_attempts, reason=reason)
        )

    def _apply(self, actor_id: str, effects: Sequence[Effect], t: float, trigger_id: str) -> None:
        for eff in effects:
            if isinstance(eff, Send):
                # Defer departure until local processing is done.
                self._push(t + eff.after_ns, "send", (actor_id, eff, trigger_id))
            elif isinstance(eff, Record):
                self._push(t + eff.after_ns, "record", (actor_id, eff, trigger_id))
            elif isinstance(eff, SetTimer):
                payload = {**eff.payload, "_timer": True}
                msg = Message(
                    msg_id=f"t{self._next_msg()}", src=actor_id, dst=actor_id, send_time_ns=t, payload=payload
                )
                self._push(t + eff.delay_ns, "timer", (msg, trigger_id))
            else:  # pragma: no cover - typing guard
                raise TypeError(f"unknown effect {eff!r}")

    def _next_msg(self) -> int:
        self._msg_counter += 1
        return self._msg_counter

    def _local_now(self, actor_id: str, t: float) -> float:
        return t + self.clock_offsets_ns[self.actors[actor_id].site_id]

    # ------------------------------------------------------------------- run
    def run(self, until_ns: float = float("inf"), max_events: int = 1_000_000) -> SimulationResult:
        if self._ran:
            raise RuntimeError("a Simulator instance runs once; build a new one")
        self._ran = True
        steps = 0
        while self._heap and self._heap[0][0] <= until_ns:
            steps += 1
            if steps > max_events:
                raise RuntimeError("max_events exceeded (livelock?)")
            t, _, tag, item = heapq.heappop(self._heap)
            if tag == "request":
                req: LocalRequest = item
                ev = self._record(req.actor_id, req.kind, t, detail={"request_id": req.request_id, **req.payload})
                actor = self.actors[req.actor_id]
                self._apply(req.actor_id, actor.on_local_request(req, self._local_now(req.actor_id, t)), t, ev.event_id)
            elif tag == "send":
                actor_id, send, trigger = item
                msg_id = f"m{self._next_msg():06d}"
                ev = self._record(
                    actor_id, "message_send", t, parents=[trigger], message_id=msg_id,
                    detail={"dst": send.dst, **send.payload},
                )
                self._transmit(actor_id, send, t, ev.event_id, msg_id)
            elif tag == "deliver":
                msg, send_event_id, attempts = item
                ev = self._record(
                    msg.dst, "message_receive", t, parents=[send_event_id], message_id=msg.msg_id,
                    detail={"src": msg.src, "attempts": attempts, **msg.payload},
                )
                actor = self.actors[msg.dst]
                self._apply(msg.dst, actor.on_message(msg, self._local_now(msg.dst, t)), t, ev.event_id)
            elif tag == "timer":
                msg, trigger = item
                actor = self.actors[msg.dst]
                # A timer is not a trace event by itself; effects are parented on the setter.
                self._apply(msg.dst, actor.on_message(msg, self._local_now(msg.dst, t)), t, trigger)
            elif tag == "record":
                actor_id, rec, trigger = item
                self._record(actor_id, rec.kind, t, parents=[trigger], detail=rec.detail)
            else:  # pragma: no cover
                raise RuntimeError(tag)
        return SimulationResult(
            network=self.network,
            events=tuple(self._events),
            dropped=tuple(self._dropped),
            clock_offsets_ns=dict(self.clock_offsets_ns),
            seed=self.seed,
            latency_evidence=self.latency_evidence,
        )
