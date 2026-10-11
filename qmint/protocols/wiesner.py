"""Ideal private-key Wiesner money (B1) and its noisy/threshold variant.

Source: S. Wiesner, "Conjugate coding" (SIGACT News 15, 1983); game W1 and the
``(3/4)^n`` simple-counterfeiting optimum are from Molina, Vidick & Watrous 2012
(arXiv:1202.4010, P01). This module implements the *scheme* and the W1 challenger
boundary; it computes no security bound (lane D owns bounds, lane C owns attacks).

Information boundary (C1):
  * ``WiesnerChallenger`` (the bank) privately holds one ``IssuerSecret`` per note.
  * The wallet / adversary receives a ``RegisterHandle``: a public ``TokenRecord``
    (serial only) plus a capability to the simulated qubits. No bases/bits ever leave
    the challenger except through the explicit ``leak_secret_TEST_ONLY`` control.

Protocol ids:
  * ``wiesner_ideal`` (games W1/W1_CV): exact projective verifier, accept iff every qubit
    measured in its secret basis gives its secret bit.
  * ``wiesner_noisy`` (game W2): an honest per-qubit noise channel acts on every presented
    qubit inside the verifier, which accepts iff the number of wrong outcomes is
    ``<= threshold``. No closed-form adversarial bound is assumed for W2.

Modes:
  * ``EXACT``    density-matrix register; ``verify`` samples from the exact outcome law and
                 ``acceptance_probability`` / ``pair_acceptance_probability`` are exact.
  * ``SHOTS``    same register, but verification is sequential projective measurement with
                 collapse and no exact-probability oracle (hardware-like).
  * ``SYMBOLIC`` no quantum state; honest notes only, acceptance from closed forms.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Literal

import numpy as np
from scipy.stats import binom, binomtest

from qmint.core.contracts import (
    AttackResult,
    Basis,
    EvidenceKind,
    GameId,
    Interval,
    IssuerSecret,
    ProtocolSpec,
    StateKind,
    TokenRecord,
    Unit,
)
from qmint.protocols.common import SecretHolder
from qmint.protocols.register import (
    ConsumedTokenError,
    FactorizedRegister,
    RegisterHandle,
    bb84_projector,
)
from qmint.quantum.bb84 import state_vector

WIESNER_IDEAL_SPEC = ProtocolSpec(
    protocol_id="wiesner_ideal",
    source_paper_id="P01",
    theorem_id="P-W1",
    protocol_revision="mvw2012_simple_counterfeiting",
    issuer_trust="honest_bank",
    same_party_agent_trust="not_applicable",
    redemption_semantics="single_verifier_bank",
    quantum_stage="note_is_quantum_state",
    quantum_memory_required=True,
    classical_authentication="not_applicable",
    adversary_game_id=GameId.W1,
    security_model_id="wiesner_ideal_exact_verifier_v1",
    proof_assumptions=["iid_uniform_bb84", "exact_projective_verifier", "no_verification_oracle"],
)

WIESNER_NOISY_SPEC = ProtocolSpec(
    protocol_id="wiesner_noisy",
    source_paper_id="P01",
    theorem_id=None,  # W2: no published closed form assumed (master plan 3.1)
    protocol_revision="qmint_threshold_verifier_v1",
    issuer_trust="honest_bank",
    same_party_agent_trust="not_applicable",
    redemption_semantics="single_verifier_bank",
    quantum_stage="note_is_quantum_state",
    quantum_memory_required=True,
    classical_authentication="not_applicable",
    adversary_game_id=GameId.W2,
    security_model_id="wiesner_noisy_threshold_v1",
    correctness_conditions=["honest acceptance = binomial survival under the declared iid channel"],
    unsupported_extensions=["(3/4)^n does NOT transfer to W2", "loss/reporting not modelled"],
)


class WiesnerMode(str, Enum):
    EXACT = "exact"
    SHOTS = "shots"
    SYMBOLIC = "symbolic"


class SerialCollisionError(RuntimeError):
    """The bank would issue a duplicate serial number."""


@dataclass(frozen=True)
class NoiseModel:
    """Honest iid per-qubit channel applied by the verifier to each presented qubit."""

    kind: Literal["depolarizing", "bit_flip"]
    p: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.p <= 1.0:
            raise ValueError("noise probability must be in [0, 1]")

    def kraus(self) -> list[np.ndarray]:
        i2 = np.eye(2, dtype=complex)
        x = np.array([[0, 1], [1, 0]], dtype=complex)
        if self.kind == "bit_flip":  # rho -> (1-p) rho + p X rho X
            return [np.sqrt(1 - self.p) * i2, np.sqrt(self.p) * x]
        # depolarizing: rho -> (1-p) rho + p I/2  ==  (1-3p/4) rho + p/4 (X.X + Y.Y + Z.Z)
        y = np.array([[0, -1j], [1j, 0]], dtype=complex)
        z = np.diag([1, -1]).astype(complex)
        return [np.sqrt(1 - 3 * self.p / 4) * i2] + [np.sqrt(self.p / 4) * m for m in (x, y, z)]

    def error_probability(self, basis: Basis) -> float:
        """Per-qubit honest error probability for a BB84 state of the given basis."""
        if self.kind == "depolarizing":
            return self.p / 2
        return self.p if Basis(basis) == Basis.Z else 0.0  # X eigenstates are invariant under X


def honest_acceptance_probability(n_errorprone: int, e: float, threshold: int) -> float:
    """Binomial survival ``sum_{k<=t} C(m,k) e^k (1-e)^(m-k)`` (master plan 3.4)."""
    return float(binom.cdf(threshold, n_errorprone, e))


def _default_serial(rng: np.random.Generator) -> str:
    return f"SN-{int(rng.integers(0, 2**63)):016x}"


@dataclass
class RedemptionResult:
    accepted: bool
    reason: Literal["accepted", "rejected", "replay", "unknown_serial"]
    reminted: RegisterHandle | None = None


class WiesnerChallenger(SecretHolder):
    """The bank / W1-W2 challenger. Sole holder of ``IssuerSecret`` objects."""

    def __init__(
        self,
        *,
        mode: WiesnerMode = WiesnerMode.EXACT,
        noise: NoiseModel | None = None,
        threshold: int | None = None,
        seed: int = 0,
        serial_factory: Callable[[np.random.Generator], str] = _default_serial,
        ownership_context: str = "wallet",
        remint: bool = True,
        max_serial_attempts: int = 8,
    ) -> None:
        if noise is not None and threshold is None:
            raise ValueError("a noisy verifier needs an explicit error threshold (game W2)")
        self.mode = WiesnerMode(mode)
        self.noise = noise
        self.threshold = 0 if threshold is None else int(threshold)
        if self.threshold < 0:
            raise ValueError("threshold must be >= 0")
        self.protocol_id = "wiesner_ideal" if (noise is None and self.threshold == 0) else "wiesner_noisy"
        self.spec = WIESNER_IDEAL_SPEC if self.protocol_id == "wiesner_ideal" else WIESNER_NOISY_SPEC
        self._rng = np.random.default_rng(seed)
        self._serial_factory = serial_factory
        self._max_serial_attempts = max_serial_attempts
        self._ownership = ownership_context
        self._remint = remint
        self._secrets: dict[str, IssuerSecret] = {}  # token_id -> secret (bank-private)
        self._ledger: dict[str, Literal["fresh", "spent"]] = {}  # serial -> status
        self._issue_counter = 0

    def __repr__(self) -> str:
        return f"WiesnerChallenger(protocol_id={self.protocol_id!r}, mode={self.mode.value}, notes={len(self._secrets)})"

    # ------------------------------------------------------------------ minting
    def mint(self, n: int, rng_seed: int) -> RegisterHandle:
        """Mint an n-qubit note: iid uniform BB84 (basis, bit) per qubit, fresh serial."""
        if n < 1:
            raise ValueError("n must be >= 1")
        rng = np.random.default_rng(rng_seed)
        bases = [Basis.Z if b == 0 else Basis.X for b in rng.integers(0, 2, size=n)]
        bits = [int(b) for b in rng.integers(0, 2, size=n)]
        serial = self._new_serial(rng)
        token_id = f"wiesner-{serial}"
        self._secrets[token_id] = IssuerSecret(
            token_id=token_id, protocol_id=self.protocol_id, bases=bases, bits=bits
        )
        self._ledger[serial] = "fresh"
        self._issue_counter += 1
        state_kind = {
            WiesnerMode.SYMBOLIC: StateKind.SYMBOLIC_RECORD,
        }.get(self.mode, StateKind.NOISY_SIMULATED if self.noise else StateKind.IDEAL_SIMULATED)
        record = TokenRecord(
            token_id=token_id,
            protocol_id=self.protocol_id,
            n_prepared=n,
            source_state_family="BB84",
            public_metadata={"serial": serial},
            issue_event_id=f"ev-issue-{self._issue_counter:06d}",
            state_kind=state_kind,
            ownership_context=self._ownership,
            backend_provenance=f"SIMULATOR:qmint.protocols.register.FactorizedRegister:{self.mode.value}",
        )
        if self.mode == WiesnerMode.SYMBOLIC:
            return RegisterHandle(None, [], record)
        reg = FactorizedRegister()
        qs = reg.add_product_state(
            [np.outer(v, v.conj()) for v in (state_vector(b, x) for b, x in zip(bases, bits, strict=True))]
        )
        return RegisterHandle(reg, qs, record)

    def _new_serial(self, rng: np.random.Generator) -> str:
        for _ in range(self._max_serial_attempts):
            s = self._serial_factory(rng)
            if s not in self._ledger:
                return s
        raise SerialCollisionError("could not draw an unused serial number")

    # ------------------------------------------------------------- verification
    def _secret_for(self, candidate: RegisterHandle) -> IssuerSecret | None:
        sec = self._secrets.get(candidate.record.token_id)
        if sec is None or candidate.n_qubits() != len(sec.bits):
            return None
        return sec

    def _groups(self, regs_qs: list[tuple[FactorizedRegister, list[int]]], secrets: list[IssuerSecret]):
        return [
            [(q, bb84_projector(b, x)) for q, b, x in zip(qs, s.bases, s.bits, strict=True)]
            for (_, qs), s in zip(regs_qs, secrets, strict=True)
        ]

    def _apply_noise(self, reg: FactorizedRegister, qs: list[int]) -> list[int]:
        if self.noise is None:
            return qs
        k = self.noise.kraus()
        return [reg.apply_channel([q], k, 1)[0] for q in qs]

    def _exact_count_distribution(
        self, cands: list[RegisterHandle], secrets: list[IssuerSecret]
    ) -> np.ndarray:
        pairs = [c._peek() for c in cands]
        regs = {id(r) for r, _ in pairs}
        if len(regs) != 1:
            # independent registers: product of marginals is exact
            dists = [self._exact_count_distribution([c], [s]) for c, s in zip(cands, secrets, strict=True)]
            out = dists[0]
            for d in dists[1:]:
                out = np.multiply.outer(out, d)
            return out
        # analysis copy only when noise must be applied: simulator artefact, not cloning
        reg = copy.deepcopy(pairs[0][0]) if self.noise else pairs[0][0]
        noisy = [(reg, self._apply_noise(reg, qs)) for _, qs in pairs]
        return reg.count_distribution(self._groups(noisy, secrets))

    def _symbolic_accept_prob(self, sec: IssuerSecret) -> float:
        if self.noise is None:
            return 1.0
        if self.noise.kind == "depolarizing":
            return honest_acceptance_probability(len(sec.bits), self.noise.p / 2, self.threshold)
        n_z = sum(1 for b in sec.bases if b == Basis.Z)
        return honest_acceptance_probability(n_z, self.noise.p, self.threshold)

    def acceptance_probability(self, candidate: RegisterHandle) -> float:
        """Exact acceptance probability of one candidate (analysis oracle; not consuming).

        Available in EXACT and SYMBOLIC modes only. Never handed to an adversary.
        """
        sec = self._secret_for(candidate)
        if sec is None:
            return 0.0
        if self.mode == WiesnerMode.SHOTS:
            raise RuntimeError("SHOTS mode has no exact-probability oracle")
        if self.mode == WiesnerMode.SYMBOLIC:
            if candidate.consumed:
                raise ConsumedTokenError("token already consumed")
            return self._symbolic_accept_prob(sec)
        d = self._exact_count_distribution([candidate], [sec])
        return float(min(1.0, d[: self.threshold + 1].sum()))

    def pair_acceptance_probability(self, c1: RegisterHandle, c2: RegisterHandle) -> float:
        """Exact Pr[both candidates accepted] (W1/W2 success event). EXACT mode only."""
        if self.mode != WiesnerMode.EXACT:
            raise RuntimeError("pair probabilities need EXACT mode")
        s1, s2 = self._secret_for(c1), self._secret_for(c2)
        if s1 is None or s2 is None:
            return 0.0
        d = self._exact_count_distribution([c1, c2], [s1, s2])
        t = self.threshold + 1
        return float(min(1.0, d[:t, :t].sum()))

    def verify(self, candidate: RegisterHandle) -> bool:
        """Challenger verification of one candidate (consumes its quantum state)."""
        return self.verify_many([candidate])[0]

    def verify_pair(self, c1: RegisterHandle, c2: RegisterHandle) -> tuple[bool, bool]:
        """W1/W2: verify both candidates independently against the same hidden secret."""
        a, b = self.verify_many([c1, c2])
        return a, b

    def verify_many(self, cands: list[RegisterHandle]) -> list[bool]:
        secrets = [self._secret_for(c) for c in cands]
        out = [False] * len(cands)
        live = [i for i, s in enumerate(secrets) if s is not None]
        if self.mode == WiesnerMode.SYMBOLIC:
            for i in live:
                if cands[i].consumed:
                    raise ConsumedTokenError("token already consumed")
                cands[i].consumed = True
                out[i] = bool(self._rng.random() < self._symbolic_accept_prob(secrets[i]))
            return out
        if not live:
            return out
        if self.mode == WiesnerMode.EXACT:
            d = self._exact_count_distribution([cands[i] for i in live], [secrets[i] for i in live])
            flat = d.ravel() / d.sum()
            idx = np.unravel_index(self._rng.choice(flat.size, p=flat), d.shape)
            for i, c in zip(live, idx, strict=True):
                cands[i]._take()
                out[i] = int(c) <= self.threshold
            return out
        # SHOTS: sequential projective measurement with collapse
        for i in live:
            reg, qs = cands[i]._take()
            qs = self._apply_noise(reg, qs)
            sec = secrets[i]
            errors = sum(
                reg.measure(q, bb84_projector(b, x), self._rng)
                for q, b, x in zip(qs, sec.bases, sec.bits, strict=True)
            )
            out[i] = errors <= self.threshold
        return out

    # ---------------------------------------------------------------- lifecycle
    def redeem(self, handle: RegisterHandle, remint_seed: int | None = None) -> RedemptionResult:
        """Spend-once redemption at the bank.

        Replay rule: a serial already presented (accepted *or* rejected) is rejected without
        touching the presented state. A first presentation is verified (consuming the
        state) and the serial is marked spent either way. On acceptance the bank optionally
        remints a fresh note of the same size with a new serial.
        """
        serial = str(handle.record.public_metadata.get("serial"))
        status = self._ledger.get(serial)
        if status is None:
            return RedemptionResult(False, "unknown_serial")
        if status == "spent":
            return RedemptionResult(False, "replay")
        ok = self.verify(handle)
        self._ledger[serial] = "spent"
        handle.record.freshness = "spent"
        if not ok:
            return RedemptionResult(False, "rejected")
        new = None
        if self._remint:
            seed = int(self._rng.integers(0, 2**63)) if remint_seed is None else remint_seed
            new = self.mint(handle.record.n_prepared, seed)
            new.record.freshness = "verified_reminted"
        return RedemptionResult(True, "accepted", new)

    def serial_status(self, serial: str) -> str | None:
        return self._ledger.get(serial)

    # --------------------------------------------------------- TEST_ONLY control
    def leak_secret_TEST_ONLY(self, handle: RegisterHandle) -> dict:
        """Deliberately UNSAFE negative control: reveals the note's secret.

        Any attack using this output is OUT_OF_MODEL for every Wiesner game.
        """
        return self._secrets[handle.record.token_id].reveal_for_testing_only()


def forge_from_leaked_secret(leaked: dict, record: TokenRecord) -> tuple[RegisterHandle, RegisterHandle]:
    """Trivial forger given a leaked secret: prepares two fresh, perfect notes."""
    if not leaked.get("TEST_ONLY"):
        raise ValueError("refusing: input is not a TEST_ONLY revelation")
    out = []
    for j in range(2):
        reg = FactorizedRegister()
        kets = [state_vector(Basis(b), x) for b, x in zip(leaked["bases"], leaked["bits"], strict=True)]
        qs = reg.add_product_state([np.outer(v, v.conj()) for v in kets])
        out.append(RegisterHandle(reg, qs, record.model_copy(update={"ownership_context": f"forgery_{j}"})))
    return out[0], out[1]


def unsafe_secret_leak_control(
    n: int, trials: int, seed: int, source_code_sha: str = "unrecorded"
) -> AttackResult:
    """Negative control: with the secret leaked, a trivial forger wins W1 every time.

    Classified OUT_OF_MODEL: the W1 theorem assumes the adversary never sees the secret.
    """
    ch = WiesnerChallenger(mode=WiesnerMode.EXACT, seed=seed)
    wins = 0
    for i in range(trials):
        note = ch.mint(n, seed + i)
        f1, f2 = forge_from_leaked_secret(ch.leak_secret_TEST_ONLY(note), note.record)
        a, b = ch.verify_pair(f1, f2)
        wins += int(a and b)
    ci = binomtest(wins, trials).proportion_ci(confidence_level=0.95, method="exact")
    return AttackResult(
        attack_id="B_TEST_ONLY_secret_leak_forger",
        game_id=GameId.W1,
        attack_capability=["TEST_ONLY_secret_revelation", "prepare_bb84_states"],
        token_n=n,
        attack_method="prepare two copies from leaked (bases, bits)",
        quantum_channel_description="none: fresh preparation from classical description",
        verifier_rule="exact projective, both candidates verified against hidden secret",
        seed=seed,
        trials=trials,
        successes=wins,
        success_rate_ci=Interval(lo=ci.low, hi=ci.high, unit=Unit.PROBABILITY, point=wins / trials),
        ci_method="clopper_pearson_95",
        proof_applicability="OUT_OF_MODEL",
        theorem_upper_bound=None,
        backend_kind="qmint.protocols.register.FactorizedRegister",
        evidence_kind=EvidenceKind.MONTE_CARLO,
        source_code_sha=source_code_sha,
    )
