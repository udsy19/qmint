"""Lane M red team: lane H classical comparators (CLASSICAL_FAIRNESS_REVIEW).

The H scenario runner's double-spend adversary re-presents the SAME secret at the other site.
These tests use stronger, still in-model adversaries (a customer with no keys).
"""

from __future__ import annotations

import hashlib

from qmint.classical import h3_escrow as h3
from qmint.classical.common import Decision, new_msg
from qmint.classical.h1_ledger import LedgerCoordinator, MerchantTerminal

KEY = b"k" * 32


def _h3(mode):
    order = {"A": "e@A", "B": "e@B"}
    iss = h3.EscrowIssuer("issuer", "A", dict(order), seed=0)
    ver = {s: h3.EscrowSiteVerifier(order[s], s, i, 2) for i, s in enumerate(order)}
    site_of = {v.node_id: s for s, v in ver.items()}
    for m in iss.issue("tok", mode):
        ver[site_of[m.dst]].handle(m, 0)

    def relay(msg):
        for m in iss.handle(msg, 0):
            ver[site_of[m.dst]].handle(m, 0)

    def present(site, secret=None):
        out = ver[site].handle(new_msg("Present", "u", ver[site].node_id, "m", token_id="tok", secret_hex=secret), 0)
        return out[0].payload["decision"]

    return iss, relay, present


# --------------------------------------------------------------- controls (pass)
def test_h1_two_merchants_race_one_token_single_accept():
    coord = LedgerCoordinator("C", "S0", frozenset({"T"}), {"MA": KEY, "MB": KEY})
    decisions = []
    for term in (MerchantTerminal("TA", "SA", "MA", KEY, "C"), MerchantTerminal("TB", "SB", "MB", KEY, "C")):
        req = term.handle(new_msg("Present", "cust", term.node_id, "m", token_id="T"), 0)[0]
        decisions.append(term.handle(coord.handle(req, 0)[0], 0)[0].payload["decision"])
    assert decisions == [Decision.ACCEPT.value, Decision.REJECT_DOUBLE_SPEND.value]


def test_h3_ot_same_secret_at_other_site_rejected():
    iss, relay, present = _h3("late_commit_ot_private")
    w = h3.OTWallet("tok", 1, iss.ot_transfer("tok", 1), 2)
    relay(new_msg("CommitC", "u", "issuer", "m", token_id="tok", c=w.commit_value(0)))
    assert present("A", w.r_z.hex()) == Decision.ACCEPT.value
    assert present("B", w.r_z.hex()) != Decision.ACCEPT.value


# --------------------------------------------------------------- M-H1: predictable OT secrets (FIXED, lane FGH)
def test_h3_ot_secrets_unpredictable():
    _, relay, present = _h3("late_commit_ot_private")
    relay(new_msg("CommitC", "u", "issuer", "m", token_id="tok", c=0))
    forged = [hashlib.sha256(f"h3-ot|0|tok|{i}".encode()).digest().hex() for i in range(2)]
    accepted = [present(s, forged[i]) == Decision.ACCEPT.value for i, s in enumerate(("A", "B"))]
    assert not all(accepted), "keyless customer double-spent at both sites"


# --------------------------------------------------------------- M-H2: re-commit (FIXED, lane FGH)
def test_h3_disclosed_second_commit_refused():
    _, relay, present = _h3("late_commit_disclosed")
    relay(new_msg("Commit", "u", "issuer", "m", token_id="tok", site="A"))
    assert present("A") == Decision.ACCEPT.value
    relay(new_msg("Commit", "u", "issuer", "m", token_id="tok", site="B"))
    assert present("B") != Decision.ACCEPT.value


def test_h3_ot_second_commit_refused():
    iss, relay, present = _h3("late_commit_ot_private")
    w = h3.OTWallet("tok", 1, iss.ot_transfer("tok", 1), 2)
    relay(new_msg("CommitC", "u", "issuer", "m", token_id="tok", c=w.commit_value(0)))
    assert present("A", w.r_z.hex()) == Decision.ACCEPT.value
    relay(new_msg("CommitC", "u", "issuer", "m", token_id="tok", c=w.commit_value(1)))
    assert present("B", w.r_z.hex()) != Decision.ACCEPT.value


# --------------------------------------------------------------- M-H3: idempotency-key collision (FIXED, lane FGH)
def test_h1_second_terminal_same_merchant_does_not_release_goods_twice():
    coord = LedgerCoordinator("C", "S0", frozenset({"T"}), {"M": KEY})
    decisions = []
    for term in (MerchantTerminal("TA", "S1", "M", KEY, "C"), MerchantTerminal("TB", "S2", "M", KEY, "C")):
        req = term.handle(new_msg("Present", "cust", term.node_id, "m", token_id="T"), 0)[0]
        decisions.append(term.handle(coord.handle(req, 0)[0], 0)[0].payload["decision"])
    assert decisions.count(Decision.ACCEPT.value) == 1, decisions
