"""Quantum-digital payments of Schiansky et al. 2023 (B3, game D1).

Sources (P04):
  * P. Schiansky et al., "Demonstration of quantum-digital payments", Nat. Commun. 14, 3849
    (2023), https://doi.org/10.1038/s41467-023-39519-w -- main text "Quantum advantage"
    steps 2-5 (modified Fig. 2 flow), Methods ("i.t.-secure MAC", "Optimal cheating strategy").
  * Supplementary Information (MOESM1): Note 2D (i.t.-secure MAC, |T| = |K|/|M| = sqrt|K|),
    Note 3B eqs. (16)-(18) (mishaps M(e,l) = (4+2*sqrt2) e + l), Note 3C eqs. (19)-(23)
    (finite-N honest/dishonest acceptance), Note 4 (lambda = N log2|C|), Table 2.
  * Author Correction (21 Aug 2023), https://doi.org/10.1038/s41467-023-40866-x : only the
    Discussion sentence on unbounded purchases changed (grow C by appending QKD states and
    authenticate with kappa). That extension is NOT implemented here.

Flow (Fig. 2 as modified in "Quantum advantage"):
  0/1. Client and TTP share secret C over a one-time secure channel (account setup).
  2.   TTP draws random b, B (length lambda), prepares |P> (bit b_j in basis B_j), stores
       (b, B) under CID, sends |P> over an untrusted quantum channel.
  3.   Client picks merchant M_i from a pre-shared database, computes m_i = MAC(C, M_i),
       measures |P> in the basis string given by m_i -> cryptogram kappa_i.
  4.   Client -> Merchant: (kappa_i, CID); Merchant -> TTP: {kappa_i, M_i, CID}.
  5.   TTP recomputes m_i and accepts iff (kappa_i)_j = b_j whenever (m_i)_j = B_j (ideal);
       with losses/errors it applies the mishap threshold of SI Note 3C.

Conventions fixed from the paper:
  * Basis-bit mapping from the step-2 example (b, B) = (0101, 0011) -> |+>|->|0>|1>:
    B_j = 0 is the diagonal (+/-) basis and B_j = 1 the rectilinear (0/1) basis. States then
    follow C7: (X,0)=|+>, (X,1)=|->, (Z,0)=|0>, (Z,1)=|1>.
  * One tag bit selects the basis of a sub-token of N states ("the token is split into several
    sub-tokens that are each measured either in H/V or D/A"; lambda = N log2|m|).

Choices NOT fixed by the paper (flagged in the lane-B handoff):
  * MAC construction: the paper allows any strongly-universal family (SI Note 2D, refs 9-10).
    We use tag = a*M xor k over GF(2^ell) with key C = (a, k), which has exactly the paper's
    cardinalities |m| = |M| = sqrt|C| and forging probability 1/|m|.
  * Error/loss estimators and granularity of the threshold test (per sub-token vs whole
    token), and strict "<" from eq. (19)'s complement. See ``ThresholdRule``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from qmint.core.contracts import (
    Basis,
    EvidenceKind,
    GameId,
    IssuerSecret,
    ProtocolSpec,
    StateKind,
    TokenRecord,
    TraceEvent,
    TransactionTrace,
)
from qmint.protocols.common import EventLog, SecretHolder
from qmint.protocols.register import FactorizedRegister, RegisterHandle, bb84_ket, bb84_projector

PAPER_URL = "https://doi.org/10.1038/s41467-023-39519-w"
CORRECTION_URL = "https://doi.org/10.1038/s41467-023-40866-x"

SCHIANSKY_SPEC = ProtocolSpec(
    protocol_id="schiansky_payment_2023",
    source_paper_id="P04",
    theorem_id=None,  # D1 bound (SI Note 3 SDP + Chernoff) is lane D's to register
    protocol_revision="ncomms_2023_v1_with_2023_08_author_correction",
    issuer_trust="honest_bank",
    same_party_agent_trust="not_applicable",
    redemption_semantics="provider_verified_merchant_bound_one_time_cryptogram",
    quantum_stage="ttp_to_client_before_merchant_choice",
    quantum_memory_required=False,
    classical_authentication="one_prior_secure_client_ttp_channel; CH1-CH3 untrusted",
    adversary_game_id=GameId.D1,
    security_model_id="schiansky_d1_v1",
    correctness_conditions=["ideal: kappa_j = b_j wherever m_j = B_j", "noisy: M(e,l) below TTP threshold"],
    proof_assumptions=[
        "honest TTP",
        "i.t.-secure (strongly universal) MAC, key C used once",
        "no coherence between photon-number states (SI Note 3A)",
        "merchant IDs valid and honest (PKI or pre-shared database)",
    ],
    unsupported_extensions=[
        "growing C via appended QKD states (2023 correction) not implemented",
        "n-time-secure MAC reuse not implemented",
    ],
)

# Paper step-2 example: B_j = 0 -> diagonal (+/-), B_j = 1 -> rectilinear (0/1).
BASIS_OF_BIT: dict[int, Basis] = {0: Basis.X, 1: Basis.Z}


# --------------------------------------------------------------------------- MAC
_IRREDUCIBLE = {1: 0b11, 2: 0b111, 4: 0x13, 8: 0x11B, 16: 0x1002B, 32: 0x10000008D, 64: 0x1000000000000001B}


def gf2_mul(a: int, b: int, ell: int) -> int:
    """Multiplication in GF(2^ell) modulo a fixed irreducible polynomial."""
    poly = _IRREDUCIBLE[ell]
    r = 0
    while b:
        if b & 1:
            r ^= a
        b >>= 1
        a <<= 1
        if a >> ell:
            a ^= poly
    return r


@dataclass(frozen=True)
class PolyMac:
    """Strongly-universal one-time MAC tag = a*M xor k over GF(2^ell); key C = (a, k)."""

    ell: int

    def __post_init__(self) -> None:
        if self.ell not in _IRREDUCIBLE:
            raise ValueError(f"ell must be one of {sorted(_IRREDUCIBLE)}")

    def keygen(self, rng: np.random.Generator) -> tuple[int, int]:
        hi = 2**self.ell
        return int(rng.integers(0, hi)), int(rng.integers(0, hi))

    def tag(self, key: tuple[int, int], merchant_id: int) -> int:
        if not 0 <= merchant_id < 2**self.ell:
            raise ValueError("merchant id out of range")
        a, k = key
        return gf2_mul(a, merchant_id, self.ell) ^ k


def basis_bits(tag: int, ell: int, N: int) -> tuple[int, ...]:
    """Tag bits (most significant first), each repeated for its sub-token of N states."""
    return tuple(b for j in range(ell) for b in [(tag >> (ell - 1 - j)) & 1] * N)


# ------------------------------------------------------------------- acceptance
def mishaps(e: float, l_: float) -> float:
    """SI eq. (18): M(e, l) = (4 + 2 sqrt 2) e + l."""
    return (4 + 2 * math.sqrt(2)) * e + l_


def threshold_from_honest(e_h: float, l_h: float, delta_h: float) -> float:
    """TTP tolerance (1 + delta_h) M(e_h, l_h) implied by SI eqs. (19)-(21)."""
    return (1 + delta_h) * mishaps(e_h, l_h)


def allowed_mishaps(p_m: float) -> float:
    """SI eq. (18) right-hand side: asymptotic secure-region edge (1/2)(1 - p_m/2)."""
    return 0.5 * (1 - p_m / 2)


def parameters_admissible(e_h: float, l_h: float, delta_h: float, delta_d: float, p_m: float) -> bool:
    """SI eq. (23): (1/2)(1-p_m/2)(1-delta_d) >= M(e_h,l_h)(1+delta_h). Configuration check
    transcribed from the paper; NOT a security certificate (lane D owns D1 bounds)."""
    return allowed_mishaps(p_m) * (1 - delta_d) >= threshold_from_honest(e_h, l_h, delta_h)


@dataclass(frozen=True)
class IdealRule:
    """Main-text step 5: accept iff kappa_j = b_j whenever m_j = B_j (no loss symbol allowed)."""


@dataclass(frozen=True)
class ThresholdRule:
    """Noise/loss-tolerant TTP test from SI Note 3C (INTERPRETATION, see module docstring).

    For each unit (``per_block``: every sub-token of N states; ``whole``: the full token):
      l_hat = (#declared losses) / (#states in unit)
      e_hat = (#wrong outcomes on non-lost states with m_j = B_j) / (#non-lost states with m_j = B_j)
              (0 if the denominator is 0)
    and accept iff M(e_hat, l_hat) < ``max_mishaps`` in every unit.
    """

    max_mishaps: float
    granularity: Literal["per_block", "whole"] = "per_block"


Cryptogram = tuple[int | None, ...]  # None = declared loss


@dataclass
class VerificationReport:
    accepted: bool
    reason: str
    units: list[dict[str, float]]


def _evaluate(
    kappa: Cryptogram,
    b: Sequence[int],
    B: Sequence[int],
    m: Sequence[int],
    rule: IdealRule | ThresholdRule,
    N: int,
) -> VerificationReport:
    lam = len(b)
    if len(kappa) != lam or any(k not in (0, 1, None) for k in kappa):
        return VerificationReport(False, "malformed cryptogram", [])
    if isinstance(rule, IdealRule):
        if any(k is None for k in kappa):
            return VerificationReport(False, "loss declared under ideal rule", [])
        ok = all(kappa[j] == b[j] for j in range(lam) if m[j] == B[j])
        return VerificationReport(ok, "accepted" if ok else "mismatch on sifted positions", [])
    units = [range(s, s + N) for s in range(0, lam, N)] if rule.granularity == "per_block" else [range(lam)]
    rep = []
    ok = True
    for u in units:
        lost = sum(1 for j in u if kappa[j] is None)
        sift = [j for j in u if kappa[j] is not None and m[j] == B[j]]
        err = sum(1 for j in sift if kappa[j] != b[j])
        e_hat = err / len(sift) if sift else 0.0
        l_hat = lost / len(u)
        mm = mishaps(e_hat, l_hat)
        rep.append({"e_hat": e_hat, "l_hat": l_hat, "mishaps": mm})
        ok &= mm < rule.max_mishaps
    return VerificationReport(ok, "accepted" if ok else "mishaps above TTP threshold", rep)


# --------------------------------------------------------------------- the system
@dataclass(frozen=True)
class ClientDevice:
    """Honest client imperfections (simulation choice): per-state loss and outcome flip."""

    loss: float = 0.0
    error: float = 0.0


PERFECT_DEVICE = ClientDevice()
DEFAULT_SITES = {"TTP": "TTP", "Client": "Client", "Merchant": "Merchant"}


class SchianskyPaymentSystem(SecretHolder):
    """TTP + honest Client(s) + Merchants with C4 events and caller-supplied times.

    Private state: the TTP's per-client keys C and per-token (b, B) are ``IssuerSecret``s; the
    honest client's copy of C lives in a separate client-private ``IssuerSecret``. Public
    ingress mirrors the channels CH1 (quantum, untrusted), CH2, CH3 (classical, untrusted).
    """

    def __init__(
        self,
        *,
        ell: int,
        N: int,
        merchants: Sequence[int],
        rule: IdealRule | ThresholdRule,
        seed: int,
        sites: Mapping[str, str] | None = None,
    ) -> None:
        if N < 1:
            raise ValueError("N must be >= 1")
        self.mac = PolyMac(ell)
        self.ell, self.N, self.lam = ell, N, ell * N
        self.merchant_db = tuple(int(x) for x in merchants)
        self.rule = rule
        self._rng = np.random.default_rng(seed)
        self.sites = {**DEFAULT_SITES, **(sites or {})}
        self._ttp_keys: dict[str, IssuerSecret] = {}
        self._client_keys: dict[str, IssuerSecret] = {}
        self._tokens: dict[str, IssuerSecret] = {}  # token_id -> (b, B) held by the TTP
        self._token_of: dict[str, str] = {}  # CID -> current token id
        self._spent: set[str] = set()
        self.log = EventLog(self.sites)
        self._accepted: dict[str, int] = {}
        self.views: dict[str, list[tuple[str, Any]]] = {"Merchant": [], "TTP": []}

    def __repr__(self) -> str:
        return f"SchianskyPaymentSystem(ell={self.ell}, N={self.N}, clients={len(self._ttp_keys)})"

    @property
    def events(self) -> list[TraceEvent]:
        return self.log.events

    # ----------------------------------------------------------------- steps
    def open_account(self, cid: str, t_ns: float) -> None:
        """Steps 0/1: C generated and shared over the one-time secure channel."""
        if cid in self._ttp_keys:
            raise ValueError("account exists")
        a, k = self.mac.keygen(self._rng)
        for store in (self._ttp_keys, self._client_keys):
            store[cid] = IssuerSecret(
                token_id=f"client-key:{cid}", protocol_id="schiansky_payment_2023", extra={"C": (a, k)}
            )
        setup = self.log.event(
            "TTP", "other", t_ns, action="account setup, C shared over secure channel", cid=cid
        )
        self.log.event("Client", "other", t_ns, [setup], action="store C", cid=cid)

    def issue_token(self, cid: str, t_ns: float, t_recv_ns: float | None = None) -> RegisterHandle:
        """Step 2: TTP prepares |P> from random (b, B) of length lambda; sends over CH1."""
        if cid not in self._ttp_keys:
            raise ValueError("unknown client id")
        b = [int(x) for x in self._rng.integers(0, 2, size=self.lam)]
        B = [int(x) for x in self._rng.integers(0, 2, size=self.lam)]
        token_id = f"qdp-{cid}-{len(self._tokens) + 1:04d}"
        self._tokens[token_id] = IssuerSecret(
            token_id=token_id,
            protocol_id="schiansky_payment_2023",
            bases=[BASIS_OF_BIT[x] for x in B],
            bits=b,
            extra={"B": B},
        )
        self._token_of[cid] = token_id
        issue = self.log.event("TTP", "issue", t_ns, token_id=token_id, lam=self.lam)
        reg = FactorizedRegister()
        qs = reg.add_product_state(
            [np.outer(v, v.conj()) for v in (bb84_ket(BASIS_OF_BIT[x], y) for x, y in zip(B, b, strict=True))]
        )
        t_q = t_ns if t_recv_ns is None else t_recv_ns
        self.log.event("Client", "quantum_exchange", t_q, [issue], channel="CH1 untrusted")
        record = TokenRecord(
            token_id=token_id,
            protocol_id="schiansky_payment_2023",
            n_prepared=self.lam,
            source_state_family="BB84",
            public_metadata={"cid": cid, "ell": self.ell, "N": self.N},
            issue_event_id=issue,
            state_kind=StateKind.IDEAL_SIMULATED,
            ownership_context=f"client:{cid}",
            backend_provenance="SIMULATOR:qmint.protocols.register.FactorizedRegister",
        )
        return RegisterHandle(reg, qs, record)

    def client_pay(
        self,
        cid: str,
        token: RegisterHandle,
        merchant_id: int,
        t_ns: float,
        *,
        device: ClientDevice = PERFECT_DEVICE,
        rng_seed: int = 0,
    ) -> Cryptogram:
        """Step 3 (honest client): choose M_i, m_i = MAC(C, M_i), measure |P> per m_i."""
        if merchant_id not in self.merchant_db:
            raise ValueError("merchant not in the pre-shared database")
        rng = np.random.default_rng(rng_seed)
        key = self._client_keys[cid].extra["C"]
        m = basis_bits(self.mac.tag(key, merchant_id), self.ell, self.N)
        self.log.event("Client", "branch_choice", t_ns, merchant="chosen (private)")
        kappa: list[int | None] = []
        for j in range(token.n_qubits()):
            o = token.measure(j, bb84_projector(BASIS_OF_BIT[m[j]], 0), rng)
            if rng.random() < device.loss:
                kappa.append(None)
            else:
                kappa.append(o ^ int(rng.random() < device.error))
        token.consumed = True
        self.log.event("Client", "measurement", t_ns, n=len(kappa))
        return tuple(kappa)

    def send_to_merchant(
        self, cid: str, kappa: Cryptogram, t_ns: float, t_recv_ns: float | None = None
    ) -> None:
        """Step 4a: Client -> Merchant over CH2: (kappa, CID)."""
        self.log.message("Client", "Merchant", "kappa+CID", t_ns, t_recv_ns)
        self.views["Merchant"].append(("kappa", kappa))
        self.views["Merchant"].append(("cid", cid))

    def merchant_forward(
        self, cid: str, merchant_id: int, kappa: Cryptogram, t_ns: float, t_recv_ns: float | None = None
    ) -> None:
        """Step 4b: Merchant -> TTP over CH3: {kappa, M_i, CID}."""
        self.log.message("Merchant", "TTP", "kappa+M+CID", t_ns, t_recv_ns)
        self.views["TTP"].append(("request", (cid, merchant_id)))

    def check(self, cid: str, merchant_id: int, kappa: Cryptogram) -> VerificationReport:
        """Stateless step-5 test against the client's current token (game semantics, D1)."""
        tid = self._token_of.get(cid)
        if tid is None:
            return VerificationReport(False, "no token issued", [])
        sec = self._tokens[tid]
        m = basis_bits(self.mac.tag(self._ttp_keys[cid].extra["C"], merchant_id), self.ell, self.N)
        return _evaluate(kappa, sec.bits, sec.extra["B"], m, self.rule, self.N)

    def ttp_verify(
        self, cid: str, merchant_id: int, kappa: Cryptogram, t_ns: float, t_result_ns: float | None = None
    ) -> VerificationReport:
        """Step 5 with the payment ledger: one accepted payment per token (one-time cryptogram)."""
        self.log.event("TTP", "local_validation_start", t_ns)
        tid = self._token_of.get(cid)
        if tid is not None and tid in self._spent:
            rep = VerificationReport(False, "token already spent", [])
        else:
            rep = self.check(cid, merchant_id, kappa)
        tr = t_ns if t_result_ns is None else t_result_ns
        if rep.accepted:
            assert tid is not None
            self._spent.add(tid)
            self._accepted[tid] = self._accepted.get(tid, 0) + 1
            self.log.event("TTP", "verification_result_available_local", tr, accepted=True)
            self.log.event("TTP", "issuer_aware_of_spend", tr)
            self.log.event("TTP", "bank_settlement_final", tr)
        else:
            self.log.event("TTP", "reject", tr, reason=rep.reason)
        return rep

    def honest_payment(
        self,
        cid: str,
        merchant_id: int,
        times: Mapping[str, float],
        *,
        device: ClientDevice = PERFECT_DEVICE,
        rng_seed: int = 0,
    ) -> VerificationReport:
        """Steps 2-5 for an already-opened account. ``times`` keys: issue, pay, to_merchant,
        forward, verify (plus optional *_recv arrival times)."""
        h = self.issue_token(cid, times["issue"], times.get("issue_recv"))
        kappa = self.client_pay(cid, h, merchant_id, times["pay"], device=device, rng_seed=rng_seed)
        self.send_to_merchant(cid, kappa, times["to_merchant"], times.get("to_merchant_recv"))
        self.merchant_forward(cid, merchant_id, kappa, times["forward"], times.get("forward_recv"))
        return self.ttp_verify(cid, merchant_id, kappa, times["verify"], times.get("verify_result"))

    def client_key_TEST_ONLY(self, cid: str) -> tuple[int, int]:
        """The client's own key C. A *malicious client* legitimately holds it (game D1);
        handing it to any other party is OUT_OF_MODEL."""
        return tuple(self._client_keys[cid].reveal_for_testing_only()["extra"]["C"])  # type: ignore[return-value]

    def trace(
        self,
        trace_id: str,
        network_id: str,
        token_id: str,
        latency_evidence: EvidenceKind = EvidenceKind.SYNTHETIC,
    ) -> TransactionTrace:
        return TransactionTrace(
            trace_id=trace_id,
            token_id=token_id,
            protocol_id="schiansky_payment_2023",
            network_id=network_id,
            events=list(self.events),
            irrevocability_rule="payment final when the TTP accepts the merchant-bound cryptogram (Fig. 1 caption)",
            double_spend_accepted=self._accepted.get(token_id, 0) > 1,
            latency_evidence=latency_evidence,
        )
