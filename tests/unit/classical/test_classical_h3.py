import pytest

from qmint.classical import scenarios as S
from qmint.classical.common import Message
from qmint.classical.h3_escrow import EscrowIssuer, EscrowSiteVerifier, OTWallet
from qmint.networks.causality import link_lower_bound_ns

SITES = {"A": "eA", "B": "eB", "C": "eC"}


def _setup(mode, assigned=None):
    iss = EscrowIssuer("issuer", "H", dict(SITES), seed=3)
    ver = {s: EscrowSiteVerifier(n, s, i, len(SITES)) for i, (s, n) in enumerate(SITES.items())}
    for m in iss.issue("tok", mode, assigned):
        assert ver[[s for s, n in SITES.items() if n == m.dst][0]].handle(m, 0.0) == []
    return iss, ver


def _present(v, secret=None):
    (r,) = v.handle(Message("Present", "cust", v.node_id, {"token_id": "tok", "secret_hex": secret}), 0.0)
    return r.payload["decision"]


def test_preassigned_rejects_unassigned_site_and_issuer_learns_site():
    iss, ver = _setup("preassigned", "B")
    assert _present(ver["A"]) == "REJECT_UNASSIGNED_SITE"
    assert _present(ver["B"]) == "ACCEPT"
    assert _present(ver["B"]) == "REJECT_DOUBLE_SPEND"
    assert iss.learned_site == {"tok": "B"}  # privacy cost recorded


def test_late_commit_disclosed_needs_activation_and_reveals_site():
    iss, ver = _setup("late_commit_disclosed")
    assert _present(ver["C"]) == "REJECT_NOT_ACTIVATED"
    for m in iss.handle(Message("Commit", "user", "issuer", {"token_id": "tok", "site": "C"}), 0.0):
        ver[[s for s, n in SITES.items() if n == m.dst][0]].handle(m, 0.0)
    assert _present(ver["A"]) == "REJECT_UNASSIGNED_SITE"
    assert _present(ver["C"]) == "ACCEPT"
    assert iss.learned_site["tok"] == "C"


@pytest.mark.parametrize("b", [0, 1, 2])
def test_ot_mode_accepts_only_chosen_site(b):
    for z in range(3):
        iss, ver = _setup("late_commit_ot_private")
        w = OTWallet("tok", z, iss.ot_transfer("tok", z), 3)
        for m in iss.handle(Message("CommitC", "user", "issuer", {"token_id": "tok", "c": w.commit_value(b)}), 0.0):
            ver[[s for s, n in SITES.items() if n == m.dst][0]].handle(m, 0.0)
        order = list(SITES)
        for i, s in enumerate(order):
            assert _present(ver[s], w.r_z.hex()) == ("ACCEPT" if i == b else "REJECT_UNASSIGNED_SITE")
        assert "tok" not in iss.learned_site


def test_ot_mode_issuer_view_independent_of_choice():
    # for uniform private z, the multiset of c values the issuer sees is identical for every b
    views = {b: sorted((b - z) % 3 for z in range(3)) for b in range(3)}
    assert views[0] == views[1] == views[2]


def test_scenarios_local_acceptance_and_commit_latency(net3):
    pre = S.run_h3(net3, "H", "preassigned")
    assert pre.local_accept_ns == {"A": S.SITE_PROC_NS}
    assert pre.double_spend_decisions["B"] == "REJECT_UNASSIGNED_SITE"
    assert pre.spending_flexibility == "preassigned_site"
    ot = S.run_h3(net3, "H", "late_commit_ot_private")
    assert ot.double_spends_successful == 0 and ot.spending_flexibility == "late_choice_any_site"
    assert ot.extra["issuer_learned_site"] is None
    assert ot.extra["stage_ii_commit_to_activation_ns"] == pytest.approx(
        link_lower_bound_ns(net3, "A", "H") + S.COORD_PROC_NS + link_lower_bound_ns(net3, "H", "B"))


def _route(ver, msgs):
    for m in msgs:
        ver[[s for s, n in SITES.items() if n == m.dst][0]].handle(m, 0.0)


def test_ot_secrets_are_issuer_private_not_derivable_from_public_data():
    """M-H1: secrets come from an issuer-held CSPRNG key; equal public inputs (seed, token id) give different secrets."""
    a, b = EscrowIssuer("i", "H", dict(SITES), seed=0), EscrowIssuer("i", "H", dict(SITES), seed=0)
    a.issue("tok", "late_commit_ot_private")
    b.issue("tok", "late_commit_ot_private")
    assert a.ot_transfer("tok", 0) != b.ot_transfer("tok", 0)
    assert "issuer_key" not in repr(a)
    k = b"\x01" * 32  # explicit test mode only: reproducible
    x, y = EscrowIssuer("i", "H", dict(SITES), issuer_key=k), EscrowIssuer("i", "H", dict(SITES), issuer_key=k)
    x.issue("tok", "late_commit_ot_private")
    y.issue("tok", "late_commit_ot_private")
    assert x.ot_transfer("tok", 2) == y.ot_transfer("tok", 2)


@pytest.mark.parametrize("mode", ["late_commit_disclosed", "late_commit_ot_private"])
def test_stage_ii_commit_is_one_shot_at_issuer_and_sites(mode):
    """M-H2: the issuer latches the first commit and relays nothing for a second; sites ignore a 2nd relay."""
    iss, ver = _setup(mode)
    kind, first, second = ("Commit", {"site": "A"}, {"site": "B"}) if mode == "late_commit_disclosed" else \
        ("CommitC", {"c": 0}, {"c": 1})
    out = iss.handle(Message(kind, "user", "issuer", {"token_id": "tok", **first}), 0.0)
    _route(ver, out)
    assert iss.handle(Message(kind, "user", "issuer", {"token_id": "tok", **second}), 0.0) == []
    assert iss.refused_commits == [("tok", kind)]
    # even a forged second relay straight to a site is ignored
    relay = "Activate" if kind == "Commit" else "RelayC"
    assert ver["B"].handle(Message(relay, "issuer", "eB", {"token_id": "tok", **second}), 0.0) == []
    assert ver["B"].tokens["tok"].get("active", False) is False and ver["B"].tokens["tok"].get("c", 0) == 0


def test_hold_until_active_cannot_be_released_by_a_second_commit():
    """M re-audit: a presentation queued (held) before activation is decided by the FIRST commit only."""
    iss = EscrowIssuer("issuer", "H", dict(SITES), issuer_key=b"k" * 32)
    ver = {s: EscrowSiteVerifier(n, s, i, len(SITES), hold_until_active=True) for i, (s, n) in enumerate(SITES.items())}
    _route(ver, iss.issue("tok", "late_commit_disclosed"))
    held = Message("Present", "cust", "eB", {"token_id": "tok"})
    assert ver["B"].handle(held, 0.0) == []  # queued
    released = []
    for m in iss.handle(Message("Commit", "user", "issuer", {"token_id": "tok", "site": "A"}), 0.0):
        released += ver[[s for s, n in SITES.items() if n == m.dst][0]].handle(m, 0.0)
    assert [r.payload["decision"] for r in released] == ["REJECT_UNASSIGNED_SITE"]
    assert _present(ver["A"]) == "ACCEPT"
    assert ver["B"].handle(held, 0.0)[0].payload["decision"] == "REJECT_UNASSIGNED_SITE"  # not held again
    assert iss.handle(Message("Commit", "user", "issuer", {"token_id": "tok", "site": "B"}), 0.0) == []
    assert _present(ver["B"]) == "REJECT_UNASSIGNED_SITE"
