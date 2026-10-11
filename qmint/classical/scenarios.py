"""Deterministic C1 scenarios for H0-H6, hosted on lane G's discrete-event engine.

Each ``run_*`` function plays: honest redemption latency per site, a double-spend attempt
(same token presented at two sites at the same instant) and, where relevant, a partition.
Every message goes through :mod:`qmint.networks.simulator` via
:mod:`qmint.classical.engine_adapter`. Cross-site delivery uses the engine's default
``Lightcone`` runtime (exactly the link lower bound) unless a scenario passes a runtime, so
times are MODELLED_LATENCY lower bounds: light cone + declared processing.
"""

from __future__ import annotations

import hashlib
import math
import random
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from qmint.classical import h0_bearer, h1_ledger, h2_quorum, h3_escrow, h4_pqc, h5_secure_hardware, h6_ecash
from qmint.classical.common import Decision, Message, ProtocolNode, new_msg
from qmint.classical.engine_adapter import HostedRun, Injection, NodeActor, React, run_hosted, wire_bytes
from qmint.core.contracts import SpacetimeNetwork
from qmint.networks.causality import link_lower_bound_ns
from qmint.networks.simulator import Partition

SITE_PROC_NS = 10_000.0  # declared local terminal processing (10 us)
COORD_PROC_NS = 50_000.0  # declared coordinator / replica processing incl. durable write (50 us)
RETRY_TIMEOUT_NS = 5_000_000.0  # H1/H2 terminal retry timer (5 ms; MerchantTerminal default)
ISSUANCE_LEAD_NS = 1e9  # issuance / provisioning happens 1 s before Stage II (arbitrarily early)
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


def _present(site: str, dst: str, **payload: Any) -> Message:
    return new_msg("Present", f"cust@{site}", dst, "s", **payload)


def _play(network: SpacetimeNetwork, nodes: Iterable[ProtocolNode | NodeActor], presents: Iterable[Message],
          t0: float = 0.0, token_id: str = "tok", reacts: Mapping[str, React] | None = None,
          partitions: Iterable[Partition] = (), before: Iterable[Injection] = ()) -> HostedRun:
    """Present every message at ``t0`` (concurrently) after the ``before`` injections. Ideal clocks."""
    inj = [*before, *(Injection(t0, m) for m in presents)]
    return run_hosted(network, nodes, inj, token_id=token_id, reacts=reacts, partitions=tuple(partitions),
                      clock_offsets_ns={s: 0.0 for s in _sites(network)})


def _by_site(run: HostedRun) -> dict[str, tuple[str, float]]:
    """``{site: (decision, absolute decision time)}`` of the first local result per presentation point."""
    return {run.clients[c].site_id: v for c, v in run.decisions().items()}


def _receipts(run: HostedRun, h_kinds: Iterable[str]) -> dict[str, float]:
    """First receipt time of any of ``h_kinds`` per receiving actor."""
    kinds = set(h_kinds)
    out: dict[str, float] = {}
    for e in run.result.of_kind("message_receive"):
        if e.detail.get("h_kind") in kinds:
            out.setdefault(e.actor_id, e.time_ns)
    return out


def _sites(network: SpacetimeNetwork) -> list[str]:
    return [s.site_id for s in network.sites]


def sim_idem_rng(node_id: str) -> random.Random:
    """Seeded idempotency-key source for ONE simulated terminal (reproducible traces). Real terminals use
    the CSPRNG default of :class:`~qmint.classical.h1_ledger.MerchantTerminal`."""
    return random.Random(f"sim-idem|{node_id}")


def _isolate(network: SpacetimeNetwork, site: str) -> Partition:
    others = frozenset(_sites(network)) - {site}
    return Partition(0.0, math.inf, frozenset({site}), others)


def _extra_accepts(decisions: Mapping[str, str]) -> int:
    """Number of successful double spends = accepted presentations of one token beyond the first."""
    return max(0, sum(d == Decision.ACCEPT.value for d in decisions.values()) - 1)


# --------------------------------------------------------------------------- #
def run_h0(network: SpacetimeNetwork, seed: int = 0) -> ScenarioResult:
    serial = h0_bearer.mint_serial(seed, 0)
    verifiers = [h0_bearer.BearerVerifier(f"v@{s}", s, frozenset({serial}), SITE_PROC_NS) for s in MERCHANT_SITES]
    # the SAME copied serial presented at two sites at t=0
    run = _play(network, verifiers, [_present(s, f"v@{s}", serial=serial) for s in MERCHANT_SITES], token_id=serial)
    res = _by_site(run)
    ds = {s: d for s, (d, _) in res.items()}
    last = MERCHANT_SITES[-1]
    return ScenarioResult(h0_bearer.PROTOCOL_ID, "negative_control", network.network_id, len(network.sites),
                          "none: copyable bearer string, offline verifiers, no shared state",
                          "valid-serial list pushed to every site at issuance", "late_choice_any_site", "none",
                          {s: t for s, (_, t) in res.items()}, None, _extra_accepts(ds), ds,
                          wire_bytes(run.result, {f"cust@{last}", f"v@{last}"}), 0)


# --------------------------------------------------------------------------- #
TerminalWrap = Callable[[h1_ledger.MerchantTerminal], ProtocolNode]


def h1_nodes(coord_site: str, tokens: frozenset[str] | None, sites: Iterable[str],
             site_proc_ns: float = SITE_PROC_NS, coord_proc_ns: float = COORD_PROC_NS,
             wrap_terminal: TerminalWrap | None = None, retry_timeout_ns: float = RETRY_TIMEOUT_NS,
             extra_tills: Mapping[str, tuple[str, str]] | None = None,
             ) -> tuple[h1_ledger.LedgerCoordinator, dict[str, ProtocolNode]]:
    """Ledger coordinator + one merchant terminal ``t@<site>`` per site (optionally wrapped, e.g. H4+H1).
    ``extra_tills`` ``{node_id: (site, merchant_site)}`` adds further tills of merchant ``m@<merchant_site>``
    (multi-till / restarted-till deployments, keyed by node id in the returned map)."""
    sites = list(sites)
    keys = {f"m@{s}": f"key|{s}".encode() for s in sites}
    coord = h1_ledger.LedgerCoordinator("coord", coord_site, tokens, keys, coord_proc_ns)
    tills = {s: (f"t@{s}", s, s) for s in sites}
    tills.update({nid: (nid, site, ms) for nid, (site, ms) in (extra_tills or {}).items()})
    terms: dict[str, ProtocolNode] = {}
    for key, (nid, site, ms) in tills.items():
        t = h1_ledger.MerchantTerminal(nid, site, f"m@{ms}", keys[f"m@{ms}"], "coord", site_proc_ns,
                                       retry_timeout_ns=retry_timeout_ns, idem_rng=sim_idem_rng(nid))
        terms[key] = wrap_terminal(t) if wrap_terminal else t
    return coord, terms


def _h1_family(network: SpacetimeNetwork, coord_site: str, tokens: frozenset[str] | None,
               payload: Callable[[str], dict[str, Any]], wrap_terminal: TerminalWrap | None = None,
               ) -> tuple[dict[str, float], dict[str, str], int]:
    """Honest spend per site (fresh ledger each) and a concurrent race of one token at both sites."""
    sites = list(MERCHANT_SITES)
    lat, nbytes = {}, 0
    for s in sites:
        coord, terms = h1_nodes(coord_site, tokens, sites, wrap_terminal=wrap_terminal)
        run = _play(network, [coord, *terms.values()], [_present(s, f"t@{s}", **payload(s))])
        lat[s] = _by_site(run)[s][1]
        nbytes = max(nbytes, wire_bytes(run.result))
    coord, terms = h1_nodes(coord_site, tokens, sites, wrap_terminal=wrap_terminal)
    race = _play(network, [coord, *terms.values()], [_present(s, f"t@{s}", **payload(s)) for s in sites])
    return lat, {s: d for s, (d, _) in _by_site(race).items()}, nbytes


def run_h1(network: SpacetimeNetwork, coord_site: str, partition_site: str | None = None,
           variant: str = "coordinator") -> ScenarioResult:
    sites = list(MERCHANT_SITES)
    tok = "tok-h1-0"
    lat, ds, nbytes = _h1_family(network, coord_site, frozenset({tok}), lambda s: {"token_id": tok})
    extra: dict[str, Any] = {"coordinator_site": coord_site,
                             "coordinator_rtt_ns": {s: 2 * link_lower_bound_ns(network, s, coord_site)
                                                    for s in sites}}
    if partition_site is not None:  # isolate one site from everyone (including the coordinator)
        coord, terms = h1_nodes(coord_site, frozenset({"tok-p0", "tok-p1"}), sites)
        run = _play(network, [coord, *terms.values()],
                    [_present(s, f"t@{s}", token_id=f"tok-p{i % 2}") for i, s in enumerate(sites)],
                    partitions=[_isolate(network, partition_site)])
        res = {s: d for s, (d, _) in _by_site(run).items()}
        extra["partition"] = {"isolated_site": partition_site, "decisions": res,
                              "availability_fraction": sum(d == "ACCEPT" for d in res.values()) / len(res)}
    return ScenarioResult(h1_ledger.PROTOCOL_ID, variant, network.network_id, len(network.sites),
                          "honest online coordinator; authenticated merchant->coordinator channel (HMAC-SHA256)",
                          "issued-serial set at coordinator only", "online_any_site",
                          "none (coordinator learns token, merchant and site at spend time)",
                          lat, {s: lat[s] - 2 * SITE_PROC_NS for s in sites},
                          _extra_accepts(ds), ds, nbytes, 1, extra=extra)


# --------------------------------------------------------------------------- #
def h2_cluster(f: int, replica_sites: list[str], leaders: list[str],
               tokens: frozenset[str], merchant_sites: list[str], site_proc_ns: float = SITE_PROC_NS,
               coord_proc_ns: float = COORD_PROC_NS, retry_timeout_ns: float = RETRY_TIMEOUT_NS,
               extra_tills: Mapping[str, tuple[str, str]] | None = None,
               ) -> tuple[dict[str, Any], Callable[[str], str]]:
    """Sharded quorum: one leader per shard at ``leaders[sh]``; followers on the other replica sites.
    A site may host several replicas (listed repeatedly in ``replica_sites``). ``extra_tills`` as in
    :func:`h1_nodes`."""
    keys = {f"m@{s}": f"key|{s}".encode() for s in merchant_sites}
    nodes: dict[str, Any] = {}
    leader_ids = []
    for sh, lsite in enumerate(leaders):
        lid = f"s{sh}r0@{lsite}"
        rest = list(replica_sites)
        rest.remove(lsite)
        fids = [f"s{sh}r{j + 1}@{x}" for j, x in enumerate(rest)][: 2 * f]
        nodes[lid] = h2_quorum.ShardReplica(lid, lsite, sh, f, True, tuple(fids), tokens, keys, coord_proc_ns)
        for fid in fids:
            nodes[fid] = h2_quorum.ShardReplica(fid, fid.split("@")[1], sh, f, False, (), tokens, keys, coord_proc_ns)
        leader_ids.append(lid)

    def route(tok: str) -> str:
        return leader_ids[h2_quorum.home_shard(tok, len(leaders))]

    tills = [(f"t@{s}", s, s) for s in merchant_sites]
    tills += [(nid, site, ms) for nid, (site, ms) in (extra_tills or {}).items()]
    for nid, site, ms in tills:
        t = h1_ledger.MerchantTerminal(nid, site, f"m@{ms}", keys[f"m@{ms}"], "", site_proc_ns,
                                       retry_timeout_ns=retry_timeout_ns, router=route, idem_rng=sim_idem_rng(nid))
        nodes[t.node_id] = t
    return nodes, route


def run_h2(network: SpacetimeNetwork, f: int = 1, replica_sites: list[str] | None = None,
           leaders: list[str] | None = None) -> ScenarioResult:
    replica_sites = replica_sites or _sites(network)
    leaders = leaders or replica_sites[:2]
    msites = list(MERCHANT_SITES)
    # pick one token per shard so both "home" and "remote" spends are observed
    toks: dict[int, str] = {}
    i = 0
    while len(toks) < len(leaders):
        tk = f"tok-h2-{i}"
        toks.setdefault(h2_quorum.home_shard(tk, len(leaders)), tk)
        i += 1
    issued = frozenset(toks.values())

    def cluster():
        return h2_cluster(f, replica_sites, leaders, issued, msites)

    lat: dict[str, float] = {}
    nbytes = 0
    for sh, tk in sorted(toks.items()):
        for s in msites:
            nodes, _ = cluster()
            run = _play(network, nodes.values(), [_present(s, f"t@{s}", token_id=tk)])
            lat[f"{s}|home_leader@{leaders[sh]}"] = _by_site(run)[s][1]
            nbytes = max(nbytes, wire_bytes(run.result))
    # race: same token at both merchant sites, concurrently
    tk = toks[0]
    nodes, _ = cluster()
    race = _play(network, nodes.values(), [_present(s, f"t@{s}", token_id=tk) for s in msites])
    ds = {s: d for s, (d, _) in _by_site(race).items()}
    # f crashes keep liveness; f+1 crashes block commits (never double accept)
    fault = {}
    for crashed in (f, f + 1):
        nodes, route = cluster()
        lead = nodes[route(tk)]
        for vid in list(lead.followers)[:crashed]:
            nodes[vid].crashed = True
        if crashed > len(lead.followers):
            lead.crashed = True
        run = _play(network, nodes.values(), [_present("A", "t@A", token_id=tk)])
        fault[f"crashed_{crashed}"] = _by_site(run)["A"][0]
    return ScenarioResult(h2_quorum.PROTOCOL_ID, f"sharded_quorum_f{f}", network.network_id, len(network.sites),
                          f"crash-fault replicas, <= {f} faulty per shard (2f+1={2 * f + 1}); honest operator",
                          "issued-serial set replicated in each home shard", "online_any_site",
                          "none (home shard learns token, merchant and site)",
                          lat, {k: v - 2 * SITE_PROC_NS for k, v in lat.items()},
                          _extra_accepts(ds), ds, nbytes, 1,
                          extra={"leaders": leaders, "replica_sites": replica_sites, "fault_tests": fault})


# --------------------------------------------------------------------------- #
@dataclass
class H3Setup:
    issuer: h3_escrow.EscrowIssuer
    verifiers: dict[str, h3_escrow.EscrowSiteVerifier]
    provisioning: list[Message]
    commit: dict[int, Message]  # chosen site index b -> Stage-II message from the user (late modes only)
    secret_hex: str | None  # what the user presents (OT mode: r_z)


def h3_setup(sites: list[str], issuer_site: str, mode: h3_escrow.Mode, token_id: str, chosen: int,
             site_proc_ns: float = SITE_PROC_NS, coord_proc_ns: float = COORD_PROC_NS, z: int = 1) -> H3Setup:
    """Issuer + hold-until-active verifiers ``e@<site>``; issuance messages and the user's Stage-II commit.
    ``preassigned`` escrows at ``sites[chosen]`` (site fixed at issuance). OT mode uses private ``z``."""
    order = {s: f"e@{s}" for s in sites}
    # Reproducible simulation: an explicit issuer-private key (never handed to any customer-side agent).
    iss = h3_escrow.EscrowIssuer("issuer", issuer_site, dict(order), processing_ns=coord_proc_ns,
                                 issuer_key=hashlib.sha256(f"sim-h3-issuer-key|{token_id}".encode()).digest())
    ver = {s: h3_escrow.EscrowSiteVerifier(order[s], s, i, len(sites), site_proc_ns, hold_until_active=True)
           for i, s in enumerate(sites)}
    prov = iss.issue(token_id, mode, assigned_site=sites[chosen] if mode == "preassigned" else None)
    commit: dict[int, Message] = {}
    secret = None
    if mode == "late_commit_disclosed":
        commit = {b: new_msg("Commit", f"user@{sites[b]}", "issuer", "s", token_id=token_id, site=sites[b])
                  for b in range(len(sites))}
    elif mode == "late_commit_ot_private":
        wallet = h3_escrow.OTWallet(token_id, z, iss.ot_transfer(token_id, z), len(sites))
        commit = {b: new_msg("CommitC", f"user@{sites[b]}", "issuer", "s", token_id=token_id,
                             c=wallet.commit_value(b)) for b in range(len(sites))}
        secret = wallet.r_z.hex()
    return H3Setup(iss, ver, prov, commit, secret)


def run_h3(network: SpacetimeNetwork, issuer_site: str, mode: h3_escrow.Mode) -> ScenarioResult:
    sites = list(MERCHANT_SITES)
    tok = "tok-h3-0"
    chosen = 0  # user's choice b = site index 0 ("A")
    other = sites[1 - chosen]
    st = h3_setup(sites, issuer_site, mode, tok, chosen)
    t2 = ISSUANCE_LEAD_NS  # Stage II: commit and presentation happen together; verifiers hold until active
    before = [Injection(0.0, m, kind="issue") for m in st.provisioning]
    if chosen in st.commit:
        before.append(Injection(t2, st.commit[chosen], kind="commitment", site=sites[chosen]))
    # honest spend at the chosen site + double-spend attempt at the OTHER site (best adversarial input it holds)
    run = _play(network, [st.issuer, *st.verifiers.values()],
                [_present(s, f"e@{s}", token_id=tok, secret_hex=st.secret_hex) for s in (sites[chosen], other)],
                t0=t2, token_id=tok, before=before)
    res = _by_site(run)
    act = _receipts(run, ("Activate", "RelayC"))
    ready = {s: max(t2, act.get(f"e@{s}", t2)) for s in sites}
    extra: dict[str, Any] = {"mode": mode, "issuer_site": issuer_site,
                             "stage_ii_commit_to_activation_ns": max(ready.values()) - t2,
                             "issuer_learned_site": st.issuer.learned_site.get(tok)}
    if mode == "late_commit_ot_private":
        extra["issuer_observed_c"] = st.issuer.observed_c[tok]
    ds = {s: d for s, (d, _) in res.items()}
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
                          flex, privacy, {sites[chosen]: res[sites[chosen]][1] - ready[sites[chosen]]}, None,
                          _extra_accepts(ds), ds, wire_bytes(run.result, _honest_actors(run, other)),
                          0 if mode == "preassigned" else 1, extra=extra)


def _honest_actors(run: HostedRun, attack_site: str) -> set[str]:
    """Every actor except the double-spend attempt's presentation point and verifier."""
    return {e.actor_id for e in run.result.events} - {f"cust@{attack_site}", f"e@{attack_site}"}


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
        vs = [h4_pqc.SignedOfflineVerifier(f"v@{s}", s, parameter_set, issuer.pk, combine == "h3_site_binding",
                                           SITE_PROC_NS) for s in sites]
        run = _play(network, vs, [_present(s, f"v@{s}", token=tokw) for s in sites], token_id=serial)
        res = _by_site(run)
        ds = {s: d for s, (d, _) in res.items()}
        lat = {s: t for s, (d, t) in res.items() if d == "ACCEPT"}
        flex = "late_choice_any_site" if combine == "none" else "preassigned_site"
        return ScenarioResult(h4_pqc.PROTOCOL_ID, f"mldsa_{combine}", network.network_id, len(network.sites),
                              "EUF-CMA of ML-DSA (computational, post-quantum); offline verifiers hold issuer pk"
                              + ("; site binding signed at issuance" if bound else ""),
                              "issuer public key at every site" + ("; token bound to one site" if bound else ""),
                              flex, "none (issuer learns site at issuance)" if bound else "none (serial linkable)",
                              lat, None, _extra_accepts(ds), ds,
                              wire_bytes(run.result, {f"cust@{sites[-1]}", f"v@{sites[-1]}"}), 0, extra=extra)
    if combine != "h1_ledger":
        raise ValueError(combine)
    tokw = issuer.issue(serial).wire()
    lat, ds, nbytes = _h1_family(network, coord_site, None, lambda s: {"token": tokw},
                                 wrap_terminal=lambda t: h4_pqc.SignedTerminal(t, parameter_set, issuer.pk))
    extra["coordinator_site"] = coord_site
    return ScenarioResult(h4_pqc.PROTOCOL_ID, "mldsa_h1_ledger", network.network_id, len(network.sites),
                          "ML-DSA EUF-CMA (computational) + honest online spent ledger",
                          "issuer public key at every site; no per-token state pre-distributed",
                          "online_any_site", "none (coordinator learns token, merchant and site)",
                          lat, {s: lat[s] - 2 * SITE_PROC_NS for s in sites},
                          _extra_accepts(ds), ds, nbytes, 1, extra=extra)


# --------------------------------------------------------------------------- #
def h5_react(device: h5_secure_hardware.SecureElement, token_id: str, site: str, merchant_id: str,
             merchant_node: str) -> React:
    """Payer side of H5: answer the merchant's challenge with an SE attestation (None if refused)."""
    def react(h: Message) -> list[Message]:
        if h.kind != "Challenge":
            return []
        att = device.pay(token_id, merchant_id, h.payload["nonce"])
        return [new_msg("Present", f"cust@{site}", merchant_node, "s", attestation=att)]
    return react


def run_h5(network: SpacetimeNetwork, tamper_resistant: bool) -> ScenarioResult:
    sites = list(MERCHANT_SITES)
    tok = "tok-h5-0"
    se = h5_secure_hardware.SecureElement("dev-1", tamper_resistant=tamper_resistant)
    se.load(tok)
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
    reacts = {f"cust@{s}": h5_react(devices[s], tok, s, merchants[s].merchant_id, merchants[s].node_id)
              for s in sites}
    run = _play(network, merchants.values(), [new_msg("Hello", f"cust@{s}", f"m@{s}", "s") for s in sites],
                token_id=tok, reacts=reacts)
    res = _by_site(run)
    ds = {s: d for s, (d, _) in res.items()}
    rec = h5_secure_hardware.reconcile([a for m in merchants.values() for a in m.accepted])
    return ScenarioResult(h5_secure_hardware.PROTOCOL_ID,
                          "assumption_holds" if tamper_resistant else "assumption_violated_clone",
                          network.network_id, len(network.sites),
                          h5_secure_hardware.ASSUMPTION_ID + ("" if tamper_resistant else " -- VIOLATED in this run"),
                          "token loaded into the wallet SE at issuance; device keys registered with merchants",
                          "late_choice_any_site", "none modelled (device id + counter visible at clearing)",
                          {"A": res["A"][1]}, None, _extra_accepts(ds), ds,
                          wire_bytes(run.result, {"cust@A", "m@A"}), 0,
                          extra={"reconciliation": rec, "real_device_benchmarked": False})


# --------------------------------------------------------------------------- #
def h6_merchant_actor(m: h6_ecash.CFNMerchant, bank_node: str) -> NodeActor:
    """CFN merchant that deposits each accepted coin with the bank immediately (best case for detection)."""
    def deposit(res: Message) -> list[Message]:
        return m.deposit_messages(bank_node) if res.payload["decision"] == Decision.ACCEPT.value else []
    return NodeActor(m, followup=deposit)


def h6_react(wallet: h6_ecash.CFNWallet, coin: dict, site: str, merchant_node: str) -> React:
    def react(h: Message) -> list[Message]:
        if h.kind != "Challenge":
            return []
        return [new_msg("Response", f"alice@{site}", merchant_node, "s", responses=wallet.respond(coin, h.payload["z"]))]
    return react


def h6_deposits(run: HostedRun, bank_node: str) -> list[dict[str, Any]]:
    """Deposit arrivals at the bank with the bank's verdict (from the trace)."""
    evs = run.result.events
    verdict = {e.causal_parent_ids[0]: e.detail["body"] for e in evs
               if e.kind == "message_send" and e.actor_id == bank_node and e.detail.get("h_kind") == "DepositResult"}
    site = {a: s for a, s in ((e.actor_id, e.site_id) for e in evs)}
    return [{"site": site[e.detail["src"]], "arrival_ns": e.time_ns, "status": verdict[e.event_id]["status"],
             "traced_account": verdict[e.event_id].get("traced_account")}
            for e in evs if e.kind == "message_receive" and e.actor_id == bank_node
            and e.detail.get("h_kind") == "Deposit"]


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
    reacts = {f"alice@{s}": h6_react(wallet, coin, s, merchants[s].node_id) for s in sites}
    # Alice spends the SAME coin at both offline merchants at t=0
    run = _play(network, [bank, *(h6_merchant_actor(m, bank.node_id) for m in merchants.values())],
                [new_msg("PresentCoin", f"alice@{s}", f"m@{s}", "s", coin=str(coin["C"]), n_terms=k // 2)
                 for s in sites], token_id=f"cfn-coin-u{u}", reacts=reacts)
    res = _by_site(run)
    ds = {s: d for s, (d, _) in res.items()}
    return ScenarioResult(h6_ecash.PROTOCOL_ID, f"cfn88_sec1_k{k}", network.network_id, len(network.sites),
                          "RSA (toy 512-bit) blind signature + cut-and-choose; bank honest for crediting; "
                          "detection-only double-spend deterrence (identity revealed ex post)",
                          "coin withdrawn in advance (k blinded candidates, k/2 opened)",
                          "late_choice_any_site",
                          "payer untraceable if coin spent once (heuristic here: SHA-256 g is not bijective)",
                          {s: t for s, (_, t) in res.items()}, None, _extra_accepts(ds), ds,
                          wire_bytes(run.result, {f"alice@{sites[-1]}", f"m@{sites[-1]}"}), 0,
                          extra={"deposits": h6_deposits(run, bank.node_id), "true_account": u,
                                 "undetected_double_spend_prob_if_independent_challenges": 2.0 ** (-(k // 2)),
                                 "detection_is_not_prevention": True, "source": h6_ecash.SOURCE})
