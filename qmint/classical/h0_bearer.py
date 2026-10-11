"""H0 -- copyable bearer string with independent offline verifiers (NEGATIVE CONTROL).

protocol_id: ``classical_h0_bearer`` (game C1).

The issuer mints a random 32-byte serial and pre-distributes the list of valid
serials to every site. Each site verifier keeps only a LOCAL spent set and never
talks to other sites. A copied serial presented at two sites is accepted twice:
this is the expected double-spend failure. H0 is not the strongest classical
baseline and can never support a general quantum-advantage claim.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from qmint.classical.common import Decision, Message, new_msg

PROTOCOL_ID = "classical_h0_bearer"


def mint_serial(seed: int, index: int) -> str:
    """Deterministic 32-byte serial (hex) for reproducible runs; not a secret in H0's model."""
    return hashlib.sha256(f"h0|{seed}|{index}".encode()).hexdigest()


@dataclass
class BearerVerifier:
    """Offline site verifier: valid-serial list + LOCAL spent set only."""

    node_id: str
    site_id: str
    valid_serials: frozenset[str]
    processing_ns: float = 10_000.0
    spent_local: set[str] = field(default_factory=set)

    def handle(self, msg: Message, now_ns: float) -> list[Message]:
        if msg.kind != "Present":
            raise ValueError(f"unexpected message {msg.kind}")
        serial = msg.payload["serial"]
        if serial not in self.valid_serials:
            decision = Decision.REJECT_UNKNOWN_TOKEN
        elif serial in self.spent_local:
            decision = Decision.REJECT_DOUBLE_SPEND  # same-site replay is caught locally
        else:
            self.spent_local.add(serial)
            decision = Decision.ACCEPT
        return [new_msg("Result", self.node_id, msg.src, "h0", serial=serial, decision=decision.value,
                        decided_at_ns=now_ns + self.processing_ns)]
