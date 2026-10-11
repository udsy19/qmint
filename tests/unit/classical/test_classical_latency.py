import math

import pytest

from qmint.classical.common import Message, deliver, path_delay_ns
from qmint.classical.h0_bearer import BearerVerifier


def test_direct_link_delay_matches_fixture(net2):
    assert path_delay_ns(net2, "A", "B") == pytest.approx(33356.4)
    assert path_delay_ns(net2, "A", "A") == 0.0


def test_lightcone_builder_is_physical(net3):
    # 100 km / c = 333564.095 ns
    assert path_delay_ns(net3, "A", "B") == pytest.approx(100_000 / 0.299792458, rel=1e-6)
    assert path_delay_ns(net3, "A", "H") == pytest.approx(path_delay_ns(net3, "A", "B") / 2, rel=1e-6)


def test_partition_makes_unreachable_and_reroutes(net3):
    assert math.isinf(path_delay_ns(net3, "A", "B", down_links=[("A", "B"), ("A", "H")]))
    # with only the direct link down, the A->H->B path is used (same length on a line)
    assert path_delay_ns(net3, "A", "B", down_links=[("A", "B")]) == pytest.approx(
        path_delay_ns(net3, "A", "H") + path_delay_ns(net3, "H", "B"))


def test_unknown_site_rejected(net2):
    with pytest.raises(ValueError):
        path_delay_ns(net2, "A", "Z")


def test_deliver_adds_propagation_and_processing_and_never_precedes_lightcone(net2):
    v = BearerVerifier("v@B", "B", frozenset({"s"}), processing_ns=7.0)
    src = BearerVerifier("v@A", "A", frozenset(), processing_ns=0.0)
    outs, arrival = deliver(net2, {"v@B": v, "v@A": src}, Message("Present", "v@A", "v@B", {"serial": "s"}), 100.0)
    assert arrival == pytest.approx(100.0 + 33356.4)
    (_, t_send), = outs
    assert t_send == pytest.approx(arrival + 7.0)
    assert arrival - 100.0 >= path_delay_ns(net2, "A", "B")


def test_message_size_is_canonical():
    m1 = Message("K", "a", "b", {"x": 1, "y": 2})
    m2 = Message("K", "a", "b", {"y": 2, "x": 1})
    assert m1.size_bytes() == m2.size_bytes() > 0
