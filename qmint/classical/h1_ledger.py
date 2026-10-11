"""H1 -- centralized online spent ledger (strong classical baseline).

protocol_id: ``classical_h1_online_ledger`` (game C1).

* ``LedgerCoordinator``: authoritative spent set with an atomic compare-and-set
  (``threading.Lock``-protected, so it is linearizable under real threads), idempotency
  keys bound to (token, merchant), per-merchant HMAC-SHA256 request authentication and
  replay handling. Every decision gets a linearization sequence number.
* ``MerchantTerminal``: site-local terminal that forwards a presentation to the
  coordinator, retries with the SAME idempotency key on timeout, and gives up with
  ``REJECT_UNAVAILABLE`` (a liveness failure, never a double accept) after ``max_attempts``.
  Every presentation gets a fresh random 128-bit idempotency key (``secrets.token_hex``),
  persisted with the pending request; it is never derived from (merchant, token, local
  counter), so a second till of the same merchant or a restarted till cannot collide with an
  earlier request (lane M finding M-H3). A ``replayed=True`` ACCEPT is honoured only for a key
  this terminal has pending (its own retry); anything else is dropped.

Double spend succeeds only under a declared protocol fault (e.g. a compromised
coordinator or merchant MAC key); validation latency always includes the honest
coordinator round trip.
"""

from __future__ import annotations

import hashlib
import hmac
import random
import secrets
import threading
from collections.abc import Callable
from dataclasses import dataclass, field

from qmint.classical.common import Decision, Message, new_msg

PROTOCOL_ID = "classical_h1_online_ledger"


def request_mac(key: bytes, token_id: str, idem_key: str, merchant_id: str) -> str:
    body = f"spend|{token_id}|{idem_key}|{merchant_id}".encode()
    return hmac.new(key, body, hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class LedgerEntry:
    token_id: str
    idem_key: str
    merchant_id: str
    seq: int


@dataclass
class LedgerCoordinator:
    node_id: str
    site_id: str
    issued: frozenset[str] | None  # None: issuance is authenticated by a signature checked at the terminal (H4+H1)
    merchant_keys: dict[str, bytes]
    processing_ns: float = 50_000.0
    spent: dict[str, LedgerEntry] = field(default_factory=dict)
    credits: dict[str, int] = field(default_factory=dict)
    history: list[tuple[int, str, str, str, str]] = field(default_factory=list)  # (seq, token, idem, merchant, decision)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _seq: int = 0

    def spend(self, token_id: str, idem_key: str, merchant_id: str, mac: str) -> tuple[Decision, bool, int]:
        """Atomic check-and-set. Returns (decision, replayed, linearization_seq)."""
        key = self.merchant_keys.get(merchant_id)
        with self._lock:
            self._seq += 1
            seq = self._seq
            replayed = False
            if key is None or not hmac.compare_digest(mac, request_mac(key, token_id, idem_key, merchant_id)):
                decision = Decision.REJECT_BAD_AUTH
            elif self.issued is not None and token_id not in self.issued:
                decision = Decision.REJECT_UNKNOWN_TOKEN
            elif token_id in self.spent:
                prev = self.spent[token_id]
                if prev.idem_key == idem_key and prev.merchant_id == merchant_id:
                    decision, replayed = Decision.ACCEPT, True  # idempotent retry: same answer, no new credit
                elif prev.idem_key == idem_key:
                    decision = Decision.REJECT_IDEMPOTENCY_MISUSE
                else:
                    decision = Decision.REJECT_DOUBLE_SPEND
            else:
                self.spent[token_id] = LedgerEntry(token_id, idem_key, merchant_id, seq)
                self.credits[merchant_id] = self.credits.get(merchant_id, 0) + 1
                decision = Decision.ACCEPT
            self.history.append((seq, token_id, idem_key, merchant_id, decision.value))
        return decision, replayed, seq

    def handle(self, msg: Message, now_ns: float) -> list[Message]:
        if msg.kind != "SpendRequest":
            raise ValueError(f"unexpected message {msg.kind}")
        p = msg.payload
        decision, replayed, seq = self.spend(p["token_id"], p["idem_key"], p["merchant_id"], p["mac"])
        return [new_msg("SpendResponse", self.node_id, msg.src, "h1", token_id=p["token_id"],
                        idem_key=p["idem_key"], decision=decision.value, replayed=replayed, seq=seq,
                        decided_at_ns=now_ns + self.processing_ns)]


@dataclass
class MerchantTerminal:
    node_id: str
    site_id: str
    merchant_id: str
    mac_key: bytes
    coordinator_id: str
    processing_ns: float = 10_000.0
    retry_timeout_ns: float = 5_000_000.0
    max_attempts: int = 3
    router: Callable[[str], str] | None = None  # token_id -> authoritative node (H2 home-shard leader)
    pending: dict[str, dict] = field(default_factory=dict)  # idem_key -> {token, customer, attempts}
    # Source of idempotency keys. None (default): OS CSPRNG. A seeded ``random.Random`` ONLY for
    # reproducible simulations (two terminals must never share one seed).
    idem_rng: random.Random | None = field(default=None, repr=False)

    def _new_idem_key(self) -> str:
        while True:
            k = secrets.token_hex(16) if self.idem_rng is None else f"{self.idem_rng.getrandbits(128):032x}"
            if k not in self.pending:
                return k

    def _request(self, idem_key: str) -> Message:
        st = self.pending[idem_key]
        dst = self.router(st["token_id"]) if self.router else self.coordinator_id
        return new_msg("SpendRequest", self.node_id, dst, "h1", token_id=st["token_id"],
                       idem_key=idem_key, merchant_id=self.merchant_id,
                       mac=request_mac(self.mac_key, st["token_id"], idem_key, self.merchant_id))

    def handle(self, msg: Message, now_ns: float) -> list[Message]:
        if msg.kind == "Present":
            idem_key = self._new_idem_key()
            self.pending[idem_key] = {"token_id": msg.payload["token_id"], "customer": msg.src, "attempts": 1}
            return [self._request(idem_key)]
        if msg.kind == "SpendResponse":
            st = self.pending.pop(msg.payload["idem_key"], None)
            if st is None:
                return []  # late duplicate / foreign replayed response: never released as a new ACCEPT
            return [new_msg("Result", self.node_id, st["customer"], "h1", token_id=st["token_id"],
                            decision=msg.payload["decision"], replayed=bool(msg.payload.get("replayed")),
                            decided_at_ns=now_ns + self.processing_ns)]
        raise ValueError(f"unexpected message {msg.kind}")

    def on_timeout(self, idem_key: str, now_ns: float) -> list[Message]:
        """Called by the host when no response arrived within ``retry_timeout_ns``."""
        st = self.pending.get(idem_key)
        if st is None:
            return []
        if st["attempts"] >= self.max_attempts:
            self.pending.pop(idem_key)
            return [new_msg("Result", self.node_id, st["customer"], "h1", token_id=st["token_id"],
                            decision=Decision.REJECT_UNAVAILABLE.value, decided_at_ns=now_ns)]
        st["attempts"] += 1
        return [self._request(idem_key)]
