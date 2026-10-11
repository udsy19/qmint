import pytest

from qmint.classical import scenarios as S
from qmint.classical.common import Message
from qmint.classical.h4_pqc import (
    FIPS204_TABLE2_SIZES,
    PQCIssuer,
    SignedOfflineVerifier,
    measure_mldsa,
    verify_token,
)


@pytest.fixture(scope="module")
def issuer():
    return PQCIssuer("ML_DSA_44", seed=1)


def test_signature_validates_and_tamper_rejected(issuer):
    w = issuer.issue("s1", 5, None).wire()
    assert verify_token("ML_DSA_44", issuer.pk, w)
    assert not verify_token("ML_DSA_44", issuer.pk, {**w, "denomination": 6})
    assert not verify_token("ML_DSA_44", PQCIssuer("ML_DSA_44", seed=2).pk, w)


def test_deterministic_keys_and_signatures():
    a, b = PQCIssuer("ML_DSA_44", seed=7), PQCIssuer("ML_DSA_44", seed=7)
    assert a.pk == b.pk
    assert a.issue("s").signature_hex == b.issue("s").signature_hex


def test_sizes_match_fips204_table2():
    m = measure_mldsa("ML_DSA_44", reps=1)
    assert (m["sk_bytes"], m["pk_bytes"], m["sig_bytes"]) == FIPS204_TABLE2_SIZES["ML_DSA_44"]
    assert m["keygen_ns_median"] > 0 and m["verify_ns_median"] > 0


def test_signature_alone_does_not_stop_double_spend(issuer):
    w = issuer.issue("s2").wire()
    for site in ("A", "B"):
        v = SignedOfflineVerifier(f"v{site}", site, "ML_DSA_44", issuer.pk)
        (r,) = v.handle(Message("Present", "c", v.node_id, {"token": w}), 0.0)
        assert r.payload["decision"] == "ACCEPT"


def test_combined_with_h3_and_h1_prevents_double_spend(net2):
    h3 = S.run_h4(net2, "h3_site_binding")
    assert h3.double_spend_decisions == {"A": "ACCEPT", "B": "REJECT_UNASSIGNED_SITE"}
    h1 = S.run_h4(net2, "h1_ledger", coord_site="A")
    assert h1.double_spends_successful == 0
    assert sorted(h1.double_spend_decisions.values()) == ["ACCEPT", "REJECT_DOUBLE_SPEND"]
    alone = S.run_h4(net2, "none")
    assert alone.double_spends_successful == 1


def test_forged_token_rejected_by_signed_terminal(net2, issuer):
    from qmint.classical.h1_ledger import MerchantTerminal
    from qmint.classical.h4_pqc import SignedTerminal

    t = SignedTerminal(MerchantTerminal("tA", "A", "m", b"k", "coord"), "ML_DSA_44", issuer.pk)
    forged = {**issuer.issue("s3").wire(), "serial": "s4"}
    (r,) = t.handle(Message("Present", "c", "tA", {"token": forged}), 0.0)
    assert r.payload["decision"] == "REJECT_BAD_SIGNATURE"
