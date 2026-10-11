"""Two-site quantum token (S-money) schemes of Kent, Lowndes, Pitalua-Garcia & Rarity 2022 (B2).

Source (P03): A. Kent, D. Lowndes, D. Pitalua-Garcia, J. Rarity, "Practical quantum tokens
without quantum memories and experimental tests", npj Quantum Information 8, 28 (2022),
https://doi.org/10.1038/s41534-022-00524-4 . Anchors used here:
  * Table 1  -- ideal schemes IQT1 and IQT2 (steps 1-11 / 1-7); overlines (bit-wise
                complements) read from the HTML table page .../tables/1.
  * Table 2  -- practical scheme QT1 (steps 0-12); Table 3 -- QT2.
  * Table 4  -- notation; "Preliminaries and notation": BB84 states
                |phi_00>=|0>, |phi_10>=|1>, |phi_01>=|+>, |phi_11>=|-> (t = state bit, u = basis),
                D_0 computational, D_1 Hadamard -- identical to the frozen C7 mapping.
  * Definitions of eps_rob / eps_cor / eps_priv / eps_unf (Results, p.3).
This module implements the *schemes* event by event; it evaluates no security bound
(Lemma 1 / Lemmas 2-4 / Theorem 1 belong to lane D; attacks to lane C).

Roles: Bob (bank) agents B (stage-I lab at P), B0, B1 (by presentation points Q0, Q1);
Alice agents A, A0, A1. Same-party agents are trusted and talk over secure authenticated
channels (paper assumption); the module records which agent learns what, and when.

Protocol ids: IQT1/IQT2 -> ``s_money_kent_2022_ideal_2site`` (game S1);
QT1/QT2 -> ``s_money_kent_2022_realistic`` (game S2).

Simulation choices that are NOT from the paper (documented, test-visible):
  * Honest realistic Alice: each pulse is reported detected independently with probability
    ``p_det`` (independent of basis, so assumption D holds) and each detected outcome is
    flipped with probability ``error`` (the paper's E). Multi-photon pulses, dark counts,
    detector efficiency mismatch, preparation biases (beta_PS, beta_PB) and misalignment
    theta (Table 5 items 1-3, 5, 8) are not simulated.
  * Message arrival times are supplied by the caller; if omitted, arrival = send time and
    the event is tagged ``latency: "unmodelled"``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

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
from qmint.protocols.register import FactorizedRegister, RegisterHandle, bb84_projector
from qmint.quantum.bb84 import state_vector

PAPER_URL = "https://doi.org/10.1038/s41534-022-00524-4"

KENT_IDEAL_SPEC = ProtocolSpec(
    protocol_id="s_money_kent_2022_ideal_2site",
    source_paper_id="P03",
    theorem_id="P-S1",
    protocol_revision="published_table_1",
    issuer_trust="honest_bank",
    same_party_agent_trust="trusted",
    redemption_semantics="one_of_two_spacelike_sites",
    quantum_stage="short_range_before_commitment",
    quantum_memory_required=False,
    classical_authentication="pre_shared_authenticated_channels",
    adversary_game_id=GameId.S1,
    security_model_id="s_money_ideal_v1",
)

KENT_REALISTIC_SPEC = ProtocolSpec(
    protocol_id="s_money_kent_2022_realistic",
    source_paper_id="P03",
    theorem_id=None,  # Theorem 1 / Lemmas 2-4 of P03: registry id owned by lane D
    protocol_revision="published_tables_2_3",
    issuer_trust="honest_bank",
    same_party_agent_trust="trusted",
    redemption_semantics="one_of_two_presentation_points",
    quantum_stage="short_range_before_commitment",
    quantum_memory_required=False,
    classical_authentication="pre_shared_authenticated_channels",
    adversary_game_id=GameId.S2,
    security_model_id="s_money_realistic_v1",
    correctness_conditions=[
        "Bob does not abort iff n >= gamma_det*N",
        "accept iff d(x_b, r_b) <= |Delta_b|*gamma_err",
    ],
    proof_assumptions=[f"P03 Table 6 assumption {a}" for a in "ABCDEFG"],
    unsupported_extensions=[
        "2^M presentation points (P03 Supplementary Note VIII) not implemented",
        "photonic multi-photon / dark-count reporting strategies (Fig. 3, Lemma 5) not simulated",
    ],
)


class KentScheme(str, Enum):
    IQT1 = "IQT1"  # Table 1, random basis per qubit
    IQT2 = "IQT2"  # Table 1, one basis z for all qubits
    QT1 = "QT1"  # Table 2
    QT2 = "QT2"  # Table 3

    @property
    def ideal(self) -> bool:
        return self in (KentScheme.IQT1, KentScheme.IQT2)

    @property
    def per_qubit_basis(self) -> bool:  # Alice sends d only in IQT1 / QT1
        return self in (KentScheme.IQT1, KentScheme.QT1)


@dataclass(frozen=True)
class KentParams:
    scheme: KentScheme
    N: int
    gamma_det: float | None = None  # QT only: Bob does not abort iff n >= gamma_det * N
    gamma_err: float | None = None  # QT only: tolerated error fraction on Delta_b

    def __post_init__(self) -> None:
        if self.N < 1:
            raise ValueError("N must be >= 1")
        s = KentScheme(self.scheme)
        if s.ideal and (self.gamma_det is not None or self.gamma_err is not None):
            raise ValueError("ideal schemes (Table 1) have no gamma_det / gamma_err")
        if not s.ideal:
            for name in ("gamma_det", "gamma_err"):
                v = getattr(self, name)
                if v is None or not 0.0 < v < 1.0:
                    raise ValueError(f"{name} must be in (0, 1) for {s.value} (Table 2 step 0)")

    @property
    def protocol_id(self) -> str:
        return (
            KENT_IDEAL_SPEC.protocol_id if KentScheme(self.scheme).ideal else KENT_REALISTIC_SPEC.protocol_id
        )


DEFAULT_SITES: dict[str, str] = {"A": "P", "B": "P", "A0": "Q0", "B0": "Q0", "A1": "Q1", "B1": "Q1"}
BOB_ROLES = ("B", "B0", "B1")
ALICE_ROLES = ("A", "A0", "A1")


class ProtocolOrderError(RuntimeError):
    """A step was attempted out of the published order (or before its inputs exist)."""


def _bits(v: Sequence[int], n: int, name: str) -> tuple[int, ...]:
    out = tuple(int(x) for x in v)
    if len(out) != n or any(x not in (0, 1) for x in out):
        raise ValueError(f"{name} must be a length-{n} bit string")
    return out


@dataclass
class ValidationOutcome:
    site: int
    accepted: bool
    delta_size: int
    errors: int


class KentSMoneySession(SecretHolder):
    """Event-by-event two-site token session; Bob's side is honest and holds the secret.

    Alice-side ingress (callable by honest or dishonest Alice): ``bank_send_quantum``
    returns her quantum register; ``alice_report_detections``, ``alice_send_d``,
    ``alice_send_c`` and ``present`` deliver her classical messages. Bob-side steps
    ``bank_distribute`` and ``bank_forward_c`` are driven by the caller with times.
    """

    def __init__(
        self,
        params: KentParams,
        *,
        seed: int,
        token_id: str = "kent-token-0",
        sites: Mapping[str, str] | None = None,
    ) -> None:
        self.params = params
        self.scheme = KentScheme(params.scheme)
        self.protocol_id = params.protocol_id
        self.token_id = token_id
        self._rng = np.random.default_rng(seed)
        self.sites = {**DEFAULT_SITES, **(sites or {})}
        self.log = EventLog(self.sites)
        self._bob: dict[str, dict[str, Any]] = {r: {} for r in BOB_ROLES}
        self._secret: IssuerSecret | None = None
        self.bob_received: list[tuple[float, str, str, Any]] = []  # (time, Bob role, item, value)
        self.aborted = False
        self.outcomes: dict[int, ValidationOutcome] = {}
        self._reveal_time: float | None = None

    def __repr__(self) -> str:
        return f"KentSMoneySession(scheme={self.scheme.value}, N={self.params.N}, events={len(self.events)})"

    # ------------------------------------------------------------------ events
    @property
    def events(self) -> list[TraceEvent]:
        return self.log.events

    def record_alice_event(self, role: str, kind: str, t: float, **detail: Any) -> str:
        """Alice-internal event (measurement, branch choice...). Not visible to Bob."""
        if role not in ALICE_ROLES:
            raise ValueError("record_alice_event is for Alice's agents")
        return self.log.event(role, kind, t, **detail)

    def _msg(
        self,
        src: str,
        dst: str,
        item: str,
        value: Any,
        t_send: float,
        t_recv: float | None,
        send_kind: str = "message_send",
    ) -> None:
        t_r = self.log.message(src, dst, item, t_send, t_recv, send_kind)
        if dst in BOB_ROLES:
            self._bob[dst][item] = value
            if src in ALICE_ROLES:
                self.bob_received.append((t_r, dst, item, value))

    # --------------------------------------------------------- stage I (quantum)
    def bank_send_quantum(self, t_ns: float, t_recv_ns: float | None = None) -> RegisterHandle:
        """Step 1: B prepares |phi_{t_k u_k}> uniformly from BB84 and sends them, labelled, to A."""
        if self._secret is not None:
            raise ProtocolOrderError("quantum stage already run")
        n = self.params.N
        t = [int(x) for x in self._rng.integers(0, 2, size=n)]
        u = [int(x) for x in self._rng.integers(0, 2, size=n)]
        bases = [Basis.Z if x == 0 else Basis.X for x in u]  # u=0 computational, u=1 Hadamard
        self._secret = IssuerSecret(
            token_id=self.token_id, protocol_id=self.protocol_id, bases=bases, bits=t, extra={"u": u}
        )
        issue = self.log.event("B", "issue", t_ns, scheme=self.scheme.value, N=n)
        reg = FactorizedRegister()
        qs = reg.add_product_state(
            [np.outer(v, v.conj()) for v in (state_vector(b, x) for b, x in zip(bases, t, strict=True))]
        )
        self.log.event("A", "quantum_exchange", t_ns if t_recv_ns is None else t_recv_ns, [issue], N=n)
        record = TokenRecord(
            token_id=self.token_id,
            protocol_id=self.protocol_id,
            n_prepared=n,
            source_state_family="BB84",
            public_metadata={"scheme": self.scheme.value, "paper": PAPER_URL},
            issue_event_id=issue,
            state_kind=StateKind.IDEAL_SIMULATED if self.scheme.ideal else StateKind.NOISY_SIMULATED,
            ownership_context="alice_A",
            backend_provenance="SIMULATOR:qmint.protocols.register.FactorizedRegister",
        )
        return RegisterHandle(reg, qs, record)

    def alice_report_detections(
        self, detected: Sequence[int], t_ns: float, order: Sequence[int] | None = None
    ) -> bool:
        """QT steps 2-3: A reports Lambda and the one-to-one g (given as the label order).

        Bob does not abort iff n = |Lambda| >= gamma_det * N. Returns ``not aborted``.
        """
        if self.scheme.ideal:
            raise ProtocolOrderError("ideal schemes have no loss reporting (Table 1)")
        self._need("B", None, "Lambda")
        lam = sorted(set(int(k) for k in detected))
        if any(not 0 <= k < self.params.N for k in lam) or len(lam) != len(detected):
            raise ValueError("Lambda must be distinct labels in [0, N)")
        g = list(lam) if order is None else [int(k) for k in order]
        if sorted(g) != lam:
            raise ValueError("g must be a one-to-one ordering of Lambda")
        self._msg("A", "B", "Lambda", tuple(lam), t_ns, t_ns)
        self._msg("A", "B", "g", tuple(g), t_ns, t_ns)
        n = len(lam)
        if n < self.params.gamma_det * self.params.N:
            self.aborted = True
            self.log.event("B", "reject", t_ns, reason="abort: n < gamma_det*N", n=n)
        return not self.aborted

    def _n_reported(self) -> int:
        if self.scheme.ideal:
            return self.params.N
        g = self._bob["B"].get("g")
        if g is None:
            raise ProtocolOrderError("Alice has not reported Lambda yet")
        return len(g)

    def _need(self, role: str, have: str | None, absent: str | None = None) -> None:
        if self._secret is None:
            raise ProtocolOrderError("quantum stage not run")
        if self.aborted:
            raise ProtocolOrderError("Bob aborted")
        if have is not None and have not in self._bob[role]:
            raise ProtocolOrderError(f"{role} lacks {have!r}")
        if absent is not None and absent in self._bob[role]:
            raise ProtocolOrderError(f"{role} already has {absent!r}")

    def alice_send_d(self, d: Sequence[int], t_ns: float) -> None:
        """IQT1 step 4 / QT1 step 5: A gives B the string d (= y xor z)."""
        if not self.scheme.per_qubit_basis:
            raise ProtocolOrderError(f"{self.scheme.value} has no d message")
        if not self.scheme.ideal:
            self._n_reported()
        self._need("B", None, "d")
        self._msg("A", "B", "d", _bits(d, self._n_reported(), "d"), t_ns, t_ns)

    def bank_distribute(self, t_ns: float, arrive_ns: Mapping[str, float] | None = None) -> None:
        """B -> B_i over secure channels: d (IQT1/QT1) and t,u (ideal) or r,s (QT step 7)."""
        if self.scheme.per_qubit_basis:
            self._need("B", "d")
        else:
            self._need("B", "g" if not self.scheme.ideal else None)
        assert self._secret is not None
        t, u = list(self._secret.bits), list(self._secret.extra["u"])
        if self.scheme.ideal:
            private = {"t": tuple(t), "u": tuple(u)}
        else:  # Table 2 step 7: r_j = t_k, s_j = u_k with j = g(k)
            g = self._bob["B"]["g"]
            private = {"r": tuple(t[k] for k in g), "s": tuple(u[k] for k in g)}
        for i in (0, 1):
            bi = f"B{i}"
            ta = None if arrive_ns is None else arrive_ns.get(bi)
            for item, val in private.items():
                self._msg("B", bi, item, val, t_ns, ta)
            if self.scheme.per_qubit_basis:
                self._msg("B", bi, "d", self._bob["B"]["d"], t_ns, ta)
                di = tuple(x ^ i for x in self._bob["B"]["d"])  # d_0 = d, d_1 = complement(d)
                self._bob[bi]["d_i"] = di
                self.log.event(bi, "other", self.events[-1].time_ns, action="compute d_i")

    # ----------------------------------------------------------- stage II
    def alice_send_c(self, c: int, t_ns: float) -> None:
        """IQT1 step 7 / QT1 step 8: A sends c = b xor z to B (commits to Q_b)."""
        self._need("B", None, "c")
        if c not in (0, 1):
            raise ValueError("c must be a bit")
        self._msg("A", "B", "c", int(c), t_ns, t_ns, send_kind="commitment")

    def bank_forward_c(self, t_ns: float, arrive_ns: Mapping[str, float] | None = None) -> None:
        """B sends c to B_i; each B_i computes d~_i in the causal past of Q_i."""
        self._need("B", "c")
        c = self._bob["B"]["c"]
        n = self._n_reported()
        for i in (0, 1):
            bi = f"B{i}"
            if not ({"t", "u"} <= self._bob[bi].keys() or {"r", "s"} <= self._bob[bi].keys()):
                raise ProtocolOrderError(f"{bi} has not received Bob's private strings")
            self._msg("B", bi, "c", c, t_ns, None if arrive_ns is None else arrive_ns.get(bi))
            if self.scheme.per_qubit_basis:
                dt = tuple(x ^ c for x in self._bob[bi]["d_i"])
            else:  # IQT2 step 6 / QT2 step 7: d~_{i,k} = i xor c for all k
                dt = (i ^ c,) * n
            self._bob[bi]["dtilde"] = dt
            self.log.event(bi, "other", self.events[-1].time_ns, action="compute dtilde")

    def present(self, i: int, x: Sequence[int], t_ns: float, t_result_ns: float | None = None) -> bool:
        """A_i presents token x to B_i at Q_i; B_i validates locally (instant validation)."""
        bi, ai = f"B{i}", f"A{i}"
        if i not in (0, 1):
            raise ValueError("two presentation points: i in {0, 1}")
        if i in self.outcomes:
            raise ProtocolOrderError(f"a token was already presented at Q{i}")
        self._need(bi, "dtilde")
        n = self._n_reported()
        xb = _bits(x, n, "x")
        self._msg(ai, bi, "x", xb, t_ns, t_ns)
        if self._reveal_time is None:
            self._reveal_time = t_ns
        self.log.event(bi, "privacy_reveal", t_ns, revealed="presentation point b", b=i)
        self.log.event(bi, "local_validation_start", t_ns)
        mem = self._bob[bi]
        ref, basis = (mem["t"], mem["u"]) if self.scheme.ideal else (mem["r"], mem["s"])
        delta = [k for k in range(n) if mem["dtilde"][k] == basis[k]]
        errors = sum(1 for k in delta if xb[k] != ref[k])
        if self.scheme.ideal:  # Table 1 step 11: x_b = t_b exactly
            ok = errors == 0
        else:  # Table 2 step 12: d(x_b, r_b) <= |Delta_b| gamma_err
            ok = errors <= len(delta) * float(self.params.gamma_err)
        tr = t_ns if t_result_ns is None else t_result_ns
        kind = "verification_result_available_local" if ok else "reject"
        self.log.event(bi, kind, tr, accepted=ok, delta_size=len(delta), errors=errors)
        self.outcomes[i] = ValidationOutcome(i, ok, len(delta), errors)
        return ok

    # ------------------------------------------------------------ inspection
    def bob_view_before_reveal(self) -> tuple[tuple[str, str, Any], ...]:
        """Everything Bob's agents received from Alice's side before the first presentation."""
        cut = float("inf") if self._reveal_time is None else self._reveal_time
        return tuple(
            (role, item, val) for (t, role, item, val) in self.bob_received if t < cut and item != "x"
        )

    def double_presentation_accepted(self) -> bool:
        return all(self.outcomes.get(i, ValidationOutcome(i, False, 0, 0)).accepted for i in (0, 1))

    def trace(
        self, trace_id: str, network_id: str, latency_evidence: EvidenceKind = EvidenceKind.SYNTHETIC
    ) -> TransactionTrace:
        return TransactionTrace(
            trace_id=trace_id,
            token_id=self.token_id,
            protocol_id=self.protocol_id,
            network_id=network_id,
            events=list(self.events),
            irrevocability_rule=(
                "P03 instant validation: B_b's local accept at Q_b is final for the token; "
                "bank settlement is outside the paper's scheme"
            ),
            double_spend_accepted=self.double_presentation_accepted(),
            latency_evidence=latency_evidence,
        )


# --------------------------------------------------------------------------- honest Alice
@dataclass(frozen=True)
class HonestChannel:
    """Honest-Alice imperfections simulated for QT1/QT2 (see module docstring)."""

    p_det: float = 1.0
    error: float = 0.0

    def __post_init__(self) -> None:
        if not (0.0 <= self.p_det <= 1.0 and 0.0 <= self.error <= 1.0):
            raise ValueError("p_det and error must be probabilities")


HONEST_STEPS = (
    "quantum",
    "measure",
    "x_to_agents",
    "report",
    "d",
    "bank_distribute",
    "choose",
    "c",
    "bank_forward_c",
    "present",
)


@dataclass
class HonestAlice:
    """Honest Alice following Table 1/2/3. Optional injected randomness for exact tests."""

    session: KentSMoneySession
    seed: int = 0
    channel: HonestChannel = field(default_factory=HonestChannel)
    p_z1: float = 0.5  # P_E(z=1); bias beta_E = |p_z1 - 1/2| (Table 5 item 7)
    y: Sequence[int] | None = None  # injected bases (IQT1: length N; QT1: per label k)
    z: int | None = None
    detected: Sequence[int] | None = None  # injected Lambda (QT)
    x: tuple[int, ...] = field(default=(), init=False)

    def run(
        self, b: int, times: Mapping[str, float], arrivals: Mapping[str, Mapping[str, float]] | None = None
    ) -> bool:
        """Run every step. ``times[step]`` is the send/action time of each ``HONEST_STEPS``
        entry; ``arrivals[step][role]`` optionally gives cross-site arrival times for the
        steps "x_to_agents" (A -> A_i), "bank_distribute" and "bank_forward_c" (B -> B_i)."""
        s, sch, rng = self.session, self.session.scheme, np.random.default_rng(self.seed)
        arr = arrivals or {}
        n_total = s.params.N
        handle = s.bank_send_quantum(times["quantum"])
        z = int(rng.random() < self.p_z1) if self.z is None else int(self.z)
        if sch.per_qubit_basis:
            w = [int(v) for v in (rng.integers(0, 2, size=n_total) if self.y is None else self.y)]
        else:
            w = [z] * n_total  # IQT2 / QT2: every qubit measured in basis D_z
        if sch.ideal:
            det = list(range(n_total))
        elif self.detected is not None:
            det = sorted(int(k) for k in self.detected)
        else:
            det = [k for k in range(n_total) if rng.random() < self.channel.p_det]
        outcomes: dict[int, int] = {}
        for k in range(n_total):
            if k not in det:
                continue
            o = handle.measure(k, bb84_projector(Basis.Z if w[k] == 0 else Basis.X, 0), rng)
            if not sch.ideal and rng.random() < self.channel.error:
                o ^= 1
            outcomes[k] = o
        s.record_alice_event("A", "measurement", times["measure"], n_measured=len(outcomes))
        order = det  # g = numerical ordering (Table 2 step 3 example)
        self.x = tuple(outcomes[k] for k in order)
        y = [w[k] for k in order]
        for i in (0, 1):  # step 3/4: A sends x to A_i over a secure channel (Alice-internal)
            s._msg("A", f"A{i}", "x", self.x, times["x_to_agents"], arr.get("x_to_agents", {}).get(f"A{i}"))
        if not sch.ideal and not s.alice_report_detections(det, times["report"], order):
            return False
        if sch.per_qubit_basis:
            s.alice_send_d([yj ^ z for yj in y], times["d"])
        s.bank_distribute(times["bank_distribute"], arr.get("bank_distribute"))
        s.record_alice_event("A", "branch_choice", times["choose"], b=b)
        s.alice_send_c(b ^ z, times["c"])
        s.bank_forward_c(times["bank_forward_c"], arr.get("bank_forward_c"))
        s.record_alice_event("A", "other", times["present"], action=f"signal A{b} to present")
        return s.present(b, self.x, times["present"])


def monotone_times(start_ns: float = 0.0, step_ns: float = 1000.0) -> dict[str, float]:
    """Strictly increasing schedule for ``HONEST_STEPS`` (SYNTHETIC, for tests/examples)."""
    return {k: start_ns + i * step_ns for i, k in enumerate(HONEST_STEPS)}
