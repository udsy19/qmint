from __future__ import annotations

import math
from decimal import Decimal, getcontext

import pytest

from qmint.core.contracts import (
    BoundRequest,
    BoundResult,
    CalibrationRecord,
    EvidenceKind,
    GameId,
    Interval,
    ProofStatus,
    SecurityAxis,
    Unit,
)
from qmint.core.interfaces import ProofEvaluator
from qmint.proofs.engine import ProofEngine
from qmint.proofs.ideal_bounds import (
    IDEAL_BASES,
    IdealBoundEvaluator,
    UnsupportedGameError,
    log10_bound,
    min_length_for_target,
)

PROTO = {GameId.W1: "wiesner_ideal", GameId.W1_CV: "wiesner_ideal", GameId.S1: "s_money_kent_2022_ideal_2site"}
CLAIM = {GameId.W1: "P-W1", GameId.W1_CV: "P-W1CV", GameId.S1: "P-S1"}
KEY = {GameId.W1: "n", GameId.W1_CV: "n", GameId.S1: "N"}


def _req(game, n, decl, axis=SecurityAxis.UNFORGEABILITY, **extra):
    params = {KEY[game]: n, "declared_assumptions": decl(CLAIM[game]), **extra}
    return BoundRequest(protocol_id=PROTO[game], game_id=game, axis=axis, parameters=params)


def test_implements_frozen_interface():
    assert isinstance(IdealBoundEvaluator(), ProofEvaluator)
    assert isinstance(ProofEngine(), ProofEvaluator)


@pytest.mark.parametrize(
    "game,base",
    [(GameId.W1, 0.75), (GameId.W1_CV, 0.75 + math.sqrt(2) / 8), (GameId.S1, 0.5 + 1 / (2 * math.sqrt(2)))],
)
def test_published_bases(game, base):
    assert IDEAL_BASES[game][0] == pytest.approx(base, rel=1e-15)
    assert 10 ** log10_bound(game, 1) == pytest.approx(base, rel=1e-14)


@pytest.mark.parametrize("game,expected", [("W1", 73), ("W1_CV", 273), ("S1", 131)])
def test_min_length_matches_bootstrap_behaviour(game, expected):
    n = min_length_for_target(game, 1e-9)
    assert n == expected
    assert log10_bound(game, n) <= -9 < log10_bound(game, n - 1)


@pytest.mark.parametrize("game", ["W1", "W1_CV", "S1"])
@pytest.mark.parametrize("eps", [0.5, 1e-3, 1e-9, 1e-30, 1e-300])
def test_min_length_rounding_is_exact(game, eps):
    n = min_length_for_target(game, eps)
    assert n * math.log10(IDEAL_BASES[GameId(game)][0]) <= math.log10(eps)
    if n > 1:
        assert (n - 1) * math.log10(IDEAL_BASES[GameId(game)][0]) > math.log10(eps)


@pytest.mark.parametrize("game", list(IDEAL_BASES))
@pytest.mark.parametrize("n", [1, 2, 8, 16, 32, 64, 128, 10**3, 10**5, 10**6])
def test_log_space_stability_against_decimal(game, n):
    getcontext().prec = 50
    r2 = Decimal(2).sqrt()
    base = {GameId.W1: Decimal(3) / 4, GameId.W1_CV: Decimal(3) / 4 + r2 / 8, GameId.S1: Decimal(1) / 2 + 1 / (2 * r2)}[game]
    exact = n * base.log10()
    got = log10_bound(game, n)
    assert math.isfinite(got)
    assert abs(Decimal(repr(got)) - exact) <= Decimal("1e-12") * max(Decimal(1), abs(exact))


def test_huge_n_has_no_underflow_to_zero(decl):
    r = IdealBoundEvaluator().evaluate(_req(GameId.W1, 10**6, decl))
    assert r.value is None  # not representable -> None, never 0.0
    assert r.log10_value == pytest.approx(10**6 * math.log10(0.75), rel=1e-12)
    assert r.theorem_id == "P-W1/unf" and r.status == ProofStatus.PUBLISHED_REPRODUCED
    assert r.evidence_kind == EvidenceKind.PUBLISHED_THEOREM


def test_result_is_frozen_contract(decl):
    r = IdealBoundEvaluator().evaluate(_req(GameId.S1, 131, decl))
    assert isinstance(r, BoundResult)
    assert r.value == pytest.approx((0.5 + 1 / (2 * math.sqrt(2))) ** 131, rel=1e-12)
    assert BoundResult.model_validate(r.model_dump()) == r  # round-trips through the frozen C5 schema


@pytest.mark.parametrize("game", ["W2", "S2", "D1", "A1", "C1", "NOPE"])
def test_w1_formula_refused_for_other_games(game):
    with pytest.raises(UnsupportedGameError):
        log10_bound(game, 10)
    with pytest.raises(UnsupportedGameError):
        min_length_for_target(game, 1e-9)


@pytest.mark.parametrize(
    "protocol,game",
    [("wiesner_noisy", "W2"), ("s_money_kent_2022_realistic", "S2"), ("schiansky_payment_2023", "D1")],
)
def test_ideal_evaluator_refuses_noisy_games(protocol, game, decl):
    req = BoundRequest(protocol_id=protocol, game_id=game, axis="epsilon_unf",
                       parameters={"n": 100, "N": 100, "declared_assumptions": decl("P-W1")})
    r = IdealBoundEvaluator().evaluate(req)
    assert r.value is None and r.log10_value is None
    assert r.status == ProofStatus.UNSUPPORTED and r.out_of_domain


def test_w2_has_no_bound_through_engine(decl):
    req = BoundRequest(protocol_id="wiesner_noisy", game_id="W2", axis="epsilon_unf",
                       parameters={"n": 100, "declared_assumptions": decl("P-W1")})
    r = ProofEngine().evaluate(req)
    assert r.value is None and r.log10_value is None and r.status == ProofStatus.UNSUPPORTED


@pytest.mark.parametrize("bad", [{"error_threshold": 0.05}, {"loss_tolerance": 0.1}, {"verifier": "threshold"},
                                 {"verification_oracle_queries": 3}, {"E": 0.01}])
def test_noise_or_oracle_makes_ideal_bound_inapplicable(bad, decl):
    r = IdealBoundEvaluator().evaluate(_req(GameId.W1, 64, decl, **bad))
    assert r.value is None and r.log10_value is None
    assert r.failed_assumptions and all(f.startswith("OUT_OF_MODEL") for f in r.failed_assumptions)


def test_noisy_calibration_blocks_ideal_bound(decl):
    cal = CalibrationRecord(
        calibration_id="c", device_id="d", experiment_family="kent_2022", data_origin=EvidenceKind.PUBLISHED_AGGREGATE,
        n_events=10, confidence_level=0.95, interval_method="cp", independence_assumptions=["iid"],
        qber_interval=Interval(lo=0.01, hi=0.03, unit=Unit.FRACTION),
    )
    req = BoundRequest(protocol_id="wiesner_ideal", game_id="W1", axis="epsilon_unf",
                       parameters={"n": 64, "declared_assumptions": decl("P-W1")}, calibration=cal)
    r = IdealBoundEvaluator().evaluate(req)
    assert r.value is None and any("calibration_qber" in f for f in r.failed_assumptions)


def test_undeclared_hypothesis_is_assumption_missing():
    req = BoundRequest(protocol_id="wiesner_ideal", game_id="W1", axis="epsilon_unf", parameters={"n": 64})
    r = IdealBoundEvaluator().evaluate(req)
    assert r.value is None
    assert "ASSUMPTION_MISSING:single_note_no_oracle" in r.failed_assumptions


@pytest.mark.parametrize("game", list(IDEAL_BASES))
def test_no_privacy_theorem_never_zero(game, decl):
    for axis in (SecurityAxis.PRIVACY, SecurityAxis.CORRECTNESS, SecurityAxis.ROBUSTNESS):
        r = IdealBoundEvaluator().evaluate(_req(game, 64, decl, axis=axis))
        assert r.value is None and r.log10_value is None and r.status == ProofStatus.UNSUPPORTED


def test_s1_is_two_site_only(decl):
    r = IdealBoundEvaluator().evaluate(_req(GameId.S1, 64, decl, M=2))
    assert r.value is None


@pytest.mark.parametrize("n", [0, -1, 1.5, True, None, "64"])
def test_bad_lengths_refused(n, decl):
    r = IdealBoundEvaluator().evaluate(_req(GameId.W1, n, decl))
    assert r.value is None and r.out_of_domain
    if not isinstance(n, (str, type(None), float)):
        with pytest.raises(ValueError):
            log10_bound("W1", n)


@pytest.mark.parametrize("eps", [0, 1, -1, 2, float("nan"), float("inf")])
def test_bad_targets_refused(eps):
    with pytest.raises(ValueError):
        min_length_for_target("W1", eps)


def test_variant_bound_is_larger_than_w1(decl):
    a = IdealBoundEvaluator().evaluate(_req(GameId.W1, 50, decl))
    b = IdealBoundEvaluator().evaluate(_req(GameId.W1_CV, 50, decl))
    assert b.log10_value > a.log10_value  # substituting W1 for W1_CV would be optimistic
