"""Deterministic C1 scenarios for H0-H6 driven by direct calls (no event engine).

Each ``run_*`` function plays: honest redemption latency per site, a double-spend attempt
(same token presented at two sites at t=0) and, where relevant, a partition. Times are
MODELLED_LATENCY lower bounds: link ``propagation_lower_bound_ns`` + declared processing.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from qmint.classical import h0_bearer, h1_ledger, h2_quorum, h3_escrow, h4_pqc, h5_secure_hardware, h6_ecash
from qmint.classical.common import Decision, Message, ProtocolNode, deliver, new_msg, path_delay_ns
from qmint.core.contracts import SpacetimeNetwork

SITE_PROC_NS = 10_000.0  # declared local terminal processing (10 us)
COORD_PROC_NS = 50_000.0  # declared coordinator / replica processing incl. durable write (50 us)
DEPOSIT_BATCH_DELAY_NS = 0.0  # H6 best case: merchants deposit immediately
MERCHANT_SITES = ("A", "B")  # the two presentation sites of every scenario (S1 is a two-site game)


@dataclass
class ScenarioResult:
    protocol_id: str
    variant: str
    network_id: str
    site_count: int
    trust_model: str
    pre_distribution: str
    spending_flexibility: str
    privacy_game: str
    local_accept_ns: dict[str, float]  # per presentation site, honest single spend
    cross_check_ns: dict[str, float] | None
    double_spends_successful: int
    double_spend_decisions: dict[str, str]
    classical_bytes: int
    issuer_calls: int
    false_rejects: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


def _run_chain(network: SpacetimeNetwork, nodes: Mapping[str, ProtocolNode], first: Message, t0: float,
               down: Iterable[tuple[str, str]] = ()) -> tuple[list[tuple[Message, float]], int]:
    """Follow a request/response chain by direct calls, always delivering the earliest pending message
    whose destination is a hosted node. Returns (terminal messages with times, bytes on the wire)."""
    down = tuple(down)
    pending = [(first, t0)]
    terminal: list[tuple[Message, float]] = []
    nbytes = 0
    while pending:
        pending.sort(key=lambda mt: mt[1])
        msg, t = pending.pop(0)
        nbytes += msg.size_bytes()
        if msg.dst not in nodes:
            terminal.append((msg, t))
            continue
        outs, _ = deliver(network, nodes, msg, t, down)
        pending.extend(outs)
    return terminal, nbytes


def _decision(terminal: list[tuple[Message, float]]) -> tuple[str, float]:
    res = [(m, t) for m, t in terminal if m.kind == "Result"]
    if not res:
        return Decision.REJECT_UNAVAILABLE.value, math.inf
    m, t = res[0]
    return m.payload["decision"], t


def _sites(network: SpacetimeNetwork) -> list[str]:
    return [s.site_id for s in network.sites]


def _extra_accepts(decisions: Mapping[str, str]) -> int:
    """Number of successful double spends = accepted presentations of one token beyond the first."""
    return max(0, sum(d == Decision.ACCEPT.value for d in decisions.values()) - 1)


# --------------------------------------------------------------------------- #
def run_h0(network: SpacetimeNetwork, seed: int = 0) -> ScenarioResult:
    serial = h0_bearer.mint_serial(seed, 0)
    lat, ds, nbytes = {}, {}, 0
    verifiers = {s: h0_bearer.BearerVerifier(f"v@{s}", s, frozenset({serial}), SITE_PROC_NS) for s in MERCHANT_SITES}
    for s, v in verifiers.items():  # the SAME copied serial presented at two sites at t=0
        term, nbytes = _run_chain(network, {v.node_id: v},
                                  new_msg("Present", f"cust@{s}", v.node_id, "s", serial=serial), 0)
        ds[s], lat[s] = _decision(term)
    return ScenarioResult(h0_bearer.PROTOCOL_ID, "negative_control", network.network_id, len(network.sites),
                          "none: copyable bearer string, offline verifiers, no shared state",
                          "valid-serial list pushed to every site at issuance", "late_choice_any_site", "none",
                          lat, None, _extra_accepts(ds), ds, nbytes, 0)


# --------------------------------------------------------------------------- #
def _h1_nodes(network: SpacetimeNetwork, coord_site: str, tokens: frozenset[str] | None,
              sites: list[str]) -> tuple[h1_ledger.LedgerCoordinator, dict[str, h1_ledger.MerchantTerminal]]:
    keys = {f"m@{s}": f"key|{s}".encode() for s in sites}
    coord = h1_ledger.LedgerCoordinator("coord", coord_site, tokens, keys, COORD_PROC_NS)
    terms = {s: h1_ledger.MerchantTerminal(f"t@{s}", s, f"m@{s}", keys[f"m@{s}"], "coord", SITE_PROC_NS)
             for s in sites}
    return coord, terms


def _h1_play(network, coord, terms, presents: dict[str, Message], down=()) -> dict[str, tuple[str, float, int]]:
    """Present concurrently at t=0 at several sites; deliver requests to the coordinator in arrival order
    (event-level race). Unreachable coordinator => terminal times out and retries, then gives up."""
    nodes: dict[str, ProtocolNode] = {coord.node_id: coord, **{t.node_id: t for t in terms.values()}}
    reqs = []
    for s, pm in presents.items():
        (req, t_send), = deliver(network, nodes, pm, 0.0, down)[0]
        reqs.append((s, req, t_send))
    reqs.sort(key=lambda x: x[2] + path_delay_ns(network, x[0], coord.site_id, down))
    out = {}
    for s, req, t_send in reqs:
        term, nbytes = _run_chain(network, nodes, req, t_send, down)
        d, t = _decision(term)
        if d == Decision.REJECT_UNAVAILABLE.value:  # lost in partition: play the retry timer
            t_now, msgs = t_send, []
            idem = req.payload["idem_key"]
            while True:
                t_now += terms[s].retry_timeout_ns
                msgs = terms[s].on_timeout(idem, t_now)
                if msgs and msgs[0].kind == "Result":
                    d, t = msgs[0].payload["decision"], t_now
                    break
                term, b2 = _run_chain(network, nodes, msgs[0], t_now, down)
                nbytes += b2
                d2, t2 = _decision(term)
                if d2 != Decision.REJECT_UNAVAILABLE.value:
                    d, t = d2, t2
                    break
        out[s] = (d, t, nbytes + presents[s].size_bytes())
    return out


def run_h1(network: SpacetimeNetwork, coord_site: str, partition_site: str | None = None,
           variant: str = "coordinator") -> ScenarioResult:
    sites = list(MERCHANT_SITES)
    tok = "tok-h1-0"
    lat, nbytes = {}, 0
    for s in sites:
        coord, terms = _h1_nodes(network, coord_site, frozenset({tok}), sites)
        r = _h1_play(network, coord, terms, {s: new_msg("Present", f"cust@{s}", f"t@{s}", "s", token_id=tok)})
        lat[s] = r[s][1]
        nbytes = r[s][2]
    coord, terms = _h1_nodes(network, coord_site, frozenset({tok}), sites)
    race = _h1_play(network, coord, terms,
                    {s: new_msg("Present", f"cust@{s}", f"t@{s}", "s", token_id=tok) for s in sites[:2]})
    extra: dict[str, Any] = {"coordinator_site": coord_site,
                             "coordinator_rtt_ns": {s: 2 * path_delay_ns(network, s, coord_site) for s in sites}}
    if partition_site is not None:
        coord, terms = _h1_nodes(network, coord_site, frozenset({"tok-p0", "tok-p1"}), sites)
        down = [(partition_site, coord_site), (coord_site, partition_site)]
        down += [(x, partition_site) for x in _sites(network) if x != partition_site]
        down += [(partition_site, x) for x in _sites(network) if x != partition_site]
        res = {}
        for i, s in enumerate(sites):
            res[s] = _h1_play(network, coord, terms,
                              {s: new_msg("Present", f"cust@{s}", f"t@{s}", "s", token_id=f"tok-p{i % 2}")},
                              down)[s][0]
        extra["partition"] = {"isolated_site": partition_site, "decisions": res,
                              "availability_fraction": sum(d == "ACCEPT" for d in res.values()) / len(res)}
    ds = {s: v[0] for s, v in race.items()}
    return ScenarioResult(h1_ledger.PROTOCOL_ID, variant, network.network_id, len(network.sites),
                          "honest online coordinator; authenticated merchant->coordinator channel (HMAC-SHA256)",
                          "issued-serial set at coordinator only", "online_any_site",
                          "none (coordinator learns token, merchant and site at spend time)",
                          lat, {s: lat[s] - 2 * SITE_PROC_NS for s in sites},
                          _extra_accepts(ds), ds, nbytes, 1, extra=extra)


# --------------------------------------------------------------------------- #
def _h2_cluster(network: SpacetimeNetwork, f: int, replica_sites: list[str], leaders: list[str],
                tokens: frozenset[str], merchant_sites: list[str]):
    keys = {f"m@{s}": f"key|{s}".encode() for s in merchant_sites}
    nodes: dict[str, Any] = {}
    leader_ids = []
    for sh, lsite in enumerate(leaders):
        lid = f"s{sh}r@{lsite}"
        fids = [f"s{sh}r@{x}" for x in replica_sites if x != lsite][: 2 * f]
        nodes[lid] = h2_quorum.ShardReplica(lid, lsite, sh, f, True, tuple(fids), tokens, keys, COORD_PROC_NS)
        for fid in fids:
            nodes[fid] = h2_quorum.ShardReplica(fid, fid.split("@")[1], sh, f, False, (), tokens, keys, COORD_PROC_NS)
        leader_ids.append(lid)

    def route(tok: str) -> str:
        return leader_ids[h2_quorum.home_shard(tok, len(leaders))]

    terms = {s: h1_ledger.MerchantTerminal(f"t@{s}", s, f"m@{s}", keys[f"m@{s}"], "", SITE_PROC_NS, router=route)
             for s in merchant_sites}
    nodes.update({t.node_id: t for t in terms.values()})
    return nodes, terms, route


def run_h2(network: SpacetimeNetwork, f: int = 1, replica_sites: list[str] | None = None,
           leaders: list[str] | None = None) -> ScenarioResult:
    replica_sites = replica_sites or _sites(network)
    leaders = leaders or replica_sites[:2]
    msites = list(MERCHANT_SITES)
    # pick one token per shard so both "home" and "remote" spends are observed
    toks = {}
    i = 0
    while len(toks) < len(leaders):
        tk = f"tok-h2-{i}"
        toks.setdefault(h2_quorum.home_shard(tk, len(leaders)), tk)
        i += 1
    lat: dict[str, float] = {}
    nbytes = 0
    for sh, tk in sorted(toks.items()):
        for s in msites:
            nodes, terms, route = _h2_cluster(network, f, replica_sites, leaders, frozenset(toks.values()), msites)
            term, b = _run_chain(network, nodes, new_msg("Present", f"cust@{s}", f"t@{s}", "s", token_id=tk), 0)
            lat[f"{s}|home_leader@{leaders[sh]}"] = _decision(term)[1]
            nbytes = max(nbytes, b)
    # race: same token at both merchant sites
    tk = toks[0]
    nodes, terms, route = _h2_cluster(network, f, replica_sites, leaders, frozenset(toks.values()), msites)
    leader_site = nodes[route(tk)].site_id
    order = sorted(msites, key=lambda s: path_delay_ns(network, s, leader_site))
    ds = {s: _decision(_run_chain(network, nodes, new_msg("Present", f"cust@{s}", f"t@{s}", "s", token_id=tk),
                                  0)[0])[0] for s in order}
    # f crashes keep liveness; f+1 crashes block commits (never double accept)
    fault = {}
    for crashed in (f, f + 1):
        nodes, terms, route = _h2_cluster(network, f, replica_sites, leaders, frozenset(toks.values()), msites)
        lead = nodes[route(tk)]
        victims = list(lead.followers)[:crashed] if crashed <= len(lead.followers) else list(lead.followers)
        for vid in victims:
            nodes[vid].crashed = True
        if crashed > len(lead.followers):
            lead.crashed = True
        fault[f"crashed_{crashed}"] = _decision(
            _run_chain(network, nodes, new_msg("Present", "cust@A", "t@A", "s", token_id=tk), 0)[0])[0]
    return ScenarioResult(h2_quorum.PROTOCOL_ID, f"sharded_quorum_f{f}", network.network_id, len(network.sites),
                          f"crash-fault replicas, <= {f} faulty per shard (2f+1={2 * f + 1}); honest operator",
                          "issued-serial set replicated in each home shard", "online_any_site",
                          "none (home shard learns token, merchant and site)",
                          lat, {k: v - 2 * SITE_PROC_NS for k, v in lat.items()},
                          _extra_accepts(ds), ds, nbytes, 1,
                          extra={"leaders": leaders, "replica_sites": replica_sites, "fault_tests": fault})


# --------------------------------------------------------------------------- #
def run_h3(network: SpacetimeNetwork, issuer_site: str, mode: h3_escrow.Mode) -> ScenarioResult:
    sites = list(MERCHANT_SITES)
    order = {s: f"e@{s}" for s in sites}

    def build():
        iss = h3_escrow.EscrowIssuer("issuer", issuer_site, dict(order), seed=0, processing_ns=COORD_PROC_NS)
        ver = {s: h3_escrow.EscrowSiteVerifier(order[s], s, i, len(sites), SITE_PROC_NS) for i, s in enumerate(sites)}
        nodes: dict[str, Any] = {"issuer": iss, **{v.node_id: v for v in ver.values()}}
        return iss, ver, nodes

    tok = "tok-h3-0"
    iss, ver, nodes = build()
    lat: dict[str, float] = {}
    nbytes = 0
    extra: dict[str, Any] = {"mode": mode, "issuer_site": issuer_site}
    secret_for: dict[int, str] = {}
    chosen = 0  # user's choice b = site index 0 ("A")
    # issuance / pre-distribution
    if mode == "preassigned":
        prov = iss.issue(tok, mode, assigned_site=sites[chosen])
    else:
        prov = iss.issue(tok, mode)
    for m in prov:
        deliver(network, nodes, m, 0.0)
        nbytes += m.size_bytes()
    t_ready = 0.0
    if mode == "late_commit_disclosed":
        commit = new_msg("Commit", f"user@{sites[chosen]}", "issuer", "s", token_id=tok, site=sites[chosen])
        term, b = _run_chain(network, nodes, commit, 0.0)
        nbytes += b
        t_ready = max(path_delay_ns(network, sites[chosen], issuer_site) + COORD_PROC_NS
                      + path_delay_ns(network, issuer_site, s) for s in sites)
    elif mode == "late_commit_ot_private":
        z = 1  # user's private OT choice (fixed for determinism; the privacy test sweeps z)
        wallet = h3_escrow.OTWallet(tok, z, iss.ot_transfer(tok, z), len(sites))
        c = wallet.commit_value(chosen)
        commit = new_msg("CommitC", f"user@{sites[chosen]}", "issuer", "s", token_id=tok, c=c)
        term, b = _run_chain(network, nodes, commit, 0.0)
        nbytes += b
        t_ready = max(path_delay_ns(network, sites[chosen], issuer_site) + COORD_PROC_NS
                      + path_delay_ns(network, issuer_site, s) for s in sites)
        secret_for[chosen] = wallet.r_z.hex()
        extra["issuer_observed_c"] = iss.observed_c[tok]
    extra["stage_ii_commit_to_activation_ns"] = t_ready
    extra["issuer_learned_site"] = iss.learned_site.get(tok)
    # honest spend at chosen site (local only) -- latency measured from presentation
    pm = new_msg("Present", f"cust@{sites[chosen]}", order[sites[chosen]], "s", token_id=tok,
                 secret_hex=secret_for.get(chosen))
    term, b = _run_chain(network, nodes, pm, 0.0)
    d0, t0 = _decision(term)
    lat[sites[chosen]] = t0
    nbytes += b
    # double-spend attempt: the user also presents at the OTHER site (best adversarial input it holds)
    other = sites[1 - chosen]
    pm2 = new_msg("Present", f"cust@{other}", order[other], "s", token_id=tok, secret_hex=secret_for.get(chosen))
    d1, _ = _decision(_run_chain(network, nodes, pm2, 0.0)[0])
    ds = {sites[chosen]: d0, other: d1}
    flex = "preassigned_site" if mode == "preassigned" else "late_choice_any_site"
    privacy = {"preassigned": "none (issuer learns site at issuance)",
               "late_commit_disclosed": "none (issuer learns site at Stage-II commit)",
               "late_commit_ot_private": "site hidden from issuer under ideal-OT receiver privacy (model)"}[mode]
    trust = {"preassigned": "honest issuer and site verifiers; authenticated provisioning",
             "late_commit_disclosed": "honest issuer relays commit; authenticated channels",
             "late_commit_ot_private": "honest-but-curious issuer; IDEAL 1-of-M OT functionality "
                                       "(real instantiation computational, NOT_IMPLEMENTED)"}[mode]
    return ScenarioResult(h3_escrow.PROTOCOL_ID, mode, network.network_id, len(network.sites), trust,
                          "per-token provisioning message to every site at issuance" if mode != "preassigned"
                          else "per-token escrow at the assigned site at issuance",
                          flex, privacy, lat, None,
                          _extra_accepts(ds), ds, nbytes,
                          0 if mode == "preassigned" else 1, extra=extra)


# --------------------------------------------------------------------------- #
def run_h4(network: SpacetimeNetwork, combine: str, coord_site: str = "A",
           parameter_set: str = "ML_DSA_44", timings: dict | None = None) -> ScenarioResult:
    sites = list(MERCHANT_SITES)
    issuer = h4_pqc.PQCIssuer(parameter_set, seed=0)
    serial = "tok-h4-0"
    extra: dict[str, Any] = {"combine": combine, "parameter_set": parameter_set, "pqc_timing": timings,
                             "pk_bytes": len(issuer.pk)}
    if combine in ("none", "h3_site_binding"):
        bound = "A" if combine == "h3_site_binding" else None
        tokw = issuer.issue(serial, 1, bound).wire()
        lat, ds, nbytes = {}, {}, 0
        for s in sites:
            v = h4_pqc.SignedOfflineVerifier(f"v@{s}", s, parameter_set, issuer.pk, combine == "h3_site_binding",
                                             SITE_PROC_NS)
            term, nbytes = _run_chain(network, {v.node_id: v},
                                      new_msg("Present", f"cust@{s}", v.node_id, "s", token=tokw), 0)
            d, t = _decision(term)
            ds[s] = d
            if d == "ACCEPT":
                lat[s] = t
        flex = "late_choice_any_site" if combine == "none" else "preassigned_site"
        return ScenarioResult(h4_pqc.PROTOCOL_ID, f"mldsa_{combine}", network.network_id, len(network.sites),
                              "EUF-CMA of ML-DSA (computational, post-quantum); offline verifiers hold issuer pk"
                              + ("; site binding signed at issuance" if bound else ""),
                              "issuer public key at every site" + ("; token bound to one site" if bound else ""),
                              flex, "none (issuer learns site at issuance)" if bound else "none (serial linkable)",
                              lat, None, _extra_accepts(ds), ds, nbytes, 0,
                              extra=extra)
    if combine != "h1_ledger":
        raise ValueError(combine)
    tokw = issuer.issue(serial).wire()
    keys = {f"m@{s}": f"key|{s}".encode() for s in sites}
    coord = h1_ledger.LedgerCoordinator("coord", coord_site, None, keys, COORD_PROC_NS)
    terms = {s: h4_pqc.SignedTerminal(h1_ledger.MerchantTerminal(f"t@{s}", s, f"m@{s}", keys[f"m@{s}"], "coord",
                                                                   SITE_PROC_NS), parameter_set, issuer.pk)
             for s in sites}
    r = _h1_play(network, coord, terms,
                 {s: new_msg("Present", f"cust@{s}", f"t@{s}", "s", token=tokw) for s in sites})
    lat = {}
    for s in sites:
        c2 = h1_ledger.LedgerCoordinator("coord", coord_site, None, keys, COORD_PROC_NS)
        t2 = {x: h4_pqc.SignedTerminal(h1_ledger.MerchantTerminal(f"t@{x}", x, f"m@{x}", keys[f"m@{x}"], "coord",
                                                                    SITE_PROC_NS), parameter_set, issuer.pk)
              for x in sites}
        lat[s] = _h1_play(network, c2, t2, {s: new_msg("Present", f"cust@{s}", f"t@{s}", "s", token=tokw)})[s][1]
    ds = {s: v[0] for s, v in r.items()}
    extra["coordinator_site"] = coord_site
    return ScenarioResult(h4_pqc.PROTOCOL_ID, "mldsa_h1_ledger", network.network_id, len(network.sites),
                          "ML-DSA EUF-CMA (computational) + honest online spent ledger",
                          "issuer public key at every site; no per-token state pre-distributed",
                          "online_any_site", "none (coordinator learns token, merchant and site)",
                          lat, {s: lat[s] - 2 * SITE_PROC_NS for s in sites},
                          _extra_accepts(ds), ds,
                          max(v[2] for v in r.values()), 1, extra=extra)


# --------------------------------------------------------------------------- #
def run_h5(network: SpacetimeNetwork, tamper_resistant: bool) -> ScenarioResult:
    sites = list(MERCHANT_SITES)
    se = h5_secure_hardware.SecureElement("dev-1", tamper_resistant=tamper_resistant)
    se.load("tok-h5-0")
    keys = {"dev-1": se.device_key_for_registration()}
    merchants = {s: h5_secure_hardware.OfflineHardwareMerchant(f"m@{s}", s, f"m@{s}", keys, SITE_PROC_NS)
                 for s in sites}
    devices = {"A": se}
    if not tamper_resistant:
        devices["B"] = se.clone()  # attack possible only because assumption H5-TR is broken
    else:
        try:
            se.clone()
        except h5_secure_hardware.TamperResistanceAssumption:
            pass
        devices["B"] = se  # the only device: second spend must come from it
    lat, ds, nbytes = {}, {}, 0
    for s in sites:
        m = merchants[s]
        hello = new_msg("Hello", f"cust@{s}", m.node_id, "s")
        (ch, t1), = deliver(network, {m.node_id: m}, hello, 0.0)[0]
        att = devices[s].pay("tok-h5-0", m.merchant_id, ch.payload["nonce"])
        pres = new_msg("Present", f"cust@{s}", m.node_id, "s", attestation=att)
        term, b = _run_chain(network, {m.node_id: m}, pres, t1)
        d, t = _decision(term)
        ds[s] = d
        if s == "A":
            lat[s] = t
            nbytes = b + hello.size_bytes() + ch.size_bytes()
    rec = h5_secure_hardware.reconcile([a for m in merchants.values() for a in m.accepted])
    return ScenarioResult(h5_secure_hardware.PROTOCOL_ID,
                          "assumption_holds" if tamper_resistant else "assumption_violated_clone",
                          network.network_id, len(network.sites),
                          h5_secure_hardware.ASSUMPTION_ID + ("" if tamper_resistant else " -- VIOLATED in this run"),
                          "token loaded into the wallet SE at issuance; device keys registered with merchants",
                          "late_choice_any_site", "none modelled (device id + counter visible at clearing)",
                          lat, None, _extra_accepts(ds), ds, nbytes, 0,
                          extra={"reconciliation": rec, "real_device_benchmarked": False})


# --------------------------------------------------------------------------- #
def run_h6(network: SpacetimeNetwork, bank_site: str, k: int = 16, modulus_bits: int = 512) -> ScenarioResult:
    sites = list(MERCHANT_SITES)
    bank = h6_ecash.CFNBank(site_id=bank_site, modulus_bits=modulus_bits, k=k, seed=0)
    u = 4242
    bank.open_account(u)
    wallet = h6_ecash.CFNWallet(u)
    coin = wallet.withdraw(bank)
    if coin is None:
        raise RuntimeError("honest withdrawal failed")
    merchants = {s: h6_ecash.CFNMerchant(f"m@{s}", s, f"m@{s}", bank.n, seed=i) for i, s in enumerate(sites)}
    lat, ds, nbytes = {}, {}, 0
    for s in sites:  # Alice spends the SAME coin at both offline merchants
        m = merchants[s]
        pc = new_msg("PresentCoin", f"alice@{s}", m.node_id, "s", coin=str(coin["C"]), n_terms=k // 2)
        (ch, t1), = deliver(network, {m.node_id: m}, pc, 0.0)[0]
        resp = new_msg("Response", f"alice@{s}", m.node_id, "s", responses=wallet.respond(coin, ch.payload["z"]))
        term, b = _run_chain(network, {m.node_id: m}, resp, t1)
        d, t = _decision(term)
        ds[s] = d
        lat[s] = t
        nbytes = b + pc.size_bytes() + ch.size_bytes()
    nodes: dict[str, Any] = {"bank": bank, **{m.node_id: m for m in merchants.values()}}
    detect = []
    for s in sites:
        for dm in merchants[s].deposit_messages("bank"):
            outs, arr = deliver(network, nodes, dm, lat[s] + DEPOSIT_BATCH_DELAY_NS)
            detect.append({"site": s, "arrival_ns": arr, "status": outs[0][0].payload["status"],
                           "traced_account": outs[0][0].payload.get("traced_account")})
    return ScenarioResult(h6_ecash.PROTOCOL_ID, f"cfn88_sec1_k{k}", network.network_id, len(network.sites),
                          "RSA (toy 512-bit) blind signature + cut-and-choose; bank honest for crediting; "
                          "detection-only double-spend deterrence (identity revealed ex post)",
                          "coin withdrawn in advance (k blinded candidates, k/2 opened)",
                          "late_choice_any_site",
                          "payer untraceable if coin spent once (heuristic here: SHA-256 g is not bijective)",
                          lat, None, _extra_accepts(ds), ds, nbytes, 0,
                          extra={"deposits": detect, "true_account": u,
                                 "undetected_double_spend_prob_if_independent_challenges": 2.0 ** (-(k // 2)),
                                 "detection_is_not_prevention": True, "source": h6_ecash.SOURCE})
