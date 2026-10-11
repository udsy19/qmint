"""POST /lab/mint and /lab/attack -- thin adapters over lane F (``qmint.quantum``).

Mint is a real lane-F code path (status OK). Attack is a ``DEMO_ADAPTER``: lane C (attack suites)
is not merged, so it combines lane-F cloner circuits, exact enumeration over BB84 states and the
published W1 bound. Every attack success value is the success of ONE specific attack and therefore
only a LOWER bound on worst-case counterfeiting success; the only upper bound shown is the
published theorem.

Issuer view (mint): the demo deliberately reveals the seeded note's bases/bits through
``IssuerSecret.reveal_for_testing_only()`` in a separate, explicitly labelled
``issuer_view`` block. That is acceptable here because (a) the note is a public seeded teaching
example -- anyone with the seed can recompute it -- and (b) no security claim is attached to it;
any attack given this view is OUT_OF_MODEL. The public ``token`` (C1 ``TokenRecord``) never
carries secret material.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Literal, TypeVar

import numpy as np
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from qmint.core.contracts import (
    AttackResult,
    Basis,
    EvidenceKind,
    GameId,
    StateKind,
    TokenRecord,
    Unit,
)
from qmint.quantum import bb84, circuits, cloner
from qmint.quantum.channels import (
    NoiseSpec,
    analytic_mean_accept_probability,
    analytic_note_accept_probability,
)
from qmint.quantum.records import circuit_fingerprint, clopper_pearson, resource_counts

from ..common import ci_from_interval, git_sha, noise_spec, provenance
from ..schemas import ERROR_RESPONSES, Envelope, NoiseIn, Quantity
from .protocols import GAMES, MVW2012, TRANSCRIPTION_NOTE

T = TypeVar("T")
R = TypeVar("R")
CONFIDENCE = 0.99
TOP_K = 32
LOWER_BOUND_NOTE = (
    "success of one specific attack: a LOWER bound on worst-case counterfeiting success, never an upper bound"
)

router = APIRouter(prefix="/lab", tags=["lab"], responses=ERROR_RESPONSES)

# Qiskit circuit objects segfault when consecutive requests build them on different threadpool threads
# (observed with qiskit 2.5 under FastAPI's sync-endpoint threadpool). All quantum work therefore runs
# serialised on ONE dedicated worker thread.
_QUANTUM_THREAD = ThreadPoolExecutor(max_workers=1, thread_name_prefix="qmint-quantum")


async def _on_quantum_thread(fn: Callable[[T], R], arg: T) -> R:
    return await asyncio.get_running_loop().run_in_executor(_QUANTUM_THREAD, fn, arg)


# --------------------------------------------------------------------------- #
# Shared
# --------------------------------------------------------------------------- #


def _sim_kind(spec: NoiseSpec) -> EvidenceKind:
    return EvidenceKind.SIMULATOR_IDEAL if spec.is_ideal else EvidenceKind.SIMULATOR_NOISY


def _note(n: int, seed: int, token_id: str) -> tuple[list[Basis], list[int]]:
    """Seeded uniformly random note; the secret is opened only inside this module."""
    revealed = bb84.random_note_secret(n, seed=seed, token_id=token_id).reveal_for_testing_only()
    return [Basis(b) for b in revealed["bases"]], [int(x) for x in revealed["bits"]]


def _bitstring(outcome: tuple[int, ...]) -> str:
    """C7 order: character i is qubit q_i (NOT Qiskit's little-endian key)."""
    return "".join(str(b) for b in outcome)


class OutcomeProbability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: str = Field(description="C7 order: character i is qubit q_i")
    probability: float


class OutcomeCount(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: str = Field(description="C7 order: character i is qubit q_i")
    count: int


# --------------------------------------------------------------------------- #
# Mint
# --------------------------------------------------------------------------- #


class MintRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    protocol_id: Literal["wiesner_ideal"] = "wiesner_ideal"
    n_qubits: int = Field(default=4, ge=1, le=bb84.MAX_STATEVECTOR_QUBITS)
    seed: int = Field(default=42, ge=0, le=2**31 - 1)
    backend: Literal["analytic", "aer"] = "analytic"
    shots: int = Field(default=4000, ge=1, le=20000)
    noise: NoiseIn | None = None


class IssuerQubit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    index: int
    basis: Basis
    bit: int
    state_label: str
    bloch: tuple[float, float, float]


class IssuerView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    domain: Literal["ISSUER_PRIVATE_DEMO"] = "ISSUER_PRIVATE_DEMO"
    warning: str
    qubits: list[IssuerQubit]


class QubitOps(BaseModel):
    model_config = ConfigDict(extra="forbid")
    index: int
    prepare: list[str]
    channel: list[str]
    verify: list[str]


class CircuitDescription(BaseModel):
    model_config = ConfigDict(extra="forbid")
    qubits: list[QubitOps]
    resources: dict[str, object]
    resources_note: str
    circuit_sha256: str
    qasm2: str | None = Field(description="noiseless verify circuit; channels are not expressible in QASM 2")
    noise_description: str | None
    bit_order_note: str


class MeasurementStats(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_outcome: str
    analytic_distribution: list[OutcomeProbability]
    analytic_truncated: bool
    analytic_method: str
    aer_counts: list[OutcomeCount] | None
    shots: int | None
    acceptance: list[Quantity]


class MintData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: TokenRecord
    issuer_view: IssuerView
    circuit: CircuitDescription
    statistics: MeasurementStats
    simulator_caveat: str


class MintResponse(Envelope):
    data: MintData


ISSUER_WARNING = (
    "Issuer-private material, revealed ONLY because this is a public, seeded teaching demo: anyone with "
    "the seed can recompute it. A real issuer never discloses bases or bits; any attack given this view is "
    "OUT_OF_MODEL."
)
SIM_CAVEAT = (
    "A simulator's state vector is classical data that can be copied freely; nothing here demonstrates "
    "physical no-cloning. Only the modelled quantum register is simulated."
)


def _ops(bases: list[Basis], bits: list[int], spec: NoiseSpec) -> list[QubitOps]:
    out = []
    for i, (b, x) in enumerate(zip(bases, bits, strict=True)):
        prep = (["x"] if x == 1 else []) + (["h"] if b == Basis.X else [])
        chan = [] if spec.channel == "none" else [f"{spec.channel}({spec.param:g})"]
        verify = (["h"] if b == Basis.X else []) + ["measure_z"]
        out.append(QubitOps(index=i, prepare=prep, channel=chan, verify=verify))
    return out


@router.post("/mint", response_model=MintResponse)
async def mint(req: MintRequest) -> MintResponse:
    return await _on_quantum_thread(run_mint, req)


def run_mint(req: MintRequest) -> MintResponse:
    spec = noise_spec(req.noise)
    n = req.n_qubits
    token_id = f"demo-wiesner-n{n}-s{req.seed}"
    bases, bits = _note(n, req.seed, token_id)
    kind = _sim_kind(spec)

    ideal_qc = circuits.build_verify_circuit(bases, bits)
    qc = circuits.build_verify_circuit(bases, bits, noise=None if spec.channel == "none" else spec)
    try:
        from qiskit import qasm2

        qasm = qasm2.dumps(ideal_qc)
    except Exception:  # pragma: no cover - qasm export is best effort
        qasm = None

    if spec.is_ideal:
        exact = bb84.analytic_outcome_distribution(bases, bits)
        dist_method = "closed form: qmint.quantum.bb84.analytic_outcome_distribution"
    else:
        exact = {k: v for k, v in circuits.qiskit_exact_distribution(bases, bits, noise=spec).items() if v > 1e-15}
        dist_method = "exact density matrix: qmint.quantum.circuits.qiskit_exact_distribution (entries <= 1e-15 dropped)"
    ranked = sorted(exact.items(), key=lambda kv: (-kv[1], kv[0]))
    expected = tuple(bits)

    p_note = analytic_note_accept_probability(spec, bases, bits)
    p_mean = analytic_mean_accept_probability(spec, n)
    acceptance = [
        Quantity(
            id="honest_accept_note_analytic",
            label="Honest acceptance of this note (closed form)",
            value=p_note,
            unit=Unit.PROBABILITY,
            evidence_kind=kind,
            method="closed_form",
            source="qmint.quantum.channels.analytic_note_accept_probability",
            formula="prod_i P(pass q_i | channel, readout)",
            note="exact-match verifier in the secret bases" + ("" if spec.is_ideal else "; " + spec.describe()),
        ),
        Quantity(
            id="honest_accept_mean_analytic",
            label="Honest acceptance, average over random notes (closed form)",
            value=p_mean,
            unit=Unit.PROBABILITY,
            evidence_kind=kind,
            method="closed_form",
            source="qmint.quantum.channels.analytic_mean_accept_probability",
            formula="(mean per-qubit pass probability)^n",
        ),
    ]
    aer_counts = None
    if req.backend == "aer":
        counts, _prov, _ = circuits.run_aer(qc, shots=req.shots, seed=req.seed, noise=spec)
        acc = circuits.accepted_shots(counts, bits)
        iv = clopper_pearson(acc, req.shots, CONFIDENCE)
        acceptance.append(
            Quantity(
                id="honest_accept_note_aer",
                label="Honest acceptance of this note (Aer shots)",
                value=acc / req.shots,
                unit=Unit.PROBABILITY,
                evidence_kind=kind,
                method="aer_sampling",
                interval=ci_from_interval(iv, CONFIDENCE, f"clopper_pearson_{CONFIDENCE}"),
                source="qmint.quantum.circuits.run_aer (local AerSimulator)",
                note=f"{acc}/{req.shots} shots exact-match; seed_simulator={req.seed}",
            )
        )
        ranked_counts = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_K]
        aer_counts = [OutcomeCount(outcome=_bitstring(k), count=int(v)) for k, v in ranked_counts]

    token = TokenRecord(
        token_id=token_id,
        protocol_id=req.protocol_id,
        n_prepared=n,
        source_state_family="BB84",
        public_metadata={"n_qubits": n, "demo": True, "backend": req.backend},
        issue_event_id=f"{token_id}:issue",
        state_kind=StateKind.IDEAL_SIMULATED if spec.is_ideal else StateKind.NOISY_SIMULATED,
        ownership_context="public_seeded_demo",
        backend_provenance=f"qmint.quantum ({req.backend}); git {git_sha()}",
    )
    issuer = IssuerView(
        warning=ISSUER_WARNING,
        qubits=[
            IssuerQubit(
                index=i,
                basis=b,
                bit=x,
                state_label=bb84.state_label(b, x).value,
                bloch=bb84.BLOCH_VECTORS[bb84.state_label(b, x)],
            )
            for i, (b, x) in enumerate(zip(bases, bits, strict=True))
        ],
    )
    circuit = CircuitDescription(
        qubits=_ops(bases, bits, spec),
        resources=resource_counts(qc),
        resources_note="logical circuit; generic CX+1q transpile is NOT a hardware-native gate count",
        circuit_sha256=circuit_fingerprint(qc),
        qasm2=qasm,
        noise_description=None if spec.is_ideal else spec.describe(),
        bit_order_note="qubit q_i is Qiskit qubit i, measured into clbit i; outcomes are shown in C7 order",
    )
    stats = MeasurementStats(
        expected_outcome=_bitstring(expected),
        analytic_distribution=[OutcomeProbability(outcome=_bitstring(k), probability=v) for k, v in ranked[:TOP_K]],
        analytic_truncated=len(ranked) > TOP_K,
        analytic_method=dist_method,
        aer_counts=aer_counts,
        shots=req.shots if req.backend == "aer" else None,
        acceptance=acceptance,
    )
    return MintResponse(
        status="OK",
        evidence_kind=kind,
        provenance=provenance(
            "qmint.quantum (lane F): bb84, circuits, channels",
            seed=req.seed,
            quantum=True,
            notes="hypothetical noise parameters" if not spec.is_ideal else None,
        ),
        data=MintData(token=token, issuer_view=issuer, circuit=circuit, statistics=stats, simulator_caveat=SIM_CAVEAT),
    )


# --------------------------------------------------------------------------- #
# Attack (DEMO_ADAPTER)
# --------------------------------------------------------------------------- #

AttackName = Literal["honest", "measure_resend", "bruss_cloner", "mvw_channel"]
_CLONER: dict[str, cloner.ClonerName] = {"bruss_cloner": "bruss2000", "mvw_channel": "mvw2012"}
_STATES = [(Basis.Z, 0), (Basis.Z, 1), (Basis.X, 0), (Basis.X, 1)]


class AttackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    protocol_id: Literal["wiesner_ideal"] = "wiesner_ideal"
    game: Literal["W1"] = "W1"
    attack: AttackName = "mvw_channel"
    n: int = Field(default=1, ge=1, le=bb84.MAX_STATEVECTOR_QUBITS)
    seed: int = Field(default=42, ge=0, le=2**31 - 1)
    backend: Literal["analytic", "aer"] = "analytic"
    shots: int = Field(default=2000, ge=1, le=20000)
    noise: NoiseIn | None = None


class AttackData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attack: AttackName
    attack_label: str
    description: str
    honest_acceptance: list[Quantity]
    single_verification_pass: Quantity
    double_verification_success: list[Quantity]
    theorem_bound: Quantity
    attack_result: AttackResult | None
    assumptions: list[str]
    notes: list[str]


class AttackResponse(Envelope):
    data: AttackData


def measure_resend_per_qubit() -> tuple[float, float]:
    """Exact (single-copy pass, both-copies pass) per qubit for random-basis measure-and-prepare-twice.

    Enumerates secret state, attacker basis (uniform) and attacker outcome with Born probabilities
    from Bloch overlaps; the attacker prepares two copies of the post-measurement state.
    """
    single = both = 0.0
    for b, x in _STATES:
        secret = bb84.state_label(b, x)
        for mb in (Basis.Z, Basis.X):
            for o in (0, 1):
                guess = bb84.state_label(mb, o)
                p_out = bb84.overlap_squared(secret, guess)
                p_pass = bb84.overlap_squared(guess, secret)
                w = 0.25 * 0.5 * p_out
                single += w * p_pass
                both += w * p_pass * p_pass
    return single, both


def cloner_single_copy_pass(name: cloner.ClonerName) -> float:
    """Average over BB84 states of P(copy 1 passes), from the cloner's Kraus operators."""
    total = 0.0
    for b, x in _STATES:
        psi = bb84.state_vector(b, x)
        for k in cloner.cloner_kraus(name):
            m = (k @ psi).reshape(2, 2)  # [copy1, copy2]
            total += float(np.sum(np.abs(psi.conj() @ m) ** 2))
    return total / 4.0


def _theorem(n: int) -> Quantity:
    return Quantity(
        id="w1_theorem_bound",
        label="W1 published upper bound (any counterfeiter)",
        value=float(cloner.W1_OPTIMAL_PER_QUBIT) ** n,
        unit=Unit.PROBABILITY,
        evidence_kind=EvidenceKind.PUBLISHED_THEOREM,
        method="closed_form",
        source=MVW2012,
        formula=GAMES[GameId.W1].formula,
        note=TRANSCRIPTION_NOTE + "; ideal noiseless W1 game only",
    )


@router.post("/attack", response_model=AttackResponse)
async def attack(req: AttackRequest) -> AttackResponse:
    return await _on_quantum_thread(run_attack, req)


def run_attack(req: AttackRequest) -> AttackResponse:
    spec = noise_spec(req.noise)
    n = req.n
    bases, bits = _note(n, req.seed, f"demo-attack-n{n}-s{req.seed}")
    kind = _sim_kind(spec)
    notes: list[str] = []
    assumptions = [
        "game W1: one note, the counterfeiter returns two registers, the bank verifies both in the secret bases",
        "per-qubit independent attacks; n-qubit values are products of per-qubit values",
    ]

    honest = [
        Quantity(
            id="honest_accept_mean",
            label="Honest acceptance (random note, closed form)",
            value=analytic_mean_accept_probability(spec, n),
            unit=Unit.PROBABILITY,
            evidence_kind=kind,
            method="closed_form",
            source="qmint.quantum.channels.analytic_mean_accept_probability",
            formula="(mean per-qubit pass probability)^n",
            note=None if spec.is_ideal else spec.describe(),
        )
    ]
    if req.backend == "aer":
        qc = circuits.build_verify_circuit(bases, bits, noise=None if spec.channel == "none" else spec)
        counts, _prov, _ = circuits.run_aer(qc, shots=req.shots, seed=req.seed, noise=spec)
        acc = circuits.accepted_shots(counts, bits)
        honest.append(
            Quantity(
                id="honest_accept_note_aer",
                label="Honest acceptance of the seeded note (Aer shots)",
                value=acc / req.shots,
                unit=Unit.PROBABILITY,
                evidence_kind=kind,
                method="aer_sampling",
                interval=ci_from_interval(clopper_pearson(acc, req.shots, CONFIDENCE), CONFIDENCE,
                                          f"clopper_pearson_{CONFIDENCE}"),
                source="qmint.quantum.circuits.run_aer (local AerSimulator)",
                note=f"closed form for this note: {analytic_note_accept_probability(spec, bases, bits):.6g}",
            )
        )
    if not spec.is_ideal:
        notes.append(
            "Declared noise affects the honest verifier only. The W1 bound and the attack values assume the "
            "ideal noiseless game; noisy/threshold verification is game W2 (no closed form)."
        )

    attack_result: AttackResult | None = None
    double: list[Quantity] = []
    ideal = EvidenceKind.SIMULATOR_IDEAL
    if req.attack == "honest":
        label = "no_counterfeiter"
        description = "Honest holder: the bank verifies the genuine note once. No counterfeiting attempt."
        single = honest[0].model_copy(update={"id": "single_verification_pass",
                                              "label": "Single verification pass (honest note)"})
        double.append(
            Quantity(
                id="double_verification_success",
                label="Both verifications pass",
                value=None,
                unit=Unit.PROBABILITY,
                evidence_kind=EvidenceKind.UNCERTIFIED,
                method="not_available",
                source="qmint.api.routes.lab",
                note="not applicable: there is only one genuine note and no counterfeiter",
            )
        )
    elif req.attack == "measure_resend":
        label = "heuristic_measure_resend"
        description = (
            "Measure each qubit in a uniformly random BB84 basis, then prepare two copies of the observed state."
        )
        s1, s2 = measure_resend_per_qubit()
        single = Quantity(
            id="single_verification_pass", label="One counterfeit passes", value=s1**n, unit=Unit.PROBABILITY,
            evidence_kind=ideal, method="exact_enumeration",
            source="qmint.api.routes.lab.measure_resend_per_qubit (bb84.overlap_squared)",
            formula="(3/4)^n", note="exact model value for this attack",
        )
        double.append(
            Quantity(
                id="double_verification_success", label="Both counterfeits pass", value=s2**n,
                unit=Unit.PROBABILITY, evidence_kind=ideal, method="exact_enumeration",
                source="qmint.api.routes.lab.measure_resend_per_qubit (bb84.overlap_squared)",
                formula="(5/8)^n  [per qubit: 1/2*1 + 1/2*(1/2)^2]", note=LOWER_BOUND_NOTE,
            )
        )
        if req.backend == "aer":
            notes.append("No Aer run for measure_resend in this adapter; exact enumeration only.")
    else:
        name = _CLONER[req.attack]
        label = cloner.attack_label(name)
        description = (
            "Bruss et al. 2000 optimal phase-covariant 1->2 cloner applied to every qubit (maximises single-copy "
            "fidelity, not the W1 figure of merit)."
            if name == "bruss2000"
            else "MVW 2012 Sec. 3.2 optimal counterfeiting channel (Stinespring circuit) applied to every qubit."
        )
        per_single = cloner_single_copy_pass(name)
        single = Quantity(
            id="single_verification_pass", label="One counterfeit passes", value=per_single**n,
            unit=Unit.PROBABILITY, evidence_kind=ideal, method="exact_enumeration",
            source="qmint.quantum.cloner.cloner_kraus", formula="(avg_psi <psi|Tr_2 Phi(psi)|psi>)^n",
        )
        double.append(
            Quantity(
                id="double_verification_success", label="Both counterfeits pass (exact)",
                value=cloner.analytic_both_pass(name, n), unit=Unit.PROBABILITY, evidence_kind=ideal,
                method="exact_enumeration", source="qmint.quantum.cloner.analytic_both_pass",
                formula="((3+2*sqrt(2))/8)^n" if name == "bruss2000" else "(3/4)^n  [exact rational per qubit]",
                note=LOWER_BOUND_NOTE,
            )
        )
        if req.backend == "aer":
            if 3 * n > bb84.MAX_STATEVECTOR_QUBITS:
                notes.append(f"Aer cloning circuit needs 3n={3 * n} qubits > 8; only n<=2 is simulated.")
            else:
                n_notes = 4
                attack_result = cloner.simulate_attack(
                    name, n, n_notes=n_notes, shots_per_note=max(1, req.shots // n_notes), seed=req.seed,
                    source_code_sha=git_sha(), confidence=CONFIDENCE,
                )
                ci = attack_result.success_rate_ci
                assert ci is not None
                double.append(
                    Quantity(
                        id="double_verification_success_aer", label="Both counterfeits pass (Aer shots)",
                        value=attack_result.successes / attack_result.trials, unit=Unit.PROBABILITY,
                        evidence_kind=attack_result.evidence_kind, method="aer_sampling",
                        interval=ci_from_interval(ci, CONFIDENCE, attack_result.ci_method or "clopper_pearson"),
                        source="qmint.quantum.cloner.simulate_attack (local AerSimulator)",
                        note=f"{attack_result.successes}/{attack_result.trials} shots over {n_notes} random notes; "
                        + LOWER_BOUND_NOTE,
                    )
                )

    return AttackResponse(
        status="DEMO_ADAPTER",
        evidence_kind=ideal,
        reason="lane C (attack suites) not merged: values come from lane-F cloner circuits, exact enumeration "
        "and the published W1 bound",
        provenance=provenance("qmint.quantum.cloner + qmint.api.routes.lab", seed=req.seed, quantum=True),
        data=AttackData(
            attack=req.attack,
            attack_label=label,
            description=description,
            honest_acceptance=honest,
            single_verification_pass=single,
            double_verification_success=double,
            theorem_bound=_theorem(n),
            attack_result=attack_result,
            assumptions=assumptions,
            notes=notes,
        ),
    )
