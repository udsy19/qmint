import threading

import pytest

from qmint.classical import scenarios as S
from qmint.classical.common import Message
from qmint.classical.h1_ledger import LedgerCoordinator, MerchantTerminal, request_mac
from qmint.networks.causality import link_lower_bound_ns

KEYS = {f"m{i}": f"k{i}".encode() for i in range(16)}


def _coord(tokens):
    return LedgerCoordinator("coord", "H", frozenset(tokens), dict(KEYS))


def _spend(c, tok, idem, m):
    return c.spend(tok, idem, m, request_mac(KEYS[m], tok, idem, m))


def test_thread_linearizability_exactly_one_accept_per_token():
    tokens = [f"t{i}" for i in range(40)]
    c = _coord(tokens)
    n_threads = 16
    barrier = threading.Barrier(n_threads)
    ops = []  # (thread, token, start_ns, end_ns, decision, seq)
    lock = threading.Lock()
    import time

    def worker(k):
        barrier.wait()
        for tok in tokens:
            t0 = time.perf_counter_ns()
            d, _, seq = _spend(c, tok, f"idem-{k}-{tok}", f"m{k}")
            t1 = time.perf_counter_ns()
            with lock:
                ops.append((k, tok, t0, t1, d.value, seq))

    th = [threading.Thread(target=worker, args=(k,)) for k in range(n_threads)]
    for t in th:
        t.start()
    for t in th:
        t.join()
    assert len(ops) == n_threads * len(tokens)
    for tok in tokens:
        acc = [o for o in ops if o[1] == tok and o[4] == "ACCEPT"]
        assert len(acc) == 1, tok
    assert sum(c.credits.values()) == len(tokens)
    # linearization: replaying ops in seq order through the sequential spec reproduces every result,
    # and seq order respects real-time order (A ends before B starts => seq(A) < seq(B)).
    spent = set()
    for o in sorted(ops, key=lambda o: o[5]):
        expect = "REJECT_DOUBLE_SPEND" if o[1] in spent else "ACCEPT"
        spent.add(o[1])
        assert o[4] == expect
    by_seq = sorted(ops, key=lambda o: o[2])
    for i, a in enumerate(by_seq[:200]):
        for b in by_seq[i + 1:]:
            if a[3] < b[2]:
                assert a[5] < b[5]


def test_idempotent_retry_same_result_no_double_credit():
    c = _coord(["t"])
    d1, rep1, _ = _spend(c, "t", "idem-1", "m0")
    d2, rep2, _ = _spend(c, "t", "idem-1", "m0")
    assert (d1.value, rep1) == ("ACCEPT", False)
    assert (d2.value, rep2) == ("ACCEPT", True)
    assert c.credits == {"m0": 1}


def test_replay_by_other_merchant_and_bad_mac_rejected():
    c = _coord(["t"])
    _spend(c, "t", "idem-1", "m0")
    assert _spend(c, "t", "idem-1", "m1")[0].value == "REJECT_IDEMPOTENCY_MISUSE"
    assert _spend(c, "t", "idem-2", "m1")[0].value == "REJECT_DOUBLE_SPEND"
    # captured request with forged merchant field -> MAC check fails
    mac = request_mac(KEYS["m0"], "t", "idem-9", "m0")
    assert c.spend("t", "idem-9", "m1", mac)[0].value == "REJECT_BAD_AUTH"
    assert c.credits == {"m0": 1}


def test_terminal_retries_with_same_idempotency_key_then_gives_up():
    t = MerchantTerminal("tA", "A", "m0", KEYS["m0"], "coord", max_attempts=2)
    (req,) = t.handle(Message("Present", "cust", "tA", {"token_id": "t"}), 0.0)
    (retry,) = t.on_timeout(req.payload["idem_key"], 1e6)
    assert retry.kind == "SpendRequest" and retry.payload["idem_key"] == req.payload["idem_key"]
    (res,) = t.on_timeout(req.payload["idem_key"], 2e6)
    assert res.kind == "Result" and res.payload["decision"] == "REJECT_UNAVAILABLE"
    c = _coord(["t"])
    (resp,) = c.handle(retry, 0.0)
    assert t.handle(resp, 0.0) == []  # late response after giving up is ignored, not double-reported


def test_event_race_one_accept_and_latency_includes_coordinator_rtt(net3):
    r = S.run_h1(net3, "H", partition_site="B")
    assert r.double_spends_successful == 0
    assert sorted(r.double_spend_decisions.values()) == ["ACCEPT", "REJECT_DOUBLE_SPEND"]
    rtt = 2 * link_lower_bound_ns(net3, "A", "H")
    assert r.local_accept_ns["A"] == pytest.approx(rtt + 2 * S.SITE_PROC_NS + S.COORD_PROC_NS)
    assert r.local_accept_ns["A"] >= rtt  # never faster than the coordinator round trip
    part = r.extra["partition"]
    assert part["decisions"]["B"] == "REJECT_UNAVAILABLE"  # safe but unavailable
    assert part["availability_fraction"] == 0.5


def test_idempotency_keys_are_random_per_presentation_not_merchant_counter():
    """M-H3: two tills of one merchant (or a restarted till) never share a key, so the 2nd presentation is a
    double spend, not an idempotent replay; a replayed ACCEPT for a key the terminal has not got pending is dropped."""
    c = _coord(["t"])
    out = []
    for nid in ("tA", "tB", "tA"):  # second till, then a restarted tA (fresh object)
        term = MerchantTerminal(nid, "A", "m0", KEYS["m0"], "coord")
        (req,) = term.handle(Message("Present", "cust", nid, {"token_id": "t"}), 0.0)
        assert len(req.payload["idem_key"]) == 32
        (resp,) = c.handle(req, 0.0)
        out.append(term.handle(resp, 0.0)[0].payload["decision"])
    assert out == ["ACCEPT", "REJECT_DOUBLE_SPEND", "REJECT_DOUBLE_SPEND"]
    other = MerchantTerminal("tC", "A", "m0", KEYS["m0"], "coord")
    forged = Message("SpendResponse", "coord", "tC", {"token_id": "t", "idem_key": "0" * 32, "decision": "ACCEPT",
                                                     "replayed": True})
    assert other.handle(forged, 0.0) == []


def test_own_retry_replay_is_honoured_and_flagged():
    c = _coord(["t"])
    t = MerchantTerminal("tA", "A", "m0", KEYS["m0"], "coord")
    (req,) = t.handle(Message("Present", "cust", "tA", {"token_id": "t"}), 0.0)
    c.handle(req, 0.0)  # first response lost
    (retry,) = t.on_timeout(req.payload["idem_key"], 1e6)
    (resp,) = c.handle(retry, 0.0)
    (res,) = t.handle(resp, 0.0)
    assert (res.payload["decision"], res.payload["replayed"]) == ("ACCEPT", True)
    assert c.credits == {"m0": 1}
