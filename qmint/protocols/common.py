"""Shared protocol-layer helpers (lane B)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from qmint.core.contracts import SecretBoundaryError, TraceEvent


class SecretHolder:
    """Mixin for challengers / bank agents that hold ``IssuerSecret`` objects.

    The frozen C1 ``IssuerSecret`` refuses pickling and ``model_dump`` but pydantic's own
    ``__deepcopy__``/``__copy__`` still duplicate it. Secret-holding objects therefore
    refuse copying and pickling themselves (defence in depth; see the lane-B handoff
    migration proposal for ``IssuerSecret.__deepcopy__``).
    """

    def __deepcopy__(self, memo: Any) -> Any:
        raise SecretBoundaryError(f"{type(self).__name__} holds issuer secrets and cannot be copied")

    def __copy__(self) -> Any:
        raise SecretBoundaryError(f"{type(self).__name__} holds issuer secrets and cannot be copied")

    def __reduce_ex__(self, protocol: Any) -> Any:
        raise SecretBoundaryError(f"{type(self).__name__} holds issuer secrets and cannot be pickled")


class CausalityError(RuntimeError):
    """An event would precede one of its causal parents."""


class EventLog:
    """C4 ``TraceEvent`` builder shared by the protocol state machines.

    Each role maps to a site id; every event of a role gets that role's previous event as a
    causal parent, and messages get a send event at the source and a receive event at the
    destination. Times are supplied by the caller; an omitted arrival time means arrival =
    send time and the receive event is tagged ``latency: "unmodelled"``.
    """

    def __init__(self, sites: Mapping[str, str]) -> None:
        self.sites = dict(sites)
        self.events: list[TraceEvent] = []
        self.last: dict[str, str] = {}

    def event(
        self,
        role: str,
        kind: str,
        t: float,
        parents: Sequence[str] = (),
        message_id: str | None = None,
        **detail: Any,
    ) -> str:
        times = {e.event_id: e.time_ns for e in self.events}
        ps = [p for p in dict.fromkeys([*parents, self.last.get(role, "")]) if p]
        for p in ps:
            if times[p] > t:
                raise CausalityError(f"{kind} at {role} (t={t}) precedes causal parent {p} (t={times[p]})")
        eid = f"ev-{len(self.events) + 1:04d}"
        self.events.append(
            TraceEvent(
                event_id=eid,
                site_id=self.sites[role],
                kind=kind,
                time_ns=float(t),
                causal_parent_ids=ps,
                message_id=message_id,
                detail={"role": role, **detail},
            )
        )
        self.last[role] = eid
        return eid

    def message(
        self,
        src: str,
        dst: str,
        item: str,
        t_send: float,
        t_recv: float | None,
        send_kind: str = "message_send",
    ) -> float:
        """Record a send/receive pair; returns the receive time."""
        mid = f"msg-{len(self.events) + 1:04d}-{item}"
        s = self.event(src, send_kind, t_send, message_id=mid, item=item, to=dst)
        extra = {} if t_recv is not None else {"latency": "unmodelled"}
        tr = t_send if t_recv is None else t_recv
        self.event(dst, "message_receive", tr, [s], message_id=mid, item=item, frm=src, **extra)
        return tr
