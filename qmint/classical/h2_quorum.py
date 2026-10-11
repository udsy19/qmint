"""H2 -- sharded, quorum-replicated authoritative spent ledger.

protocol_id: ``classical_h2_quorum`` (game C1).

Tokens are hashed to a HOME SHARD; a redemption is routed only to that shard (not a
strawman global wait). Each shard is a replica group of ``2f+1`` crash-fault replicas
with a stable leader (steady-state Multi-Paxos / Raft-style commit): the leader
serialises spends of a token, sends ``Accept`` to its followers and commits once a
majority (``f+1`` including itself) has persisted the entry. Up to ``f`` crashed
replicas per shard keep the shard live; ``f+1`` crashes make it unavailable (no commit,
never a double accept).

Out of scope (documented, NOT implemented): leader election / view change, Byzantine
replicas, cross-shard transactions, log compaction. A conflicting spend that arrives
while the first is still in flight is rejected conservatively (the first may later
fail to commit, leaving the token locked: an availability, not a safety, cost).
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field

from qmint.classical.common import Decision, Message, new_msg
from qmint.classical.h1_ledger import request_mac

PROTOCOL_ID = "classical_h2_quorum"


def home_shard(token_id: str, n_shards: int) -> int:
    return int.from_bytes(hashlib.sha256(token_id.encode()).digest()[:8], "big") % n_shards


@dataclass
class ShardReplica:
    node_id: str
    site_id: str
    shard: int
    f: int
    is_leader: bool
    followers: tuple[str, ...] = ()
    issued: frozenset[str] = frozenset()
    merchant_keys: dict[str, bytes] = field(default_factory=dict)
    processing_ns: float = 50_000.0
    crashed: bool = False
    committed: dict[str, tuple[str, str]] = field(default_factory=dict)  # token -> (idem, merchant)
    accepted_log: dict[int, str] = field(default_factory=dict)  # follower persistent log: slot -> token
    inflight: dict[str, dict] = field(default_factory=dict)  # leader: token -> {idem, merchant, slot, acks, client}
    _slot: int = 0

    @property
    def quorum(self) -> int:
        return self.f + 1

    def handle(self, msg: Message, now_ns: float) -> list[Message]:
        if self.crashed:
            return []
        if msg.kind == "SpendRequest":
            return self._on_spend(msg, now_ns)
        if msg.kind == "Accept":
            self.accepted_log[msg.payload["slot"]] = msg.payload["token_id"]
            return [new_msg("AcceptAck", self.node_id, msg.src, "h2", slot=msg.payload["slot"],
                            token_id=msg.payload["token_id"])]
        if msg.kind == "AcceptAck":
            return self._on_ack(msg, now_ns)
        if msg.kind == "Commit":
            self.committed[msg.payload["token_id"]] = (msg.payload["idem_key"], msg.payload["merchant_id"])
            return []
        raise ValueError(f"unexpected message {msg.kind}")

    def _reply(self, client: str, token_id: str, idem_key: str, decision: Decision, now_ns: float) -> Message:
        return new_msg("SpendResponse", self.node_id, client, "h2", token_id=token_id, idem_key=idem_key,
                       decision=decision.value, decided_at_ns=now_ns + self.processing_ns)

    def _on_spend(self, msg: Message, now_ns: float) -> list[Message]:
        if not self.is_leader:
            raise ValueError("SpendRequest routed to a non-leader replica")
        p = msg.payload
        tok, idem, merchant = p["token_id"], p["idem_key"], p["merchant_id"]
        key = self.merchant_keys.get(merchant)
        if key is None or not hmac.compare_digest(p["mac"], request_mac(key, tok, idem, merchant)):
            return [self._reply(msg.src, tok, idem, Decision.REJECT_BAD_AUTH, now_ns)]
        if tok not in self.issued:
            return [self._reply(msg.src, tok, idem, Decision.REJECT_UNKNOWN_TOKEN, now_ns)]
        if tok in self.committed:
            same = self.committed[tok] == (idem, merchant)
            return [self._reply(msg.src, tok, idem, Decision.ACCEPT if same else Decision.REJECT_DOUBLE_SPEND,
                                now_ns)]
        if tok in self.inflight:
            if (self.inflight[tok]["idem"], self.inflight[tok]["merchant"]) == (idem, merchant):
                return []  # retry of an in-flight request: answer comes when it commits
            return [self._reply(msg.src, tok, idem, Decision.REJECT_DOUBLE_SPEND, now_ns)]
        self._slot += 1
        self.inflight[tok] = {"idem": idem, "merchant": merchant, "slot": self._slot,
                              "acks": {self.node_id}, "client": msg.src}
        self.accepted_log[self._slot] = tok
        return [new_msg("Accept", self.node_id, fid, "h2", slot=self._slot, token_id=tok) for fid in self.followers]

    def _on_ack(self, msg: Message, now_ns: float) -> list[Message]:
        tok = msg.payload["token_id"]
        st = self.inflight.get(tok)
        if st is None or st["slot"] != msg.payload["slot"]:
            return []  # late ack after commit
        st["acks"].add(msg.src)
        if len(st["acks"]) < self.quorum:
            return []
        self.inflight.pop(tok)
        self.committed[tok] = (st["idem"], st["merchant"])
        out = [self._reply(st["client"], tok, st["idem"], Decision.ACCEPT, now_ns)]
        out += [new_msg("Commit", self.node_id, fid, "h2", token_id=tok, idem_key=st["idem"],
                        merchant_id=st["merchant"]) for fid in self.followers]
        return out
