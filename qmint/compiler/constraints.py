"""Parameter-space DSL for the security-certificate compiler (lane I, master plan 4.1-4.3, 7 Lane I).

A ``Problem`` is one fully specified, paper-faithful request: a registered (protocol, game) pair with a
published theorem, a device description (scalars or ``{"lo", "hi"}`` intervals, exactly the parameter
names of lane D's ``qmint.proofs.finite_size`` / ``ideal_bounds``), declared theorem hypotheses,
targets, and a finite decision grid shared by every selector.

Supported families and their decision variables (everything else is rejected, never approximated):

  ideal  W1 / W1_CV / S1   n or N                                             (MVW2012 Thm 1-2, KLPR2022 Lemma 1)
  S2     Kent 2022 QT1/QT2 N, gamma_det, gamma_err, nu_cor, nu_unf          (KLPR2022 Lemmas 2-4, Thm 1-2)
                           device: P_det, E, beta_PB, beta_PS, theta, P_noqub (from mu), beta_E, M, C,
                           reporting strategy in {QT1, QT2}
  D1     Schiansky 2023    N, delta_d, delta_h                              (SI Eqs. 19-23)
                           device: e_h, l_h, p_m, merchants = 2.
                           D1 is NEVER certifiable (lane D checker): outputs are UNCERTIFIED by construction.

S2 threshold coordinates are relative to the WORST-CASE device endpoint (P_det_lo, E_hi,
beta_PB_hi, P_noqub_hi) so the same grid is valid on every corner of an uncertainty box; see
``benchmarks/frozen_experiments.yaml`` (grids).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import cached_property, lru_cache
from pathlib import Path
from typing import Any

import yaml

from qmint.core.contracts import CalibrationRecord, GameId, SecurityAxis, Targets
from qmint.core.serialization import canonical_hash
from qmint.proofs.assumption_check import endpoints
from qmint.proofs.registry import default_registry
from qmint.proofs.reproduce import kent_p_noqub

ROOT = Path(__file__).resolve().parents[2]
FROZEN_PATH = ROOT / "benchmarks" / "frozen_experiments.yaml"


class UnsupportedCombination(ValueError):
    """The request combines a protocol/game/parameter/assumption the published theorems do not cover."""


FAMILY_OF_GAME: dict[GameId, str] = {GameId.W1: "ideal", GameId.W1_CV: "ideal", GameId.S1: "ideal",
                                     GameId.S2: "S2", GameId.D1: "D1"}
PROTOCOL_OF_GAME: dict[GameId, str] = {
    GameId.W1: "wiesner_ideal",
    GameId.W1_CV: "wiesner_ideal",
    GameId.S1: "s_money_kent_2022_ideal_2site",
    GameId.S2: "s_money_kent_2022_realistic",
    GameId.D1: "schiansky_payment_2023",
}
CLAIM_OF_GAME: dict[GameId, str] = {GameId.W1: "P-W1", GameId.W1_CV: "P-W1CV", GameId.S1: "P-S1",
                                    GameId.S2: "P-S2", GameId.D1: "P-D1"}
SECURITY_MODEL: dict[GameId, str] = {
    GameId.W1: "MVW2012-Thm1-simple-counterfeiting",
    GameId.W1_CV: "MVW2012-Thm2-classical-verification",
    GameId.S1: "KLPR2022-Lemma1-ideal-2site",
    GameId.S2: "KLPR2022-QT1QT2-Table6",
    GameId.D1: "Schiansky2023-SI-Note3",
}
LENGTH_KEY: dict[GameId, str] = {GameId.W1: "n", GameId.W1_CV: "n", GameId.S1: "N", GameId.S2: "N", GameId.D1: "N"}

# Device keys each family accepts (anything else is an unsupported combination).
_DEVICE_KEYS: dict[str, frozenset[str]] = {
    "ideal": frozenset(),
    "S2": frozenset({"P_det", "E", "beta_PB", "beta_PS", "theta", "P_noqub", "beta_E", "M", "C"}),
    "D1": frozenset({"e_h", "l_h", "p_m", "merchants"}),
}
_META_KEYS = frozenset({"declared_assumptions", "noise_source", "reporting_strategy"})
ALLOWED_REPORTING = frozenset({"QT1", "QT2"})  # KLPR2022 Lemma 5: only these satisfy Table 6 C/D
CALIBRATION_FAMILY = {"S2": "kent_2022", "D1": "schiansky_2023"}

# Decision axes per family (order = grid-index tuple order used by the tie-break).
DECISION_AXES: dict[str, tuple[str, ...]] = {
    "ideal": ("N",),
    "S2": ("N", "r_det", "r_err", "r_cor", "r_unf"),
    "D1": ("N", "delta_d", "delta_h"),
}
# Decision parameters each lane-D bound actually reads (from qmint.proofs.finite_size.FORMULAS keys).
AXIS_DECISIONS: dict[str, dict[SecurityAxis, tuple[str, ...]]] = {
    "ideal": {SecurityAxis.UNFORGEABILITY: ("N",)},
    "S2": {
        SecurityAxis.ROBUSTNESS: ("N", "gamma_det"),
        SecurityAxis.CORRECTNESS: ("N", "gamma_err", "nu_cor"),
        SecurityAxis.UNFORGEABILITY: ("N", "gamma_det", "gamma_err", "nu_unf"),
        SecurityAxis.PRIVACY: (),
    },
    "D1": {
        SecurityAxis.UNFORGEABILITY: ("N", "delta_d", "delta_h"),
        SecurityAxis.CORRECTNESS: ("N", "delta_d", "delta_h"),
    },
}


# --------------------------------------------------------------------------- #
# Frozen pre-registration
# --------------------------------------------------------------------------- #


@lru_cache(maxsize=1)
def frozen() -> dict[str, Any]:
    return yaml.safe_load(FROZEN_PATH.read_text(encoding="utf-8"))


def _geom_int(k_lo: int, k_hi: int) -> tuple[int, ...]:
    vals = tuple(round(10 ** (k / 40)) for k in range(k_lo, k_hi + 1))
    if len(set(vals)) != len(vals):
        raise ValueError("N grid has duplicate rounded values")
    return vals


def build_grid(family: str, *, small: bool = False) -> dict[str, tuple[float, ...]]:
    """The pre-registered grid (every axis sorted ascending). ``small`` = the oracle-agreement strides."""
    g = frozen()["grids"]
    if family == "ideal":
        spec = g["ideal"]["N"]
        out: dict[str, tuple[float, ...]] = {"N": tuple(range(spec["lo"], spec["hi"] + 1))}
        strides = {"N": g["ideal"]["small"]["N_stride"]}
    elif family == "S2":
        s = g["S2"]
        out = {
            "N": _geom_int(s["N"]["k_lo"], s["N"]["k_hi"]),
            "r_det": tuple(sorted(1 - 10 ** (-j / 10) for j in range(s["r_det"]["j_lo"], s["r_det"]["j_hi"] + 1))),
            "r_err": tuple(sorted(1 + 10 ** (-j / 10) for j in range(s["r_err"]["j_lo"], s["r_err"]["j_hi"] + 1))),
            "r_cor": tuple(sorted(1 - 10 ** (-j / 10) for j in range(s["r_cor"]["j_lo"], s["r_cor"]["j_hi"] + 1))),
            "r_unf": tuple(sorted(1 + 10 ** (-j / 10) for j in range(s["r_unf"]["j_lo"], s["r_unf"]["j_hi"] + 1))),
        }
        strides = {"N": s["small"]["N_stride"], **{a: s["small"][f"{a}_stride"] for a in ("r_det", "r_err", "r_cor", "r_unf")}}
    elif family == "D1":
        s = g["D1"]
        out = {
            "N": _geom_int(s["N"]["k_lo"], s["N"]["k_hi"]),
            "delta_d": tuple(10 ** (-3 + i / 40) for i in range(s["delta_d"]["i_lo"], s["delta_d"]["i_hi"] + 1)),
            "delta_h": tuple(10 ** (-3 + i / 40) for i in range(s["delta_h"]["i_lo"], s["delta_h"]["i_hi"] + 1)),
        }
        strides = {"N": s["small"]["N_stride"], "delta_d": s["small"]["delta_d_stride"], "delta_h": s["small"]["delta_h_stride"]}
    else:
        raise UnsupportedCombination(f"no grid for family {family!r}")
    if small:  # stride over the ascending value list, starting at index 0
        out = {a: v[:: strides[a]] for a, v in out.items()}
    return out


# --------------------------------------------------------------------------- #
# Problem
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Problem:
    scenario_id: str
    game: GameId
    device: Mapping[str, Any]
    targets: Targets
    grid: Mapping[str, tuple[float, ...]]
    calibration: CalibrationRecord | None = None
    meta: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate(self.game, self.device, self.targets, self.calibration)
        fam = self.family
        if tuple(self.grid) != DECISION_AXES[fam]:
            raise UnsupportedCombination(f"grid axes {tuple(self.grid)} != {DECISION_AXES[fam]} for {fam}")
        for a, vals in self.grid.items():
            if not vals or list(vals) != sorted(vals):
                raise UnsupportedCombination(f"grid axis {a} must be non-empty and ascending")

    # -- identity -------------------------------------------------------------
    @property
    def family(self) -> str:
        return FAMILY_OF_GAME[self.game]

    @property
    def protocol_id(self) -> str:
        return PROTOCOL_OF_GAME[self.game]

    @property
    def axis_names(self) -> tuple[str, ...]:
        return DECISION_AXES[self.family]

    @property
    def shape(self) -> tuple[int, ...]:
        return tuple(len(self.grid[a]) for a in self.axis_names)

    @property
    def target_axes(self) -> tuple[SecurityAxis, ...]:
        return tuple(a for a in SecurityAxis if getattr(self.targets, a.value) is not None)

    def target_log10(self, axis: SecurityAxis) -> float:
        return math.log10(getattr(self.targets, axis.value))

    @cached_property
    def device_hash(self) -> str:
        return canonical_hash({"device": dict(self.device), "calibration": self.calibration})

    # -- worst-case anchors for the relative S2 coordinates --------------------
    @cached_property
    def anchors(self) -> dict[str, float]:
        if self.family != "S2":
            return {}
        d = self.device
        p_det_lo = endpoints(d["P_det"])[0]
        b_pb_hi = endpoints(d["beta_PB"])[1]
        return {
            "P_det_lo": p_det_lo,
            "E_hi": endpoints(d["E"])[1],
            "A_lo": p_det_lo * (1 - 2 * b_pb_hi),
            "P_noqub_hi": endpoints(d["P_noqub"])[1],
        }

    # -- grid index -> engine parameters ------------------------------------
    def decision_values(self, idx: tuple[int, ...]) -> dict[str, float]:
        """Map a grid-index tuple to the theorem's decision parameters."""
        v = {a: self.grid[a][i] for a, i in zip(self.axis_names, idx, strict=True)}
        return self.decisions_from_coords(v)

    def decisions_from_coords(self, v: Mapping[str, float]) -> dict[str, Any]:
        fam = self.family
        if fam == "ideal":
            return {LENGTH_KEY[self.game]: int(v["N"])}
        if fam == "D1":
            return {"N": int(v["N"]), "delta_d": v["delta_d"], "delta_h": v["delta_h"]}
        a = self.anchors
        return {
            "N": int(v["N"]),
            "gamma_det": v["r_det"] * a["P_det_lo"],
            "gamma_err": v["r_err"] * a["E_hi"],
            "nu_cor": v["r_cor"] * a["A_lo"] / 2,
            "nu_unf": v["r_unf"] * a["P_noqub_hi"],
        }

    def engine_params(self, decisions: Mapping[str, Any], axis: SecurityAxis | None = None) -> dict[str, Any]:
        """Device + decision parameters for one axis (only the decisions that axis reads) or all axes."""
        if axis is not None and self.family != "ideal":
            keys = AXIS_DECISIONS[self.family].get(axis, ())
            decisions = {k: decisions[k] for k in keys if k in decisions}
        return {**self.device, **decisions}


# --------------------------------------------------------------------------- #
# Validation: reject unsupported combinations (never borrow an approximate formula)
# --------------------------------------------------------------------------- #


def validate(game: GameId | str, device: Mapping[str, Any], targets: Targets, calibration: CalibrationRecord | None) -> None:
    try:
        g = GameId(game)
    except ValueError as e:
        raise UnsupportedCombination(f"unknown game {game!r}") from e
    if g not in FAMILY_OF_GAME:
        raise UnsupportedCombination(
            f"game {g.value}: no published theorem / certified bound registered (lane D); the compiler refuses it"
        )
    fam = FAMILY_OF_GAME[g]
    if all(getattr(targets, a.value) is None for a in SecurityAxis):
        raise UnsupportedCombination("at least one epsilon target is required")
    if targets.epsilon_unf is None:
        raise UnsupportedCombination("an unforgeability target is mandatory (security first, then cost)")
    unknown = set(device) - _DEVICE_KEYS[fam] - _META_KEYS
    if unknown:
        raise UnsupportedCombination(f"{fam}: parameters {sorted(unknown)} are not part of the {g.value} theorem")
    if not device.get("declared_assumptions"):
        raise UnsupportedCombination("declared_assumptions missing: theorem hypotheses must be declared explicitly")
    if fam == "ideal":
        if calibration is not None:
            raise UnsupportedCombination("ideal theorems take no calibration (noise-free model); use S2/D1")
        return
    if calibration is not None and calibration.experiment_family != CALIBRATION_FAMILY[fam]:
        raise UnsupportedCombination(
            f"calibration family {calibration.experiment_family!r} cannot be used in the {g.value} proof model "
            f"(needs {CALIBRATION_FAMILY[fam]!r}; no cross-protocol calibration transfer)"
        )
    if fam == "S2":
        rs = device.get("reporting_strategy")
        if rs not in ALLOWED_REPORTING:
            raise UnsupportedCombination(
                f"reporting strategy {rs!r} unsupported: only {sorted(ALLOWED_REPORTING)} satisfy KLPR2022 Table 6 C/D (Lemma 5)"
            )
        for k in ("P_det", "E", "beta_PB", "beta_PS", "theta", "P_noqub"):
            if device.get(k) is None:
                raise UnsupportedCombination(f"S2 device parameter {k} missing")
        lo, hi = endpoints(device["theta"])
        if not (0 < lo and hi < math.pi / 4):
            raise UnsupportedCombination("theta must lie in (0, pi/4) on the whole interval (Table 5 item 2)")
        for k in ("beta_PB", "beta_PS"):
            lo, hi = endpoints(device[k])
            if not (0 < lo and hi < 0.5):
                raise UnsupportedCombination(f"{k} must lie in (0, 1/2)")
        m = device.get("M", 1)
        if isinstance(m, bool) or not isinstance(m, int) or m < 1:
            raise UnsupportedCombination("M must be an integer >= 1")
        if m > 1 and device.get("C") is None:
            raise UnsupportedCombination("M > 1 requires C (number of spacelike-separated presentation-point pairs)")
        if targets.epsilon_priv is not None and device.get("beta_E") is None:
            raise UnsupportedCombination("privacy target requires beta_E (Lemma 4)")
    if fam == "D1":
        if device.get("merchants", 2) != 2:
            raise UnsupportedCombination("D1 analysis covers exactly two merchants (SI Note 3A)")
        for k in ("e_h", "l_h", "p_m"):
            if device.get(k) is None and not (calibration is not None and k == "e_h" and calibration.qber_interval):
                raise UnsupportedCombination(f"D1 device parameter {k} missing")


# --------------------------------------------------------------------------- #
# Frozen scenario construction
# --------------------------------------------------------------------------- #


def declarations(game: GameId) -> list[str]:
    """The theorem hypotheses a scenario must DECLARE (unverifiable idealisations; recorded as declared)."""
    return list(default_registry().claim(CLAIM_OF_GAME[game]).required_declarations)


def _rel_interval(x: float, rel: float) -> dict[str, float]:
    return {"lo": x * (1 - rel), "hi": x * (1 + rel)}


def s2_device(name: str, *, interval: bool, M: int = 1, beta_E: float | None = None) -> dict[str, Any]:
    """Engine-ready KLPR2022 device for a frozen device id (point or HYPOTHETICAL interval box)."""
    spec = frozen()["devices"]["S2"]
    common, dev = spec["common"], spec[name]
    p_det, mu = common["P_det"]["value"], common["mu"]["value"]
    th = dev["theta_deg"]
    b_pb = dev.get("beta_PB", dev.get("beta"))
    b_ps = dev.get("beta_PS", dev.get("beta"))
    out: dict[str, Any] = {
        "reporting_strategy": common["reporting_strategy"]["value"],
        "noise_source": dev.get("noise_source", common["noise_source"]),
        "declared_assumptions": declarations(GameId.S2),
        "M": M,
    }
    if M > 1:
        L = 2**M
        out["C"] = L * (L - 1) // 2
    if not interval:
        out.update(P_det=p_det, E=dev["E"], beta_PB=b_pb, beta_PS=b_ps, theta=math.radians(th), P_noqub=kent_p_noqub(mu))
    else:
        s = spec["interval_stress"]
        th_lo = max(th - s["theta_abs_deg"], 1e-6)
        out.update(
            P_det=_rel_interval(p_det, s["P_det_rel"]),
            E=_rel_interval(dev["E"], s["E_rel"]),
            beta_PB=_rel_interval(b_pb, s["beta_rel"]),
            beta_PS=_rel_interval(b_ps, s["beta_rel"]),
            theta={"lo": math.radians(th_lo), "hi": math.radians(th + s["theta_abs_deg"])},
            P_noqub={"lo": kent_p_noqub(mu * (1 - s["mu_rel"])), "hi": kent_p_noqub(mu * (1 + s["mu_rel"]))},
        )
    if beta_E is not None:
        out["beta_E"] = beta_E
    return out


def _d1_value(v: Mapping[str, Any]) -> Any:
    return {"lo": v["lo"], "hi": v["hi"]} if "lo" in v else v["value"]


def d1_device(name: str) -> dict[str, Any]:
    """Engine-ready Schiansky 2023 device. For Zenodo-derived devices e_h is omitted: the caller must
    supply the ``CalibrationRecord`` (qmint.compiler.calibration) whose qber interval becomes e_h."""
    spec = frozen()["devices"]["D1"]
    dev = spec[name]
    out: dict[str, Any] = {
        "merchants": spec["common"]["merchants"],
        "declared_assumptions": declarations(GameId.D1),
        "l_h": _d1_value(dev["l_h"]),
        "p_m": _d1_value(dev["p_m"]),
        "noise_source": dev.get("noise_source", "calibration"),
    }
    if "value" in dev["e_h"] or "lo" in dev["e_h"]:
        out["e_h"] = _d1_value(dev["e_h"])
    return out


def ideal_device(game: GameId) -> dict[str, Any]:
    return {"declared_assumptions": declarations(game)}


def make_targets(game: GameId, eps_unf: float, honest: float | None, eps_priv: float | None = None) -> Targets:
    fam = FAMILY_OF_GAME.get(GameId(game))
    kw: dict[str, float | None] = {"epsilon_unf": eps_unf, "epsilon_priv": eps_priv}
    if honest is not None:
        if fam == "S2":
            kw.update(epsilon_rob=honest / 2, epsilon_cor=honest / 2)
        elif fam == "D1":
            kw["epsilon_cor"] = honest
        else:
            raise UnsupportedCombination(f"{game}: no honest-failure model in the ideal theorem")
    return Targets(**kw)
