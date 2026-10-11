"""Causality predicates: spacelike classification, ordering, violation detection."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from qmint.core.contracts import Site, TraceEvent
from qmint.networks.causality import (
    C_M_PER_NS,
    Order,
    Separation,
    Stamp,
    is_spacelike,
    order_with_uncertainty,
    propagation_violations,
    retrocausal_violations,
    separation,
)
from qmint.networks.topology import synthetic_two_site

A = Site(site_id="A", frame="f", x_m=0, y_m=0, trust_domain="t", clock_error_bound_ns=0)
B = Site(site_id="B", frame="f", x_m=C_M_PER_NS * 1000.0, y_m=0, trust_domain="t", clock_error_bound_ns=0)  # 1000 ns


def test_spacelike_basic():
    assert separation(0, A, 999, B) is Separation.SPACELIKE
    assert separation(0, A, 1000.001, B) is Separation.TIMELIKE_OR_LIGHTLIKE
    assert separation(0, A, -1500, B) is Separation.TIMELIKE_OR_LIGHTLIKE
    assert separation(0, A, 0, A) is Separation.TIMELIKE_OR_LIGHTLIKE  # same place, same time


def test_clock_uncertainty_makes_borderline_ambiguous():
    assert separation(0, A, 950, B, 30, 30) is Separation.AMBIGUOUS
    assert separation(0, A, 900, B, 30, 30) is Separation.SPACELIKE
    assert separation(0, A, 1100, B, 30, 30) is Separation.TIMELIKE_OR_LIGHTLIKE


def test_frames_must_match():
    C = Site(site_id="C", frame="other", x_m=0, y_m=0, trust_domain="t", clock_error_bound_ns=0)
    with pytest.raises(ValueError):
        separation(0, A, 0, C)


@given(st.floats(-1e4, 1e4), st.floats(-1e4, 1e4), st.floats(0, 500), st.floats(0, 500))
def test_separation_monotone_in_uncertainty(t1, t2, e1, e2):
    """If certain with errors, the exact-clock answer agrees (never contradicts)."""
    with_err = separation(t1, A, t2, B, e1, e2)
    exact = separation(t1, A, t2, B)
    if with_err is not Separation.AMBIGUOUS:
        assert with_err is exact


def test_order_with_uncertainty():
    assert order_with_uncertainty(Stamp(0, 5), Stamp(20, 5)) is Order.BEFORE
    assert order_with_uncertainty(Stamp(20, 5), Stamp(0, 5)) is Order.AFTER
    assert order_with_uncertainty(Stamp(0, 15), Stamp(20, 6)) is Order.UNDETERMINED


def _ev(eid, site, kind, t, parents=(), mid=None):
    return TraceEvent(event_id=eid, site_id=site, kind=kind, time_ns=t, causal_parent_ids=list(parents), message_id=mid)


def test_detects_retrocausal_and_faster_than_light():
    net = synthetic_two_site(1.0).network  # L0, L1 1 km -> 3335.6 ns
    evs = [
        _ev("s", "L0", "message_send", 0.0, mid="m"),
        _ev("r", "L1", "message_receive", 100.0, ["s"], "m"),
    ]
    assert propagation_violations(evs, net)
    back = [_ev("s", "L0", "message_send", 10.0, mid="m"), _ev("r", "L1", "message_receive", 5.0, ["s"], "m")]
    assert retrocausal_violations(back)


def test_detects_transitive_superluminal_path():
    """Each hop is legal-looking locally but the path smuggles information too fast."""
    net = synthetic_two_site(1.0).network
    evs = [
        _ev("a", "L0", "branch_choice", 0.0),
        _ev("b", "L0", "other", 10.0, ["a"]),
        _ev("c", "L1", "verification_result_available_local", 20.0, ["b"]),  # not a message edge
    ]
    assert any("information from a@L0" in v for v in propagation_violations(evs, net))


def test_is_spacelike_uses_site_clock_bounds():
    net = synthetic_two_site(1.0, clock_error_bound_ns=2000.0).network
    e0 = _ev("x", "L0", "verification_result_available_local", 0.0)
    e1 = _ev("y", "L1", "verification_result_available_local", 0.0)
    assert is_spacelike(e0, e1, net, use_clock_bounds=False)
    assert not is_spacelike(e0, e1, net)  # 2*2000 ns error > 3335.6 ns light cone -> ambiguous
