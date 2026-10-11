"""G1 cross-implementation agreement: lane C attack channels vs lane B Wiesner (via interfaces)."""

import json
import math
from pathlib import Path

import pytest

from qmint.attacks import crossrun
from qmint.attacks.heuristic import W1_PRODUCT_ATTACKS, joint_outcome_probs
from qmint.core.contracts import AttackResult, EvidenceKind

ROOT = Path(__file__).resolve().parents[2]

EXPECTED = {  # per-qubit both-pass, uniform BB84 secret (C's independent challenger values)
    "A01_basis_guess_resend": 5 / 8,
    "A01b_basis_guess_bayes_resend": (3 + math.sqrt(5)) / 8,
    "A02_breidbart_resend": 5 / 8,
    "A02b_breidbart_bayes_resend": (3 + math.sqrt(5)) / 8,
    "A03_universal_buzek_hillery": 2 / 3,
    "A03b_phase_covariant_xz": (3 + 2 * math.sqrt(2)) / 8,
    "A04_mvw_optimal_channel": 3 / 4,
}


@pytest.mark.parametrize("attack_id", sorted(EXPECTED))
@pytest.mark.parametrize("n", [1, 2, 3])
def test_lane_b_exact_equals_lane_c_and_closed_form(attack_id, n):
    kraus = W1_PRODUCT_ATTACKS[attack_id][0]()
    c = joint_outcome_probs(kraus)["pp"] ** n
    for seed in (0, 1, 2, 3):  # different hidden secrets: per-qubit values are state independent
        b = crossrun.b_exact_pair(kraus, n, seed)
        assert b == pytest.approx(EXPECTED[attack_id] ** n, abs=1e-12)
        assert b == pytest.approx(c, abs=1e-12)
    assert crossrun.CLOSED_FORM_PER_QUBIT[attack_id][0] == pytest.approx(EXPECTED[attack_id], abs=1e-15)


@pytest.mark.parametrize("attack_id", sorted(crossrun.F_CIRCUIT_OF))
def test_lane_f_circuits_match(attack_id):
    name = crossrun.F_CIRCUIT_OF[attack_id]
    assert crossrun.f_circuit_per_qubit(name) == pytest.approx(EXPECTED[attack_id], abs=1e-12)
    assert crossrun.f_kraus_on_b(name, 2, 5) == pytest.approx(EXPECTED[attack_id] ** 2, abs=1e-12)


def test_no_attack_exceeds_w1_optimum():
    for attack_id in EXPECTED:
        assert crossrun.b_exact_pair(W1_PRODUCT_ATTACKS[attack_id][0](), 1, 9) <= 0.75 + 1e-12


def test_crossrun_records_and_mc_cover_exact():
    out = crossrun.crossrun(ns=(1,), seeds=(0,), trials=300, seed=11)
    assert all(r["agrees"] for r in out["rows"])
    for r in out["rows"]:  # MC from B's destructive verify_pair is consistent with the exact value (4 sigma)
        mc, p = r["B_monte_carlo"], r["closed_form_value"]
        assert abs(mc["successes"] / mc["trials"] - p) < 4 * math.sqrt(p * (1 - p) / mc["trials"])
    kinds = {r.evidence_kind for r in out["records"]}
    assert kinds == {EvidenceKind.SIMULATOR_IDEAL, EvidenceKind.MONTE_CARLO}
    for r in out["records"]:
        assert isinstance(r, AttackResult)
        assert r.proof_applicability == "IN_MODEL" and r.theorem_upper_bound == pytest.approx(0.75)
        assert "lane B" in r.backend_kind


def test_secret_leak_control_out_of_model_on_both_implementations():
    leak = crossrun.secret_leak_control(n=3, trials=20, seed=4)
    assert leak["agrees"]
    assert leak["B_exact_pair_acceptance"] == pytest.approx(1.0, abs=1e-12)
    assert leak["record"].proof_applicability == "OUT_OF_MODEL" and leak["record"].theorem_upper_bound is None


def test_secret_boundary_live():
    assert all(crossrun.secret_boundary_checks().values())


def test_committed_g1_evidence_all_pass():
    ev = json.loads((ROOT / "handoffs" / "Q-G1_evidence.json").read_text())
    assert ev["gate"] == "G1" and ev["all_pass"] is True
    assert set(ev["checks"]) == {
        "C_sdp_n1", "D_independent_exact_recheck", "F_bb84_three_way_agreement", "B_secret_boundary",
        "Q_cross_implementation", "Q_secret_leak_control",
    }
    for rec in ev["attack_results"]:
        AttackResult.model_validate(rec)
