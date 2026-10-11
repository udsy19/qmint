"""Shared primitives for the classical comparator state machines (lane H).

Every H-protocol is a pure, deterministic state machine:

    node.handle(message, now_ns) -> list[Message]

There is deliberately NO event queue here: lane G owns the discrete-event engine.
For lane-H tests and the baseline runner, message timing is computed with
``path_delay_ns`` on a frozen C4 ``SpacetimeNetwork`` (sum of declared
``propagation_lower_bound_ns`` along the fastest path) plus each node's declared
``processing_ns``. Because ``propagation_lower_bound_ns`` is a LOWER bound, every
latency computed here is an optimistic (classical-favourable) lower bound.
"""

from __future__ import annotations

import heapq
import itertools
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

from qmint.core.contracts import EvidenceKind, Link, Site, SpacetimeNetwork, TopologySource
from qmint.core.serialization import canonical_json

SPEED_OF_LIGHT_M_PER_NS = 0.299792458


class Decision(str, Enum):
    ACCEPT = "ACCEPT"
    REJECT_DOUBLE_SPEND = "REJECT_DOUBLE_SPEND"
    REJECT_UNKNOWN_TOKEN = "REJECT_UNKNOWN_TOKEN"
    REJECT_UNASSIGNED_SITE = "REJECT_UNASSIGNED_SITE"
    REJECT_NOT_ACTIVATED = "REJECT_NOT_ACTIVATED"
    REJECT_BAD_AUTH = "REJECT_BAD_AUTH"
    REJECT_BAD_SIGNATURE = "REJECT_BAD_SIGNATURE"
    REJECT_IDEMPOTENCY_MISUSE = "REJECT_IDEMPOTENCY_MISUSE"
    REJECT_UNAVAILABLE = "REJECT_UNAVAILABLE"  # liveness failure (e.g. partition), not a security event
    REJECT_DEVICE_REFUSED = "REJECT_DEVICE_REFUSED"


_msg_counter = itertools.count()


@dataclass(frozen=True)
class Message:
    """An explicit protocol message. ``payload`` must be JSON-serialisable (byte-size accounting)."""

    kind: str
    src: str  # node id
    dst: str  # node id
    payload: Mapping[str, Any] = field(default_factory=dict)
    msg_id: str = ""

    def size_bytes(self) -> int:
        """Canonical-JSON size of the message (a declared, implementation-independent byte cost)."""
        body = {"kind": self.kind, "src": self.src, "dst": self.dst, "payload": dict(self.payload)}
        return len(canonical_json(body).encode("utf-8"))


def new_msg(kind: str, src: str, dst: str, prefix: str, **payload: Any) -> Message:
    """Construct a message with a deterministic per-process sequence id (ids never affect logic)."""
    return Message(kind=kind, src=src, dst=dst, payload=payload, msg_id=f"{prefix}-{next(_msg_counter)}")


class ProtocolNode(Protocol):
    """Structural interface a lane-G engine can host."""

    node_id: str
    site_id: str
    processing_ns: float

    def handle(self, msg: Message, now_ns: float) -> list[Message]: ...


# --------------------------------------------------------------------------- #
# Tiny latency function on a frozen C4 network (NOT an event engine)
# --------------------------------------------------------------------------- #


def path_delay_ns(
    network: SpacetimeNetwork,
    src_site: str,
    dst_site: str,
    down_links: Iterable[tuple[str, str]] = (),
) -> float:
    """Fastest-path sum of ``propagation_lower_bound_ns`` from src to dst (Dijkstra).

    ``down_links`` models a partition (directed (src, dst) pairs removed).
    Returns ``math.inf`` when dst is unreachable. Same-site delay is 0.
    """
    ids = {s.site_id for s in network.sites}
    if src_site not in ids or dst_site not in ids:
        raise ValueError(f"unknown site in path {src_site}->{dst_site}")
    if src_site == dst_site:
        return 0.0
    down = set(down_links)
    adj: dict[str, list[tuple[str, float]]] = {}
    for lk in network.links:
        if (lk.src, lk.dst) in down:
            continue
        adj.setdefault(lk.src, []).append((lk.dst, lk.propagation_lower_bound_ns))
    dist = {src_site: 0.0}
    heap = [(0.0, src_site)]
    while heap:
        d, u = heapq.heappop(heap)
        if u == dst_site:
            return d
        if d > dist.get(u, math.inf):
            continue
        for v, w in adj.get(u, []):
            nd = d + w
            if nd < dist.get(v, math.inf):
                dist[v] = nd
                heapq.heappush(heap, (nd, v))
    return math.inf


def deliver(
    network: SpacetimeNetwork,
    nodes: Mapping[str, ProtocolNode],
    msg: Message,
    sent_at_ns: float,
    down_links: Iterable[tuple[str, str]] = (),
) -> tuple[list[tuple[Message, float]], float]:
    """Deliver ONE message by direct call (no queue, no scheduling policy).

    Returns ``(outputs, arrival_ns)``; each output is paired with its send time
    (= arrival + the handling node's declared ``processing_ns``). If the destination is
    unreachable (partition) the message is lost: ``([], inf)``.
    """
    dst = nodes[msg.dst]
    src_site = nodes[msg.src].site_id if msg.src in nodes else dst.site_id
    delay = path_delay_ns(network, src_site, dst.site_id, down_links)
    if math.isinf(delay):
        return [], math.inf
    arrival = sent_at_ns + delay
    outs = dst.handle(msg, arrival)
    return [(m, arrival + dst.processing_ns) for m in outs], arrival


def lightcone_network(
    network_id: str,
    coords_m: Mapping[str, tuple[float, float]],
    trust_domain: str = "bank",
    clock_error_bound_ns: float = 1.0,
) -> SpacetimeNetwork:
    """Fully connected SYNTHETIC network whose link lower bounds are straight-line distance / c.

    Scenario helper for lane-H tests only; lane G owns realistic topologies (fiber, RIPE).
    """
    sites = [
        Site(site_id=k, frame="flat_local_approx", x_m=x, y_m=y, trust_domain=trust_domain,
             clock_error_bound_ns=clock_error_bound_ns)
        for k, (x, y) in coords_m.items()
    ]
    links = []
    for a, b in itertools.permutations(coords_m, 2):
        (xa, ya), (xb, yb) = coords_m[a], coords_m[b]
        d = math.hypot(xa - xb, ya - yb)
        links.append(Link(src=a, dst=b, propagation_lower_bound_ns=round(d / SPEED_OF_LIGHT_M_PER_NS, 3),
                          latency_model="lightcone", latency_evidence=EvidenceKind.MODELLED_LATENCY, authenticated=True))
    return SpacetimeNetwork(network_id=network_id, topology_source=TopologySource.SYNTHETIC,
                            sites=sites, links=links)
