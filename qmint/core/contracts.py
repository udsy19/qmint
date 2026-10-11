"""Frozen integration contracts C0-C7 (schema_version 1.0.0).

FROZEN at the bootstrap commit. Lead-owned. Any change is a versioned migration
(`schemas/v2/`), never an in-place edit. See project/CONTRACTS.md for prose.

Design rules encoded here (master plan section 5):
  * Unavailable security bounds are ``None`` -- never ``0``.
  * ``SecurityCertificate`` defaults to ``UNCERTIFIED``; ``CERTIFIED`` is only
    constructible when every target has a non-null bound <= target, assumptions
    are met, a proof reference exists and evidence hashes are present.
  * ``IssuerSecret`` lives in a separate security domain: it refuses ordinary
    serialization and redacts its repr. Controlled revelation is TEST_ONLY.
  * Probabilities are in [0, 1]; physical quantities carry explicit units.
  * Evidence kind, proof status and claim level are required enumerations.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_serializer,
    model_validator,
)

SCHEMA_VERSION = "1.0.0"


# --------------------------------------------------------------------------- #
# C7 -- frozen conventions: enumerations and unit-carrying scalar types
# --------------------------------------------------------------------------- #


class Basis(str, Enum):
    """BB84 basis. Z: {|0>,|1>}; X: {|+>,|->}. Never inferred from Qiskit bit order."""

    Z = "Z"
    X = "X"


class BB84State(str, Enum):
    """Explicit BB84 preparation labels (C7). (basis, bit) -> state is fixed below."""

    ZERO = "0"  # Z, bit 0
    ONE = "1"  # Z, bit 1
    PLUS = "+"  # X, bit 0
    MINUS = "-"  # X, bit 1


BB84_STATE_OF: dict[tuple[Basis, int], BB84State] = {
    (Basis.Z, 0): BB84State.ZERO,
    (Basis.Z, 1): BB84State.ONE,
    (Basis.X, 0): BB84State.PLUS,
    (Basis.X, 1): BB84State.MINUS,
}

Bit = Literal[0, 1]


class EvidenceKind(str, Enum):
    """What kind of evidence a number is. Never interchangeable."""

    PUBLISHED_THEOREM = "PUBLISHED_THEOREM"  # bound transcribed from a peer-reviewed proof
    NUMERICAL_SDP = "NUMERICAL_SDP"  # floating-point solver output, not a proof
    CERTIFIED_NUMERIC = "CERTIFIED_NUMERIC"  # numeric bound with rigorous residual accounting
    MONTE_CARLO = "MONTE_CARLO"  # attack success estimate: a LOWER bound on worst case
    PHOTON_EXPERIMENT = "PHOTON_EXPERIMENT"  # real recorded photon events (e.g. Zenodo 7979319)
    PUBLISHED_AGGREGATE = "PUBLISHED_AGGREGATE"  # number quoted in a paper table/text
    DIGITIZED_FIGURE = "DIGITIZED_FIGURE"  # read off a published figure, with digitization error
    SYNTHETIC = "SYNTHETIC"  # generated fixture / hypothetical scenario
    SIMULATOR_IDEAL = "SIMULATOR_IDEAL"  # noiseless circuit/statevector simulation
    SIMULATOR_NOISY = "SIMULATOR_NOISY"  # simulation under a declared noise model
    QPU = "QPU"  # actual quantum hardware job with job id
    MODELLED_LATENCY = "MODELLED_LATENCY"  # latency from a model (light-cone, queue model)
    MEASURED_LATENCY = "MEASURED_LATENCY"  # latency from real measurements (e.g. RIPE Atlas)
    UNCERTIFIED = "UNCERTIFIED"  # no applicable evidence


class ProofStatus(str, Enum):
    """Status of a proof obligation / bound (master plan 3.6)."""

    PUBLISHED_REPRODUCED = "PUBLISHED_REPRODUCED"
    NUMERICALLY_SUPPORTED = "NUMERICALLY_SUPPORTED"
    CERTIFIED_NUMERIC = "CERTIFIED_NUMERIC"
    CONJECTURE = "CONJECTURE"
    UNSUPPORTED = "UNSUPPORTED"


class CertificateStatus(str, Enum):
    CERTIFIED = "CERTIFIED"  # every target met by an applicable, checked bound
    UNCERTIFIED = "UNCERTIFIED"  # default; missing bound/assumption/check
    INFEASIBLE = "INFEASIBLE"  # applicable bounds exist but targets cannot be met
    UNSAFE = "UNSAFE"  # an attack exceeds the claimed bound / targets
    OUT_OF_MODEL = "OUT_OF_MODEL"  # request violates the proof's trust/physical model


class ClaimLevel(str, Enum):
    """Research claims hierarchy (master plan 4.6)."""

    L0 = "L0"  # pipeline compiles, test vectors pass
    L1 = "L1"  # independent reproduction of published results
    L2 = "L2"  # measured resource improvement under explicit published bound
    L3 = "L3"  # modeled communication advantage in defined deployment scenarios
    L4 = "L4"  # experimental security evidence for a physical implementation
    L5 = "L5"  # deployment-grade (out of scope)


class StateKind(str, Enum):
    PHYSICAL_QUANTUM = "physical_quantum"
    IDEAL_SIMULATED = "ideal_simulated"
    NOISY_SIMULATED = "noisy_simulated"
    SYMBOLIC_RECORD = "symbolic_record"
    MEASURED_CLASSICAL_TRANSCRIPT = "measured_classical_transcript"


class GameId(str, Enum):
    """Named, versioned security experiments (master plan 3.1)."""

    W1 = "W1"  # Wiesner simple 1->2 counterfeiting, exact verifier (MVW 2012): (3/4)^n
    W1_CV = "W1_CV"  # MVW 2012 distinct classical-verification variant: (3/4+sqrt2/8)^n
    W2 = "W2"  # noisy/threshold Wiesner -- NO published closed form assumed
    S1 = "S1"  # ideal two-site S-token (Kent et al. 2022): (1/2+1/(2sqrt2))^N
    S2 = "S2"  # realistic noisy/lossy S-token (Kent et al. 2022 finite-size)
    D1 = "D1"  # 2023 quantum-digital payment cryptogram (Schiansky et al.)
    A1 = "A1"  # anonymity / issuer tracking (Gavinsky et al. 2025)
    C1 = "C1"  # classical double-spend systems game


class SecurityAxis(str, Enum):
    UNFORGEABILITY = "epsilon_unf"
    CORRECTNESS = "epsilon_cor"
    ROBUSTNESS = "epsilon_rob"
    PRIVACY = "epsilon_priv"


class TopologySource(str, Enum):
    PAPER = "paper"
    MEASURED_RIPE = "measured_ripe"
    SYNTHETIC = "synthetic"


# Registered protocol identifiers and the ONLY games each may be scored under.
# Adding a protocol is a contract migration.
PROTOCOL_GAMES: dict[str, frozenset[GameId]] = {
    "wiesner_ideal": frozenset({GameId.W1, GameId.W1_CV}),
    "wiesner_noisy": frozenset({GameId.W2}),
    "s_money_kent_2022_ideal_2site": frozenset({GameId.S1}),
    "s_money_kent_2022_realistic": frozenset({GameId.S2}),
    "schiansky_payment_2023": frozenset({GameId.D1}),
    "gavinsky_anon_2025": frozenset({GameId.A1}),
    "classical_h0_bearer": frozenset({GameId.C1}),
    "classical_h1_online_ledger": frozenset({GameId.C1}),
    "classical_h2_quorum": frozenset({GameId.C1}),
    "classical_h3_preallocated_escrow": frozenset({GameId.C1}),
    "classical_h4_pqc_signed": frozenset({GameId.C1}),
    "classical_h5_secure_hardware": frozenset({GameId.C1}),
    "classical_h6_anonymous_ecash": frozenset({GameId.C1}),
}

QUANTUM_PROTOCOLS = frozenset(p for p in PROTOCOL_GAMES if not p.startswith("classical_"))


def check_protocol_game(protocol_id: str, game_id: GameId | str) -> None:
    """Raise ValueError if `game_id` is not a registered game for `protocol_id`."""
    if protocol_id not in PROTOCOL_GAMES:
        raise ValueError(f"unregistered protocol_id {protocol_id!r}")
    g = GameId(game_id)
    if g not in PROTOCOL_GAMES[protocol_id]:
        raise ValueError(
            f"game {g.value} is not a registered game for protocol {protocol_id!r}; "
            f"allowed: {sorted(x.value for x in PROTOCOL_GAMES[protocol_id])}"
        )


def _finite(v: float) -> float:
    if not math.isfinite(v):
        raise ValueError("value must be finite")
    return v


Probability = Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]
NonNegFloat = Annotated[float, Field(ge=0.0, allow_inf_nan=False)]
NonNegInt = Annotated[int, Field(ge=0)]
PosInt = Annotated[int, Field(ge=1)]
Sha256Hex = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class Unit(str, Enum):
    """Canonical units. Fractions/probabilities are dimensionless in [0,1], never percent."""

    FRACTION = "fraction"
    PROBABILITY = "probability"
    NANOSECOND = "ns"
    SECOND = "s"
    METER = "m"
    KILOMETER = "km"
    DECIBEL = "dB"
    COUNT = "count"
    HERTZ = "Hz"
    BYTE = "byte"


class Interval(BaseModel):
    """Closed interval [lo, hi] with explicit unit and (optional) confidence semantics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lo: float = Field(allow_inf_nan=False)
    hi: float = Field(allow_inf_nan=False)
    unit: Unit
    point: float | None = Field(default=None, allow_inf_nan=False)

    @model_validator(mode="after")
    def _ordered(self) -> Interval:
        if self.lo > self.hi:
            raise ValueError("interval lo > hi")
        if self.point is not None and not (self.lo <= self.point <= self.hi):
            raise ValueError("point estimate outside interval")
        if self.unit in (Unit.FRACTION, Unit.PROBABILITY) and not (0.0 <= self.lo and self.hi <= 1.0):
            raise ValueError("fraction/probability interval must lie in [0,1]")
        return self


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, use_enum_values=False)


# --------------------------------------------------------------------------- #
# C0 -- ProtocolSpec
# --------------------------------------------------------------------------- #


class ProtocolSpec(_Strict):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    protocol_id: str
    source_paper_id: str = Field(min_length=1)  # e.g. "P03" (research/PRIOR_ART_MATRIX.csv)
    theorem_id: str | None = None  # e.g. "P-S1" (proofs/OBLIGATIONS.yaml); None = no theorem
    protocol_revision: str = Field(min_length=1)
    issuer_trust: Literal["honest_bank", "honest_but_curious", "malicious", "not_applicable"]
    same_party_agent_trust: Literal["trusted", "untrusted", "not_applicable"]
    redemption_semantics: str = Field(min_length=1)
    quantum_stage: str = Field(min_length=1)
    quantum_memory_required: bool
    classical_authentication: str = Field(min_length=1)
    adversary_game_id: GameId
    security_model_id: str = Field(min_length=1)
    correctness_conditions: list[str] = Field(default_factory=list)
    proof_assumptions: list[str] = Field(default_factory=list)
    unsupported_extensions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _game_registered(self) -> ProtocolSpec:
        check_protocol_game(self.protocol_id, self.adversary_game_id)
        return self


# --------------------------------------------------------------------------- #
# C1 -- TokenRecord (public) and IssuerSecret (private domain)
# --------------------------------------------------------------------------- #


class SecretBoundaryError(RuntimeError):
    """Raised when issuer-secret material would cross into a public/adversary domain."""


_FORBIDDEN_PUBLIC_KEYS = frozenset(
    {"basis", "bases", "bits", "secret", "secret_bases", "secret_bits", "outcomes", "key", "verifier_key"}
)


class TokenRecord(_Strict):
    """Public, wallet-side token record. MUST NOT contain bases, bits or verifier secrets."""

    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    token_id: str = Field(min_length=1)
    protocol_id: str
    n_prepared: PosInt
    commitment_time_utc_ns: int | None = None
    source_state_family: str = Field(min_length=1)  # e.g. "BB84"
    public_metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    issue_event_id: str = Field(min_length=1)
    state_kind: StateKind
    freshness: Literal["fresh", "spent", "verified_reminted", "unknown"] = "fresh"
    ownership_context: str = Field(min_length=1)
    backend_provenance: str = Field(min_length=1)

    @field_validator("protocol_id")
    @classmethod
    def _registered(cls, v: str) -> str:
        if v not in PROTOCOL_GAMES:
            raise ValueError(f"unregistered protocol_id {v!r}")
        return v

    @field_validator("public_metadata")
    @classmethod
    def _no_secret_keys(cls, v: dict[str, Any]) -> dict[str, Any]:
        bad = {k for k in v if k.lower() in _FORBIDDEN_PUBLIC_KEYS or "secret" in k.lower()}
        if bad:
            raise SecretBoundaryError(f"public_metadata contains secret-like keys: {sorted(bad)}")
        return v


class IssuerSecret(_Strict):
    """Issuer-private verification material. Separate security domain (C1).

    * ``repr``/``str`` are redacted.
    * ``model_dump``/``model_dump_json`` raise ``SecretBoundaryError``.
    * ``qmint.core.serialization.canonical_json`` refuses any object containing it.
    * Tests may call ``reveal_for_testing_only()`` which returns a dict tagged TEST_ONLY.
    """

    token_id: str = Field(min_length=1)
    protocol_id: str
    bases: list[Basis] = Field(default_factory=list)
    bits: list[int] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)  # protocol-specific private data

    @model_validator(mode="after")
    def _shape(self) -> IssuerSecret:
        if self.bases and self.bits and len(self.bases) != len(self.bits):
            raise ValueError("bases and bits length mismatch")
        if any(b not in (0, 1) for b in self.bits):
            raise ValueError("bits must be 0/1")
        return self

    def __repr__(self) -> str:  # noqa: D105
        return f"IssuerSecret(token_id={self.token_id!r}, protocol_id={self.protocol_id!r}, <REDACTED>)"

    __str__ = __repr__

    def model_dump(self, *a: Any, **k: Any) -> dict[str, Any]:  # type: ignore[override]
        raise SecretBoundaryError("IssuerSecret cannot be serialized; use reveal_for_testing_only() in tests")

    def model_dump_json(self, *a: Any, **k: Any) -> str:  # type: ignore[override]
        raise SecretBoundaryError("IssuerSecret cannot be serialized")

    def __getstate__(self) -> Any:
        raise SecretBoundaryError("IssuerSecret cannot be pickled")

    @model_serializer(mode="plain")
    def _refuse_serialization(self) -> Any:
        # Fires when pydantic serializes a parent model holding this secret in an Any field.
        raise SecretBoundaryError("IssuerSecret cannot be serialized (nested in a parent model)")

    def reveal_for_testing_only(self) -> dict[str, Any]:
        """Controlled TEST_ONLY revelation. Any attack given this output is OUT_OF_MODEL."""
        return {
            "TEST_ONLY": True,
            "token_id": self.token_id,
            "protocol_id": self.protocol_id,
            "bases": [b.value for b in self.bases],
            "bits": list(self.bits),
            "extra": dict(self.extra),
        }


# --------------------------------------------------------------------------- #
# C2 -- MeasurementEvent, PhotonEvent, CalibrationRecord
# --------------------------------------------------------------------------- #


class MeasurementEvent(_Strict):
    event_id: str = Field(min_length=1)
    token_id: str = Field(min_length=1)
    site_id: str = Field(min_length=1)
    clock_id: str = Field(min_length=1)
    event_time_utc_ns: int
    timestamp_accuracy_ns: NonNegFloat
    causal_parent_ids: list[str] = Field(default_factory=list)
    basis: Basis | None = None
    outcome: int | None = None
    valid: bool
    shots: NonNegInt | None = None
    backend: str = Field(min_length=1)
    job_id: str | None = None
    source_kind: EvidenceKind
    noise_model: str | None = None

    @field_validator("outcome")
    @classmethod
    def _bit(cls, v: int | None) -> int | None:
        if v is not None and v not in (0, 1):
            raise ValueError("outcome must be 0/1 or None")
        return v


class PhotonEvent(_Strict):
    dataset_id: str = Field(min_length=1)  # e.g. "zenodo:7979319"
    file_hash: Sha256Hex
    record_index: NonNegInt
    raw_channel: NonNegInt
    arrival_ns: float = Field(allow_inf_nan=False)
    channel_mapping_version: str = Field(min_length=1)
    coincidence_id: str | None = None
    decode_status: Literal["ok", "malformed", "duplicate", "out_of_range"]


class CalibrationRecord(_Strict):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    calibration_id: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    experiment_family: str = Field(min_length=1)  # e.g. "schiansky_2023"; consumers must match
    data_origin: EvidenceKind
    dataset_sha256: Sha256Hex | None = None
    time_start_ns: float | None = None
    time_end_ns: float | None = None
    n_events: NonNegInt
    detection_efficiency_interval: Interval | None = None
    qber_interval: Interval | None = None
    loss_interval: Interval | None = None
    multiphoton_interval: Interval | None = None
    basis_bias_interval: Interval | None = None
    clock_drift_interval: Interval | None = None
    confidence_level: Probability
    interval_method: str = Field(min_length=1)  # e.g. "clopper_pearson", "block_bootstrap"
    independence_assumptions: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _provenance(self) -> CalibrationRecord:
        if self.data_origin == EvidenceKind.PHOTON_EXPERIMENT and self.dataset_sha256 is None:
            raise ValueError("PHOTON_EXPERIMENT calibration requires dataset_sha256")
        return self


# --------------------------------------------------------------------------- #
# C3 -- AttackResult
# --------------------------------------------------------------------------- #


class AttackResult(_Strict):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    attack_id: str = Field(min_length=1)  # e.g. "A01_measure_resend"
    game_id: GameId
    attack_capability: list[str] = Field(min_length=1)
    token_n: PosInt
    attack_method: str = Field(min_length=1)
    quantum_channel_description: str = Field(min_length=1)
    verifier_rule: str = Field(min_length=1)
    seed: int | None = None
    trials: NonNegInt
    successes: NonNegInt
    success_rate_ci: Interval | None = None
    ci_method: str | None = None
    sdp_primal: float | None = Field(default=None, allow_inf_nan=False)
    sdp_dual: float | None = Field(default=None, allow_inf_nan=False)
    dual_feasibility_residual: float | None = Field(default=None, allow_inf_nan=False)
    primal_feasibility_residual: float | None = Field(default=None, allow_inf_nan=False)
    solver: str | None = None
    proof_applicability: Literal["IN_MODEL", "OUT_OF_MODEL", "NO_THEOREM"]
    theorem_upper_bound: Probability | None = None
    backend_kind: str = Field(min_length=1)
    evidence_kind: EvidenceKind
    source_code_sha: str = Field(min_length=1)

    @model_validator(mode="after")
    def _consistency(self) -> AttackResult:
        if self.successes > self.trials:
            raise ValueError("successes > trials")
        if self.trials > 0 and self.success_rate_ci is None:
            raise ValueError("Monte Carlo trials require success_rate_ci")
        if self.evidence_kind == EvidenceKind.MONTE_CARLO and self.trials == 0:
            raise ValueError("MONTE_CARLO evidence requires trials > 0")
        if self.evidence_kind in (EvidenceKind.NUMERICAL_SDP, EvidenceKind.CERTIFIED_NUMERIC):
            if self.sdp_primal is None or self.sdp_dual is None or self.dual_feasibility_residual is None:
                raise ValueError("SDP evidence requires sdp_primal, sdp_dual and dual_feasibility_residual")
        return self


# --------------------------------------------------------------------------- #
# C4 -- SpacetimeNetwork and TransactionTrace
# --------------------------------------------------------------------------- #


class Site(_Strict):
    site_id: str = Field(min_length=1)
    frame: str = Field(min_length=1)  # declared metric/frame, e.g. "earth_fixed_inertial_approx"
    x_m: float = Field(allow_inf_nan=False)
    y_m: float = Field(allow_inf_nan=False)
    z_m: float = Field(default=0.0, allow_inf_nan=False)
    trust_domain: str = Field(min_length=1)
    clock_error_bound_ns: NonNegFloat


class Link(_Strict):
    src: str
    dst: str
    propagation_lower_bound_ns: NonNegFloat  # physics (light-cone) or declared lower bound
    latency_model: str = Field(min_length=1)  # e.g. "lightcone", "fiber_2/3c", "ripe:<msm_id>"
    latency_evidence: EvidenceKind
    authenticated: bool
    message_cost_bytes: NonNegInt = 0


class SpacetimeNetwork(_Strict):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    network_id: str = Field(min_length=1)
    topology_source: TopologySource
    sites: list[Site] = Field(min_length=1)
    links: list[Link] = Field(default_factory=list)
    event_queue_policy: str = "fifo"

    @model_validator(mode="after")
    def _links_ref_sites(self) -> SpacetimeNetwork:
        ids = {s.site_id for s in self.sites}
        if len(ids) != len(self.sites):
            raise ValueError("duplicate site_id")
        for lk in self.links:
            if lk.src not in ids or lk.dst not in ids:
                raise ValueError(f"link {lk.src}->{lk.dst} references unknown site")
        return self


class TraceEvent(_Strict):
    event_id: str = Field(min_length=1)
    site_id: str = Field(min_length=1)
    kind: Literal[
        "issue",
        "quantum_exchange",
        "measurement",
        "commitment",
        "branch_choice",
        "message_send",
        "message_receive",
        "local_validation_start",
        "verification_result_available_local",
        "issuer_aware_of_spend",
        "bank_settlement_final",
        "merchant_funds_irrevocable",
        "buyer_receipt",
        "reject",
        "privacy_reveal",
        "other",
    ]
    time_ns: float = Field(allow_inf_nan=False)
    causal_parent_ids: list[str] = Field(default_factory=list)
    message_id: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


class TransactionTrace(_Strict):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    trace_id: str = Field(min_length=1)
    token_id: str = Field(min_length=1)
    protocol_id: str
    network_id: str = Field(min_length=1)
    events: list[TraceEvent] = Field(min_length=1)
    irrevocability_rule: str = Field(min_length=1)
    double_spend_accepted: bool
    latency_breakdown_ns: dict[str, float] = Field(default_factory=dict)
    latency_evidence: EvidenceKind

    @model_validator(mode="after")
    def _dag(self) -> TransactionTrace:
        by_id = {e.event_id: e for e in self.events}
        if len(by_id) != len(self.events):
            raise ValueError("duplicate event_id")
        for e in self.events:
            for p in e.causal_parent_ids:
                if p not in by_id:
                    raise ValueError(f"event {e.event_id} has unknown parent {p}")
                if by_id[p].time_ns > e.time_ns:
                    raise ValueError(f"retrocausal edge {p}->{e.event_id}")
        return self


# --------------------------------------------------------------------------- #
# C5 -- SecurityCertificate (+ proof-evaluator request/response)
# --------------------------------------------------------------------------- #


class UpperBounds(_Strict):
    epsilon_unf: Probability | None = None
    epsilon_cor: Probability | None = None
    epsilon_rob: Probability | None = None
    epsilon_priv: Probability | None = None


class Targets(_Strict):
    epsilon_unf: Probability | None = None
    epsilon_cor: Probability | None = None
    epsilon_rob: Probability | None = None
    epsilon_priv: Probability | None = None


class SecurityCertificate(_Strict):
    certificate_version: Literal["1.0.0"] = SCHEMA_VERSION
    protocol_id: str
    game_id: GameId
    security_model_id: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    upper_bounds: UpperBounds = Field(default_factory=UpperBounds)
    log10_upper_bounds: dict[str, float] = Field(default_factory=dict)  # for bounds below float range
    targets: Targets = Field(default_factory=Targets)
    assumptions_met: bool = False
    failed_assumptions: list[str] = Field(default_factory=list)
    proof_reference: str | None = None
    proof_check_status: CertificateStatus = CertificateStatus.UNCERTIFIED
    checker_id: str | None = None  # independent checker that re-derived every bound
    evidence_kind: EvidenceKind = EvidenceKind.UNCERTIFIED
    claim_level: ClaimLevel = ClaimLevel.L0
    reason: str = Field(min_length=1)
    calibration_id: str | None = None
    software_revision: str | None = None
    evidence_hashes: list[Sha256Hex] = Field(default_factory=list)

    @model_validator(mode="after")
    def _certified_requires_everything(self) -> SecurityCertificate:
        check_protocol_game(self.protocol_id, self.game_id)
        if self.proof_check_status != CertificateStatus.CERTIFIED:
            return self
        missing: list[str] = []
        if not self.assumptions_met or self.failed_assumptions:
            missing.append("assumptions_met")
        if not self.proof_reference:
            missing.append("proof_reference")
        if not self.checker_id:
            missing.append("checker_id")
        if not self.evidence_hashes:
            missing.append("evidence_hashes")
        if self.evidence_kind not in (EvidenceKind.PUBLISHED_THEOREM, EvidenceKind.CERTIFIED_NUMERIC):
            missing.append("evidence_kind must be PUBLISHED_THEOREM or CERTIFIED_NUMERIC")
        tdict = self.targets.model_dump()
        if all(v is None for v in tdict.values()):
            missing.append("at least one target")
        for axis, target in tdict.items():
            if target is None:
                continue
            bound = getattr(self.upper_bounds, axis)
            lb = self.log10_upper_bounds.get(axis)
            if bound is None and lb is None:
                missing.append(f"bound for {axis}")
            elif lb is not None and target > 0 and lb > math.log10(target):
                missing.append(f"{axis} log-bound exceeds target")
            elif bound is not None and bound > target:
                missing.append(f"{axis} bound exceeds target")
        if missing:
            raise ValueError(f"CERTIFIED status not justified: {missing}")
        return self


class BoundRequest(_Strict):
    """Input to a ProofEvaluator (qmint.core.interfaces)."""

    protocol_id: str
    game_id: GameId
    axis: SecurityAxis
    parameters: dict[str, Any] = Field(default_factory=dict)
    calibration: CalibrationRecord | None = None

    @model_validator(mode="after")
    def _registered(self) -> BoundRequest:
        check_protocol_game(self.protocol_id, self.game_id)
        return self


class BoundResult(_Strict):
    """Output of a ProofEvaluator. ``value is None`` means no applicable bound (never 0)."""

    protocol_id: str
    game_id: GameId
    axis: SecurityAxis
    value: Probability | None = None
    log10_value: float | None = Field(default=None, allow_inf_nan=False)
    status: ProofStatus
    theorem_id: str | None = None
    evidence_kind: EvidenceKind
    assumptions_checked: list[str] = Field(default_factory=list)
    failed_assumptions: list[str] = Field(default_factory=list)
    out_of_domain: bool = False
    notes: str = ""

    @model_validator(mode="after")
    def _no_free_bounds(self) -> BoundResult:
        has_bound = self.value is not None or self.log10_value is not None
        if has_bound and self.status == ProofStatus.UNSUPPORTED:
            raise ValueError("UNSUPPORTED result must not carry a bound value")
        if has_bound and (self.out_of_domain or self.failed_assumptions):
            raise ValueError("out-of-domain / failed-assumption result must not carry a bound value")
        if has_bound and not self.theorem_id:
            raise ValueError("a bound value requires a theorem_id")
        if self.log10_value is not None and self.log10_value > 0:
            raise ValueError("log10 of a probability bound must be <= 0")
        return self


# --------------------------------------------------------------------------- #
# C6 -- BenchmarkRecord and EvidenceManifest
# --------------------------------------------------------------------------- #


class BenchmarkRecord(_Strict):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    record_id: str = Field(min_length=1)
    protocol_id: str
    classical_or_quantum: Literal["classical", "quantum"]
    security_target: Targets
    trust_model: str = Field(min_length=1)
    pre_distribution: str = Field(min_length=1)
    spending_flexibility: Literal["late_choice_any_site", "preassigned_site", "online_any_site", "none"]
    privacy_game: str = Field(min_length=1)  # "none" if no privacy claim
    network_id: str = Field(min_length=1)
    site_count: PosInt
    issue_seconds: NonNegFloat | None = None
    redemption_local_seconds: NonNegFloat | None = None
    network_cross_check_seconds: NonNegFloat | None = None
    total_setup_cost: NonNegFloat | None = None
    photons_prepared: NonNegInt | None = None
    photons_detected: NonNegInt | None = None
    classical_bytes: NonNegInt | None = None
    issuer_calls: NonNegInt | None = None
    false_rejects: NonNegInt | None = None
    double_spends_successful: NonNegInt | None = None
    numerical_ci: dict[str, Interval] = Field(default_factory=dict)
    run_repetition: NonNegInt = 0
    method: str = Field(min_length=1)
    configuration: dict[str, Any] = Field(default_factory=dict)
    evidence_kind: EvidenceKind
    claim_level: ClaimLevel = ClaimLevel.L0
    git_sha: str = Field(min_length=1)
    environment_lock: str = Field(min_length=1)
    data_sha: Sha256Hex | None = None

    @field_validator("protocol_id")
    @classmethod
    def _registered(cls, v: str) -> str:
        if v not in PROTOCOL_GAMES:
            raise ValueError(f"unregistered protocol_id {v!r}")
        return v

    @model_validator(mode="after")
    def _kind(self) -> BenchmarkRecord:
        is_q = self.protocol_id in QUANTUM_PROTOCOLS
        if is_q != (self.classical_or_quantum == "quantum"):
            raise ValueError("classical_or_quantum inconsistent with protocol_id")
        return self


class ManifestEntry(_Strict):
    path_or_uri: str = Field(min_length=1)
    sha256: Sha256Hex
    role: Literal["input", "output", "script", "environment"]
    original_or_derived: Literal["original", "derived"]
    upstream_checksum: str | None = None  # e.g. Zenodo "md5:..." exactly as published


class EvidenceManifest(_Strict):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    manifest_id: str = Field(min_length=1)
    created_utc: str = Field(min_length=1)  # ISO-8601
    source_urls: list[str] = Field(default_factory=list)
    retrieved_utc: str | None = None
    command: str = Field(min_length=1)
    git_sha: str = Field(min_length=1)
    environment: dict[str, str] = Field(default_factory=dict)
    seeds: list[int] = Field(default_factory=list)
    evidence_kind: EvidenceKind
    entries: list[ManifestEntry] = Field(min_length=1)


# All contract models, exported for schema generation (schemas/v1/*.json).
CONTRACT_MODELS: dict[str, type[BaseModel]] = {
    "protocol": ProtocolSpec,
    "token": TokenRecord,
    "measurement": MeasurementEvent,
    "photon": PhotonEvent,
    "calibration": CalibrationRecord,
    "attack": AttackResult,
    "network": SpacetimeNetwork,
    "trace": TransactionTrace,
    "certificate": SecurityCertificate,
    "bound_request": BoundRequest,
    "bound_result": BoundResult,
    "benchmark": BenchmarkRecord,
    "manifest": EvidenceManifest,
}
