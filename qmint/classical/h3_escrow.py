"""H3 -- preallocated / escrowed site balances (local instant acceptance).

protocol_id: ``classical_h3_preallocated_escrow`` (game C1). Three modes:

``preassigned``
    At issuance the token is escrowed at ONE site chosen up front. That site accepts
    locally with no coordination; every other site rejects (``REJECT_UNASSIGNED_SITE``).
    Cost: lost late-choice flexibility and the issuer learns the spending site at issuance.

``late_commit_disclosed``
    The token is provisioned (inactive) at every site. Before presenting, the user sends
    ``Commit(b)`` to the issuer, who relays ``Activate`` to all sites. Late choice is
    restored, but the issuer learns ``b`` and the commit must reach the site before
    presentation (the same causal requirement S-money's Stage-II bit ``c`` has, Kent et
    al. 2022 Table I steps 7-9, arXiv:2104.11717v4).

``late_commit_ot_private``
    Classical mirror of S-money's IQT1 bit-masking: the issuer draws one random secret per
    site ``r_0..r_{M-1}`` and gives each site the hashes; the user obtains ONE secret ``r_z``
    for a private uniform ``z`` through an IDEAL 1-out-of-M oblivious-transfer functionality
    (``IdealOT``), later sends ``c = (b - z) mod M``; site ``i`` accepts ``x`` iff
    ``H(x) = H(r_{(i - c) mod M})``. The issuer sees only ``c``, which is independent of ``b``
    when ``z`` is uniform and hidden. CAVEAT: ``IdealOT`` is a trusted functionality; any real
    two-party classical OT needs computational assumptions (or trusted setup/hardware), so
    unforgeability is computational, never information-theoretic. OT instantiation is
    NOT_IMPLEMENTED here.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Literal

from qmint.classical.common import Decision, Message, new_msg

PROTOCOL_ID = "classical_h3_preallocated_escrow"
Mode = Literal["preassigned", "late_commit_disclosed", "late_commit_ot_private"]


def _h(x: bytes) -> str:
    return hashlib.sha256(b"h3|" + x).hexdigest()


class IdealOT:
    """Ideal 1-out-of-M OT functionality: receiver learns secrets[z] only; sender learns nothing.

    This is a MODEL (trusted functionality), not a cryptographic implementation.
    By definition the sender (issuer) observes nothing about ``choice``.
    """

    @staticmethod
    def transfer(sender_secrets: list[bytes], choice: int) -> bytes:
        return sender_secrets[choice]


@dataclass
class EscrowIssuer:
    node_id: str
    site_id: str
    site_nodes: dict[str, str]  # site_id -> verifier node id, in a fixed order (index = site number)
    seed: int = 0
    processing_ns: float = 50_000.0
    learned_site: dict[str, str] = field(default_factory=dict)  # privacy ledger: what the issuer learns
    observed_c: dict[str, int] = field(default_factory=dict)
    _ot_secrets: dict[str, list[bytes]] = field(default_factory=dict, repr=False)

    @property
    def order(self) -> list[str]:
        return list(self.site_nodes)

    def issue(self, token_id: str, mode: Mode, assigned_site: str | None = None) -> list[Message]:
        if mode == "preassigned":
            if assigned_site not in self.site_nodes:
                raise ValueError("preassigned mode needs a known assigned_site")
            self.learned_site[token_id] = assigned_site  # issuer learns the spending site at issuance
            return [new_msg("Provision", self.node_id, node, "h3", token_id=token_id, mode=mode,
                            assigned=(sid == assigned_site)) for sid, node in self.site_nodes.items()]
        if mode == "late_commit_disclosed":
            return [new_msg("Provision", self.node_id, node, "h3", token_id=token_id, mode=mode)
                    for node in self.site_nodes.values()]
        if mode == "late_commit_ot_private":
            m = len(self.site_nodes)
            secrets = [hashlib.sha256(f"h3-ot|{self.seed}|{token_id}|{i}".encode()).digest() for i in range(m)]
            self._ot_secrets[token_id] = secrets
            hashes = [_h(s) for s in secrets]
            return [new_msg("Provision", self.node_id, node, "h3", token_id=token_id, mode=mode, hashes=hashes)
                    for node in self.site_nodes.values()]
        raise ValueError(f"unknown mode {mode}")

    def ot_transfer(self, token_id: str, z: int) -> bytes:
        """User side of the ideal OT: returns r_z; the issuer's state is NOT updated with z."""
        return IdealOT.transfer(self._ot_secrets[token_id], z)

    def handle(self, msg: Message, now_ns: float) -> list[Message]:
        tok = msg.payload["token_id"]
        if msg.kind == "Commit":  # late_commit_disclosed
            b = msg.payload["site"]
            self.learned_site[tok] = b
            return [new_msg("Activate", self.node_id, node, "h3", token_id=tok, site=b)
                    for node in self.site_nodes.values()]
        if msg.kind == "CommitC":  # late_commit_ot_private
            c = int(msg.payload["c"])
            self.observed_c[tok] = c
            return [new_msg("RelayC", self.node_id, node, "h3", token_id=tok, c=c)
                    for node in self.site_nodes.values()]
        raise ValueError(f"unexpected message {msg.kind}")


@dataclass
class EscrowSiteVerifier:
    node_id: str
    site_id: str
    site_index: int
    n_sites: int
    processing_ns: float = 10_000.0
    tokens: dict[str, dict] = field(default_factory=dict)
    spent_local: set[str] = field(default_factory=set)

    def handle(self, msg: Message, now_ns: float) -> list[Message]:
        p = msg.payload
        tok = p["token_id"]
        if msg.kind == "Provision":
            self.tokens[tok] = dict(p)
            return []
        if msg.kind == "Activate":
            self.tokens[tok]["active"] = p["site"] == self.site_id
            return []
        if msg.kind == "RelayC":
            self.tokens[tok]["c"] = int(p["c"])
            return []
        if msg.kind == "Present":
            decision = self._decide(tok, p.get("secret_hex"))
            if decision == Decision.ACCEPT:
                self.spent_local.add(tok)
            return [new_msg("Result", self.node_id, msg.src, "h3", token_id=tok, decision=decision.value,
                            decided_at_ns=now_ns + self.processing_ns)]
        raise ValueError(f"unexpected message {msg.kind}")

    def _decide(self, tok: str, secret_hex: str | None) -> Decision:
        st = self.tokens.get(tok)
        if st is None:
            return Decision.REJECT_UNKNOWN_TOKEN
        if tok in self.spent_local:
            return Decision.REJECT_DOUBLE_SPEND
        mode = st["mode"]
        if mode == "preassigned":
            return Decision.ACCEPT if st["assigned"] else Decision.REJECT_UNASSIGNED_SITE
        if mode == "late_commit_disclosed":
            if "active" not in st:
                return Decision.REJECT_NOT_ACTIVATED
            return Decision.ACCEPT if st["active"] else Decision.REJECT_UNASSIGNED_SITE
        if "c" not in st:
            return Decision.REJECT_NOT_ACTIVATED
        expected = st["hashes"][(self.site_index - st["c"]) % self.n_sites]
        if secret_hex is None or _h(bytes.fromhex(secret_hex)) != expected:
            return Decision.REJECT_UNASSIGNED_SITE
        return Decision.ACCEPT


@dataclass
class OTWallet:
    """User wallet for ``late_commit_ot_private``: holds private z and r_z only."""

    token_id: str
    z: int
    r_z: bytes
    n_sites: int

    def commit_value(self, b: int) -> int:
        return (b - self.z) % self.n_sites
