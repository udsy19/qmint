from qmint.classical import scenarios as S
from qmint.classical.common import Message
from qmint.classical.h0_bearer import BearerVerifier, mint_serial


def _present(v, serial):
    (r,) = v.handle(Message("Present", "cust", v.node_id, {"serial": serial}), 0.0)
    return r.payload["decision"]


def test_h0_double_spend_succeeds_across_sites():
    s = mint_serial(0, 0)
    a = BearerVerifier("vA", "A", frozenset({s}))
    b = BearerVerifier("vB", "B", frozenset({s}))
    assert _present(a, s) == "ACCEPT"
    assert _present(b, s) == "ACCEPT"  # negative control: the copy is accepted


def test_h0_same_site_replay_and_unknown_rejected():
    s = mint_serial(0, 0)
    a = BearerVerifier("vA", "A", frozenset({s}))
    assert _present(a, s) == "ACCEPT"
    assert _present(a, s) == "REJECT_DOUBLE_SPEND"
    assert _present(a, mint_serial(0, 1)) == "REJECT_UNKNOWN_TOKEN"


def test_h0_scenario_counts_one_double_spend(net2):
    r = S.run_h0(net2)
    assert r.double_spends_successful == 1
    assert r.local_accept_ns == {"A": S.SITE_PROC_NS, "B": S.SITE_PROC_NS}
