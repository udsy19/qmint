"""X11 comparability matrix: each classical H-construction vs S-money S1 (master plan section 8).

Qualitative only. Every cell reads ``H: <left> || S1: <right>``. Status is ``QUALIFIED``
when the pair can be compared after the listed concessions are priced, ``INCOMPARABLE``
when a fundamental prerequisite differs (security goal not met, detection vs prevention,
trusted tamper-resistant hardware). No pair is plain ``COMPARABLE``: every classical
construction differs from S1 in at least the adversary model (computational or trust-based
vs information-theoretic in the ideal model).

S1 anchors: Kent, Lowndes, Pitalua-Garcia, Rarity, "Practical quantum tokens without quantum
memories and experimental tests", arXiv:2104.11717v4 (npj Quantum Inf. 2022): Table I (IQT1/IQT2,
steps 1-11), Lemma 1 eq. (1) eps_unf = (1/2 + 1/(2 sqrt 2))^N, definitions on p.3-4.
"""

from __future__ import annotations

import csv
from pathlib import Path

COLUMNS = [
    "pair_id", "left_protocol", "right_protocol", "adversary_power", "quantum_capability", "issuer_trust",
    "agent_trust", "trusted_hardware", "pre_shared_key_bits", "preassignment_of_site", "spender_privacy",
    "site_count", "spacelike_separation", "finality_semantics", "availability_assumptions", "proof_certainty",
    "security_target", "local_verification_metric", "issuance_included", "comparability_status",
]
RIGHT = "s_money_kent_2022_ideal_2site"

S1 = {
    "adversary_power": "unbounded dishonest Alice (information-theoretic), ideal lossless/noiseless model",
    "quantum_capability": "Bob prepares BB84 qubits, Alice measures on receipt (no quantum memory)",
    "issuer_trust": "Bob honest for eps_unf; privacy defined against Bob guessing b before presentation",
    "agent_trust": "trusted agents B,B0,B1 and A,A0,A1 controlling secure laboratories",
    "trusted_hardware": "secure laboratories of trusted agents; no tamper-resistant user device",
    "pre_shared_key_bits": "secure authenticated same-party channels from previously distributed keys "
                           "(budget not given in Lemma 1)",
    "preassignment_of_site": "none: b chosen in Stage II, but c=b XOR z must reach B_i in causal past of Q_i "
                             "(Table I steps 7-9)",
    "spender_privacy": "eps_priv-private: Bob's guess of b before presentation <= 1/2^M + eps_priv",
    "site_count": "2 (2^M via Appendix H, not used here)",
    "spacelike_separation": "Q0,Q1 may be spacelike separated; validation without cross-checking",
    "finality_semantics": "local validation at Q_b; settlement/irrevocability not specified",
    "availability_assumptions": "Stage-II bit c relayed to both sites before presentation; ideal: no loss",
    "proof_certainty": "PUBLISHED_THEOREM Lemma 1 eq.(1) (ideal model only)",
    "security_target": "eps_unf=(1/2+1/(2*sqrt2))^N",
    "local_verification_metric": "near-instant local check at Q_b; no paper latency number used",
    "issuance_included": "Stage I quantum exchange + t,u distribution, arbitrarily early",
}

_COMMON_CLASSICAL = {"quantum_capability": "none", "site_count": "2"}

H = {
    "X11-H0": ("classical_h0_bearer[negative_control]", "INCOMPARABLE", {
        "adversary_power": "any copier (no assumption needed to double spend)",
        "issuer_trust": "irrelevant: double spend succeeds anyway",
        "agent_trust": "honest site verifiers", "trusted_hardware": "none", "pre_shared_key_bits": "0",
        "preassignment_of_site": "none (late choice)", "spender_privacy": "none (serial linkable)",
        "spacelike_separation": "both sites accept spacelike-separated copies",
        "finality_semantics": "local accept; no conflict resolution",
        "availability_assumptions": "offline; always available",
        "proof_certainty": "negative control: double spend observed in model (1 extra accept)",
        "security_target": "none met (C1 double spend succeeds)",
        "local_verification_metric": "MODELLED local processing only",
        "issuance_included": "serial list push to every site"}),
    "X11-H1": ("classical_h1_online_ledger[coordinator]", "QUALIFIED", {
        "adversary_power": "double-spend prevention needs only honest coordinator + authenticated channels "
                           "(info-theoretic MACs possible with key budget; HMAC-SHA256 used here = computational)",
        "issuer_trust": "honest online coordinator (single point of trust/failure)",
        "agent_trust": "honest merchant terminals", "trusted_hardware": "none",
        "pre_shared_key_bits": "one MAC key per merchant (256 bit here)",
        "preassignment_of_site": "none (late choice, any site)",
        "spender_privacy": "none: coordinator learns token, merchant and site at spend time",
        "spacelike_separation": "conflicting spends serialised at coordinator; validation waits >= RTT to coordinator",
        "finality_semantics": "coordinator commit = authoritative spent state at decision time",
        "availability_assumptions": "coordinator reachable; partitioned site cannot accept (availability 0.5 "
                                    "in modelled scenario)",
        "proof_certainty": "linearizable CAS tested (threads + event race); no formal proof",
        "security_target": "0 double spends under declared faults absent (tested vs the replay and strong adversaries, lane-M fixes M-H1/H2/H3 applied)",
        "local_verification_metric": "MODELLED: local proc + coordinator RTT lower bound",
        "issuance_included": "issued-set at coordinator only"}),
    "X11-H2": ("classical_h2_quorum[sharded_quorum_f1]", "QUALIFIED", {
        "adversary_power": "crash faults <= f per shard; computational channel auth",
        "issuer_trust": "honest operator; crash-only replicas (Byzantine NOT modelled)",
        "agent_trust": "honest replicas/terminals", "trusted_hardware": "none",
        "pre_shared_key_bits": "MAC key per merchant + intra-cluster auth (not modelled)",
        "preassignment_of_site": "none for user; token has fixed home shard (latency depends on placement)",
        "spender_privacy": "none: home shard learns token, merchant and site",
        "spacelike_separation": "conflicts serialised by home-shard leader; validation >= RTT to leader + "
                                "leader-to-nearest-quorum RTT",
        "finality_semantics": "majority-replicated commit (survives f crashes)",
        "availability_assumptions": "home-shard majority reachable; f+1 crashes => unavailable (tested)",
        "proof_certainty": "quorum-intersection argument + tests; leader election NOT implemented",
        "security_target": "0 double spends with <= f crash faults (tested vs the replay and strong adversaries, lane-M fixes M-H1/H2/H3 applied)",
        "local_verification_metric": "MODELLED: depends on home-shard placement (co-located vs remote)",
        "issuance_included": "issued-set replicated in home shard"}),
    "X11-H3-preassigned": ("classical_h3_preallocated_escrow[preassigned]", "QUALIFIED", {
        "adversary_power": "prevention needs only honest site verifier + authenticated provisioning",
        "issuer_trust": "honest issuer", "agent_trust": "honest site verifiers", "trusted_hardware": "none",
        "pre_shared_key_bits": "authenticated issuer->site provisioning channel",
        "preassignment_of_site": "YES: site fixed at issuance (lost late-choice flexibility)",
        "spender_privacy": "none: issuer learns spending site at issuance",
        "spacelike_separation": "no cross-site coordination needed; other site rejects",
        "finality_semantics": "local escrow accept", "availability_assumptions": "offline at assigned site only",
        "proof_certainty": "tested state machine; trivial argument (only one site holds the escrow)",
        "security_target": "0 double spends (tested vs the replay and strong adversaries, lane-M fixes M-H1/H2/H3 applied)",
        "local_verification_metric": "MODELLED: local processing only",
        "issuance_included": "escrow provisioning to assigned site"}),
    "X11-H3-late-disclosed": ("classical_h3_preallocated_escrow[late_commit_disclosed]", "QUALIFIED", {
        "adversary_power": "prevention needs honest issuer relay + authenticated channels",
        "issuer_trust": "honest issuer relays ONE commit per token (one-shot latch)", "agent_trust": "honest site verifiers",
        "trusted_hardware": "none", "pre_shared_key_bits": "authenticated user->issuer and issuer->site channels",
        "preassignment_of_site": "none: late commit, SAME causal requirement as S1's Stage-II bit c",
        "spender_privacy": "none: issuer learns b at commit (S1 hides b)",
        "spacelike_separation": "commit must reach both sites before presentation; presentation itself local",
        "finality_semantics": "local accept after activation",
        "availability_assumptions": "issuer reachable during Stage II (as S1's relay of c)",
        "proof_certainty": "tested state machine",
        "security_target": "0 double spends (tested vs the replay and strong adversaries, lane-M fixes M-H1/H2/H3 applied)",
        "local_verification_metric": "MODELLED: local processing; Stage-II commit latency reported separately",
        "issuance_included": "inactive provisioning at every site"}),
    "X11-H3-late-ot": ("classical_h3_preallocated_escrow[late_commit_ot_private]", "QUALIFIED", {
        "adversary_power": "COMPUTATIONAL: real 1-of-M OT needs hardness assumptions (or trusted setup); "
                           "modelled with an IDEAL OT functionality",
        "issuer_trust": "honest-but-curious issuer (sees only c)", "agent_trust": "honest site verifiers",
        "trusted_hardware": "none (ideal OT functionality is a model, NOT_IMPLEMENTED instantiation)",
        "pre_shared_key_bits": "authenticated channels; OT setup",
        "preassignment_of_site": "none: same Stage-II c=(b-z) mod M relay pattern as S1",
        "spender_privacy": "c independent of b under ideal OT (computational in any real instantiation)",
        "spacelike_separation": "same as S1: c must reach both sites before presentation; local validation",
        "finality_semantics": "local accept",
        "availability_assumptions": "issuer relay of c during Stage II (as S1)",
        "proof_certainty": "reduction to OT security (not formally proved here); tested state machine",
        "security_target": "forgery = guessing a 256-bit issuer-held CSPRNG-keyed secret given ideal OT; one-shot "
                           "Stage II; computational otherwise; 0 double spends (tested vs the replay and strong "
                           "adversaries, lane-M fixes M-H1/H2/H3 applied)",
        "local_verification_metric": "MODELLED: local hash check",
        "issuance_included": "per-site secret hashes provisioned at issuance + OT"}),
    "X11-H4": ("classical_h4_pqc_signed[mldsa_none]", "INCOMPARABLE", {
        "adversary_power": "ML-DSA EUF-CMA (computational, post-quantum) -- forgery hard, COPYING trivial",
        "issuer_trust": "honest issuer key", "agent_trust": "honest site verifiers", "trusted_hardware": "none",
        "pre_shared_key_bits": "0 (public key only)", "preassignment_of_site": "none",
        "spender_privacy": "none (serial linkable)",
        "spacelike_separation": "both sites accept the copied signed token",
        "finality_semantics": "local accept; no conflict resolution",
        "availability_assumptions": "offline", "proof_certainty": "FIPS 204 standard; double spend observed",
        "security_target": "C1 not met: signature alone does not stop double spend",
        "local_verification_metric": "MODELLED proc; pure-Python ML-DSA verify time reported separately",
        "issuance_included": "keygen + sign per token"}),
    "X11-H4+H1": ("classical_h4_pqc_signed[mldsa_h1_ledger]", "QUALIFIED", {
        "adversary_power": "ML-DSA EUF-CMA (computational) + honest coordinator",
        "issuer_trust": "honest issuer key + honest coordinator", "agent_trust": "honest terminals",
        "trusted_hardware": "none", "pre_shared_key_bits": "MAC key per merchant",
        "preassignment_of_site": "none (online any site)",
        "spender_privacy": "none: coordinator learns token, merchant, site",
        "spacelike_separation": "validation waits >= coordinator RTT",
        "finality_semantics": "coordinator commit", "availability_assumptions": "coordinator reachable",
        "proof_certainty": "tested", "security_target": "0 double spends (tested vs the replay and strong adversaries, lane-M fixes M-H1/H2/H3 applied)",
        "local_verification_metric": "MODELLED: local + coordinator RTT",
        "issuance_included": "keygen + sign; no per-token state at sites"}),
    "X11-H4+H3": ("classical_h4_pqc_signed[mldsa_h3_site_binding]", "QUALIFIED", {
        "adversary_power": "ML-DSA EUF-CMA (computational)",
        "issuer_trust": "honest issuer key", "agent_trust": "honest site verifiers (local spent set)",
        "trusted_hardware": "none", "pre_shared_key_bits": "0 (public key only)",
        "preassignment_of_site": "YES: site bound into signed token at issuance",
        "spender_privacy": "none: issuer learns site at issuance",
        "spacelike_separation": "no coordination; other site rejects",
        "finality_semantics": "local accept", "availability_assumptions": "offline at bound site",
        "proof_certainty": "tested; relies on ML-DSA unforgeability",
        "security_target": "0 double spends (tested vs the replay and strong adversaries, lane-M fixes M-H1/H2/H3 applied)",
        "local_verification_metric": "MODELLED local proc; ML-DSA verify measured separately",
        "issuance_included": "keygen + sign; no per-token provisioning needed"}),
    "X11-H5": ("classical_h5_secure_hardware[assumption_holds]", "INCOMPARABLE", {
        "adversary_power": "bounded by tamper-resistance assumption H5-TR (physical/engineering, untested)",
        "issuer_trust": "honest issuer registers device keys", "agent_trust": "user device SE trusted by bank",
        "trusted_hardware": "YES: tamper-resistant secure element in the payer's device",
        "pre_shared_key_bits": "device attestation key (HMAC stand-in)",
        "preassignment_of_site": "none (late choice, any site, offline)",
        "spender_privacy": "not modelled (device id + counter visible at clearing)",
        "spacelike_separation": "no coordination; SE refuses second spend",
        "finality_semantics": "local accept; ex-post clearing detects clones (OUT_OF_MODEL)",
        "availability_assumptions": "offline; always available",
        "proof_certainty": "trust model only; broken assumption => double spend (tested)",
        "security_target": "0 double spends IF H5-TR holds (tested vs the replay and strong adversaries)",
        "local_verification_metric": "MODELLED local challenge-response; no real device benchmarked",
        "issuance_included": "token loaded into SE; device provisioning"}),
    "X11-H6": ("classical_h6_anonymous_ecash[cfn88_sec1_k16]", "INCOMPARABLE", {
        "adversary_power": "RSA blind signatures (computational; toy 512-bit here) + cut-and-choose",
        "issuer_trust": "honest bank for crediting; payer privacy vs bank",
        "agent_trust": "offline merchants pick random challenges", "trusted_hardware": "none",
        "pre_shared_key_bits": "0 (bank public key)", "preassignment_of_site": "none (late choice, offline)",
        "spender_privacy": "untraceable if spent once (heuristic here: SHA-256 g not bijective)",
        "spacelike_separation": "both offline merchants ACCEPT; double spender identified only at deposit",
        "finality_semantics": "DETECTION ex post, not prevention",
        "availability_assumptions": "offline payment; bank needed for deposit",
        "proof_certainty": "CFN88 Sec.1 construction reproduced; detection prob 1-2^-(k/2) if challenges independent",
        "security_target": "C1 prevention NOT met; identification of double spender",
        "local_verification_metric": "MODELLED local verification",
        "issuance_included": "withdrawal with k blinded candidates"}),
}


def rows() -> list[dict[str, str]]:
    out = []
    for pair_id, (left, status, h) in H.items():
        h = {**_COMMON_CLASSICAL, **h}
        row = {"pair_id": pair_id, "left_protocol": left, "right_protocol": RIGHT, "comparability_status": status}
        for col in COLUMNS:
            if col not in row:
                row[col] = f"H: {h[col]} || S1: {S1[col]}"
        out.append(row)
    return out


def write_csv(path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows())
    return path
