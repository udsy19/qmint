"""Security Certificate Studio backend (lane D: ``qmint.proofs``).

``GET  /certificates/catalog`` -- per game: the registered theorem (``proofs/OBLIGATIONS.yaml``), its
  hypotheses that must be declared, parameters, axes and anchors; the calibration sources; and presets
  taken from lane D's committed example certificates (``proofs/certificates/*.json``).
``POST /certificates`` -- runs the request through ``ProofEngine`` (one ``BoundRequest`` per axis),
  builds the draft ``SecurityCertificate`` and hands it to ``IndependentProofChecker``. Only the
  checker can return CERTIFIED; nothing in this module sets that status.

Never a numerical estimate presented as a proof: a missing theorem is ``null`` with a reason, never 0.
The studio additionally classifies an UNCERTIFIED verdict as OUT_OF_MODEL / INFEASIBLE / UNCERTIFIED
from the checker's and evaluator's reasons; that classification is labelled as such and never alters
the checker's status. Resource optimisation belongs to lane I (compiler, in flight) -> NOT_AVAILABLE;
only the ideal-game THEOREM sizing (minimal n for a target under W1 / W1_CV / S1) is offered.
"""

from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from qmint.core.config import REPO_ROOT
from qmint.core.contracts import (
    PROTOCOL_GAMES,
    BoundRequest,
    BoundResult,
    CalibrationRecord,
    CertificateStatus,
    EvidenceKind,
    GameId,
    SecurityAxis,
    SecurityCertificate,
    Targets,
    Unit,
    check_protocol_game,
)
from qmint.core.serialization import canonical_json, file_sha256, sha256_hex
from qmint.proofs.assumption_check import endpoints, merge_calibration
from qmint.proofs.checker import IndependentProofChecker
from qmint.proofs.engine import ProofEngine
from qmint.proofs.ideal_bounds import IDEAL_BASES, log10_bound, min_length_for_target
from qmint.proofs.registry import OBLIGATIONS_PATH, Claim, default_registry

from ..common import git_sha, provenance
from ..schemas import ERROR_RESPONSES, Envelope, Quantity

CERT_DIR = REPO_ROOT / "proofs" / "certificates"
CAL_PATH = REPO_ROOT / "reports" / "data_working" / "schiansky2023" / "calibration_records.json"
AXIS_LABEL = {
    SecurityAxis.UNFORGEABILITY: "Unforgeability",
    SecurityAxis.CORRECTNESS: "Correctness",
    SecurityAxis.ROBUSTNESS: "Robustness",
    SecurityAxis.PRIVACY: "Privacy",
}
CalibrationSource = Literal["none", "schiansky_photon_Z", "schiansky_photon_X", "schiansky_published_aggregate"]
NoiseSource = Literal["published_kent_2022", "published_schiansky_2023", "hypothetical", "calibration"]
Verdict = Literal["CERTIFIED", "UNCERTIFIED", "INFEASIBLE", "OUT_OF_MODEL"]
LANE_I_REASON = (
    "Resource optimisation (choosing N, thresholds and analysis variables to minimise photons under all targets) "
    "is the certificate compiler, lane I, which is in flight and not merged. Nothing here searches parameters."
)
_PARAM_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,31}$")


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# request
# --------------------------------------------------------------------------- #


class IntervalIn(_M):
    lo: float = Field(allow_inf_nan=False)
    hi: float = Field(allow_inf_nan=False)

    @field_validator("hi")
    @classmethod
    def _ordered(cls, hi: float, info: Any) -> float:
        if "lo" in info.data and info.data["lo"] > hi:
            raise ValueError("interval lo > hi")
        return hi


class TargetsIn(_M):
    epsilon_unf: float | None = Field(default=None, gt=0.0, lt=1.0)
    epsilon_cor: float | None = Field(default=None, gt=0.0, lt=1.0)
    epsilon_rob: float | None = Field(default=None, gt=0.0, lt=1.0)
    epsilon_priv: float | None = Field(default=None, gt=0.0, lt=1.0)


class CertificateRequest(_M):
    game: GameId = GameId.W1
    protocol_id: str | None = Field(default=None, description="defaults to the protocol registered for the game")
    targets: TargetsIn = Field(default_factory=lambda: TargetsIn(epsilon_unf=1e-9))
    parameters: dict[str, int | float | IntervalIn] = Field(
        default_factory=lambda: {"n": 73}, description="theorem parameters: a number or an interval {lo, hi}"
    )
    honest_error_tolerance: float | None = Field(
        default=None, ge=0.0, lt=0.5,
        description="ideal games: any value > 0 is outside the theorem; S2: used as gamma_err when not given",
    )
    declared_assumptions: list[str] = Field(default_factory=list, max_length=32)
    noise_source: NoiseSource | None = None
    calibration: CalibrationSource = "none"

    @field_validator("parameters")
    @classmethod
    def _keys(cls, v: dict[str, Any]) -> dict[str, Any]:
        if len(v) > 32:
            raise ValueError("at most 32 parameters")
        bad = [k for k in v if not _PARAM_KEY.match(k)]
        if bad:
            raise ValueError(f"invalid parameter names: {bad}")
        return v


# --------------------------------------------------------------------------- #
# response
# --------------------------------------------------------------------------- #


class Declaration(_M):
    name: str
    description: str
    declared: bool


class AxisAnchor(_M):
    axis: SecurityAxis
    bound_id: str
    anchor: str
    formula: str
    domain: str
    monotonicity: dict[str, str]
    domain_only: list[str]


class TheoremInfo(_M):
    claim_id: str
    game: str
    protocol: str
    status: str
    statement: str
    citation: str | None
    url: str | None
    quantifier: str
    finite_or_asymptotic: str
    assumptions: list[str]
    caveats: list[str]
    parameters: dict[str, str]
    calibration_families: list[str]
    axes: list[AxisAnchor]


class UncertaintyStep(_M):
    parameter: str
    lo: float
    hi: float
    direction: Literal["increasing", "decreasing", "domain_only", "undocumented"]
    endpoint_used: str


class AxisResult(_M):
    axis: SecurityAxis
    label: str
    target: float | None
    result: BoundResult
    applicable: bool
    meets_target: bool | None
    uncertainty: list[UncertaintyStep]


class CalibrationInfo(_M):
    source: CalibrationSource
    calibration_id: str | None
    experiment_family: str | None
    data_origin: EvidenceKind | None
    dataset_sha256: str | None
    accepted_families: list[str]
    family_matches: bool | None
    intervals: dict[str, dict[str, float | None]]
    note: str


class CurvePoint(_M):
    n: int
    log10_bound: float


class Sizing(_M):
    status: Literal["OK", "NOT_AVAILABLE"]
    label: str
    reason: str
    quantities: list[Quantity]
    curve: list[CurvePoint] = Field(default_factory=list, description="ideal games: log10 bound vs n (THEOREM)")


class CheckerInfo(_M):
    status: CertificateStatus
    checker_id: str | None
    reasons: list[str]


class Classification(_M):
    verdict: Verdict
    headline: str
    reasons: list[str]
    derived_from: str


class ExportBlock(_M):
    filename: str
    canonical_json: str
    sha256: str
    obligations_sha256: str


class CertificateData(_M):
    game: GameId
    protocol_id: str
    effective_parameters: dict[str, Any]
    theorem: TheoremInfo | None
    no_theorem_reason: str | None
    declarations: list[Declaration]
    calibration: CalibrationInfo
    axes: list[AxisResult]
    sizing: Sizing
    optimization: Sizing
    draft_certificate: SecurityCertificate
    checked_certificate: SecurityCertificate
    checker: CheckerInfo
    classification: Classification
    export: ExportBlock


class CertificateResponse(Envelope):
    data: CertificateData


class Preset(_M):
    id: str
    title: str
    summary: str
    source: str
    request: CertificateRequest


class GameEntry(_M):
    game: GameId
    protocol_ids: list[str]
    theorem: TheoremInfo | None
    no_theorem_reason: str | None
    declarations: list[Declaration]
    sizing_available: bool


class CalibrationOption(_M):
    source: CalibrationSource
    label: str
    calibration_id: str | None
    experiment_family: str | None
    data_origin: EvidenceKind | None
    intervals: dict[str, dict[str, float | None]]


class CatalogData(_M):
    games: list[GameEntry]
    calibrations: list[CalibrationOption]
    presets: list[Preset]
    noise_sources: list[str]


class CatalogResponse(Envelope):
    data: CatalogData


# --------------------------------------------------------------------------- #
# registry views
# --------------------------------------------------------------------------- #


def _claim_for(game: GameId) -> Claim | None:
    reg = default_registry()
    claims = [c for c in reg.claims if c.game == game.value]
    with_bounds = [c for c in claims if c.bounds]
    return (with_bounds or claims or [None])[0]


def _describe(claim: Claim, name: str) -> str:
    if name.startswith("table6_"):
        letters = "/".join(t for t in name.split("_")[1:] if len(t) == 1 and t.isupper())
        hit = next((a for a in claim.assumptions if a.startswith(f"Table 6 {letters}")), None)
        if hit:
            return hit
    if name == "independent_rounds":
        hit = next((a for a in claim.assumptions if "INDEPENDENT" in a), None)
        if hit:
            return hit
    return name.replace("_", " ")


def _theorem(claim: Claim | None) -> TheoremInfo | None:
    if claim is None or not claim.bounds:
        return None
    src = default_registry().sources.get(claim.source)
    return TheoremInfo(
        claim_id=claim.claim_id, game=claim.game, protocol=claim.protocol, status=claim.status.value,
        statement=claim.source_and_theorem, citation=src.citation if src else None, url=src.url if src else None,
        quantifier=claim.quantifier_over_adversaries, finite_or_asymptotic=claim.finite_n_or_asymptotic,
        assumptions=list(claim.assumptions), caveats=list(claim.caveats), parameters=dict(claim.parameters),
        calibration_families=list(claim.calibration_families),
        axes=[AxisAnchor(axis=b.axis, bound_id=b.bound_id, anchor=b.anchor, formula=b.formula, domain=b.domain,
                         monotonicity=dict(b.monotonicity), domain_only=list(b.domain_only)) for b in claim.bounds],
    )


def _no_theorem_reason(game: GameId, claim: Claim | None) -> str | None:
    if claim is not None and claim.bounds:
        return None
    if claim is None:
        return f"no proof obligation is registered for game {game.value}; no bound exists (never 0)"
    return f"{claim.claim_id} ({claim.status.value}): no published or certified bound for {game.value}. {claim.caveats[0]}"


def _declarations(claim: Claim | None, declared: list[str]) -> list[Declaration]:
    if claim is None or not claim.bounds:
        return []
    return [Declaration(name=n, description=_describe(claim, n), declared=n in declared) for n in claim.required_declarations]


# --------------------------------------------------------------------------- #
# calibration sources
# --------------------------------------------------------------------------- #


@lru_cache(maxsize=1)
def _calibrations() -> dict[str, CalibrationRecord]:
    """Lane E's committed records, keyed by studio source name (photon Z / X runs and the paper's values)."""
    by_id = {r.calibration_id: r for r in
             (CalibrationRecord.model_validate(x) for x in json.loads(CAL_PATH.read_text(encoding="utf-8")))}
    return {
        "schiansky_photon_Z": by_id["schiansky2023-zenodo7979319-Z-v1"],
        "schiansky_photon_X": by_id["schiansky2023-zenodo7979319-X-v1"],
        "schiansky_published_aggregate": by_id["schiansky2023-published-aggregate-v1"],
    }


def _intervals(rec: CalibrationRecord | None) -> dict[str, dict[str, float | None]]:
    if rec is None:
        return {}
    out = {}
    for name in ("qber_interval", "loss_interval", "multiphoton_interval", "basis_bias_interval"):
        iv = getattr(rec, name)
        if iv is not None:
            out[name] = {"lo": iv.lo, "hi": iv.hi, "point": iv.point}
    return out


_CAL_LABEL = {
    "none": "No calibration (declared parameters only)",
    "schiansky_photon_Z": "Schiansky 2023 photon data, H/V runs (lane E, PHOTON_EXPERIMENT)",
    "schiansky_photon_X": "Schiansky 2023 photon data, D/A runs (lane E, PHOTON_EXPERIMENT)",
    "schiansky_published_aggregate": "Schiansky 2023 paper values (PUBLISHED_AGGREGATE)",
}


def _calibration_info(source: CalibrationSource, rec: CalibrationRecord | None, claim: Claim | None) -> CalibrationInfo:
    families = list(claim.calibration_families) if claim else []
    if rec is None:
        return CalibrationInfo(source=source, calibration_id=None, experiment_family=None, data_origin=None,
                               dataset_sha256=None, accepted_families=families, family_matches=None, intervals={},
                               note="no calibration record attached")
    matches = rec.experiment_family in families
    if claim is not None and claim.game in {g.value for g in IDEAL_BASES}:
        note = "ideal theorems admit no measured noise: any non-zero calibration interval puts the request OUT_OF_MODEL"
    elif matches:
        note = f"family {rec.experiment_family!r} matches the theorem; intervals are merged as a hull and propagated to the worst endpoint"
    else:
        note = (f"family {rec.experiment_family!r} is not one the theorem was proven for {families or '(none)'}; "
                "the evaluator rejects it (CALIBRATION_FAMILY_MISMATCH) instead of transferring the data")
    return CalibrationInfo(source=source, calibration_id=rec.calibration_id, experiment_family=rec.experiment_family,
                           data_origin=rec.data_origin, dataset_sha256=rec.dataset_sha256, accepted_families=families,
                           family_matches=matches, intervals=_intervals(rec), note=note)


# --------------------------------------------------------------------------- #
# evaluation
# --------------------------------------------------------------------------- #


def _protocol_for(game: GameId, requested: str | None) -> str:
    if requested is not None:
        try:
            check_protocol_game(requested, game)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        return requested
    return sorted(p for p, gs in PROTOCOL_GAMES.items() if game in gs)[0]


def _effective_params(req: CertificateRequest) -> dict[str, Any]:
    params: dict[str, Any] = {k: (v.model_dump() if isinstance(v, IntervalIn) else v) for k, v in req.parameters.items()}
    tol = req.honest_error_tolerance
    if tol is not None:
        if req.game in IDEAL_BASES:
            params["error_threshold"] = tol
        elif req.game == GameId.S2:
            params.setdefault("gamma_err", tol)
    params["declared_assumptions"] = list(req.declared_assumptions)
    if req.noise_source is not None:
        params["noise_source"] = req.noise_source
    return params


def _uncertainty(claim: Claim | None, axis: SecurityAxis, params: dict[str, Any]) -> list[UncertaintyStep]:
    if claim is None:
        return []
    spec = next((b for b in claim.bounds if b.axis == axis), None)
    if spec is None:
        return []
    steps = []
    for k, v in params.items():
        if not isinstance(v, dict):
            continue
        lo, hi = endpoints(v)
        if lo == hi:
            continue
        if k in spec.monotonicity:
            d = spec.monotonicity[k]
            used = f"hi = {hi:g} (bound grows with {k})" if d == "increasing" else f"lo = {lo:g} (bound grows as {k} falls)"
            steps.append(UncertaintyStep(parameter=k, lo=lo, hi=hi, direction=d, endpoint_used=used))
        elif k in spec.domain_only:
            steps.append(UncertaintyStep(parameter=k, lo=lo, hi=hi, direction="domain_only",
                                         endpoint_used="value independent; theorem domain checked on every corner"))
        else:
            steps.append(UncertaintyStep(parameter=k, lo=lo, hi=hi, direction="undocumented",
                                         endpoint_used="refused if the axis uses it: no documented monotonicity, never guessed"))
    return steps


def _meets(res: BoundResult, target: float | None) -> bool | None:
    if target is None or res.log10_value is None:
        return None
    return res.log10_value <= math.log10(target)


def _sizing(game: GameId, req: CertificateRequest, params: dict[str, Any]) -> Sizing:
    if game not in IDEAL_BASES:
        return Sizing(status="NOT_AVAILABLE", label="THEOREM sizing", reason=(
            f"No closed-form sizing for {game.value}: finite-size and noisy games need the certificate compiler "
            "(lane I, in flight). The declared N is evaluated as given."), quantities=[])
    target = req.targets.epsilon_unf
    if target is None:
        return Sizing(status="NOT_AVAILABLE", label="THEOREM sizing", quantities=[],
                      reason="set an unforgeability target to size the ideal token")
    base, bound_id, key = IDEAL_BASES[game]
    n_min = min_length_for_target(game, target)
    claim, spec = default_registry().bound(bound_id)
    note = "THEOREM sizing in the ideal lossless, noiseless model only; not an optimisation and not a certificate by itself"
    q = [
        Quantity(id="n_min", label=f"Minimal {key} with {spec.formula} ≤ target", value=float(n_min), unit=Unit.COUNT,
                 evidence_kind=EvidenceKind.PUBLISHED_THEOREM, method="closed_form", source=f"{bound_id} ({spec.anchor})",
                 formula=f"min {key}: {key}·log10({base:.6g}) ≤ log10({target:g})", note=note),
        Quantity(id="photons_min", label="Single-photon states per token at that size", value=float(n_min), unit=Unit.COUNT,
                 evidence_kind=EvidenceKind.PUBLISHED_THEOREM, method="closed_form", source=f"{bound_id} ({spec.anchor})",
                 note="ideal model: one qubit per prepared single photon, every photon detected; real losses need S2/D1"),
    ]
    requested = params.get(key, params.get("n" if key == "N" else "N"))
    if isinstance(requested, int):
        q.append(Quantity(id="requested_size", label=f"Requested {key}", value=float(requested), unit=Unit.COUNT,
                          evidence_kind=EvidenceKind.PUBLISHED_THEOREM, method="closed_form", source="request",
                          note="meets the target" if requested >= n_min else f"below the theorem size by {n_min - requested}"))
    top = max(2 * n_min, requested if isinstance(requested, int) else 0, 8)
    step = max(1, top // 60)
    curve = [CurvePoint(n=n, log10_bound=log10_bound(game, n)) for n in range(1, top + 1, step)]
    return Sizing(status="OK", label="THEOREM sizing", reason=f"{claim.claim_id}: {spec.anchor}", quantities=q, curve=curve)


def _checker_reasons(cert: SecurityCertificate) -> list[str]:
    """Split the checker's reason into items, collapsing repeated tokens (one per axis) inside each item."""
    out = []
    for r in cert.reason.removeprefix("UNCERTIFIED by independent checker: ").split(" | "):
        head, sep, tail = r.partition(": ")
        if sep and head == "assumptions not met":
            r = head + sep + ", ".join(dict.fromkeys(t.strip() for t in tail.split(", ")))
        if r:
            out.append(r)
    return out


def _classify(checked: SecurityCertificate, axes: list[AxisResult], game: GameId, theorem: TheoremInfo | None) -> Classification:
    derived = ("studio classification of the evaluator and checker reasons; the independent checker itself returns "
               "only CERTIFIED or UNCERTIFIED, and its status is exported unchanged")
    checker_reasons = _checker_reasons(checked)
    if checked.proof_check_status == CertificateStatus.CERTIFIED:
        return Classification(verdict="CERTIFIED", headline="Independent checker re-derived every bound and every target is met",
                              reasons=[checked.reason], derived_from="IndependentProofChecker verdict")
    failed = [f for a in axes for f in a.result.failed_assumptions]
    oom = [f for f in failed if f.startswith(("OUT_OF_MODEL", "CALIBRATION_FAMILY_MISMATCH", "CALIBRATION_ORIGIN"))]
    if oom:
        return Classification(verdict="OUT_OF_MODEL", headline="The request leaves the theorem's model; no bound is transferred",
                              reasons=sorted(set(oom)) + checker_reasons, derived_from=derived)
    targeted = [a for a in axes if a.target is not None]
    if (theorem is not None and game != GameId.D1 and targeted and all(a.applicable for a in targeted)
            and checked.assumptions_met and any(a.meets_target is False for a in targeted)):
        return Classification(verdict="INFEASIBLE", headline="Applicable bounds exist but do not reach every target at these parameters",
                              reasons=[f"{a.label}: bound 10^{a.result.log10_value:.4g} > target {a.target:g}"
                                       for a in targeted if a.meets_target is False] + checker_reasons, derived_from=derived)
    headline = {
        GameId.D1: "D1 is never certified: fitted SDP boundary, informal de Finetti step, open Chernoff question",
    }.get(game, "No complete, independently checked bound for every target" if theorem else "No applicable theorem")
    return Classification(verdict="UNCERTIFIED", headline=headline, reasons=checker_reasons, derived_from=derived)


def evaluate(req: CertificateRequest) -> CertificateData:
    game = req.game
    protocol_id = _protocol_for(game, req.protocol_id)
    claim = _claim_for(game)
    theorem = _theorem(claim)
    cal = None if req.calibration == "none" else _calibrations()[req.calibration]
    params = _effective_params(req)
    targets = Targets(**req.targets.model_dump())
    engine, checker = ProofEngine(), IndependentProofChecker()
    obligations_sha = file_sha256(OBLIGATIONS_PATH)
    hashes = [obligations_sha] + ([cal.dataset_sha256] if cal and cal.dataset_sha256 else [])
    # Shown parameters include calibration intervals only when the theorem accepts that family; a rejected
    # calibration is never presented as if it had been propagated.
    accepted = cal is not None and claim is not None and cal.experiment_family in claim.calibration_families
    merged = merge_calibration(game.value, params, cal) if accepted else dict(params)

    axes = []
    try:
        for axis in SecurityAxis:
            res = engine.evaluate(BoundRequest(protocol_id=protocol_id, game_id=game, axis=axis, parameters=params, calibration=cal))
            tgt = getattr(targets, axis.value)
            axes.append(AxisResult(axis=axis, label=AXIS_LABEL[axis], target=tgt, result=res,
                                   applicable=res.log10_value is not None, meets_target=_meets(res, tgt),
                                   uncertainty=_uncertainty(claim, axis, merged)))
        draft = engine.draft_certificate(protocol_id, game, params, targets,
                                         security_model_id=f"{claim.claim_id if claim else game.value}-studio",
                                         evidence_hashes=hashes, calibration=cal, software_revision=git_sha())
    except (TypeError, ValueError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"parameters rejected by the proof engine: {e}") from e
    checked = checker.check(draft)
    canon = canonical_json(checked)
    return CertificateData(
        game=game, protocol_id=protocol_id, effective_parameters=merged, theorem=theorem,
        no_theorem_reason=_no_theorem_reason(game, claim), declarations=_declarations(claim, req.declared_assumptions),
        calibration=_calibration_info(req.calibration, cal, claim), axes=axes, sizing=_sizing(game, req, params),
        optimization=Sizing(status="NOT_AVAILABLE", label="Resource optimisation", reason=LANE_I_REASON, quantities=[]),
        draft_certificate=draft, checked_certificate=checked,
        checker=CheckerInfo(status=checked.proof_check_status, checker_id=checked.checker_id,
                            reasons=_checker_reasons(checked)),
        classification=_classify(checked, axes, game, theorem),
        export=ExportBlock(filename=f"qmint-certificate-{game.value}-{sha256_hex(canon)[:12]}.json", canonical_json=canon,
                           sha256=sha256_hex(canon), obligations_sha256=obligations_sha),
    )


# --------------------------------------------------------------------------- #
# presets (lane D example certificates + studio demonstrations of failure states)
# --------------------------------------------------------------------------- #


def _from_certificate(name: str) -> CertificateRequest:
    cert = json.loads((CERT_DIR / f"{name}.json").read_text(encoding="utf-8"))
    p = dict(cert["parameters"])
    declared = p.pop("declared_assumptions", [])
    noise = p.pop("noise_source", None)
    return CertificateRequest(game=cert["game_id"], protocol_id=cert["protocol_id"],
                              targets=TargetsIn(**{k: v for k, v in cert["targets"].items() if v is not None}),
                              parameters=p, declared_assumptions=declared, noise_source=noise)


@lru_cache(maxsize=1)
def _presets() -> tuple[Preset, ...]:
    reg = default_registry()
    w1 = _from_certificate("W1_n73")
    s2 = _from_certificate("S2_fig5_theta10_E058_hypothetical")
    src = "lane D proofs/certificates/{}.json (qmint.proofs.reproduce)"
    return (
        Preset(id="w1-n73", title="Wiesner W1 · n = 73", summary="MVW2012 Theorem 1 at the smallest n with (3/4)^n ≤ 1e-9.",
               source=src.format("W1_n73"), request=w1),
        Preset(id="s2-fig5", title="S-money S2 · Kent Fig. 5 hypothetical",
               summary="All four axes with a hypothetical β = 6e-6 tuple (θ = 10°, E = 0.058).",
               source=src.format("S2_fig5_theta10_E058_hypothetical"), request=s2),
        Preset(id="s2-kent-exp", title="S-money S2 · Kent experimental tuple",
               summary="The paper's measured biases violate Theorem 1's domain (f ≤ 0): no unforgeability bound.",
               source=src.format("S2_kent_experimental_tuple"), request=_from_certificate("S2_kent_experimental_tuple")),
        Preset(id="d1-schiansky", title="Schiansky D1 · published tuple",
               summary="Reproduces p_d = 5.9e-45 (SI Eq. 22). The checker never certifies D1.",
               source=src.format("D1_schiansky_published"), request=_from_certificate("D1_schiansky_published")),
        Preset(id="s2-photon-mismatch", title="S2 with Schiansky photon calibration",
               summary="Measured QBER from a different experiment family: rejected, not transferred.",
               source="lane E calibration_records.json + lane D assumption_check",
               request=s2.model_copy(update={"calibration": "schiansky_photon_X", "noise_source": None})),
        Preset(id="d1-photon", title="D1 with Schiansky photon calibration",
               summary="Same family: the measured D/A QBER interval enters e_h; still never certified.",
               source="lane E calibration_records.json",
               request=_from_certificate("D1_schiansky_published").model_copy(update={"calibration": "schiansky_photon_X"})),
        Preset(id="w1-noisy", title="W1 with 2 % honest-error tolerance",
               summary="(3/4)^n is a zero-tolerance theorem; tolerating errors is game W2, which has no bound.",
               source="lane D ideal_bounds.check_noise_free",
               request=w1.model_copy(update={"honest_error_tolerance": 0.02})),
        Preset(id="w1-privacy", title="W1 with a privacy target",
               summary="No privacy theorem exists for Wiesner money: the axis has no bound (never 0).",
               source="proofs/OBLIGATIONS.yaml P-PRIV caveat",
               request=w1.model_copy(update={"targets": TargetsIn(epsilon_unf=1e-9, epsilon_priv=1e-6)})),
        Preset(id="w2", title="Noisy Wiesner W2", summary="No published closed form; SDP support only (P-W2).",
               source="proofs/OBLIGATIONS.yaml P-W2",
               request=CertificateRequest(game=GameId.W2, parameters={"n": 73},
                                          declared_assumptions=list(reg.claim("P-W1").required_declarations))),
    )


router = APIRouter(tags=["certificates"], responses=ERROR_RESPONSES)


@router.get("/certificates/catalog", response_model=CatalogResponse)
def catalog() -> CatalogResponse:
    games = []
    for g in GameId:
        claim = _claim_for(g)
        games.append(GameEntry(game=g, protocol_ids=sorted(p for p, gs in PROTOCOL_GAMES.items() if g in gs),
                               theorem=_theorem(claim), no_theorem_reason=_no_theorem_reason(g, claim),
                               declarations=_declarations(claim, []), sizing_available=g in IDEAL_BASES))
    cals = [CalibrationOption(source="none", label=_CAL_LABEL["none"], calibration_id=None, experiment_family=None,
                              data_origin=None, intervals={})]
    for key, rec in _calibrations().items():
        cals.append(CalibrationOption(source=key, label=_CAL_LABEL[key], calibration_id=rec.calibration_id,  # type: ignore[arg-type]
                                      experiment_family=rec.experiment_family, data_origin=rec.data_origin,
                                      intervals=_intervals(rec)))
    return CatalogResponse(
        status="OK", evidence_kind=None,
        provenance=provenance("qmint.proofs registry (lane D) + qmint.photonics calibration (lane E)"),
        data=CatalogData(games=games, calibrations=cals, presets=list(_presets()),
                         noise_sources=["published_kent_2022", "published_schiansky_2023", "hypothetical", "calibration"]),
    )


@router.post("/certificates", response_model=CertificateResponse)
def certificates(req: CertificateRequest) -> CertificateResponse:
    data = evaluate(req)
    certified = data.checked_certificate.proof_check_status == CertificateStatus.CERTIFIED
    return CertificateResponse(
        status="OK",
        evidence_kind=data.checked_certificate.evidence_kind if certified else EvidenceKind.UNCERTIFIED,
        provenance=provenance("qmint.proofs.engine + qmint.proofs.checker (lane D)",
                              notes="CERTIFIED only from IndependentProofChecker; estimates are never proofs"),
        data=data,
    )
