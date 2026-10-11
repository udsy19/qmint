"""POST /lab/mint and /lab/attack -- the quantum lab, over the merged research lanes.

Lanes used (all real code paths, status ``OK``):

* lane B ``qmint.protocols.wiesner`` -- the bank. ``WiesnerChallenger`` mints a note, keeps the
  ``IssuerSecret`` and hands the wallet a ``RegisterHandle`` whose public ``TokenRecord`` carries
  the serial only. Verification, spend-once redemption and replay refusal are the bank's.
* lane F ``qmint.quantum`` -- channels (Kraus), prepare/verify circuits, local Aer sampling,
  closed-form per-qubit acceptance (an independent cross-check of the bank's exact value).
* lane C ``qmint.attacks`` -- per-qubit attack channels, exact per-position joint pass
  probabilities, Monte Carlo runners for the toy W2 / leaky-oracle games, the Choi SDP and its
  exact-rational dual certification.
* lane D ``qmint.proofs`` -- the published W1 / W1_CV theorem values (log space, game-guarded),
  the registry anchors, and the independent exact re-verification of the SDP dual.

Information boundary. The issuer secret never leaves the server in a normal response: no bases,
bits, state labels, outcome strings, circuit gates, QASM, gate counts or circuit hashes (a hash of
a <= 8-qubit secret circuit is brute-forceable). The ONLY exception is the explicit
``teaching_reveal=true`` request flag on /lab/mint, which adds one ``teaching`` block produced by
the bank's ``leak_secret_TEST_ONLY`` control and labelled ``TEST_ONLY_TEACHING_REVEAL`` /
``OUT_OF_MODEL``: anything done with it is outside every Wiesner security game.

Evidence discipline. Exact model values use ``method="exact_enumeration"`` / ``"closed_form"``;
fresh-note Monte Carlo uses ``method="monte_carlo"`` with a Clopper-Pearson interval; every
attack success value is the success of ONE attack and therefore only a LOWER bound on the
worst-case counterfeiter. The only upper bounds shown are the published theorem (W1 only) and
the SDP dual certificates (W1, n <= 2). Hardware (QPU) is never run: submission is disabled.

Limits. n <= 8 qubits, shots <= 20 000, trials <= 5 000 (A08 <= 400: each trial makes ~10n oracle
queries). Each request has a 20 s compute deadline; exceeding it returns HTTP 504 with
``error.code = "timeout"``. All quantum work runs on ONE worker thread (see ``_QUANTUM_THREAD``).
"""

from __future__ import annotations

import asyncio
import math
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal, TypeVar

import numpy as np
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from scipy.stats import binom

from qmint.attacks import heuristic
from qmint.attacks.certify import certify_w1_dual, exact_choi_value_of_mvw_channel
from qmint.attacks.coherent_sdp import solve_w1
from qmint.attacks.records import attacks_source_sha
from qmint.attacks.stats import clopper_pearson_interval
from qmint.core.contracts import AttackResult, Basis, EvidenceKind, GameId, Interval, TokenRecord, Unit
from qmint.proofs import sdp_exact
from qmint.proofs.ideal_bounds import log10_bound
from qmint.proofs.registry import default_registry
from qmint.protocols.wiesner import WiesnerChallenger, WiesnerMode, unsafe_secret_leak_control
from qmint.quantum import bb84, circuits
from qmint.quantum.channels import NoiseSpec, analytic_correct_probability
from qmint.quantum.records import circuit_fingerprint, resource_counts

from ..common import git_sha, provenance
from ..schemas import ERROR_RESPONSES, ApiError, ApiErrorBody, ConfidenceInterval, Envelope, Method, Quantity

T = TypeVar("T")
R = TypeVar("R")

MAX_N = bb84.MAX_STATEVECTOR_QUBITS
MAX_SHOTS = 20_000
MAX_TRIALS = 5_000
MAX_TRIALS_A08 = 400
MAX_SDP_N = 2
REQUEST_DEADLINE_S = 20.0
QUEUE_GRACE_S = 25.0  # extra wall time allowed while waiting for the single quantum worker
CONFIDENCE = 0.95
CI_METHOD = "clopper_pearson_0.95"
TOP_K = 32
LOWER_BOUND_NOTE = "success of ONE specific attack: a LOWER bound on worst-case counterfeiting, never an upper bound"
C_EVIDENCE = "handoffs/C-C1-evidence.json"

router = APIRouter(
    prefix="/lab",
    tags=["lab"],
    responses={**ERROR_RESPONSES, 504: {"model": ApiError, "description": "Compute deadline exceeded"}},
)

# Qiskit circuit objects segfault when consecutive requests build them on different threadpool threads
# (observed with qiskit 2.5 under FastAPI's sync-endpoint threadpool). All quantum work therefore runs
# serialised on ONE dedicated worker thread.
_QUANTUM_THREAD = ThreadPoolExecutor(max_workers=1, thread_name_prefix="qmint-quantum")


class LabTimeout(RuntimeError):
    """The cooperative compute deadline of one lab request expired."""


@dataclass
class Deadline:
    seconds: float
    start: float = 0.0

    def __post_init__(self) -> None:
        self.start = time.perf_counter()

    def check(self) -> None:
        if time.perf_counter() - self.start > self.seconds:
            raise LabTimeout(f"compute deadline of {self.seconds:g} s exceeded")

    def elapsed_ms(self) -> float:
        return round((time.perf_counter() - self.start) * 1000.0, 1)


def _timeout_response(message: str) -> JSONResponse:
    body = ApiError(error=ApiErrorBody(code="timeout", message=message))
    return JSONResponse(status_code=504, content=body.model_dump())


async def _bounded(fn: Callable[[T, Deadline], R], req: T) -> R | JSONResponse:
    loop = asyncio.get_running_loop()

    def work() -> R:
        return fn(req, Deadline(REQUEST_DEADLINE_S))

    try:
        return await asyncio.wait_for(loop.run_in_executor(_QUANTUM_THREAD, work), REQUEST_DEADLINE_S + QUEUE_GRACE_S)
    except LabTimeout as e:
        return _timeout_response(f"{e}; reduce n, shots or trials")
    except TimeoutError:
        return _timeout_response("the quantum worker is busy; request waited too long in the queue")


# --------------------------------------------------------------------------- #
# Shared request / response building blocks
# --------------------------------------------------------------------------- #

class LabQuantity(Quantity):
    """``Quantity`` under the OpenAPI name the lab web client already imports (``schemas.Method`` now
    includes ``monte_carlo`` and ``numerical_sdp``, so no widening is needed)."""


class LabNoise(BaseModel):
    """Declared (hypothetical) iid qubit channel between minting and verification.

    Readout error is deliberately absent: the lane-B register verifier has no classical readout
    stage, and a readout flip in the secret basis cannot be expressed as a channel on the note
    without knowing the secret.
    """

    model_config = ConfigDict(extra="forbid")
    channel: Literal["none", "depolarizing", "dephasing", "amplitude_damping"] = "none"
    strength: float = Field(default=0.0, ge=0.0, le=1.0, description="p (depolarizing/dephasing) or gamma (damping)")

    @model_validator(mode="after")
    def _none_has_no_strength(self) -> LabNoise:
        if self.channel == "none" and self.strength != 0.0:
            raise ValueError("channel 'none' takes strength 0")
        return self

    def spec(self) -> NoiseSpec:
        return NoiseSpec(self.channel, self.strength)


def _sim_kind(spec: NoiseSpec) -> EvidenceKind:
    return EvidenceKind.SIMULATOR_IDEAL if spec.is_ideal else EvidenceKind.SIMULATOR_NOISY


def _ci(successes: int, trials: int) -> ConfidenceInterval:
    lo, hi = clopper_pearson_interval(successes, trials, CONFIDENCE)
    return ConfidenceInterval(lo=lo, hi=hi, confidence=CONFIDENCE, method=CI_METHOD)


def _q(
    id: str,
    label: str,
    value: float | None,
    kind: EvidenceKind,
    method: Method,
    source: str,
    *,
    interval: ConfidenceInterval | None = None,
    formula: str | None = None,
    note: str | None = None,
    unit: Unit = Unit.PROBABILITY,
) -> LabQuantity:
    log10 = math.log10(value) if value is not None and 0 < value < 1e-300 else None
    return LabQuantity(
        id=id, label=label, value=value, log10_value=log10, unit=unit, evidence_kind=kind, method=method,
        interval=interval, source=source, formula=formula, note=note,
    )


def _mean_qubit_error(spec: NoiseSpec) -> float:
    """Average per-qubit honest error over the four BB84 states (lane-F closed form)."""
    return 1.0 - 0.25 * sum(analytic_correct_probability(spec, b, x) for b in (Basis.Z, Basis.X) for x in (0, 1))


def _channel_kraus(spec: NoiseSpec) -> list[np.ndarray] | None:
    return None if spec.channel == "none" else spec.kraus()


def _seeds(seed: int, k: int) -> list[int]:
    return [int(x) for x in np.random.default_rng([seed, 0x1AB]).integers(0, 2**62, k)]


def _theorem_w1(n: int, noisy: bool) -> LabQuantity:
    """MVW 2012 Theorem 1 via lane D (game-guarded, log space)."""
    claim, spec = default_registry().bound("P-W1/unf")
    src = default_registry().sources[claim.source]
    lg = log10_bound(GameId.W1, n)
    note = "ideal game W1 only: one note, two outputs, exact verifier, no oracle"
    if noisy:
        note += "; the declared noise affects the honest holder here, the theorem itself assumes no noise"
    return _q(
        "w1_theorem_bound", "W1 theorem: no counterfeiter beats", 10**lg, EvidenceKind.PUBLISHED_THEOREM,
        "closed_form", f"{src.citation}; {spec.anchor}; {src.url}", formula=spec.formula, note=note,
    )


def _no_theorem(id: str, label: str, why: str) -> LabQuantity:
    return _q(id, label, None, EvidenceKind.UNCERTIFIED, "not_available", "qmint.proofs.registry (no matching claim)",
              note=why)


def _qpu_not_run() -> LabQuantity:
    return _q(
        "qpu", "Quantum hardware", None, EvidenceKind.QPU, "not_available", "qmint.quantum.ionq (lane J)",
        note="not run: paid hardware submission is disabled in this build (lane J); no QPU number exists",
    )


class RunInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    backends: list[str]
    seed: int
    shots: int | None
    trials: int
    elapsed_ms: float
    deadline_s: float = REQUEST_DEADLINE_S
    limits: dict[str, int] = Field(
        default_factory=lambda: {"n_max": MAX_N, "shots_max": MAX_SHOTS, "trials_max": MAX_TRIALS,
                                 "trials_max_a08": MAX_TRIALS_A08, "sdp_n_max": MAX_SDP_N}
    )


SIM_CAVEAT = (
    "A simulator's state is classical data that can be copied freely; nothing here demonstrates physical "
    "no-cloning. Only the modelled quantum register is simulated."
)


# --------------------------------------------------------------------------- #
# Mint
# --------------------------------------------------------------------------- #


class MintRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    protocol_id: Literal["wiesner_ideal", "wiesner_noisy"] = "wiesner_ideal"
    n_qubits: int = Field(default=4, ge=1, le=MAX_N)
    threshold: int = Field(default=0, ge=0, le=MAX_N, description="max wrong positions accepted (wiesner_noisy)")
    seed: int = Field(default=42, ge=0, le=2**31 - 1)
    noise: LabNoise = Field(default_factory=LabNoise)
    backend: Literal["exact", "aer"] = "aer"
    shots: int = Field(default=2000, ge=1, le=MAX_SHOTS)
    trials: int = Field(default=1000, ge=0, le=MAX_TRIALS, description="fresh notes for the honest Monte Carlo")
    teaching_reveal: bool = Field(
        default=False,
        description="TEST_ONLY: also return the issuer secret of this note (OUT_OF_MODEL teaching view)",
    )

    @model_validator(mode="after")
    def _threshold_matches_protocol(self) -> MintRequest:
        if self.protocol_id == "wiesner_ideal" and self.threshold != 0:
            raise ValueError("wiesner_ideal uses the exact verifier: threshold must be 0")
        if self.protocol_id == "wiesner_noisy" and not 1 <= self.threshold < self.n_qubits:
            raise ValueError("wiesner_noisy needs 1 <= threshold < n_qubits")
        return self


class LabProtocolInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    protocol_id: str
    game_id: GameId
    threshold: int
    verifier_rule: str
    security_model_id: str
    proof_assumptions: list[str]
    unsupported_extensions: list[str]


class FlowStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Literal["mint", "transmit", "verify", "replay", "remint"]
    label: str
    result: Literal["done", "accepted", "rejected", "refused", "skipped"]
    detail: str
    serial: str | None = None


class QubitOps(BaseModel):
    model_config = ConfigDict(extra="forbid")
    index: int
    prepare: list[str] = Field(description="'secret' (redacted) or gates x / h")
    channel: list[str]
    verify: list[str] = Field(description="'secret' (redacted) or gates h / measure_z")


class CircuitDescription(BaseModel):
    model_config = ConfigDict(extra="forbid")
    redacted: bool
    qubits: list[QubitOps]
    noise_description: str | None
    bit_order_note: str


class ErrorCountRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    errors: int
    exact_probability: float
    sampled_count: int | None
    accepted: bool


class MintStatistics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    threshold: int
    shots: int | None
    acceptance: list[LabQuantity]
    error_counts: list[ErrorCountRow]
    error_counts_note: str


class TeachingQubit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    index: int
    basis: Basis
    bit: int
    state_label: str
    bloch: tuple[float, float, float]


class OutcomeProbability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: str = Field(description="C7 order: character i is qubit q_i")
    probability: float


class TeachingReveal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    domain: Literal["TEST_ONLY_TEACHING_REVEAL"] = "TEST_ONLY_TEACHING_REVEAL"
    proof_applicability: Literal["OUT_OF_MODEL"] = "OUT_OF_MODEL"
    warning: str
    qubits: list[TeachingQubit]
    expected_outcome: str
    outcome_distribution: list[OutcomeProbability]
    outcome_distribution_truncated: bool
    circuit: CircuitDescription
    qasm2: str | None
    resources: dict[str, object]
    circuit_sha256: str


class MintData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: TokenRecord
    protocol: LabProtocolInfo
    flow: list[FlowStep]
    circuit: CircuitDescription
    statistics: MintStatistics
    theorem: LabQuantity
    hardware: LabQuantity
    teaching: TeachingReveal | None
    run: RunInfo
    simulator_caveat: str


class MintResponse(Envelope):
    data: MintData


TEACHING_WARNING = (
    "TEST_ONLY teaching reveal: the bank's leak_secret_TEST_ONLY control was called because you asked for it. "
    "A real issuer never discloses bases or bits; with them a trivial forger wins every time (OUT_OF_MODEL)."
)
BIT_ORDER = "qubit q_i is Qiskit qubit i, measured into clbit i; outcomes are shown in C7 order (char i = q_i)"


def _error_distribution(spec: NoiseSpec, bases: Sequence[Basis], bits: Sequence[int]) -> np.ndarray:
    """Exact Poisson-binomial law of the number of wrong positions (lane-F per-qubit closed forms)."""
    dist = np.array([1.0])
    for b, x in zip(bases, bits, strict=True):
        e = 1.0 - analytic_correct_probability(spec, b, x)
        dist = np.convolve(dist, [1.0 - e, e])
    return dist


def _ops(n: int, spec: NoiseSpec, bases: Sequence[Basis] | None = None, bits: Sequence[int] | None = None) -> list[QubitOps]:
    chan = [] if spec.channel == "none" else [f"{spec.channel}({spec.param:g})"]
    if bases is None or bits is None:
        return [QubitOps(index=i, prepare=["secret"], channel=chan, verify=["secret"]) for i in range(n)]
    return [
        QubitOps(
            index=i,
            prepare=(["x"] if x == 1 else []) + (["h"] if b == Basis.X else []),
            channel=chan,
            verify=(["h"] if b == Basis.X else []) + ["measure_z"],
        )
        for i, (b, x) in enumerate(zip(bases, bits, strict=True))
    ]


def _honest_mc(n: int, threshold: int, spec: NoiseSpec, trials: int, seed: int, dl: Deadline) -> int:
    """Honest acceptance over FRESH notes, each minted and verified once by a lane-B bank."""
    bank = WiesnerChallenger(mode=WiesnerMode.EXACT, threshold=threshold or None, seed=seed, ownership_context="lab_mc")
    kraus = _channel_kraus(spec)
    wins = 0
    for i, s in enumerate(_seeds(seed, trials)):
        if i % 64 == 0:
            dl.check()
        note = bank.mint(n, s)
        if kraus is not None:
            (note,) = note.split(kraus, copies=1)
        wins += bank.verify(note)
    return wins


@router.post("/mint", response_model=MintResponse)
async def mint(req: MintRequest) -> MintResponse | JSONResponse:
    return await _bounded(run_mint, req)


def run_mint(req: MintRequest, dl: Deadline | None = None) -> MintResponse:
    dl = dl or Deadline(REQUEST_DEADLINE_S)
    spec = req.noise.spec()
    n, t = req.n_qubits, req.threshold
    kind = _sim_kind(spec)

    # -- the bank (lane B) mints; the wallet only ever sees the public record -----------------
    bank = WiesnerChallenger(mode=WiesnerMode.EXACT, threshold=t or None, seed=req.seed, ownership_context="lab_wallet")
    note = bank.mint(n, req.seed)
    token = note.record.model_copy(deep=True)
    serial = str(token.public_metadata["serial"])
    # Bank-side analysis only (Aer circuit, closed-form cross-check). Leaves the server ONLY via `teaching`.
    bank_secret = bank.leak_secret_TEST_ONLY(note)
    bases = [Basis(b) for b in bank_secret["bases"]]
    bits = [int(x) for x in bank_secret["bits"]]

    kraus = _channel_kraus(spec)
    sent = note.split(kraus, copies=1)[0] if kraus is not None else note
    p_bank = bank.acceptance_probability(sent)  # exact, non-consuming analysis oracle (lane B register)
    dist = _error_distribution(spec, bases, bits)
    p_closed = float(dist[: t + 1].sum())
    if not math.isclose(p_bank, p_closed, rel_tol=1e-9, abs_tol=1e-12):  # two independent code paths
        raise RuntimeError(f"bank exact acceptance {p_bank} != lane-F closed form {p_closed}")

    redeemed = bank.redeem(sent)
    replay = bank.redeem(sent)
    flow = [
        FlowStep(id="mint", label="Bank mints the note", result="done", serial=serial,
                 detail=f"{n} qubits, each one of |0⟩ |1⟩ |+⟩ |−⟩ chosen uniformly; the bank keeps the choice secret"),
        FlowStep(id="transmit", label="Holder stores / sends it", result="done",
                 detail="ideal channel: nothing disturbs the qubits" if kraus is None
                 else f"{spec.channel}({spec.param:g}) acts on every qubit (hypothetical noise)"),
        FlowStep(id="verify", label="Bank verifies (spend once)", result="accepted" if redeemed.accepted else "rejected",
                 serial=serial,
                 detail=("each qubit measured in its secret basis; " +
                         ("all must match" if t == 0 else f"at most {t} mismatches allowed")
                         + "; one sampled verification (the note is consumed)")),
        FlowStep(id="replay", label="Same serial presented again", result="refused" if replay.reason == "replay" else "rejected",
                 serial=serial, detail=f"bank ledger: serial is '{bank.serial_status(serial)}'; replay refused without measuring"),
    ]
    if redeemed.reminted is not None:
        new_serial = str(redeemed.reminted.record.public_metadata["serial"])
        flow.append(FlowStep(id="remint", label="Bank issues a fresh note", result="done", serial=new_serial,
                             detail="accepted notes are replaced by a new note with a new serial"))
    else:
        flow.append(FlowStep(id="remint", label="Bank issues a fresh note", result="skipped",
                             detail="nothing reminted: the note was rejected"))

    # -- statistics ------------------------------------------------------------------------------
    e_bar = _mean_qubit_error(spec)
    acceptance = [
        _q("honest_accept_mean", "Honest acceptance, any note (closed form)", float(binom.cdf(t, n, e_bar)), kind,
           "closed_form", "qmint.quantum.channels.analytic_correct_probability + binomial",
           formula=f"P[Bin(n, ē) ≤ t], ē = {e_bar:.6g}", note=None if spec.is_ideal else spec.describe()),
        _q("honest_accept_note_exact", "Honest acceptance, this note (bank exact)", p_bank, kind, "exact_enumeration",
           "qmint.protocols.wiesner.WiesnerChallenger.acceptance_probability",
           note="bank-side analysis oracle; cross-checked against the lane-F closed form to 1e-9"),
    ]
    sampled: dict[int, int] | None = None
    backends = ["qmint.protocols.register.FactorizedRegister (exact)"]
    if req.backend == "aer":
        dl.check()
        qc = circuits.build_verify_circuit(bases, bits, noise=None if spec.channel == "none" else spec)
        counts, prov, _ = circuits.run_aer(qc, shots=req.shots, seed=req.seed, noise=spec)
        sampled = {}
        for outcome, c in counts.items():
            k = sum(int(a != b) for a, b in zip(outcome, bits, strict=True))
            sampled[k] = sampled.get(k, 0) + int(c)
        acc = sum(c for k, c in sampled.items() if k <= t)
        acceptance.append(
            _q("honest_accept_note_aer", "Honest acceptance, this note (Aer shots)", acc / req.shots, kind,
               "aer_sampling", f"qmint.quantum.circuits.run_aer ({prov.backend_name}, local)",
               interval=_ci(acc, req.shots), note=f"{acc}/{req.shots} shots; seed_simulator={req.seed}")
        )
        backends.append(f"{prov.backend_name} (local, {prov.simulator_method})")
    if req.trials:
        wins = _honest_mc(n, t, spec, req.trials, req.seed, dl)
        acceptance.append(
            _q("honest_accept_mc", "Honest acceptance, fresh notes (Monte Carlo)", wins / req.trials, kind, "monte_carlo",
               "qmint.protocols.wiesner.WiesnerChallenger (one fresh note per trial)", interval=_ci(wins, req.trials),
               note=f"{wins}/{req.trials} fresh notes accepted")
        )
    rows = [
        ErrorCountRow(errors=k, exact_probability=float(p), sampled_count=None if sampled is None else sampled.get(k, 0),
                      accepted=k <= t)
        for k, p in enumerate(dist)
    ]

    noisy_game = req.protocol_id == "wiesner_noisy"
    theorem = (
        _no_theorem("w2_theorem_bound", "W2 theorem bound",
                    "game W2 (threshold verifier): no published closed-form bound; (3/4)^n does NOT transfer")
        if noisy_game else _theorem_w1(n, noisy=not spec.is_ideal)
    )

    teaching = None
    if req.teaching_reveal:
        dl.check()
        exact = (bb84.analytic_outcome_distribution(bases, bits) if spec.channel == "none"
                 else circuits.qiskit_exact_distribution(bases, bits, noise=spec))
        ranked = sorted(((k, v) for k, v in exact.items() if v > 1e-15), key=lambda kv: (-kv[1], kv[0]))
        qc = circuits.build_verify_circuit(bases, bits, noise=None if spec.channel == "none" else spec)
        try:
            from qiskit import qasm2

            qasm = qasm2.dumps(circuits.build_verify_circuit(bases, bits))
        except Exception:  # pragma: no cover - QASM export is best effort
            qasm = None
        teaching = TeachingReveal(
            warning=TEACHING_WARNING,
            qubits=[
                TeachingQubit(index=i, basis=b, bit=x, state_label=bb84.state_label(b, x).value,
                              bloch=bb84.BLOCH_VECTORS[bb84.state_label(b, x)])
                for i, (b, x) in enumerate(zip(bases, bits, strict=True))
            ],
            expected_outcome="".join(map(str, bits)),
            outcome_distribution=[OutcomeProbability(outcome="".join(map(str, k)), probability=v) for k, v in ranked[:TOP_K]],
            outcome_distribution_truncated=len(ranked) > TOP_K,
            circuit=CircuitDescription(redacted=False, qubits=_ops(n, spec, bases, bits),
                                       noise_description=None if spec.is_ideal else spec.describe(), bit_order_note=BIT_ORDER),
            qasm2=qasm,
            resources=resource_counts(qc),
            circuit_sha256=circuit_fingerprint(qc),
        )
    del bank_secret, bases, bits

    spec_obj = bank.spec
    return MintResponse(
        status="OK",
        evidence_kind=kind,
        provenance=provenance(
            "qmint.protocols.wiesner (lane B) + qmint.quantum (lane F) + qmint.proofs (lane D)",
            seed=req.seed, quantum=True, notes=None if spec.is_ideal else "hypothetical noise parameters",
        ),
        data=MintData(
            token=token,
            protocol=LabProtocolInfo(
                protocol_id=spec_obj.protocol_id, game_id=spec_obj.adversary_game_id, threshold=t,
                verifier_rule="measure every qubit in its secret basis; accept iff wrong positions ≤ threshold",
                security_model_id=spec_obj.security_model_id, proof_assumptions=list(spec_obj.proof_assumptions),
                unsupported_extensions=list(spec_obj.unsupported_extensions),
            ),
            flow=flow,
            circuit=CircuitDescription(redacted=True, qubits=_ops(n, spec), bit_order_note=BIT_ORDER,
                                       noise_description=None if spec.is_ideal else spec.describe()),
            statistics=MintStatistics(
                threshold=t, shots=req.shots if req.backend == "aer" else None, acceptance=acceptance,
                error_counts=rows,
                error_counts_note="number of wrong positions in one verification of this note; per-position results "
                "are never returned (they would reveal the secret)",
            ),
            theorem=theorem,
            hardware=_qpu_not_run(),
            teaching=teaching,
            run=RunInfo(backends=backends, seed=req.seed, shots=req.shots if req.backend == "aer" else None,
                        trials=req.trials, elapsed_ms=dl.elapsed_ms()),
            simulator_caveat=SIM_CAVEAT,
        ),
    )


# --------------------------------------------------------------------------- #
# Attack
# --------------------------------------------------------------------------- #

AttackId = Literal[
    "A01_basis_guess_resend",
    "A01b_basis_guess_bayes_resend",
    "A02_breidbart_resend",
    "A02b_breidbart_bayes_resend",
    "A03_universal_buzek_hillery",
    "A03b_phase_covariant_xz",
    "A04_mvw_optimal_channel",
    "A06_split_and_report_loss",
    "A08_adaptive_oracle_probe",
    "CTRL_secret_leak",
]
Applicability = Literal["IN_MODEL", "NO_THEOREM", "OUT_OF_MODEL"]


@dataclass(frozen=True)
class _AttackSpec:
    label: str
    plain: str
    game: GameId
    applicability: Applicability
    capability: tuple[str, ...]


_W1_CAP = ("one_note", "per_qubit_channel", "no_verifier_oracle")
ATTACKS: dict[str, _AttackSpec] = {
    "A01_basis_guess_resend": _AttackSpec(
        "A01 · measure and resend", "Guess Z or X for each qubit, measure it, then prepare two copies of what you saw.",
        GameId.W1, "IN_MODEL", _W1_CAP),
    "A01b_basis_guess_bayes_resend": _AttackSpec(
        "A01b · measure, smarter resend", "As A01, but resend the two-qubit state that is most likely to pass "
        "given the outcome.", GameId.W1, "IN_MODEL", _W1_CAP),
    "A02_breidbart_resend": _AttackSpec(
        "A02 · Breidbart measure-resend", "Measure every qubit in the 'Breidbart' basis halfway between Z and X "
        "(π/8), then prepare two copies.", GameId.W1, "IN_MODEL", _W1_CAP),
    "A02b_breidbart_bayes_resend": _AttackSpec(
        "A02b · Breidbart, smarter resend", "Breidbart measurement followed by the most-likely-to-pass resend.",
        GameId.W1, "IN_MODEL", _W1_CAP),
    "A03_universal_buzek_hillery": _AttackSpec(
        "A03 · universal cloner", "Bužek–Hillery cloner: makes two imperfect copies of ANY qubit state equally well.",
        GameId.W1, "IN_MODEL", _W1_CAP),
    "A03b_phase_covariant_xz": _AttackSpec(
        "A03b · phase-covariant cloner", "A cloner tuned to the circle of states that contains |0⟩ |1⟩ |+⟩ |−⟩ "
        "(Bruß et al. 2000), better than the universal one here.", GameId.W1, "IN_MODEL", _W1_CAP),
    "A04_mvw_optimal_channel": _AttackSpec(
        "A04 · optimal channel (MVW)", "The explicit channel of Molina–Vidick–Watrous 2012 that reaches the "
        "theorem's 3/4 per qubit: nothing does better.", GameId.W1, "IN_MODEL", _W1_CAP),
    "A06_split_and_report_loss": _AttackSpec(
        "A06 · split and report loss", "Against a lossy toy verifier that ignores qubits reported as lost: give "
        "each copy the original qubits the other copy reports as lost; clone the rest.", GameId.W2, "NO_THEOREM",
        ("one_note", "per_qubit_channel", "selective_loss_reporting", "no_verifier_oracle")),
    "A08_adaptive_oracle_probe": _AttackSpec(
        "A08 · leaky verifier probing", "If the bank answered accept/reject AND handed the note back, you could "
        "probe each qubit until you learn it, then print perfect copies.", GameId.W1, "OUT_OF_MODEL",
        ("one_note", "accept_reject_oracle", "note_returned_after_query", "repeated_queries")),
    "CTRL_secret_leak": _AttackSpec(
        "Control · secret leaked", "Negative control: the bank's secret is handed to the attacker, who simply "
        "prepares two perfect notes. Shows what the secret protects.", GameId.W1, "OUT_OF_MODEL",
        ("one_note", "issuer_secret_revealed")),
}


class AttackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attack: AttackId = "A04_mvw_optimal_channel"
    n: int = Field(default=2, ge=1, le=MAX_N)
    seed: int = Field(default=42, ge=0, le=2**31 - 1)
    trials: int = Field(default=1000, ge=0, le=MAX_TRIALS)
    noise: LabNoise = Field(default_factory=LabNoise, description="honest holder's channel (honest acceptance only)")
    max_loss_fraction: float = Field(default=0.5, ge=0.0, le=1.0, description="A06 toy verifier")
    max_error_fraction: float = Field(default=0.0, ge=0.0, le=0.5, description="A06 toy verifier")
    probes: int = Field(default=10, ge=1, le=16, description="A08 Z-probes per position")
    include_sdp: bool = True

    @model_validator(mode="after")
    def _caps(self) -> AttackRequest:
        if self.attack == "A08_adaptive_oracle_probe" and self.trials > MAX_TRIALS_A08:
            raise ValueError(f"A08 makes ~{self.probes}n oracle queries per trial: trials must be <= {MAX_TRIALS_A08}")
        return self


class SdpBracket(BaseModel):
    """Two-sided enclosure of the OPTIMAL W1 counterfeit probability for small n."""

    model_config = ConfigDict(extra="forbid")
    n: int
    status: Literal["OK", "UNSUPPORTED"]
    reason: str | None = None
    lower: LabQuantity | None = None
    upper_certified: LabQuantity | None = None
    upper_independent: LabQuantity | None = None
    numerical: LabQuantity | None = None
    recorded_evidence: str = C_EVIDENCE


class AttackData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attack: AttackId
    attack_label: str
    description: str
    game_id: GameId
    proof_applicability: Applicability
    capabilities: list[str]
    honest_acceptance: list[LabQuantity]
    single_copy_pass: LabQuantity
    counterfeit_success: list[LabQuantity]
    theorem_bound: LabQuantity
    sdp: SdpBracket | None
    hardware: LabQuantity
    attack_result: AttackResult | None
    assumptions: list[str]
    notes: list[str]
    run: RunInfo
    simulator_caveat: str


class AttackResponse(Envelope):
    data: AttackData


@lru_cache(maxsize=MAX_SDP_N)
def sdp_bracket(n: int) -> SdpBracket:
    """W1 optimum for n <= 2: live SCS solve, lane-C exact certification of its dual, lane-D
    independent exact verification of the analytic dual, exact achieving channel as the lower end."""
    if n > MAX_SDP_N:
        return SdpBracket(n=n, status="UNSUPPORTED",
                          reason=f"W1 n={n} needs Choi dimension {8**n} > 64: refused by the size guard; for "
                          "n ≥ 3 only the theorem (MVW 2012 Sec. 3.4) applies")
    rep = solve_w1(n, "SCS")
    cert = certify_w1_dual(rep.Y, n, rep.dual_value)
    lower = exact_choi_value_of_mvw_channel(n)
    indep = sdp_exact.w1_independent_upper_bound(n)
    return SdpBracket(
        n=n,
        status="OK",
        lower=_q("sdp_lower", "Achieved by an explicit channel (exact)", float(lower), EvidenceKind.SIMULATOR_IDEAL,
                 "exact_enumeration", "qmint.attacks.certify.exact_choi_value_of_mvw_channel",
                 formula=f"⟨G_n, J_MVW⟩ = {lower}", note="exact rational arithmetic: a rigorous LOWER end"),
        upper_certified=_q("sdp_upper_certified", "No channel exceeds (certified dual)", cert.bound_float_up,
                           EvidenceKind.CERTIFIED_NUMERIC, "exact_enumeration", "qmint.attacks.certify.certify_w1_dual",
                           formula="Tr Y′ with Y′ ⊗ 1 − G_n ≻ 0 verified by exact LDLᵀ",
                           note=f"SCS dual rounded to dyadics, shifted by δ = {float(cert.delta):.3g}; weak duality"),
        upper_independent=_q("sdp_upper_independent", "Independent exact check (lane D)", float(indep),
                             EvidenceKind.CERTIFIED_NUMERIC, "exact_enumeration",
                             "qmint.proofs.sdp_exact.w1_independent_upper_bound",
                             formula=f"Y = (3/8)^n·1 ⇒ OPT ≤ {indep}",
                             note="separate code path: own rational G_n and exact PSD test; imports nothing from lane C"),
        numerical=_q("sdp_numerical", "Numerical SDP (SCS)", rep.primal_value, EvidenceKind.NUMERICAL_SDP,
                     "numerical_sdp", "qmint.attacks.coherent_sdp.solve_w1 (cvxpy/SCS)",
                     note=f"primal {rep.primal_value:.12g}, dual {rep.dual_value:.12g}; floating point, not a proof"),
    )


def _pair_mc_lane_b(kraus: list[np.ndarray], n: int, trials: int, seed: int, dl: Deadline) -> tuple[int, int]:
    """(both pass, first copy passes) over FRESH lane-B notes: an implementation independent of lane C's challenger."""
    bank = WiesnerChallenger(mode=WiesnerMode.EXACT, seed=seed, ownership_context="lab_attack")
    both = first = 0
    for i, s in enumerate(_seeds(seed, trials)):
        if i % 64 == 0:
            dl.check()
        c1, c2 = bank.mint(n, s).split(kraus)
        a, b = bank.verify_pair(c1, c2)
        both += a and b
        first += a
    return both, first


def _attack_record(attack: str, spec: _AttackSpec, n: int, seed: int, trials: int, wins: int, method: str,
                   verifier: str, backend: str, bound: float | None) -> AttackResult:
    lo, hi = clopper_pearson_interval(wins, trials, CONFIDENCE)
    return AttackResult(
        attack_id=attack, game_id=spec.game, attack_capability=list(spec.capability), token_n=n, attack_method=method,
        quantum_channel_description=spec.plain, verifier_rule=verifier, seed=seed, trials=trials, successes=wins,
        success_rate_ci=Interval(lo=lo, hi=hi, unit=Unit.PROBABILITY, point=wins / trials), ci_method=CI_METHOD,
        proof_applicability=spec.applicability, theorem_upper_bound=bound, backend_kind=backend,
        evidence_kind=EvidenceKind.MONTE_CARLO, source_code_sha=attacks_source_sha(),
    )


@router.post("/attack", response_model=AttackResponse)
async def attack(req: AttackRequest) -> AttackResponse | JSONResponse:
    return await _bounded(run_attack, req)


def run_attack(req: AttackRequest, dl: Deadline | None = None) -> AttackResponse:
    dl = dl or Deadline(REQUEST_DEADLINE_S)
    spec = ATTACKS[req.attack]
    noise = req.noise.spec()
    n, trials = req.n, req.trials
    kind = _sim_kind(noise)
    exact_kind = EvidenceKind.SIMULATOR_IDEAL
    notes: list[str] = []
    backends = ["exact enumeration (numpy)"]
    assumptions = [
        "one genuine note; the counterfeiter returns two candidate notes; the bank verifies both in the secret bases",
        "Monte Carlo draws a FRESH secret note per trial (never repeated shots of one note)",
    ]
    if not noise.is_ideal:
        notes.append("Declared noise affects the honest holder only. Attack values and the W1 theorem are for the "
                     "ideal noiseless game; a noisy/threshold verifier is game W2 (no closed form).")

    # -- honest acceptance -------------------------------------------------------------------
    e_bar = _mean_qubit_error(noise)
    if req.attack == "A06_split_and_report_loss":
        honest_val = heuristic.honest_acceptance_w2(n, 0.0, e_bar, req.max_loss_fraction, req.max_error_fraction)
        honest_src, honest_formula = "qmint.attacks.heuristic.honest_acceptance_w2 (no loss)", "toy W2 rule, iid error ē"
    else:
        honest_val = (1.0 - e_bar) ** n
        honest_src, honest_formula = "qmint.quantum.channels.analytic_correct_probability", "(1 − ē)^n"
    honest = [_q("honest_accept_mean", "Honest acceptance (closed form)", honest_val, kind, "closed_form", honest_src,
                 formula=f"{honest_formula}, ē = {e_bar:.6g}")]
    if trials and req.attack != "A06_split_and_report_loss":
        wins = _honest_mc(n, 0, noise, trials, req.seed, dl)
        honest.append(_q("honest_accept_mc", "Honest acceptance (Monte Carlo)", wins / trials, kind, "monte_carlo",
                         "qmint.protocols.wiesner.WiesnerChallenger (fresh notes)", interval=_ci(wins, trials),
                         note=f"{wins}/{trials} fresh notes"))

    w1_bound = 0.75**n
    counterfeit: list[LabQuantity] = []
    record: AttackResult | None = None
    single: LabQuantity
    sdp: SdpBracket | None = None

    if req.attack in heuristic.W1_PRODUCT_ATTACKS:
        factory, method = heuristic.W1_PRODUCT_ATTACKS[req.attack]
        kraus = factory()
        jp = heuristic.joint_outcome_probs(kraus)
        p1, pp = jp["pp"] + jp["pf"], jp["pp"]
        single = _q("single_copy_pass", "One counterfeit passes", p1**n, exact_kind, "exact_enumeration",
                    "qmint.attacks.heuristic.joint_outcome_probs", formula=f"({p1:.6g})^n",
                    note="exact model value: copy 1 alone, averaged over the uniform secret")
        counterfeit.append(_q("counterfeit_exact", "Both counterfeits pass (exact)", pp**n, exact_kind,
                              "exact_enumeration", "qmint.attacks.heuristic.w1_product_exact",
                              formula=f"({pp:.6g})^n", note=LOWER_BOUND_NOTE))
        if trials:
            both, first = _pair_mc_lane_b(kraus, n, trials, req.seed, dl)
            backends.append("qmint.protocols.register.FactorizedRegister (Monte Carlo)")
            counterfeit.append(_q("counterfeit_mc", "Both counterfeits pass (Monte Carlo)", both / trials,
                                  EvidenceKind.MONTE_CARLO, "monte_carlo",
                                  "lane-C Kraus channel against the lane-B bank (qmint.protocols.wiesner)",
                                  interval=_ci(both, trials), note=f"{both}/{trials} fresh notes; " + LOWER_BOUND_NOTE))
            record = _attack_record(req.attack, spec, n, req.seed, trials, both, method,
                                    "exact projective BB84 verifier on every position; both candidates must pass",
                                    "qmint.protocols.register.FactorizedRegister", w1_bound)
            notes.append(f"Copy 1 alone passed in {first}/{trials} trials (exact {p1**n:.6g}).")
        theorem = _theorem_w1(n, noisy=not noise.is_ideal)
        if req.include_sdp:
            dl.check()
            sdp = sdp_bracket(n)
            if sdp.status == "OK":
                backends.append("cvxpy/SCS + exact rational certificates")
    elif req.attack == "A06_split_and_report_loss":
        k = heuristic.a06_plan(n, req.max_loss_fraction)
        exact = heuristic.a06_exact(n, k, req.max_loss_fraction, req.max_error_fraction)
        rule = (f"toy W2: accept iff lost ≤ ⌊{req.max_loss_fraction:g}·n⌋ and errors ≤ "
                f"⌊{req.max_error_fraction:g}·reported⌋")
        single = _q("single_copy_pass", "One counterfeit passes", None, EvidenceKind.UNCERTIFIED, "not_available",
                    "qmint.api.routes.lab", note="not computed separately for this attack")
        counterfeit.append(_q("counterfeit_exact", "Both counterfeits pass (exact)", exact, exact_kind,
                              "exact_enumeration", "qmint.attacks.heuristic.a06_exact",
                              formula=f"{k} exclusive positions per copy, MVW clone on the other {n - 2 * k}",
                              note=LOWER_BOUND_NOTE))
        if trials:
            dl.check()
            wins = heuristic.mc_a06_split_loss(n, req.max_loss_fraction, req.max_error_fraction, trials, req.seed)
            backends.append("qmint.attacks.games.ThresholdLossChallenger (Monte Carlo)")
            counterfeit.append(_q("counterfeit_mc", "Both counterfeits pass (Monte Carlo)", wins / trials,
                                  EvidenceKind.MONTE_CARLO, "monte_carlo", "qmint.attacks.heuristic.mc_a06_split_loss",
                                  interval=_ci(wins, trials), note=f"{wins}/{trials} fresh notes; " + LOWER_BOUND_NOTE))
            record = _attack_record(req.attack, spec, n, req.seed, trials, wins,
                                    "split-and-report-loss + MVW cloning", rule,
                                    "qmint.attacks.games.ThresholdLossChallenger", None)
        theorem = _no_theorem("theorem_bound", "Theorem bound",
                              "toy W2 loss/threshold verifier: no published theorem; (3/4)^n does NOT transfer")
        assumptions.append(rule + "; loss flags are fixed before any outcome is revealed")
        assumptions.append(f"with loss allowed, the W1 value (3/4)^n = {w1_bound:.6g} is shown for contrast only")
    elif req.attack == "A08_adaptive_oracle_probe":
        exact = heuristic.a08_exact(n, req.probes)
        single = _q("single_copy_pass", "One counterfeit passes", None, EvidenceKind.UNCERTIFIED, "not_available",
                    "qmint.api.routes.lab", note="the forged copies are identical; reported jointly")
        counterfeit.append(_q("counterfeit_exact", "Both counterfeits pass (exact)", exact, exact_kind,
                              "exact_enumeration", "qmint.attacks.heuristic.a08_exact",
                              formula=f"(1 − 2^−{req.probes})^n", note=LOWER_BOUND_NOTE))
        if trials:
            dl.check()
            stats = heuristic.mc_a08_oracle(n, req.probes, trials, req.seed)
            backends.append("qmint.attacks.games.LeakyOracleChallenger (Monte Carlo)")
            counterfeit.append(_q("counterfeit_mc", "Both counterfeits pass (Monte Carlo)", stats.wins / trials,
                                  EvidenceKind.MONTE_CARLO, "monte_carlo", "qmint.attacks.heuristic.mc_a08_oracle",
                                  interval=_ci(stats.wins, trials),
                                  note=f"{stats.wins}/{trials} fresh notes; mean {stats.mean_queries:.1f} oracle queries"))
            record = _attack_record(req.attack, spec, n, req.seed, trials, stats.wins, "adaptive accept/reject probing",
                                    "toy leaky verifier: reveals accept/reject and returns the post-measurement note",
                                    "qmint.attacks.games.LeakyOracleChallenger", None)
        theorem = _no_theorem("theorem_bound", "Theorem bound",
                              "OUT_OF_MODEL: W1 forbids verifier-oracle access, so (3/4)^n does not apply")
        assumptions.append(f"W1 value (3/4)^n = {w1_bound:.6g} shown for contrast only")
    else:  # CTRL_secret_leak
        single = _q("single_copy_pass", "One counterfeit passes", 1.0, exact_kind, "exact_enumeration",
                    "qmint.protocols.wiesner.forge_from_leaked_secret", note="perfect preparation from the leaked secret")
        counterfeit.append(_q("counterfeit_exact", "Both counterfeits pass (exact)", 1.0, exact_kind,
                              "exact_enumeration", "qmint.protocols.wiesner.forge_from_leaked_secret",
                              note="trivial forger: two perfect notes"))
        if trials:
            dl.check()
            record = unsafe_secret_leak_control(n, trials, req.seed, source_code_sha=git_sha())
            backends.append("qmint.protocols.wiesner (Monte Carlo)")
            counterfeit.append(_q("counterfeit_mc", "Both counterfeits pass (Monte Carlo)", record.successes / trials,
                                  EvidenceKind.MONTE_CARLO, "monte_carlo",
                                  "qmint.protocols.wiesner.unsafe_secret_leak_control",
                                  interval=_ci(record.successes, trials), note=f"{record.successes}/{trials} fresh notes"))
        theorem = _no_theorem("theorem_bound", "Theorem bound",
                              "OUT_OF_MODEL: the theorem assumes the secret stays with the bank")

    return AttackResponse(
        status="OK",
        evidence_kind=exact_kind,
        provenance=provenance(
            "qmint.attacks (lane C) + qmint.protocols.wiesner (lane B) + qmint.proofs (lane D) + qmint.quantum (lane F)",
            seed=req.seed, quantum=True,
            notes=f"attack source sha256 {attacks_source_sha()[:16]}; recorded lane-C evidence {C_EVIDENCE}",
        ),
        data=AttackData(
            attack=req.attack, attack_label=spec.label, description=spec.plain, game_id=spec.game,
            proof_applicability=spec.applicability, capabilities=list(spec.capability),
            honest_acceptance=honest, single_copy_pass=single, counterfeit_success=counterfeit,
            theorem_bound=theorem, sdp=sdp, hardware=_qpu_not_run(), attack_result=record,
            assumptions=assumptions, notes=notes,
            run=RunInfo(backends=backends, seed=req.seed, shots=None, trials=trials, elapsed_ms=dl.elapsed_ms()),
            simulator_caveat=SIM_CAVEAT,
        ),
    )
