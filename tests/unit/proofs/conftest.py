"""Shared fixtures for lane-D proof tests (deterministic, no network)."""

from __future__ import annotations

import math

import pytest

from qmint.proofs.registry import default_registry


def _decl(claim_id: str) -> list[str]:
    return list(default_registry().claim(claim_id).required_declarations)


@pytest.fixture
def decl():
    return _decl


@pytest.fixture
def kent_fig5_params(decl):
    """Kent 2022 Fig. 5 point theta=10deg, E=0.058, beta=6e-6 (Methods p.12) with an admissible
    (gamma_err, nu_cor) choice; hypothetical improved source, so noise_source='hypothetical'."""
    return dict(
        N=40_000_000,
        P_det=0.019,
        gamma_det=0.018,
        E=0.058,
        gamma_err=0.0613,
        nu_cor=0.0094,
        beta_PB=6e-6,
        beta_PS=6e-6,
        theta=math.radians(10),
        P_noqub=1 - 1.09 * math.exp(-0.09),
        nu_unf=3.9e-3,
        beta_E=1e-10,
        noise_source="hypothetical",
        declared_assumptions=decl("P-S2"),
    )


@pytest.fixture
def d1_params(decl):
    """Schiansky 2023 SI Table 2 tuple."""
    return dict(
        N=4_200_000,
        p_m=0.0602,
        delta_d=0.01,
        delta_h=0.031,
        e_h=0.03278,
        l_h=0.224,
        noise_source="published_schiansky_2023",
        declared_assumptions=decl("P-D1"),
    )
