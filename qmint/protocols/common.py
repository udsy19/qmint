"""Shared protocol-layer helpers (lane B)."""

from __future__ import annotations

import secrets
import weakref
from collections.abc import Mapping, Sequence
from typing import Any

from qmint.core.contracts import SecretBoundaryError, TraceEvent


class CapabilityBoundaryError(RuntimeError):
    """A holder tried to duplicate, serialize or re-bind a simulator capability (M-B1/M-B2)."""


class PrivateVault:
    """Simulator-side store that keeps private state out of party-facing objects (M-B2).

    A party-facing object (a wallet's token handle, Alice's session) holds only an opaque
    random key. The value (simulated register, Bob's secrets) lives here, bound to that one
    owner object: a lookup succeeds only for the object that bound it, so a copy built by any
    route (``copy``, ``pickle``, ``copyreg``, ``__new__`` + ``__dict__``) resolves to nothing.
    The entry is dropped when its owner is garbage collected.

    This is an API-boundary measure inside a single-process simulator, not physics: code that
    imports this module (or walks the gc) can still reach the values. Such code is
    OUT_OF_MODEL for every game; the guarantee is that the owner's object graph (``vars()``,
    attributes, containers) holds no amplitudes and no secrets, and that no public method
    returns them.
    """

    def __init__(self, label: str) -> None:
        self._label = label
        self._items: dict[str, tuple[weakref.ref[Any], Any]] = {}

    def bind(self, owner: Any, value: Any) -> str:
        key = secrets.token_hex(16)
        self._items[key] = (weakref.ref(owner), value)
        weakref.finalize(owner, self._items.pop, key, None)
        return key

    def get(self, owner: Any, key: str | None) -> Any:
        item = self._items.get(key) if key is not None else None
        if item is None or item[0]() is not owner:
            raise CapabilityBoundaryError(
                f"{type(owner).__name__} is not bound to a {self._label} (copied or forged object?)"
            )
        return item[1]


class NonCopyable:
    """Mixin: refuse every Python duplication path (``copy``, ``deepcopy``, ``pickle``).

    ``copy``/``deepcopy`` consult ``__copy__``/``__deepcopy__`` before ``copyreg``; ``pickle``
    consults a ``copyreg``/``dispatch_table`` reducer first, but whatever such a reducer
    rebuilds is not bound in its ``PrivateVault`` and therefore holds no capability.
    """

    _copy_error: type[Exception] = CapabilityBoundaryError
    _copy_what = "a simulator capability"

    def _refuse(self, action: str) -> Exception:
        return self._copy_error(f"{type(self).__name__} holds {self._copy_what} and cannot be {action}")

    def __copy__(self) -> Any:
        raise self._refuse("copied")

    def __deepcopy__(self, memo: Any) -> Any:
        raise self._refuse("copied")

    def __reduce_ex__(self, protocol: Any) -> Any:
        raise self._refuse("pickled")

    def __reduce__(self) -> Any:
        raise self._refuse("pickled")

    def __getstate__(self) -> Any:
        raise self._refuse("pickled")


class SecretHolder(NonCopyable):
    """Mixin for challengers / bank agents that hold ``IssuerSecret`` objects.

    The frozen C1 ``IssuerSecret`` refuses pickling and ``model_dump`` but pydantic's own
    ``__deepcopy__``/``__copy__`` still duplicate it. Secret-holding objects therefore
    refuse copying and pickling themselves (defence in depth; see the lane-B handoff
    migration proposal for ``IssuerSecret.__deepcopy__``).
    """

    _copy_error = SecretBoundaryError
    _copy_what = "issuer secrets"


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
