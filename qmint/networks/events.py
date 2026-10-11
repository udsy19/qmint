"""Actor interface and event records for the QMint discrete-event engine (lane G).

This module is the shared actor contract. Protocol lanes (B quantum, H classical)
write their parties as *pure state machines* and expose them to the engine through
the :class:`Actor` protocol below:

* ``on_local_request(request, now_ns) -> list[Effect]`` -- something happens *at* the
  actor's site without a network message (a user presents a token, a buyer chooses a
  branch, a bank decides to settle).
* ``on_message(msg, now_ns) -> list[Effect]`` -- a :class:`Message` (or a timer the actor
  set itself) is delivered.

``now_ns`` handed to actors is the actor's *local clock reading* (true coordinate time
plus the site's clock offset, bounded by ``Site.clock_error_bound_ns``). The engine itself
schedules in coordinate time; physics checks are done in coordinate time.

Effects an actor may return:

* :class:`Send` -- send ``payload`` to another actor, optionally after a local processing
  delay ``after_ns``. Cross-site delivery obeys the link's propagation lower bound.
* :class:`Record` -- record a C4 :class:`~qmint.core.contracts.TraceEvent` of a given kind
  (e.g. ``verification_result_available_local``) at ``now + after_ns``.
* :class:`SetTimer` -- deliver ``payload`` back to the same actor after ``delay_ns``
  (timeouts, retries). Timers are local and carry no information across space.

All records are immutable dataclasses so traces cannot be edited after the fact.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Protocol, get_args, runtime_checkable

from qmint.core.contracts import TraceEvent

#: Every event kind allowed by the frozen C4 ``TraceEvent`` contract.
TRACE_EVENT_KINDS: frozenset[str] = frozenset(get_args(TraceEvent.model_fields["kind"].annotation))

#: Kinds that must never be conflated (master plan 7, lane G). Local validation is not
#: issuer awareness is not settlement is not irrevocability.
SETTLEMENT_LADDER: tuple[str, ...] = (
    "verification_result_available_local",
    "issuer_aware_of_spend",
    "bank_settlement_final",
    "merchant_funds_irrevocable",
)


def _frozen_map(m: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(m or {}))


def check_kind(kind: str) -> str:
    if kind not in TRACE_EVENT_KINDS:
        raise ValueError(f"unknown trace event kind {kind!r}; allowed: {sorted(TRACE_EVENT_KINDS)}")
    return kind


@dataclass(frozen=True)
class Message:
    """A message in flight. ``send_time_ns`` is engine coordinate time (not a local clock)."""

    msg_id: str
    src: str  # sending actor id
    dst: str  # receiving actor id
    send_time_ns: float
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", _frozen_map(self.payload))

    @property
    def is_timer(self) -> bool:
        return self.src == self.dst and bool(self.payload.get("_timer", False))


@dataclass(frozen=True)
class LocalRequest:
    """An exogenous local input at an actor (user action, operator decision).

    ``kind`` is the C4 trace kind recorded for the request itself (``branch_choice``,
    ``local_validation_start``, ``issue``, ...).
    """

    request_id: str
    actor_id: str
    time_ns: float  # coordinate time at which the request occurs
    kind: str = "other"
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        check_kind(self.kind)
        object.__setattr__(self, "payload", _frozen_map(self.payload))


@dataclass(frozen=True)
class Send:
    dst: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    after_ns: float = 0.0  # local processing delay before the message leaves

    def __post_init__(self) -> None:
        if not self.after_ns >= 0.0:
            raise ValueError("Send.after_ns must be >= 0")
        object.__setattr__(self, "payload", _frozen_map(self.payload))


@dataclass(frozen=True)
class Record:
    kind: str
    detail: Mapping[str, Any] = field(default_factory=dict)
    after_ns: float = 0.0

    def __post_init__(self) -> None:
        check_kind(self.kind)
        if not self.after_ns >= 0.0:
            raise ValueError("Record.after_ns must be >= 0")
        object.__setattr__(self, "detail", _frozen_map(self.detail))


@dataclass(frozen=True)
class SetTimer:
    delay_ns: float
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.delay_ns >= 0.0:
            raise ValueError("SetTimer.delay_ns must be >= 0")
        object.__setattr__(self, "payload", _frozen_map(self.payload))


Effect = Send | Record | SetTimer


@runtime_checkable
class Actor(Protocol):
    """A party hosted at exactly one site. Must be deterministic given its inputs."""

    actor_id: str
    site_id: str

    def on_message(self, msg: Message, now_ns: float) -> list[Effect]: ...

    def on_local_request(self, request: LocalRequest, now_ns: float) -> list[Effect]: ...


@dataclass(frozen=True)
class SimEvent:
    """Engine-side record of one trace event (converted to a C4 ``TraceEvent`` on export)."""

    event_id: str
    site_id: str
    actor_id: str
    kind: str
    time_ns: float  # coordinate time
    local_clock_ns: float  # what the site's clock read at that moment
    causal_parent_ids: tuple[str, ...] = ()
    message_id: str | None = None
    detail: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        check_kind(self.kind)
        object.__setattr__(self, "detail", _frozen_map(self.detail))

    def to_trace_event(self) -> TraceEvent:
        detail = dict(self.detail)
        detail.setdefault("actor_id", self.actor_id)
        detail.setdefault("local_clock_ns", self.local_clock_ns)
        return TraceEvent(
            event_id=self.event_id,
            site_id=self.site_id,
            kind=self.kind,
            time_ns=self.time_ns,
            causal_parent_ids=list(self.causal_parent_ids),
            message_id=self.message_id,
            detail=detail,
        )


@dataclass(frozen=True)
class DroppedMessage:
    """A message the network never delivered (loss after all retries, or partition)."""

    msg_id: str
    src: str
    dst: str
    send_time_ns: float
    attempts: int
    reason: str  # "loss" | "partition"
