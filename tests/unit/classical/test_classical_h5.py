import pytest

from qmint.classical import scenarios as S
from qmint.classical.h5_secure_hardware import SecureElement, TamperResistanceAssumption


def test_tamper_resistant_se_refuses_second_spend_and_cloning():
    se = SecureElement("d")
    se.load("t")
    assert se.pay("t", "m", "n1") is not None
    assert se.pay("t", "m", "n2") is None
    with pytest.raises(TamperResistanceAssumption):
        se.clone()


def test_assumption_holds_scenario(net2):
    r = S.run_h5(net2, tamper_resistant=True)
    assert r.double_spends_successful == 0
    assert r.double_spend_decisions["B"] == "REJECT_DEVICE_REFUSED"
    assert r.extra["reconciliation"]["classification"] == "IN_MODEL"
    assert r.extra["real_device_benchmarked"] is False


def test_broken_assumption_double_spend_is_out_of_model(net2):
    r = S.run_h5(net2, tamper_resistant=False)
    assert r.double_spends_successful == 1  # not simulated as unbreakable
    rec = r.extra["reconciliation"]
    assert rec["classification"] == "OUT_OF_MODEL" and rec["double_spends_detected_ex_post"] == 1
    assert "VIOLATED" in r.trust_model


def test_attestation_replay_rejected():
    from qmint.classical.common import Message
    from qmint.classical.h5_secure_hardware import OfflineHardwareMerchant

    se = SecureElement("d")
    se.load("t")
    m = OfflineHardwareMerchant("mA", "A", "mA", {"d": se.device_key_for_registration()})
    (ch,) = m.handle(Message("Hello", "c", "mA"), 0.0)
    att = se.pay("t", "mA", ch.payload["nonce"])
    (r1,) = m.handle(Message("Present", "c", "mA", {"attestation": att}), 0.0)
    (r2,) = m.handle(Message("Present", "c", "mA", {"attestation": att}), 0.0)
    assert (r1.payload["decision"], r2.payload["decision"]) == ("ACCEPT", "REJECT_BAD_AUTH")
