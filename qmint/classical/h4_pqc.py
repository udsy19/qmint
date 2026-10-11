"""H4 -- post-quantum signed bearer authorization (ML-DSA, FIPS 204).

protocol_id: ``classical_h4_pqc_signed`` (game C1).

Signatures use the installed ``dilithium_py`` package (v1.4.0, MIT, G. Pope), a PURE-PYTHON
reference implementation of ML-DSA (FIPS 204). Its README states it is an educational
resource not designed to be secure or fast, so measured keygen/sign/verify times here
are NOT representative of optimized implementations (e.g. liboqs / AVX2); only the
byte sizes are implementation-independent (FIPS 204 Table 2, p.16).

Key point the tests demonstrate: an unforgeable signature lets ANY site check
authenticity offline, but a signed token is still a copyable bit string, so a signature
alone does NOT stop double spending. It must be combined with H1 (online spent ledger,
``SignedTerminal``) or H3 (signed site binding, ``SignedOfflineVerifier(enforce_site_binding=True)``).
"""

from __future__ import annotations

import hashlib
import statistics
import time
from dataclasses import dataclass, field

from dilithium_py.ml_dsa import ML_DSA_44, ML_DSA_65, ML_DSA_87

from qmint.classical.common import Decision, Message, new_msg
from qmint.classical.h1_ledger import MerchantTerminal
from qmint.core.serialization import canonical_json

PROTOCOL_ID = "classical_h4_pqc_signed"
PARAMETER_SETS = {"ML_DSA_44": ML_DSA_44, "ML_DSA_65": ML_DSA_65, "ML_DSA_87": ML_DSA_87}
# FIPS 204 Table 2 (p.16), bytes: (private key, public key, signature).
FIPS204_TABLE2_SIZES = {"ML_DSA_44": (2560, 1312, 2420), "ML_DSA_65": (4032, 1952, 3309),
                        "ML_DSA_87": (4896, 2592, 4627)}
SIG_CONTEXT = b"qmint-h4-token-v1"
IMPLEMENTATION_NOTE = ("dilithium_py 1.4.0 pure-Python reference ML-DSA; timings not representative of "
                       "optimized implementations; byte sizes per FIPS 204 Table 2")


@dataclass(frozen=True)
class SignedToken:
    serial: str
    denomination: int
    bound_site: str | None
    signature_hex: str

    def wire(self) -> dict:
        return {"serial": self.serial, "denomination": self.denomination, "bound_site": self.bound_site,
                "signature_hex": self.signature_hex}


def token_message(serial: str, denomination: int, bound_site: str | None) -> bytes:
    return canonical_json({"serial": serial, "denomination": denomination, "bound_site": bound_site}).encode()


@dataclass
class PQCIssuer:
    parameter_set: str = "ML_DSA_44"
    seed: int = 0
    pk: bytes = field(init=False, repr=False)
    _sk: bytes = field(init=False, repr=False)

    def __post_init__(self) -> None:
        xi = hashlib.sha256(f"h4-keyseed|{self.seed}".encode()).digest()  # deterministic 32-byte seed
        self.pk, self._sk = PARAMETER_SETS[self.parameter_set].key_derive(xi)

    def issue(self, serial: str, denomination: int = 1, bound_site: str | None = None) -> SignedToken:
        sig = PARAMETER_SETS[self.parameter_set].sign(self._sk, token_message(serial, denomination, bound_site),
                                                       ctx=SIG_CONTEXT, deterministic=True)
        return SignedToken(serial, denomination, bound_site, sig.hex())


def verify_token(parameter_set: str, pk: bytes, wire: dict) -> bool:
    msg = token_message(wire["serial"], wire["denomination"], wire["bound_site"])
    return PARAMETER_SETS[parameter_set].verify(pk, msg, bytes.fromhex(wire["signature_hex"]), ctx=SIG_CONTEXT)


@dataclass
class SignedOfflineVerifier:
    """Offline site verifier holding only the issuer public key and a LOCAL spent set.

    ``enforce_site_binding=False``: pure H4 (double spend across sites succeeds).
    ``enforce_site_binding=True``: H4+H3 (token signed for one site; rejected elsewhere).
    """

    node_id: str
    site_id: str
    parameter_set: str
    pk: bytes
    enforce_site_binding: bool = False
    processing_ns: float = 10_000.0
    spent_local: set[str] = field(default_factory=set)

    def handle(self, msg: Message, now_ns: float) -> list[Message]:
        if msg.kind != "Present":
            raise ValueError(f"unexpected message {msg.kind}")
        wire = msg.payload["token"]
        if not verify_token(self.parameter_set, self.pk, wire):
            d = Decision.REJECT_BAD_SIGNATURE
        elif self.enforce_site_binding and wire["bound_site"] != self.site_id:
            d = Decision.REJECT_UNASSIGNED_SITE
        elif wire["serial"] in self.spent_local:
            d = Decision.REJECT_DOUBLE_SPEND
        else:
            self.spent_local.add(wire["serial"])
            d = Decision.ACCEPT
        return [new_msg("Result", self.node_id, msg.src, "h4", token_id=wire["serial"], decision=d.value,
                        decided_at_ns=now_ns + self.processing_ns)]


@dataclass
class SignedTerminal:
    """H4+H1: verify the ML-DSA signature locally, then CAS the serial at the online ledger."""

    inner: MerchantTerminal
    parameter_set: str
    pk: bytes

    @property
    def node_id(self) -> str:
        return self.inner.node_id

    @property
    def site_id(self) -> str:
        return self.inner.site_id

    @property
    def processing_ns(self) -> float:
        return self.inner.processing_ns

    def handle(self, msg: Message, now_ns: float) -> list[Message]:
        if msg.kind == "Present":
            wire = msg.payload["token"]
            if not verify_token(self.parameter_set, self.pk, wire):
                return [new_msg("Result", self.node_id, msg.src, "h4", token_id=wire["serial"],
                                decision=Decision.REJECT_BAD_SIGNATURE.value, decided_at_ns=now_ns)]
            msg = Message("Present", msg.src, msg.dst, {"token_id": wire["serial"]}, msg.msg_id)
        return self.inner.handle(msg, now_ns)

    def on_timeout(self, idem_key: str, now_ns: float) -> list[Message]:
        return self.inner.on_timeout(idem_key, now_ns)


def measure_mldsa(parameter_set: str = "ML_DSA_44", reps: int = 5, seed: int = 0) -> dict:
    """Measure keygen/sign/verify wall time (median, ns) and byte sizes on this machine."""
    scheme = PARAMETER_SETS[parameter_set]
    kg, sg, vf = [], [], []
    pk = sk = sig = b""
    for r in range(reps):
        xi = hashlib.sha256(f"h4-bench|{seed}|{r}".encode()).digest()
        msg = token_message(f"bench-{r}", 1, None)
        t0 = time.perf_counter_ns()
        pk, sk = scheme.key_derive(xi)
        t1 = time.perf_counter_ns()
        sig = scheme.sign(sk, msg, ctx=SIG_CONTEXT, deterministic=True)
        t2 = time.perf_counter_ns()
        ok = scheme.verify(pk, msg, sig, ctx=SIG_CONTEXT)
        t3 = time.perf_counter_ns()
        if not ok:
            raise RuntimeError("ML-DSA self-check failed")
        kg.append(t1 - t0)
        sg.append(t2 - t1)
        vf.append(t3 - t2)
    return {
        "parameter_set": parameter_set,
        "reps": reps,
        "keygen_ns_median": statistics.median(kg),
        "sign_ns_median": statistics.median(sg),
        "verify_ns_median": statistics.median(vf),
        "sk_bytes": len(sk),
        "pk_bytes": len(pk),
        "sig_bytes": len(sig),
        "fips204_table2_sk_pk_sig": list(FIPS204_TABLE2_SIZES[parameter_set]),
        "timing_evidence": "wall-clock perf_counter_ns on this host, pure-Python reference implementation",
        "implementation_note": IMPLEMENTATION_NOTE,
    }
