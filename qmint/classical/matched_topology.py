"""Matched-topology comparison: S-money (lane G) vs classical H0-H6 (lane H) on ONE engine.

Every protocol runs on the identical lane-G ``TopologyCase`` (same C4 ``SpacetimeNetwork``,
same runtime latency model, same seed) with the same choreography, so the only thing that
differs is the protocol's message pattern:

* Sites ``L0`` (issuer / bank HQ / ledger / Alice's choice) and ``L1``; ``T_CHOICE_NS``: Alice
  chooses the presentation site ``b`` at ``L0`` (``branch_choice``).
* Stage II, when the protocol has one, starts at the choice: S-money's ``c = b XOR z`` to B and
  B's relay to both B_i (Kent et al. 2022, arXiv:2104.11717v4, Table I steps 7-9), H3's
  ``Commit``/``CommitC`` to the issuer and its ``Activate``/``RelayC`` relay to every site.
* Alice signals her agents over her own channel; both sites see a presentation at the same
  nominal time (the genuine one at ``L_b``, a dummy at ``L_(1-b)``), exactly like G's S-money
  ``SUserAgent`` (A0 waits the nominal one-way delay).
* Offline protocols report outcomes one-way to G's ``IssuerHQ`` at ``L0`` (same rule as
  S-money: settlement when every site has reported). Ledger protocols (H1, H2, H4+H1) are
  issuer-aware and settled at the authoritative commit.

Reported separately (never conflated): local-validation latency (from the later of
presentation and Stage-II arrival at ``L_b`` to the local result), pre-presentation commit
latency (choice -> Stage-II message at every site), issuer awareness and settlement (both
from the choice), choice -> local accept (Jiang et al. 2024's "transaction time"), and the
synchronous cross-site round trips on the accept's causal path (G's detector).

Double-spend adversaries (security outcomes from the real H state machines, never latency):

* ``replay``: the weak adversary of lanes H/GH. The genuine presentation is made at EVERY site at the
  same nominal time (race), nothing else.
* ``strong`` (lane M finding M-H4): ``replay`` plus an adaptive second wave made after the first
  outcome is in the customer's causal past, using only what a customer legitimately holds (her
  token / wallet, r_z and z in H3-OT, her own Stage-II message, the results): a second Stage-II
  commit to the other site (H3 late modes), re-presentation at the other site, presentations of
  forged OT secrets derived from public data (H3-OT, the pre-fix M-H1 derivation), and, for the
  ledger designs, presentations at a second till of the SAME merchant at the other site and at a
  fresh (restarted) till of that merchant at L_b (M-H3 deployment). Successful double spends =
  accepted presentations of the token - 1.

Processing is a matched parameter: every model in ``PROC_MODELS`` applies ONE per-step processing
time to every protocol node, S-money's B_i included (relays cost 0 for S-money's B0 and H3's issuer
alike), so the sweep doubles as the processing-time sensitivity analysis (lane M re-audit of M-H5).

Evidence: MODELLED_LATENCY. Runtime link delays come from G's topology cases (paper fibre,
synthetic fibre at 2/3 c, or RIPE RTT/2 resampling = MEASURED_LATENCY *inputs*). Security is
not simulated: S-money validity is symbolic (G), classical double-spend outcomes come from the
real H state machines.

    python -m qmint.classical.matched_topology [--out reports/classical_baseline_notes] [--ripe-seeds 20]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from qmint.classical import (
    comparability,
    h0_bearer,
    h1_ledger,
    h2_quorum,
    h3_escrow,
    h4_pqc,
    h5_secure_hardware,
    h6_ecash,
)
from qmint.classical import scenarios as S
from qmint.classical.common import Decision, ProtocolNode, new_msg
from qmint.classical.common import Message as HMessage
from qmint.classical.engine_adapter import NodeActor, PresentationPoint, React, inject, wire_bytes, wrap
from qmint.core.contracts import BenchmarkRecord, EvidenceKind, Targets, TraceEvent, TransactionTrace
from qmint.core.serialization import canonical_hash, canonical_json, file_sha256
from qmint.networks.causality import (
    assert_causal,
    lightcone_delay_ns,
    site_distance_m,
    synchronous_cross_site_round_trips,
)
from qmint.networks.events import Effect, LocalRequest, Message, Record, Send
from qmint.networks.ripe import load_fixture, ripe_two_site_case
from qmint.networks.s_money_sites import (
    S_MONEY_IRREVOCABILITY_RULE,
    S_MONEY_PROTOCOL_ID,
    IssuerHQ,
    nominal_one_way_ns,
    run_s_money,
)
from qmint.networks.simulator import SimulationResult, Simulator
from qmint.networks.topology import (
    JIANG2024_PROC_NS,
    TopologyCase,
    jiang2024_intercity,
    jiang2024_intracity,
    synthetic_two_site,
)

ROOT = Path(__file__).resolve().parents[2]
T_CHOICE_NS = 1_000_000.0  # Stage II starts 1 ms after issuance (t = 0), as in G's run_s_money
PROC_MODELS: dict[str, float] = {
    # ONE per-step processing time applied to EVERY node of EVERY protocol (S-money's B_i included)
    "jiang_dTproc_1507ns": JIANG2024_PROC_NS,  # Jiang et al. 2024 SI: measured mean dT_proc = 1.507 us
    "zero_processing": 0.0,  # pure communication structure
    "h_site_10us": S.SITE_PROC_NS,  # lane H's declared terminal processing, applied to all (sensitivity)
    "h_coord_50us": S.COORD_PROC_NS,  # lane H's declared coordinator processing, applied to all (sensitivity)
}
ADVERSARIES = ("replay", "strong")
RIPE_PROBES = (6330, 6251)  # Helsinki anchor -> Tampere anchor (G's committed fixture)
S1 = "S1_s_money"
LEDGER_RULE = "bank_settlement_final := authoritative ledger / quorum commit (first ACCEPT decision)"
HQ_RULE = S_MONEY_IRREVOCABILITY_RULE  # offline protocols settle exactly like G's S-money HQ
PAIR_OF = {"H0": "X11-H0", "H1": "X11-H1", "H2": "X11-H2", "H3_preassigned": "X11-H3-preassigned",
           "H3_late_commit_disclosed": "X11-H3-late-disclosed", "H3_late_commit_ot_private": "X11-H3-late-ot",
           "H4+H1": "X11-H4+H1", "H4+H3": "X11-H4+H3", "H5": "X11-H5", "H6": "X11-H6"}
PROTOCOLS: tuple[str, ...] = (S1, *PAIR_OF)


# --------------------------------------------------------------------------- #
# Topologies (all lane G builders)
# --------------------------------------------------------------------------- #


def matched_cases() -> dict[str, TopologyCase]:
    return {
        "paper_jinan_2.766km_fibre": jiang2024_intracity(),
        "paper_yiyuan_mazhan_60.54km_fibre": jiang2024_intercity(),
        "synthetic_10km": synthetic_two_site(10.0),
        "synthetic_100km": synthetic_two_site(100.0),
        "synthetic_1000km": synthetic_two_site(1000.0),
        "ripe_helsinki_tampere": ripe_two_site_case(load_fixture(), *RIPE_PROBES),
    }


# --------------------------------------------------------------------------- #
# Classical protocol specs on two sites
# --------------------------------------------------------------------------- #


@dataclass
class Spec:
    protocol_id: str
    variant: str
    token_id: str
    nodes: list[ProtocolNode | NodeActor]
    present: dict[int, list[HMessage]]  # what A_i hands the till at site i when told "go"
    verifier: dict[int, str]  # first verifier actor at site i
    trust_model: str
    pre_distribution: str
    spending_flexibility: str
    privacy_game: str
    issuer_calls: int
    ledger: bool = False  # True: issuer awareness / settlement = authoritative commit
    reacts: dict[int, React] = field(default_factory=dict)
    commit: dict[int, HMessage] = field(default_factory=dict)  # Stage-II message for choice b
    commit_kinds: tuple[str, ...] = ()
    issuance: list[HMessage] = field(default_factory=list)  # sent by ``issuer_actor`` at t = 0
    issuer_actor: str | None = None
    strong_present: dict[int, list[HMessage]] = field(default_factory=dict)  # extra wave-2 attempts at site i
    strong_attempts: tuple[str, ...] = ()  # human-readable list of the strong adversary's attempts


def _ledger_records(m: HMessage) -> list[Record]:
    """Ledger/quorum commit: the authority knows of the spend and it is final (C4 ladder events)."""
    if m.kind == "SpendResponse" and m.payload["decision"] == Decision.ACCEPT.value and not m.payload.get("replayed"):
        d = {"token_id": m.payload["token_id"], "rule": "ledger commit"}
        return [Record("issuer_aware_of_spend", d), Record("bank_settlement_final", d)]
    return []


def _present(site: str, dst: str, kind: str = "Present", **payload: Any) -> HMessage:
    return new_msg(kind, f"cust@{site}", dst, "s", **payload)


def _two(f: Callable[[int, str], list[HMessage]], sites: tuple[str, str]) -> dict[int, list[HMessage]]:
    return {i: f(i, s) for i, s in enumerate(sites)}


def spec_for(label: str, sites: tuple[str, str], p: float, b: int, retry_ns: float, strong: bool = False) -> Spec:
    """Build the nodes of one classical protocol on (L0, L1) with every node's processing = ``p``.
    ``strong``: also deploy what the strong adversary needs (extra tills of the merchant at L_b) and
    fill ``strong_present``."""
    l0 = sites[0]
    lb, lo = sites[b], sites[1 - b]
    tills = {f"t2@{lo}": (lo, lb), f"t3@{lb}": (lb, lb)} if strong else None  # 2nd till / restarted till of m@L_b
    if label == "H0":
        serial = h0_bearer.mint_serial(0, 0)
        vs = [h0_bearer.BearerVerifier(f"v@{s}", s, frozenset({serial}), p) for s in sites]
        return Spec(h0_bearer.PROTOCOL_ID, "negative_control", serial, vs,
                    _two(lambda i, s: [_present(s, f"v@{s}", serial=serial)], sites), {0: vs[0].node_id, 1: vs[1].node_id},
                    "none: copyable bearer string, offline verifiers", "valid-serial list at every site",
                    "late_choice_any_site", "none", 0)
    if label in ("H1", "H4+H1"):
        tok = "tok-h1-0"
        wrap_t, payload, tokens = None, {"token_id": tok}, frozenset({tok})
        pid, var, trust = h1_ledger.PROTOCOL_ID, "coordinator", "honest online coordinator at L0; HMAC-authenticated"
        if label == "H4+H1":
            issuer = h4_pqc.PQCIssuer("ML_DSA_44", seed=0)
            payload, tokens = {"token": issuer.issue(tok).wire()}, None
            pid, var, trust = h4_pqc.PROTOCOL_ID, "mldsa_h1_ledger", "ML-DSA EUF-CMA + honest online ledger at L0"

            def wrap_t(t):
                return h4_pqc.SignedTerminal(t, "ML_DSA_44", issuer.pk)
        coord, terms = S.h1_nodes(l0, tokens, sites, p, p, wrap_terminal=wrap_t, retry_timeout_ns=retry_ns,
                                  extra_tills=tills)
        return Spec(pid, var, tok, [NodeActor(coord, annotate=_ledger_records), *terms.values()],
                    _two(lambda i, s: [_present(s, f"t@{s}", **payload)], sites), {0: f"t@{sites[0]}", 1: f"t@{sites[1]}"},
                    trust, "issued set at the ledger only", "online_any_site",
                    "none (ledger learns token, merchant, site)", 1, ledger=True,
                    **_ledger_strong(sites, b, payload, strong))
    if label == "H2":
        tok = "tok-h2-0"
        # f = 1 needs 2f+1 = 3 replicas on two sites: leader + one follower at L0, one follower at L1
        nodes, route = S.h2_cluster(1, [l0, l0, sites[1]], [l0], frozenset({tok}), list(sites), p, p,
                                    retry_timeout_ns=retry_ns, extra_tills=tills)
        actors = [NodeActor(n, annotate=_ledger_records) if n.node_id == route(tok) else n for n in nodes.values()]
        return Spec(h2_quorum.PROTOCOL_ID, "sharded_quorum_f1_majority_at_L0", tok, actors,
                    _two(lambda i, s: [_present(s, f"t@{s}", token_id=tok)], sites),
                    {0: f"t@{sites[0]}", 1: f"t@{sites[1]}"},
                    "crash-fault replicas (2 of 3 at L0, so the commit quorum is local to L0); honest operator",
                    "issued set replicated in the home shard", "online_any_site", "none (home shard learns site)",
                    1, ledger=True, **_ledger_strong(sites, b, {"token_id": tok}, strong))
    if label.startswith("H3_"):
        mode = label[3:]
        tok = "tok-h3-0"
        # The issuer only RELAYS the Stage-II message: zero processing, matched to G's S-money B0 -> B1 relay.
        st = S.h3_setup(list(sites), l0, mode, tok, chosen=b, site_proc_ns=p, coord_proc_ns=0.0)  # type: ignore[arg-type]
        strong_kw: dict[str, Any] = {}
        if strong:
            attempts = ["race: genuine presentation at both sites", f"re-present at {lo} after the accept"]
            forged: list[HMessage] = []
            if mode != "preassigned":
                attempts.insert(1, f"second Stage-II commit to {lo} after the accept")
            if mode == "late_commit_ot_private":
                forged = [_present(lo, f"e@{lo}", token_id=tok, secret_hex=hashlib.sha256(
                    f"h3-ot|0|{tok}|{i}".encode()).hexdigest()) for i in range(2)]
                attempts.append(f"present OT secrets derived from public data (seed 0 + token id) at {lo}")
            strong_kw = {"strong_present": {1 - b: forged}, "strong_attempts": tuple(attempts)}
        privacy = {"preassigned": "none (issuer learns site at issuance)",
                   "late_commit_disclosed": "none (issuer learns b at Stage-II commit)",
                   "late_commit_ot_private": "b hidden from issuer under IDEAL OT (computational in practice)"}[mode]
        return Spec(h3_escrow.PROTOCOL_ID, mode, tok, [st.issuer, *st.verifiers.values()],
                    _two(lambda i, s: [_present(s, f"e@{s}", token_id=tok, secret_hex=st.secret_hex)], sites),
                    {0: f"e@{sites[0]}", 1: f"e@{sites[1]}"},
                    "honest issuer at L0 + site verifiers" + ("; IDEAL 1-of-2 OT" if "ot" in mode else ""),
                    "per-token provisioning to every site at issuance", "preassigned_site" if mode == "preassigned"
                    else "late_choice_any_site", privacy, 0 if mode == "preassigned" else 1,
                    commit=st.commit, commit_kinds=("Activate", "RelayC"), issuance=st.provisioning,
                    issuer_actor=st.issuer.node_id, **strong_kw)
    if label == "H4+H3":
        issuer = h4_pqc.PQCIssuer("ML_DSA_44", seed=0)
        tokw = issuer.issue("tok-h4-0", 1, sites[b]).wire()  # site bound at issuance = the later choice (best case)
        vs = [h4_pqc.SignedOfflineVerifier(f"v@{s}", s, "ML_DSA_44", issuer.pk, True, p) for s in sites]
        return Spec(h4_pqc.PROTOCOL_ID, "mldsa_h3_site_binding", "tok-h4-0", vs,
                    _two(lambda i, s: [_present(s, f"v@{s}", token=tokw)], sites), {0: f"v@{sites[0]}", 1: f"v@{sites[1]}"},
                    "ML-DSA EUF-CMA; site signed into the token at issuance", "issuer pk at every site",
                    "preassigned_site", "none (issuer learns site at issuance)", 0)
    if label == "H5":
        tok = "tok-h5-0"
        se = h5_secure_hardware.SecureElement("dev-1")
        se.load(tok)
        keys = {"dev-1": se.device_key_for_registration()}
        ms = [h5_secure_hardware.OfflineHardwareMerchant(f"m@{s}", s, f"m@{s}", keys, p) for s in sites]
        return Spec(h5_secure_hardware.PROTOCOL_ID, "assumption_holds", tok, ms,
                    _two(lambda i, s: [_present(s, f"m@{s}", kind="Hello")], sites), {0: f"m@{sites[0]}", 1: f"m@{sites[1]}"},
                    h5_secure_hardware.ASSUMPTION_ID, "token in the payer's SE; device keys at merchants",
                    "late_choice_any_site", "none modelled", 0,
                    reacts={i: S.h5_react(se, tok, s, f"m@{s}", f"m@{s}") for i, s in enumerate(sites)})
    if label == "H6":
        bank = h6_ecash.CFNBank(site_id=l0, k=16, seed=0, processing_ns=p)
        bank.open_account(4242)
        wallet = h6_ecash.CFNWallet(4242)
        coin = wallet.withdraw(bank)
        assert coin is not None
        ms = [h6_ecash.CFNMerchant(f"m@{s}", s, f"m@{s}", bank.n, seed=i, processing_ns=p) for i, s in enumerate(sites)]
        return Spec(h6_ecash.PROTOCOL_ID, "cfn88_sec1_k16", "cfn-coin-u4242",
                    [bank, *(S.h6_merchant_actor(m, bank.node_id) for m in ms)],
                    _two(lambda i, s: [_present(s, f"m@{s}", kind="PresentCoin", coin=str(coin["C"]), n_terms=8)],
                         sites), {0: f"m@{sites[0]}", 1: f"m@{sites[1]}"},
                    "toy RSA blind signature + cut-and-choose; detection, not prevention", "coin withdrawn in advance",
                    "late_choice_any_site", "payer untraceable if spent once (heuristic)", 0,
                    reacts={i: S.h6_react(wallet, coin, f"cust@{s}", f"m@{s}") for i, s in enumerate(sites)})
    raise ValueError(label)


def _ledger_strong(sites: tuple[str, str], b: int, payload: Mapping[str, Any], strong: bool) -> dict[str, Any]:
    """Strong-adversary attempts against a ledger design deployed with a 2nd / restarted till of m@L_b."""
    if not strong:
        return {}
    lb, lo = sites[b], sites[1 - b]
    return {"strong_present": {1 - b: [_present(lo, f"t2@{lo}", **payload)], b: [_present(lb, f"t3@{lb}", **payload)]},
            "strong_attempts": ("race: genuine presentation at both sites", f"re-present at {lo} after the accept",
                                f"present at a second till of merchant m@{lb} located at {lo}",
                                f"present at a restarted (fresh) till of merchant m@{lb} at {lb}")}


def _generic_strong_attempts(sites: tuple[str, str], b: int) -> tuple[str, ...]:
    return ("race: genuine presentation at both sites", f"re-present at {sites[1 - b]} after the first outcome")


@dataclass
class ChoiceAgent:
    """Alice's agent A at L0: on ``branch_choice`` sends the Stage-II message (if any) and tells
    every site's presentation point to present (genuine at L_b, dummy elsewhere). The local point
    is told after ``go_delay_ns`` so both presentations are simultaneous (as G's S-money A0)."""

    actor_id: str
    site_id: str
    points: tuple[str, ...]
    go_delay_ns: tuple[float, ...]
    commit: Mapping[int, HMessage]
    adversary: str | None = None  # "replay" / "strong": present the token at EVERY site (double-spend race)

    def on_local_request(self, request: LocalRequest, now_ns: float) -> list[Effect]:
        b = int(request.payload["b"])
        eff: list[Effect] = [Send(self.commit[b].dst, wrap(self.commit[b]))] if b in self.commit else []
        eff += [Send(pt, {"type": "go", "genuine": self.adversary is not None or i == b}, after_ns=self.go_delay_ns[i])
                for i, pt in enumerate(self.points)]
        return eff

    def on_message(self, msg: Message, now_ns: float) -> list[Effect]:
        return []


# --------------------------------------------------------------------------- #
# Runs and metrics
# --------------------------------------------------------------------------- #


@dataclass
class MatchedRun:
    case_id: str
    protocol: str
    protocol_id: str
    variant: str
    b: int
    proc_model: str
    seed: int
    adversary: str | None  # None (honest), "replay" or "strong"
    result: SimulationResult
    trace: TransactionTrace
    metrics: dict[str, Any]
    spec: Spec | None = None


def _rel(ev, t0: float) -> float | None:
    return None if ev is None else ev.time_ns - t0


def _metrics(res: SimulationResult, trace: TransactionTrace, site_b: str, commit_rx: dict[str, float],
             token_id: str) -> dict[str, Any]:
    choice = res.first("branch_choice")
    assert choice is not None
    t0 = choice.time_ns
    pres = res.first("local_validation_start", site_id=site_b)
    acc = res.first("verification_result_available_local", site_id=site_b)
    accepted = acc is not None and acc.detail.get("accepted") is True
    ready = None if pres is None else max(pres.time_ns, commit_rx.get(site_b, float("-inf")))
    rts: list[str] = []
    if accepted and pres is not None:  # trigger = the receipt that started the presentation (as G does)
        trigger = pres.causal_parent_ids[0] if pres.causal_parent_ids else pres.event_id
        rts = synchronous_cross_site_round_trips(trace.events, acc.event_id, trigger)
    return {
        "honest_decision": None if acc is None else acc.detail.get("decision", "ACCEPT" if accepted else "REJECT"),
        "choice_to_local_accept_ns": _rel(acc, t0) if accepted else None,
        "local_validation_ns": acc.time_ns - ready if accepted and ready is not None else None,
        "pre_presentation_commit_ns": (max(commit_rx.values()) - t0) if commit_rx else None,
        "commit_at_Lb_before_presentation": (commit_rx[site_b] <= pres.time_ns + 1e-6)
        if commit_rx and pres is not None else None,
        "issuer_aware_ns": _rel(res.first("issuer_aware_of_spend"), t0),
        "settlement_ns": _rel(res.first("bank_settlement_final"), t0),
        "sync_cross_site_msgs_after_presentation": len(rts),
        "accepted_sites": len(res.accepted_sites(token_id)),
        "accepted_presentations": sum(1 for e in res.of_kind("verification_result_available_local")
                                      if e.detail.get("token_id") == token_id and e.detail.get("accepted") is True),
    }


def run_classical(case: TopologyCase, label: str, b: int, proc_ns: float, *, case_id: str = "", seed: int = 0,
                  adversary: str | None = None, proc_model: str = "") -> MatchedRun:
    if adversary not in (None, *ADVERSARIES):
        raise ValueError(adversary)
    sites = case.site_ids[:2]
    nominal = nominal_one_way_ns(case, sites[0], sites[1])
    worst = max(nominal, nominal_one_way_ns(case, sites[1], sites[0]))
    retry_ns = max(S.RETRY_TIMEOUT_NS, 4 * worst)
    strong = adversary == "strong"
    spec = spec_for(label, sites, proc_ns, b, retry_ns, strong)
    hq = None if spec.ledger else "HQ"
    points = [PresentationPoint(f"cust@{s}", s, spec.token_id, spec.reacts.get(i), hq, spec.present[i])
              for i, s in enumerate(sites)]
    alice = ChoiceAgent("alice", sites[0], tuple(pt.actor_id for pt in points), (nominal, 0.0), spec.commit,
                        adversary)
    actors = [n if isinstance(n, NodeActor) else NodeActor(n) for n in spec.nodes]
    extra = [] if hq is None else [IssuerHQ(hq, sites[0], n_sites=2)]
    sim = Simulator(case.network, [*actors, *points, alice, *extra], case.link_runtime, seed=seed)
    if spec.issuance:
        sim.schedule(LocalRequest("issuance", spec.issuer_actor, 0.0, kind="issue", payload=inject(spec.issuance)))
    sim.schedule(LocalRequest("choice", "alice", T_CHOICE_NS, kind="branch_choice", payload={"b": b}))
    if strong:  # adaptive second wave, after the first outcome is in the customer's causal past
        t_w2 = T_CHOICE_NS + 6 * worst + 20 * proc_ns + 1_000.0
        if (1 - b) in spec.commit:  # second Stage-II commit, to the other site
            sim.schedule(LocalRequest("recommit", points[0].actor_id, t_w2, kind="commitment",
                                      payload=inject([spec.commit[1 - b]])))
        t_p2 = t_w2 + 3 * worst + 10 * proc_ns + 1_000.0
        wave2 = {1 - b: [*spec.present[1 - b], *spec.strong_present.get(1 - b, [])],
                 b: list(spec.strong_present.get(b, []))}
        for i, msgs in wave2.items():
            for j, m in enumerate(msgs):
                sim.schedule(LocalRequest(f"w2-{i}-{j}", points[i].actor_id, t_p2 + j * (3 * worst + 10 * proc_ns + 1e3),
                                          kind="local_validation_start", payload=inject([m])))
    res = sim.run()
    trace = res.to_transaction_trace(
        trace_id=f"gh-{label}-{case_id or case.network.network_id}-b{b}-{proc_model}-seed{seed}"
                 + (f"-{adversary}" if adversary else ""),
        token_id=spec.token_id, protocol_id=spec.protocol_id,
        irrevocability_rule=LEDGER_RULE if spec.ledger else HQ_RULE,
        double_spend_accepted=res.double_spend_accepted(spec.token_id))
    assert_causal(trace, case.network)
    site_of = {a.actor_id: a.site_id for a in actors}
    commit_rx: dict[str, float] = {}
    for e in res.of_kind("message_receive"):
        if e.detail.get("h_kind") in spec.commit_kinds:
            commit_rx.setdefault(site_of[e.actor_id], e.time_ns)
    m = _metrics(res, trace, sites[b], commit_rx, spec.token_id)
    m["classical_bytes"] = wire_bytes(res)
    if strong:
        m["strong_attempts"] = spec.strong_attempts or _generic_strong_attempts(sites, b)
    return MatchedRun(case_id, label, spec.protocol_id, spec.variant, b, proc_model, seed, adversary, res, trace,
                      m, spec)


def run_smoney(case: TopologyCase, b: int, proc_ns: float, *, case_id: str = "", seed: int = 0,
               proc_model: str = "") -> MatchedRun:
    run = run_s_money(case, b, t_choice_ns=T_CHOICE_NS, proc_ns=proc_ns, seed=seed)
    res = run.result
    commit_rx: dict[str, float] = {}
    for e in res.of_kind("message_receive"):
        if e.detail.get("type") == "commitment" and e.actor_id.startswith("B"):
            commit_rx.setdefault(e.site_id, e.time_ns)
    m = _metrics(res, run.trace, case.site_ids[b], commit_rx, "tok-s-0")
    assert m["sync_cross_site_msgs_after_presentation"] == len(run.local_round_trips)
    m["classical_bytes"] = None
    return MatchedRun(case_id, S1, S_MONEY_PROTOCOL_ID, "kent2022_table1_event_model_g", b, proc_model, seed, None,
                      res, run.trace, m)


def run_matched(case: TopologyCase, label: str, b: int, proc_model: str, seed: int = 0, case_id: str = "",
                adversary: str | None = None) -> MatchedRun:
    p = PROC_MODELS[proc_model]
    if label == S1:
        if adversary is not None:
            raise ValueError("S-money double spending is not simulated (token validity is symbolic in G's model)")
        return run_smoney(case, b, p, case_id=case_id, seed=seed, proc_model=proc_model)
    return run_classical(case, label, b, p, case_id=case_id, seed=seed, adversary=adversary,
                         proc_model=proc_model)


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #

METRICS = ("choice_to_local_accept_ns", "local_validation_ns", "pre_presentation_commit_ns", "issuer_aware_ns",
           "settlement_ns")
CSV_COLUMNS = ["case_id", "network_id", "topology_source", "straight_line_m", "runtime_latency_model",
               "input_latency_evidence", "proc_model", "proc_ns", "protocol", "protocol_id", "variant", "b",
               "n_seeds", *METRICS, "commit_at_Lb_before_presentation", "sync_cross_site_msgs_after_presentation",
               "honest_decision", "race_accepted_sites", "strong_accepted_presentations", "strong_double_spends",
               "s_money_minus_protocol_choice_to_accept_ns",
               "comparability_status", "evidence_kind", "notes"]


def _median(vals: list[Any]) -> Any:
    xs = [v for v in vals if v is not None]
    if not xs:
        return None
    if isinstance(xs[0], bool):
        return all(xs)
    return statistics.median(xs)


def _status(label: str) -> str:
    return "S1 (reference)" if label == S1 else comparability.H[PAIR_OF[label]][1]


NOTES = {
    S1: "G's two-site event model: c relayed B0->B1 (Kent 2022 Table I steps 7-9); validity symbolic",
    "H0": "negative control: double spend accepted",
    "H1": "ledger at L0: remote site pays a synchronous RTT",
    "H2": "3 replicas, 2 at L0: quorum local to L0, so behaves like H1",
    "H3_preassigned": "site fixed at issuance (= b, best case): no late choice",
    "H3_late_commit_disclosed": "issuer learns b at commit",
    "H3_late_commit_ot_private": "ideal OT functionality; computational in any real instantiation",
    "H4+H1": "ML-DSA signature + ledger at L0",
    "H4+H3": "site signed at issuance (= b, best case): no late choice",
    "H5": "trusted tamper-resistant hardware assumption",
    "H6": "detection ex post, not prevention",
}


def sweep(seeds_ripe: int = 20, case_ids: tuple[str, ...] | None = None,
          ) -> tuple[list[dict[str, Any]], dict[str, MatchedRun]]:
    """All cases x protocols x proc models x b. Returns CSV rows and the seed-0 runs (traces)."""
    rows: list[dict[str, Any]] = []
    keep: dict[str, MatchedRun] = {}
    for case_id, case in matched_cases().items():
        if case_ids is not None and case_id not in case_ids:
            continue
        ripe = case.network.topology_source.value == "measured_ripe"
        seeds = range(seeds_ripe if ripe else 1)
        lat_models = sorted({rt.latency.name.split(":")[0] for rt in case.link_runtime.values()})
        for proc_model, p in PROC_MODELS.items():
            for b in (1, 0):
                by_label: dict[str, dict[str, Any]] = {}
                for label in PROTOCOLS:
                    runs = [run_matched(case, label, b, proc_model, s, case_id) for s in seeds]
                    adv = {} if label == S1 else {a: [run_matched(case, label, b, proc_model, s, case_id, a)
                                                      for s in seeds] for a in ADVERSARIES}
                    for r in [runs[0], *(v[0] for v in adv.values())]:
                        keep[f"{case_id}|{label}|b{b}|{proc_model}|{r.adversary or 'honest'}"] = r
                    agg = {k: _median([r.metrics[k] for r in runs]) for k in (*METRICS,
                           "commit_at_Lb_before_presentation", "sync_cross_site_msgs_after_presentation")}
                    by_label[label] = agg
                    rows.append({
                        "case_id": case_id, "network_id": case.network.network_id,
                        "topology_source": case.network.topology_source.value,
                        "straight_line_m": round(site_distance_m(*case.network.sites[:2]), 3),
                        "runtime_latency_model": "|".join(lat_models),
                        "input_latency_evidence": "MEASURED_LATENCY (RIPE RTT/2)" if ripe else
                        str(case.provenance.get("input_evidence", "SYNTHETIC")),
                        "proc_model": proc_model, "proc_ns": p, "protocol": label,
                        "protocol_id": runs[0].protocol_id, "variant": runs[0].variant, "b": b,
                        "n_seeds": len(runs), **agg,
                        "honest_decision": runs[0].metrics["honest_decision"],
                        "race_accepted_sites": max(r.metrics["accepted_sites"] for r in adv["replay"]) if adv else None,
                        "strong_accepted_presentations":
                            max(r.metrics["accepted_presentations"] for r in adv["strong"]) if adv else None,
                        "strong_double_spends":
                            max(r.metrics["accepted_presentations"] - 1 for r in adv["strong"]) if adv else None,
                        "comparability_status": _status(label), "evidence_kind": EvidenceKind.MODELLED_LATENCY.value,
                        "notes": NOTES[label] + ("; median over seeds" if ripe else ""),
                    })
                s1 = by_label[S1]["choice_to_local_accept_ns"]
                for row in rows[-len(PROTOCOLS):]:
                    v = row["choice_to_local_accept_ns"]
                    row["s_money_minus_protocol_choice_to_accept_ns"] = None if v is None or s1 is None else s1 - v
    return rows, keep


def _fmt(v: Any) -> Any:
    if isinstance(v, float):
        return f"{v:.3f}"
    return "" if v is None else v


def write_csv(rows: list[dict[str, Any]], path: Path) -> Path:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: _fmt(r.get(k)) for k in CSV_COLUMNS})
    return path


FIG6_CASES = ("paper_jinan_2.766km_fibre", "paper_yiyuan_mazhan_60.54km_fibre", "synthetic_100km",
              "ripe_helsinki_tampere")
FIG6_PANELS = {"S1": (S1, None), "H1_race": ("H1", "replay"), "H3_late_commit": ("H3_late_commit_disclosed", None),
               "H3_late_commit_ot": ("H3_late_commit_ot_private", None)}


def _event_row(e: TraceEvent, x_of: Mapping[str, float], t0: float) -> dict[str, Any]:
    d = e.detail
    label = d.get("h_kind") or d.get("type") or ""
    return {"event_id": e.event_id, "kind": e.kind, "site_id": e.site_id, "x_m": x_of[e.site_id],
            "t_ns": e.time_ns - t0, "actor": d.get("actor_id"), "label": label, "message_id": e.message_id,
            "parents": list(e.causal_parent_ids),
            **({"decision": d.get("decision"), "accepted": d.get("accepted")}
               if e.kind == "verification_result_available_local" else {})}


def figure6(runs: Mapping[str, MatchedRun], proc_model: str = "jiang_dTproc_1507ns", b: int = 1) -> dict[str, Any]:
    """Spacetime-diagram data: S1 vs H1 race vs H3 late commit, per case (seed 0)."""
    cases = matched_cases()
    out: dict[str, Any] = {
        "description": "Figure 6 data: x = distance from L0 along the site axis, t = time since branch_choice. "
                       "Message edges join message_send -> message_receive. The light cone is |dx| = c dt.",
        "evidence_kind": EvidenceKind.MODELLED_LATENCY.value, "proc_model": proc_model, "b": b,
        "c_m_per_ns": 0.299792458, "cases": {}}
    for case_id in FIG6_CASES:
        case = cases[case_id]
        s0, s1 = case.network.sites[:2]
        x_of = {s0.site_id: 0.0, s1.site_id: site_distance_m(s0, s1)}
        panels = {}
        for panel, (label, adv) in FIG6_PANELS.items():
            r = runs[f"{case_id}|{label}|b{b}|{proc_model}|{adv or 'honest'}"]
            t0 = r.result.first("branch_choice").time_ns
            evs = [_event_row(e, x_of, t0) for e in r.trace.events if e.time_ns >= t0 - 1e-6]
            sends = {e["message_id"]: e for e in evs if e["kind"] == "message_send"}
            edges = [{"message_id": e["message_id"], "label": e["label"], "from_site": sends[e["message_id"]]["site_id"],
                      "to_site": e["site_id"], "t_send_ns": sends[e["message_id"]]["t_ns"], "t_recv_ns": e["t_ns"]}
                     for e in evs if e["kind"] == "message_receive" and e["message_id"] in sends]
            panels[panel] = {"protocol": label, "protocol_id": r.protocol_id, "variant": r.variant,
                             "adversarial_double_spend_attempt": adv is not None, "adversary": adv, "trace_id": r.trace.trace_id,
                             "metrics": r.metrics, "events": evs, "message_edges": edges}
        out["cases"][case_id] = {
            "network_id": case.network.network_id, "topology_source": case.network.topology_source.value,
            "sites": {s0.site_id: {"x_m": 0.0, "role": "L0: issuer/HQ/ledger, Alice's choice"},
                      s1.site_id: {"x_m": x_of[s1.site_id], "role": "L1"}},
            "lightcone_ns": lightcone_delay_ns(s0, s1),
            "input_latency_evidence": "MEASURED_LATENCY (RIPE RTT/2)"
            if case.network.topology_source.value == "measured_ripe" else case.provenance.get("input_evidence"),
            "panels": panels}
    return out


def to_record(row: dict[str, Any], zero_row: dict[str, Any] | None, git_sha: str, env_lock: str) -> BenchmarkRecord:
    """One C6 record per (case, protocol, proc model) for b = 1 (the remote presentation site)."""
    q = row["protocol"] == S1
    lv = row["local_validation_ns"]
    cross = None if zero_row is None or zero_row["local_validation_ns"] is None else zero_row["local_validation_ns"]
    config = {k: row[k] for k in (*METRICS, "case_id", "proc_model", "proc_ns", "b", "n_seeds", "variant",
                                  "commit_at_Lb_before_presentation", "sync_cross_site_msgs_after_presentation",
                                  "honest_decision", "race_accepted_sites", "strong_accepted_presentations",
                                  "strong_double_spends", "input_latency_evidence",
                                  "comparability_status", "notes")}
    if not q:
        spec = spec_for(row["protocol"], ("L0", "L1"), 0.0, 1, S.RETRY_TIMEOUT_NS, strong=True)
        config["strong_adversary_attempts"] = list(spec.strong_attempts or _generic_strong_attempts(("L0", "L1"), 1))
    config["semantics"] = {
        "double_spends_successful": "STRONG adversary (accepted presentations - 1, max over seeds); "
                                    "race_accepted_sites is the weak replay-at-other-site adversary",
        "redemption_local_seconds": "local validation: later of presentation / Stage-II arrival at L_b -> local result",
        "network_cross_check_seconds": "same path under zero processing = communication waited for after presentation",
        "all *_ns in configuration": "measured from branch_choice at L0 unless named otherwise"}
    body = {"protocol": row["protocol"], "case": row["case_id"], "proc": row["proc_model"], "config": config}
    if q:
        trust, pre, flex, priv = ("trusted agents A,A0,A1 / B,B0,B1 (Kent 2022); timing model only, no epsilon",
                                  "Stage I quantum exchange + secret record pre-distributed to B1", "late_choice_any_site",
                                  "not evaluated (timing model only)")
    else:
        trust, pre, flex, priv = spec.trust_model, spec.pre_distribution, spec.spending_flexibility, spec.privacy_game
    return BenchmarkRecord(
        record_id=f"GH-{row['protocol']}-{row['case_id']}-{row['proc_model']}-{canonical_hash(body)[:12]}",
        protocol_id=row["protocol_id"], classical_or_quantum="quantum" if q else "classical",
        security_target=Targets(), trust_model=trust, pre_distribution=pre, spending_flexibility=flex,
        privacy_game=priv, network_id=row["network_id"], site_count=2,
        redemption_local_seconds=None if lv is None else lv / 1e9,
        network_cross_check_seconds=None if cross is None else cross / 1e9,
        classical_bytes=None, issuer_calls=None if q else (1 if row["protocol"] in ("H1", "H2", "H4+H1") else 0),
        double_spends_successful=None if q else row["strong_double_spends"],
        method="lane-GH matched topology: lane-G engine hosting S-money (G) and H0-H6 state machines (H) "
               "(qmint.classical.matched_topology)",
        configuration=json.loads(canonical_json(config)), evidence_kind=EvidenceKind.MODELLED_LATENCY,
        git_sha=git_sha, environment_lock=env_lock)


def main(argv: list[str] | None = None) -> int:
    from qmint.classical.run_baselines import _git_sha

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(ROOT / "reports" / "classical_baseline_notes"))
    ap.add_argument("--ripe-seeds", type=int, default=20)
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows, runs = sweep(args.ripe_seeds)
    write_csv(rows, out / "matched_topology_results.csv")
    (out / "figure6_trace_data.json").write_text(json.dumps(figure6(runs), indent=1, sort_keys=True) + "\n")
    with open(out / "matched_topology_traces.jsonl", "w", encoding="utf-8") as fh:
        for r in runs.values():
            if r.proc_model == "jiang_dTproc_1507ns" and r.b == 1:
                fh.write(canonical_json(r.trace) + "\n")
    git_sha = _git_sha()
    env_lock = f"requirements.lock sha256:{file_sha256(ROOT / 'requirements.lock')}"
    zero = {(r["case_id"], r["protocol"]): r for r in rows if r["proc_model"] == "zero_processing" and r["b"] == 1}
    with open(out / "matched_topology_records.jsonl", "w", encoding="utf-8") as fh:
        for r in rows:
            if r["b"] == 1:
                fh.write(canonical_json(to_record(r, zero.get((r["case_id"], r["protocol"])), git_sha, env_lock))
                         + "\n")
    print(f"wrote {len(rows)} rows, {len(runs)} traces to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
