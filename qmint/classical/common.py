"""Shared primitives for the classical comparator state machines (lane H).

Every H-protocol is a pure, deterministic state machine:

    node.handle(message, now_ns) -> list[Message]

There is deliberately NO event queue here: the nodes are hosted on lane G's discrete-event
engine through :mod:`qmint.classical.engine_adapter` (light-cone / link lower bounds,
runtime latency models, partitions, retry timers). Each node declares ``processing_ns``,
the local delay before its outputs leave.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

from qmint.core.contracts import EvidenceKind, Site, SpacetimeNetwork, TopologySource
from qmint.core.serialization import canonical_json
from qmint.networks.topology import FLAT_FRAME, lightcone_links


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


def lightcone_network(
    network_id: str,
    coords_m: Mapping[str, tuple[float, float]],
    trust_domain: str = "bank",
    clock_error_bound_ns: float = 1.0,
) -> SpacetimeNetwork:
    """Fully connected SYNTHETIC network whose link lower bounds are the exact light cone.

    Scenario helper for lane-H baselines; links come from lane G's ``lightcone_links`` so the
    engine's causality check accepts them (no rounding below the light cone).
    """
    sites = [
        Site(site_id=k, frame=FLAT_FRAME, x_m=x, y_m=y, trust_domain=trust_domain,
             clock_error_bound_ns=clock_error_bound_ns)
        for k, (x, y) in coords_m.items()
    ]
    return SpacetimeNetwork(network_id=network_id, topology_source=TopologySource.SYNTHETIC, sites=sites,
                            links=lightcone_links(sites, "lightcone", EvidenceKind.MODELLED_LATENCY))
