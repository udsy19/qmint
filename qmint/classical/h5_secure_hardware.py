"""H5 -- hardware-backed offline credential: a TRUST MODEL, not a security proof.

protocol_id: ``classical_h5_secure_hardware`` (game C1).

Assumption H5-TR (declared, untestable here): the wallet's secure element (SE / TEE)
is tamper resistant -- its token store, monotonic anti-replay counter and attestation
key cannot be read, rolled back or cloned. Under H5-TR an offline merchant at ANY site
can accept instantly with late site choice and no coordination, and the SE refuses a
second spend of the same token.

This is NOT simulated as unbreakable: ``SecureElement(tamper_resistant=False)`` models a
broken assumption (state extraction / cloning, e.g. via fault injection or side channels),
after which offline double spending succeeds and is only detectable ex post by
``reconcile`` -- classified ``OUT_OF_MODEL`` because the trust assumption failed.

Attestations use HMAC-SHA256 as a SYMMETRIC STAND-IN for an asymmetric device-attestation
signature (real deployments use per-device certified signing keys; with HMAC a merchant
holding the key could forge, which is out of this model). No real device is benchmarked.
"""

from __future__ import annotations

import copy
import hashlib
import hmac
from dataclasses import dataclass, field

from qmint.classical.common import Decision, Message, new_msg

PROTOCOL_ID = "classical_h5_secure_hardware"
ASSUMPTION_ID = "H5-TR: tamper-resistant secure element (no state extraction, cloning or counter rollback)"


class TamperResistanceAssumption(RuntimeError):
    """Raised when code tries to read SE internals while the tamper-resistance assumption holds."""


def _attest_mac(key: bytes, device_id: str, token_id: str, merchant_id: str, nonce: str, counter: int) -> str:
    body = f"h5|{device_id}|{token_id}|{merchant_id}|{nonce}|{counter}".encode()
    return hmac.new(key, body, hashlib.sha256).hexdigest()


@dataclass
class SecureElement:
    device_id: str
    tamper_resistant: bool = True
    _key: bytes = field(default=b"", repr=False)
    _tokens: set[str] = field(default_factory=set, repr=False)
    _counter: int = field(default=0, repr=False)

    def __post_init__(self) -> None:
        if not self._key:
            self._key = hashlib.sha256(f"h5-device-key|{self.device_id}".encode()).digest()

    def load(self, token_id: str) -> None:
        self._tokens.add(token_id)

    def pay(self, token_id: str, merchant_id: str, nonce: str) -> dict | None:
        """Atomically remove the token, bump the monotonic counter, attest. None = refused."""
        if token_id not in self._tokens:
            return None
        self._tokens.discard(token_id)
        self._counter += 1
        return {"device_id": self.device_id, "token_id": token_id, "merchant_id": merchant_id, "nonce": nonce,
                "counter": self._counter,
                "mac": _attest_mac(self._key, self.device_id, token_id, merchant_id, nonce, self._counter)}

    def clone(self) -> SecureElement:
        """Adversarial state extraction. Impossible under H5-TR; succeeds when the assumption is broken."""
        if self.tamper_resistant:
            raise TamperResistanceAssumption(ASSUMPTION_ID)
        return copy.deepcopy(self)

    def device_key_for_registration(self) -> bytes:
        """Issuer-side device registration at manufacture (models the attestation-key certificate)."""
        return self._key


@dataclass
class OfflineHardwareMerchant:
    node_id: str
    site_id: str
    merchant_id: str
    device_keys: dict[str, bytes]  # issuer-registered device keys
    processing_ns: float = 10_000.0
    accepted: list[dict] = field(default_factory=list)
    _issued_nonces: set[str] = field(default_factory=set)
    _n: int = 0

    def handle(self, msg: Message, now_ns: float) -> list[Message]:
        if msg.kind == "Hello":
            self._n += 1
            nonce = hashlib.sha256(f"{self.merchant_id}|{self._n}".encode()).hexdigest()[:32]
            self._issued_nonces.add(nonce)
            return [new_msg("Challenge", self.node_id, msg.src, "h5", nonce=nonce)]
        if msg.kind == "Present":
            att = msg.payload.get("attestation")
            d = self._decide(att)
            if d == Decision.ACCEPT:
                self._issued_nonces.discard(att["nonce"])  # nonce single-use: replay rejected
                self.accepted.append(dict(att))
            return [new_msg("Result", self.node_id, msg.src, "h5", token_id=(att or {}).get("token_id", ""),
                            decision=d.value, decided_at_ns=now_ns + self.processing_ns)]
        raise ValueError(f"unexpected message {msg.kind}")

    def _decide(self, att: dict | None) -> Decision:
        if att is None:
            return Decision.REJECT_DEVICE_REFUSED
        key = self.device_keys.get(att["device_id"])
        if key is None or att["merchant_id"] != self.merchant_id or att["nonce"] not in self._issued_nonces:
            return Decision.REJECT_BAD_AUTH
        good = _attest_mac(key, att["device_id"], att["token_id"], att["merchant_id"], att["nonce"], att["counter"])
        return Decision.ACCEPT if hmac.compare_digest(good, att["mac"]) else Decision.REJECT_BAD_AUTH


def reconcile(accepted: list[dict]) -> dict:
    """Ex-post clearing: duplicate (device, token) or (device, counter) => assumption H5-TR was violated."""
    seen_tok: dict[tuple[str, str], int] = {}
    seen_ctr: dict[tuple[str, int], int] = {}
    for a in accepted:
        seen_tok[(a["device_id"], a["token_id"])] = seen_tok.get((a["device_id"], a["token_id"]), 0) + 1
        seen_ctr[(a["device_id"], a["counter"])] = seen_ctr.get((a["device_id"], a["counter"]), 0) + 1
    dup_tokens = sorted(k for k, v in seen_tok.items() if v > 1)
    dup_counters = sorted(k for k, v in seen_ctr.items() if v > 1)
    violated = bool(dup_tokens or dup_counters)
    return {"double_spends_detected_ex_post": len(dup_tokens), "duplicate_counters": len(dup_counters),
            "classification": "OUT_OF_MODEL" if violated else "IN_MODEL",
            "violated_assumption": ASSUMPTION_ID if violated else None}
