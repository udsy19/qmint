"""Single ``ProofEvaluator`` entry point and draft-certificate builder for consumers (lanes I/K/N).

``ProofEngine.evaluate`` dispatches by game: W1/W1_CV/S1 -> ``IdealBoundEvaluator``,
S2/D1 -> ``FiniteSizeBoundEvaluator``; every other game (W2, A1, C1) gets a value-less
UNSUPPORTED result. ``draft_certificate`` assembles an UNCERTIFIED ``SecurityCertificate``
from evaluator results; only ``IndependentProofChecker.check`` may promote it to CERTIFIED.
"""

from __future__ import annotations

from typing import Any

from qmint.core.contracts import (
    BoundRequest,
    BoundResult,
    CalibrationRecord,
    CertificateStatus,
    EvidenceKind,
    GameId,
    SecurityAxis,
    SecurityCertificate,
    Targets,
    UpperBounds,
)
from qmint.proofs.assumption_check import merge_calibration
from qmint.proofs.finite_size import FiniteSizeBoundEvaluator
from qmint.proofs.ideal_bounds import IDEAL_BASES, IdealBoundEvaluator
from qmint.proofs.registry import Registry, default_registry
from qmint.proofs.results import unsupported


class ProofEngine:
    evaluator_id = "qmint.proofs.engine/v1"

    def __init__(self, registry: Registry | None = None) -> None:
        self._registry = registry or default_registry()
        self._ideal = IdealBoundEvaluator(self._registry)
        self._finite = FiniteSizeBoundEvaluator(self._registry)

    def evaluate(self, request: BoundRequest) -> BoundResult:
        if request.game_id in IDEAL_BASES:
            return self._ideal.evaluate(request)
        if request.game_id in (GameId.S2, GameId.D1):
            return self._finite.evaluate(request)
        return unsupported(request, f"no published theorem or certified bound for game {request.game_id.value}")

    def draft_certificate(
        self,
        protocol_id: str,
        game_id: GameId | str,
        parameters: dict[str, Any],
        targets: Targets,
        *,
        security_model_id: str,
        evidence_hashes: list[str],
        calibration: CalibrationRecord | None = None,
        software_revision: str | None = None,
    ) -> SecurityCertificate:
        """Evaluate every targeted axis and return an UNCERTIFIED draft for the checker."""
        game = GameId(game_id)
        bounds: dict[str, float | None] = {}
        logs: dict[str, float] = {}
        failed: list[str] = []
        refs: set[str] = set()
        kinds: set[EvidenceKind] = set()
        for axis in SecurityAxis:
            if getattr(targets, axis.value) is None:
                continue
            res = self.evaluate(
                BoundRequest(protocol_id=protocol_id, game_id=game, axis=axis, parameters=parameters, calibration=calibration)
            )
            if res.value is None and res.log10_value is None:
                failed += res.failed_assumptions or [f"{axis.value}: {res.notes}"]
                continue
            bounds[axis.value] = res.value
            if res.log10_value is not None:
                logs[axis.value] = res.log10_value
            refs.add(res.theorem_id.split("/")[0] if res.theorem_id else "")
            kinds.add(res.evidence_kind)
        kind = kinds.pop() if len(kinds) == 1 else EvidenceKind.UNCERTIFIED
        return SecurityCertificate(
            protocol_id=protocol_id,
            game_id=game,
            security_model_id=security_model_id,
            parameters=merge_calibration(game.value, parameters, calibration),
            upper_bounds=UpperBounds(**bounds),
            log10_upper_bounds=logs,
            targets=targets,
            assumptions_met=not failed,
            failed_assumptions=failed,
            proof_reference=refs.pop() if len(refs) == 1 else None,
            proof_check_status=CertificateStatus.UNCERTIFIED,
            evidence_kind=kind,
            reason="draft from qmint.proofs.engine; requires IndependentProofChecker",
            calibration_id=calibration.calibration_id if calibration else None,
            software_revision=software_revision,
            evidence_hashes=evidence_hashes,
        )
