import pytest

from qmint.classical import scenarios as S
from qmint.classical.h6_ecash import CFNBank, CFNWallet, trace_double_spender, verify_payment


@pytest.fixture(scope="module")
def setup():
    bank = CFNBank(k=16, seed=5)
    bank.open_account(77)
    w = CFNWallet(77, seed=1)
    coin = w.withdraw(bank)
    assert coin is not None
    return bank, w, coin


def test_honest_payment_verifies_and_counter_advances(setup):
    bank, w, coin = setup
    z = [1, 0] * 4
    assert verify_payment(bank.n, coin["C"], z, w.respond(coin, z))
    assert bank.counters[77] == 16


def test_tampered_response_rejected(setup):
    bank, w, coin = setup
    z = [1] * 8
    resp = w.respond(coin, z)
    resp[0] = {**resp[0], "a": "00" * 32}
    assert not verify_payment(bank.n, coin["C"], z, resp)


def test_double_spend_reveals_identity_single_spend_does_not(setup):
    bank, w, coin = setup
    z1, z2 = [0] * 8, [0] * 7 + [1]
    assert trace_double_spender(z1, w.respond(coin, z1), z2, w.respond(coin, z2)) == 77
    assert trace_double_spender(z1, w.respond(coin, z1), z1, w.respond(coin, z1)) is None  # collusion case


def test_cut_and_choose_catches_malformed_candidate():
    bank = CFNBank(k=8, seed=6)
    bank.open_account(1)
    blinded = [2] * 8  # garbage candidates
    reveal = bank.withdraw_challenge(1, blinded)
    openings = {i: (3, b"\0" * 32, b"\0" * 32, b"\0" * 32) for i in reveal}
    assert bank.withdraw_sign(1, openings) is None
    assert bank.counters[1] == 0


def test_detection_is_not_prevention(net2):
    r = S.run_h6(net2, "A")
    assert r.double_spend_decisions == {"A": "ACCEPT", "B": "ACCEPT"}
    assert r.double_spends_successful == 1
    statuses = sorted(d["status"] for d in r.extra["deposits"])
    assert statuses == ["CREDITED", "DOUBLE_SPEND_DETECTED"]
    traced = [d["traced_account"] for d in r.extra["deposits"] if d["status"] == "DOUBLE_SPEND_DETECTED"]
    assert traced == [r.extra["true_account"]]
    # detection happens strictly after both merchants already accepted
    assert min(d["arrival_ns"] for d in r.extra["deposits"]) > max(r.local_accept_ns.values()) - 1e-9
