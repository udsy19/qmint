import pytest

from qmint.classical.common import Message
from qmint.classical.engine_adapter import Injection, run_hosted
from qmint.classical.h0_bearer import BearerVerifier
from qmint.networks.causality import assert_causal, link_lower_bound_ns, network_violations


def test_lightcone_builder_is_physical_and_engine_accepted(net2, net3):
    assert link_lower_bound_ns(net3, "A", "B") == pytest.approx(100_000 / 0.299792458, rel=1e-9)
    assert link_lower_bound_ns(net3, "A", "H") == pytest.approx(link_lower_bound_ns(net3, "A", "B") / 2, rel=1e-9)
    assert link_lower_bound_ns(net2, "A", "A") == 0.0
    assert network_violations(net2) == [] and network_violations(net3) == []


def test_engine_delivery_adds_propagation_and_processing(net2):
    v = BearerVerifier("v@B", "B", frozenset({"s"}), processing_ns=7.0)
    # a customer at site A presents to the verifier at B: one cross-site hop, then 7 ns processing
    run = run_hosted(net2, [v], [Injection(100.0, Message("Present", "cust", "v@B", {"serial": "s"}), site="A")],
                     token_id="s")
    recv = run.result.first("message_receive", site_id="B")
    assert recv.time_ns == pytest.approx(100.0 + link_lower_bound_ns(net2, "A", "B"))
    (res,) = run.result.of_kind("verification_result_available_local")
    # result travels back to the customer at A
    assert res.time_ns == pytest.approx(recv.time_ns + 7.0 + link_lower_bound_ns(net2, "B", "A"))
    assert res.detail["decision"] == "ACCEPT" and res.site_id == "A"
    trace = run.result.to_transaction_trace("t", "s", "classical_h0_bearer", "none", False)
    assert_causal(trace, net2)


def test_message_size_is_canonical():
    m1 = Message("K", "a", "b", {"x": 1, "y": 2})
    m2 = Message("K", "a", "b", {"y": 2, "x": 1})
    assert m1.size_bytes() == m2.size_bytes() > 0
