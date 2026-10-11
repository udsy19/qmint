"""F4: photonic source/loss/detector model, kept separate from qubit gate noise."""

import ast
import math
from pathlib import Path

import pytest

from qmint.core.contracts import EvidenceKind
from qmint.quantum import photonic_model as pm
from qmint.quantum.records import clopper_pearson


def test_module_is_independent_of_gate_noise():
    tree = ast.parse(Path(pm.__file__).read_text())
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mods.add(node.module or "")
        elif isinstance(node, ast.Import):
            mods.update(a.name for a in node.names)
    assert not any(m.startswith(("qmint.quantum.channels", "qiskit", "qmint.quantum.circuits")) for m in mods)
    assert pm.PHOTONIC_EVIDENCE_KIND == EvidenceKind.SYNTHETIC != EvidenceKind.PHOTON_EXPERIMENT


def test_validation():
    with pytest.raises(ValueError):
        pm.PhotonicLinkParams(eta_link=1.5)
    with pytest.raises(ValueError):
        pm.PhotonicLinkParams(mu=-1)
    with pytest.raises(ValueError):
        pm.transmission_from_loss_db(-3)
    assert abs(pm.transmission_from_loss_db(10) - 0.1) < 1e-15


@pytest.mark.parametrize("mu", [0.0, 0.1, 0.5, 2.0])
def test_poisson_multiphoton_closed_form(mu):
    f = pm.multiphoton_fraction(pm.PhotonicLinkParams(mu=mu))
    assert abs(f["p_vacuum"] - math.exp(-mu)) < 1e-14
    assert abs(f["p_multi"] - (1 - math.exp(-mu) * (1 + mu))) < 1e-12


def test_heralded_reduces_vacuum():
    p = pm.PhotonicLinkParams(source="heralded_spdc", mu=0.1, herald_efficiency=0.5)
    f = pm.multiphoton_fraction(p)
    assert f["p_vacuum"] == 0.0  # no herald dark counts -> herald implies >= 1 photon
    # P(k|herald) ∝ r^k (1-(1/2)^k), r = mu/(1+mu); sum_{k>=1} = r/(1-r) - (r/2)/(1-r/2)
    r = 0.1 / 1.1
    total = r / (1 - r) - (r / 2) / (1 - r / 2)
    assert abs(f["p_single"] - (r / 2) / total) < 1e-12
    assert abs(f["p_multi"] - (total - r / 2) / total) < 1e-12


@pytest.mark.parametrize(
    "params",
    [
        pm.PhotonicLinkParams(mu=0.5, eta_link=0.3, eta_det=0.6, p_dark=1e-3, e_opt=0.02),
        pm.PhotonicLinkParams(source="heralded_spdc", mu=0.2, herald_efficiency=0.4, herald_dark_prob=1e-3,
                              eta_link=0.5, eta_det=0.8, p_dark=1e-2, e_opt=0.05),
    ],
)
def test_click_statistics_consistent_and_match_monte_carlo(params):
    cs = pm.click_statistics(params)
    total = cs["p_no_click"] + cs["p_correct_only"] + cs["p_wrong_only"] + cs["p_double"]
    assert abs(total - 1) < 1e-12
    pulses = 100_000
    ev = pm.simulate_pulses(params, pulses, seed=4)
    s = ev.summary()
    assert ev.evidence_kind == EvidenceKind.SYNTHETIC
    for key, val in (("detected_pulses", cs["p_detect"]), ("decoded_ok", cs["p_pass"])):
        ci = clopper_pearson(s[key], pulses, 0.9999)
        assert ci.lo <= val <= ci.hi, key


def test_ideal_poisson_detection_closed_form():
    p = pm.PhotonicLinkParams(mu=0.4, eta_link=0.25, eta_det=0.5)
    cs = pm.click_statistics(p)
    assert abs(cs["p_detect"] - (1 - math.exp(-0.4 * 0.125))) < 1e-14
    assert cs["qber_given_detect"] == 0.0


def test_dark_counts_only_give_random_bits():
    cs = pm.click_statistics(pm.PhotonicLinkParams(mu=0.0, p_dark=0.01))
    assert abs(cs["qber_given_detect"] - 0.5) < 1e-12


def test_note_acceptance_without_loss_tolerance_collapses():
    p = pm.PhotonicLinkParams(mu=0.1, eta_link=pm.transmission_from_loss_db(3), eta_det=0.6)
    assert pm.note_accept_probability(p, 8) < 1e-6
