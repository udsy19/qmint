"""Certificate emission (always re-validated by lane D's independent checker) and infeasibility certificates.

Release rule (P-OPT): a configuration is RELEASED only if ``IndependentProofChecker.check`` -- a code path
separate from the engine that scored it -- returns CERTIFIED. Anything else is reported with the
checker's reasons and excluded from certified Pareto fronts. D1 is UNCERTIFIED by construction.
"""

from __future__ import annotations

import itertools
import math
from collections import Counter
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from qmint.compiler.constraints import FROZEN_PATH, SECURITY_MODEL, Problem
from qmint.compiler.scoring import Scorer, proof_version
from qmint.compiler.selectors import Selection
from qmint.core.contracts import CertificateStatus, GameId, SecurityAxis, SecurityCertificate, Targets
from qmint.core.serialization import canonical_hash, file_sha256
from qmint.proofs.checker import IndependentProofChecker
from qmint.proofs.engine import ProofEngine


@dataclass
class CertOutcome:
    certificate: SecurityCertificate
    released: bool
    uncertified_by_construction: bool  # D1: the checker never certifies (not a checker "failure")

    @property
    def checker_rejected(self) -> bool:
        return not self.released and not self.uncertified_by_construction


def evidence_hashes(problem: Problem) -> list[str]:
    return [file_sha256(FROZEN_PATH), canonical_hash(proof_version()), problem.device_hash]


def certify(problem: Problem, selection: Selection, *, engine: ProofEngine | None = None,
            checker: IndependentProofChecker | None = None, software_revision: str | None = None) -> CertOutcome:
    """Draft through the engine, then re-validate through the independent checker."""
    if selection.status != "FEASIBLE" or selection.decisions is None:
        raise ValueError("only FEASIBLE selections can be certified")
    engine = engine or ProofEngine()
    checker = checker or IndependentProofChecker()
    params = problem.engine_params(selection.decisions)
    draft = engine.draft_certificate(
        problem.protocol_id, problem.game, params, problem.targets,
        security_model_id=SECURITY_MODEL[problem.game], evidence_hashes=evidence_hashes(problem),
        calibration=problem.calibration, software_revision=software_revision,
    )
    checked = checker.check(draft)
    released = checked.proof_check_status == CertificateStatus.CERTIFIED
    return CertOutcome(checked, released, uncertified_by_construction=problem.game == GameId.D1)


# --------------------------------------------------------------------------- #
# Infeasibility certificates
# --------------------------------------------------------------------------- #


class AxisDiagnosis(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    axis: str
    target: float
    best_log10_found: float | None  # lowest applicable bound seen on the probed grid (None = never applicable)
    points_probed: int
    points_with_bound: int
    reasons: dict[str, int] = Field(default_factory=dict)  # engine notes / failed assumptions -> count


class InfeasibilityCertificate(BaseModel):
    """Why no grid configuration meets the request. Never a security claim."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario_id: str
    protocol_id: str
    game_id: GameId
    status: CertificateStatus  # INFEASIBLE (bounds exist, targets unmet) or OUT_OF_MODEL (no theorem/assumption)
    targets: Targets
    probed_at: dict[str, Any]
    axes: list[AxisDiagnosis]
    missing_assumptions: list[str]
    reason: str


def _short(note: str) -> str:
    note = note.split(" | ")[0].split(" not applicable: ")[-1]
    return note if len(note) <= 220 else note[:217] + "..."


def diagnose(problem: Problem, scorer: Scorer | None = None, *, stride: int = 4, note: str = "") -> InfeasibilityCertificate:
    """Probe every threshold tuple (stride ``stride``) at the LARGEST grid N and explain each axis."""
    scorer = scorer or Scorer(cache=True)
    n_last = problem.shape[0] - 1
    others = [range(0, k, stride) for k in problem.shape[1:]]
    stats: dict[SecurityAxis, dict[str, Any]] = {a: {"best": None, "probed": 0, "with": 0, "reasons": Counter()}
                                                 for a in problem.target_axes}
    missing: set[str] = set()
    for rest in itertools.product(*others):
        dec = problem.decision_values((n_last, *rest))
        for a in problem.target_axes:
            sc = scorer.score(problem, a, dec)
            st = stats[a]
            st["probed"] += 1
            missing.update(f for f in sc.failed if f.startswith("ASSUMPTION_MISSING"))
            if sc.log10 is None:
                st["reasons"][_short(sc.notes) or ";".join(sc.failed)] += 1
                for f in sc.failed:
                    st["reasons"][f] += 1
                continue
            st["with"] += 1
            st["best"] = sc.log10 if st["best"] is None else min(st["best"], sc.log10)
            if not sc.meets(problem.target_log10(a)):
                st["reasons"]["bound above target"] += 1
    axes = [
        AxisDiagnosis(axis=a.value, target=getattr(problem.targets, a.value), best_log10_found=st["best"],
                      points_probed=st["probed"], points_with_bound=st["with"],
                      reasons=dict(st["reasons"].most_common(6)))
        for a, st in stats.items()
    ]
    out_of_model = bool(missing) or any(d.points_with_bound == 0 and "no published theorem" in " ".join(d.reasons)
                                        for d in axes)
    failing = [d.axis for d in axes if d.best_log10_found is None or d.best_log10_found > math.log10(d.target)]
    reason = (note + " | " if note else "") + (
        f"unmet axes at N={problem.grid['N'][n_last]}: {failing}" if failing else "each axis is met somewhere but never jointly"
    )
    return InfeasibilityCertificate(
        scenario_id=problem.scenario_id, protocol_id=problem.protocol_id, game_id=problem.game,
        status=CertificateStatus.OUT_OF_MODEL if out_of_model else CertificateStatus.INFEASIBLE,
        targets=problem.targets, probed_at={"N": problem.grid["N"][n_last], "threshold_stride": stride},
        axes=axes, missing_assumptions=sorted(missing), reason=reason,
    )
