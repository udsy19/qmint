"""DSL: paper-faithful parameter spaces; unsupported combinations are rejected, never approximated."""

from __future__ import annotations

import math

import pytest

from qmint.compiler.calibration import calibration_record
from qmint.compiler.constraints import (
    Problem,
    UnsupportedCombination,
    build_grid,
    d1_device,
    declarations,
    ideal_device,
    make_targets,
    s2_device,
)
from qmint.core.contracts import GameId, Targets


@pytest.mark.parametrize("game", [GameId.W2, GameId.A1, GameId.C1])
def test_games_without_theorem_are_rejected(game):
    with pytest.raises(UnsupportedCombination, match="no published theorem"):
        Problem("x", game, {"declared_assumptions": ["a"]}, Targets(epsilon_unf=1e-9), build_grid("ideal"))


def test_reporting_strategy_outside_lemma5_rejected():
    dev = {**s2_device("K22-F5a", interval=False), "reporting_strategy": "report_with_basis"}
    with pytest.raises(UnsupportedCombination, match="Table 6 C/D"):
        Problem("x", GameId.S2, dev, make_targets(GameId.S2, 1e-9, 1e-3), build_grid("S2"))


def test_ideal_game_refuses_noise_parameters_and_honest_targets():
    with pytest.raises(UnsupportedCombination, match="not part of the W1 theorem"):
        Problem("x", GameId.W1, {**ideal_device(GameId.W1), "E": 0.01}, Targets(epsilon_unf=1e-9), build_grid("ideal"))
    with pytest.raises(UnsupportedCombination, match="no honest-failure model"):
        make_targets(GameId.W1, 1e-9, 1e-3)


def test_cross_protocol_calibration_rejected():
    with pytest.raises(UnsupportedCombination, match="no cross-protocol calibration transfer"):
        Problem("x", GameId.S2, s2_device("K22-F5a", interval=False), make_targets(GameId.S2, 1e-9, 1e-3),
                build_grid("S2"), calibration=calibration_record("iid"))


def test_d1_two_merchants_only_and_s2_domain_checks():
    with pytest.raises(UnsupportedCombination, match="two merchants"):
        Problem("x", GameId.D1, {**d1_device("D1-PUB-SI"), "merchants": 3}, make_targets(GameId.D1, 1e-9, 1e-3), build_grid("D1"))
    with pytest.raises(UnsupportedCombination, match="theta"):
        Problem("x", GameId.S2, {**s2_device("K22-F5a", interval=False), "theta": math.pi / 3},
                make_targets(GameId.S2, 1e-9, 1e-3), build_grid("S2"))
    with pytest.raises(UnsupportedCombination, match="requires C"):
        Problem("x", GameId.S2, {**s2_device("K22-F5a", interval=False), "M": 2}, make_targets(GameId.S2, 1e-9, 1e-3),
                build_grid("S2"))


def test_declarations_and_unforgeability_target_mandatory():
    with pytest.raises(UnsupportedCombination, match="declared_assumptions"):
        Problem("x", GameId.W1, {}, Targets(epsilon_unf=1e-9), build_grid("ideal"))
    with pytest.raises(UnsupportedCombination, match="unforgeability target is mandatory"):
        Problem("x", GameId.S2, s2_device("K22-F5a", interval=False), Targets(epsilon_cor=1e-3), build_grid("S2"))


def test_grids_follow_preregistration():
    s2 = build_grid("S2")
    assert len(s2["N"]) == 281 and s2["N"][0] == 1000 and s2["N"][-1] == 10**10
    assert [len(s2[a]) for a in ("r_det", "r_err", "r_cor", "r_unf")] == [26, 30, 30, 30]
    assert all(list(v) == sorted(v) for v in s2.values())
    d1 = build_grid("D1")
    assert len(d1["N"]) == 321 and len(d1["delta_d"]) == 121 and d1["delta_d"][-1] == pytest.approx(1.0)
    assert build_grid("ideal")["N"] == tuple(range(1, 513))
    small = build_grid("S2", small=True)
    assert small["N"] == s2["N"][::8] and small["r_err"] == s2["r_err"][::4]


def test_relative_coordinates_use_worst_case_endpoints():
    p = Problem("x", GameId.S2, s2_device("K22-F5a", interval=True), make_targets(GameId.S2, 1e-9, 1e-3), build_grid("S2"))
    a = p.anchors
    assert a["P_det_lo"] == pytest.approx(0.019 * 0.98)
    assert a["E_hi"] == pytest.approx(0.058 * 1.03)
    dec = p.decision_values((0, 0, 0, 0, 0))
    assert dec["gamma_det"] < a["P_det_lo"] and dec["gamma_err"] > a["E_hi"] and dec["nu_unf"] > a["P_noqub_hi"]


def test_s2_sites_use_all_pairs():
    dev = s2_device("K22-F5a", interval=False, M=3)
    assert dev["C"] == 8 * 7 // 2
    assert set(declarations(GameId.S2)) <= set(dev["declared_assumptions"])
