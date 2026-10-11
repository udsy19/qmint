"""Lane B / B2: Kent et al. 2022 two-site token schemes (Tables 1-3 of P03)."""

import copy
import itertools
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
import pytest
from scipy.stats import binom, binomtest

from qmint.core.contracts import ProtocolSpec, SecretBoundaryError, TransactionTrace
from qmint.core.serialization import canonical_json
from qmint.protocols import kent_smoney_2022 as K
from qmint.protocols.common import CausalityError
from qmint.protocols.register import bb84_projector, projector_from_angle

IDEAL = [K.KentScheme.IQT1, K.KentScheme.IQT2]
REAL = [K.KentScheme.QT1, K.KentScheme.QT2]


def params(scheme, N, gdet=0.3, gerr=0.1):
    if K.KentScheme(scheme).ideal:
        return K.KentParams(scheme, N)
    return K.KentParams(scheme, N, gamma_det=gdet, gamma_err=gerr)


def honest(scheme, N, b, seed, **kw):
    s = K.KentSMoneySession(params(scheme, N, **kw.pop("p", {})), seed=seed)
    alice = K.HonestAlice(s, seed=seed + 1, **kw)
    ok = alice.run(b, K.monotone_times())
    return s, alice, ok


# -------------------------------------------------------------- spec / params
def test_ideal_spec_matches_frozen_fixture():
    fx = json.loads(
        (Path(__file__).resolve().parents[2] / "fixtures/contracts/protocol_smoney_ideal.json").read_text()
    )
    assert K.KENT_IDEAL_SPEC == ProtocolSpec(**fx)
    assert K.KENT_REALISTIC_SPEC.adversary_game_id.value == "S2"


def test_params_validation():
    with pytest.raises(ValueError):
        K.KentParams(K.KentScheme.IQT1, 4, gamma_det=0.5)
    with pytest.raises(ValueError):
        K.KentParams(K.KentScheme.QT1, 4, gamma_det=0.5)
    assert K.KentParams(K.KentScheme.QT2, 4, 0.5, 0.1).protocol_id == "s_money_kent_2022_realistic"
    assert K.KentParams(K.KentScheme.IQT2, 4).protocol_id == "s_money_kent_2022_ideal_2site"


# ------------------------------------------------------- honest correctness
@pytest.mark.parametrize("scheme", IDEAL + REAL)
@pytest.mark.parametrize("b", [0, 1])
def test_honest_accepted_at_chosen_site(scheme, b):
    for seed in range(10):
        s, _, ok = honest(scheme, 64, b, seed * 7)
        assert ok and s.outcomes[b].accepted and s.outcomes[b].errors == 0
        assert not s.double_presentation_accepted()


@pytest.mark.parametrize("scheme", IDEAL)
def test_honest_token_rejected_at_other_site(scheme):
    rejected = 0
    for seed in range(30):
        s, alice, _ = honest(scheme, 32, 0, seed)
        rejected += not s.present(1, alice.x, 1e9)
    assert rejected == 30  # accept prob 2^-|Delta_1|, mean (3/4)^32 ~ 1e-4


@pytest.mark.parametrize("scheme", IDEAL)
def test_other_site_acceptance_rate_is_three_quarters_power(scheme):
    N, trials, acc = 3, 3000, 0
    for seed in range(trials):
        s, alice, _ = honest(scheme, N, 1, 10_000 + seed)
        acc += s.present(0, alice.x, 1e9)
    ci = binomtest(acc, trials).proportion_ci(confidence_level=0.999, method="exact")
    assert ci.low <= 0.75**N <= ci.high


# ----------------------------------------------------- event ordering / trace
@pytest.mark.parametrize("scheme", IDEAL + REAL)
def test_trace_is_valid_dag_with_published_order(scheme):
    s, _, ok = honest(scheme, 16, 1, 3)
    tr = s.trace("tr-1", "net-synthetic-2site-10km")
    assert isinstance(tr, TransactionTrace) and ok and not tr.double_spend_accepted
    kinds = [e.kind for e in tr.events]
    first = {k: kinds.index(k) for k in set(kinds)}
    assert first["issue"] < first["quantum_exchange"] < first["measurement"]
    assert first["branch_choice"] < first["commitment"] < first["privacy_reveal"]
    assert (
        first["privacy_reveal"]
        < first["local_validation_start"]
        < first["verification_result_available_local"]
    )
    # B_1 computed d~_1 before validating at Q_1, from local data only
    b1 = [e for e in tr.events if e.detail.get("role") == "B1"]
    acts = [e.detail.get("action") for e in b1]
    assert acts.index("compute dtilde") < [e.kind for e in b1].index("local_validation_start")
    assert all(e.site_id == "Q1" for e in b1)
    canonical_json(tr)  # serializable, contains no IssuerSecret


def test_arrival_before_send_is_rejected():
    s = K.KentSMoneySession(params(K.KentScheme.IQT1, 4), seed=1)
    a = K.HonestAlice(s, seed=2)
    with pytest.raises(CausalityError):
        a.run(0, K.monotone_times(), arrivals={"bank_distribute": {"B0": -5.0, "B1": -5.0}})


def test_caller_supplied_arrivals_recorded():
    s = K.KentSMoneySession(params(K.KentScheme.IQT1, 4), seed=1)
    t = K.monotone_times(step_ns=10_000)
    arrive = {
        "x_to_agents": {"A0": t["x_to_agents"] + 33356.4, "A1": t["x_to_agents"] + 33356.4},
        "bank_distribute": {"B0": t["bank_distribute"] + 5, "B1": t["bank_distribute"] + 5},
        "bank_forward_c": {"B0": t["bank_forward_c"] + 7, "B1": t["bank_forward_c"] + 7},
    }
    K.HonestAlice(s, seed=2).run(0, t, arrivals=arrive)
    rx = [e for e in s.events if e.kind == "message_receive" and e.detail["role"] == "A1"]
    assert rx and rx[0].time_ns == pytest.approx(t["x_to_agents"] + 33356.4)


def test_step_order_enforced():
    s = K.KentSMoneySession(params(K.KentScheme.IQT1, 4), seed=1)
    with pytest.raises(K.ProtocolOrderError):
        s.alice_send_d([0, 0, 0, 0], 0.0)  # before quantum stage
    s.bank_send_quantum(0.0)
    with pytest.raises(K.ProtocolOrderError):
        s.present(0, [0, 0, 0, 0], 1.0)  # before d~_0 exists
    with pytest.raises(K.ProtocolOrderError):
        s.alice_report_detections([0, 1], 1.0)  # ideal scheme has no loss reporting
    s.alice_send_d([0, 1, 0, 1], 1.0)
    with pytest.raises(K.ProtocolOrderError):
        s.alice_send_d([0, 1, 0, 1], 2.0)
    s2 = K.KentSMoneySession(params(K.KentScheme.IQT2, 4), seed=1)
    s2.bank_send_quantum(0.0)
    with pytest.raises(K.ProtocolOrderError):
        s2.alice_send_d([0, 0, 0, 0], 1.0)  # IQT2 discards steps 4-5


# ------------------------------------------------------------------ privacy
def _bob_view_distribution(scheme, N, b, p_z1=0.5, detected=None):
    """Exact law of Bob's pre-reveal view, enumerating Alice's random choices (y, z)."""
    dist = Counter()
    ys = list(itertools.product((0, 1), repeat=N)) if K.KentScheme(scheme).per_qubit_basis else [None]
    for y in ys:
        for z in (0, 1):
            s = K.KentSMoneySession(params(scheme, N, gdet=0.3), seed=5)
            K.HonestAlice(s, seed=6, y=y, z=z, detected=detected).run(b, K.monotone_times())
            w = (p_z1 if z else 1 - p_z1) / len(ys)
            dist[s.bob_view_before_reveal()] += w
    return dist


@pytest.mark.parametrize(
    "scheme,detected", [("IQT1", None), ("IQT2", None), ("QT1", [0, 2]), ("QT2", [1, 2])]
)
def test_bob_view_before_reveal_independent_of_choice(scheme, detected):
    d0 = _bob_view_distribution(scheme, 3, 0, detected=detected)
    d1 = _bob_view_distribution(scheme, 3, 1, detected=detected)
    assert d0.keys() == d1.keys()
    assert all(math.isclose(d0[k], d1[k]) for k in d0)
    items = {item for view in d0 for (_, item, _) in view}
    assert "x" not in items and "c" in items


@pytest.mark.parametrize("p_z1", [0.5, 0.6, 0.75])
def test_biased_z_gives_bob_exactly_beta_e_advantage(p_z1):
    """Optimal pre-reveal guess of b from Bob's view succeeds w.p. 1/2 + beta_E (cf. P03 Lemma 4)."""
    joint = {b: _bob_view_distribution("IQT1", 2, b, p_z1=p_z1) for b in (0, 1)}
    views = set(joint[0]) | set(joint[1])
    p_guess = sum(max(0.5 * joint[0][v], 0.5 * joint[1][v]) for v in views)
    assert p_guess == pytest.approx(0.5 + abs(p_z1 - 0.5), abs=1e-12)


def test_secrets_stay_on_bobs_side():
    s, alice, _ = honest(K.KentScheme.IQT1, 8, 0, 4)
    with pytest.raises(SecretBoundaryError):
        copy.deepcopy(s)
    view_items = {item for (_, item, _) in s.bob_view_before_reveal()}
    assert view_items == {"d", "c"}
    # the trace records message names and timing only, never string values (t, u, x, d)
    tr = s.trace("t", "n")
    assert all(not isinstance(v, (list, tuple)) for e in tr.events for v in e.detail.values())
    assert set(alice.__dict__) >= {"x"} and not hasattr(alice, "_secret")


def test_alice_facing_session_holds_no_bob_state():
    """M-B2: Bob's IssuerSecret / t,u live in the Bob-side vault, not in the session's attributes."""
    from qmint.core.contracts import IssuerSecret
    from qmint.protocols.common import CapabilityBoundaryError

    s, _, _ = honest(K.KentScheme.IQT1, 8, 0, 4)

    def walk(o, seen):
        if id(o) in seen:
            return
        seen.add(id(o))
        yield o
        if isinstance(o, dict):
            for v in [*o.keys(), *o.values()]:
                yield from walk(v, seen)
        elif isinstance(o, (list, tuple, set)):
            for v in o:
                yield from walk(v, seen)
        elif hasattr(o, "__dict__"):
            for v in vars(o).values():
                yield from walk(v, seen)

    objs = list(walk(s, set()))
    assert not any(isinstance(o, (IssuerSecret, K._BobSide, np.random.Generator)) for o in objs)
    t = s._bank().secret.bits
    assert not any(isinstance(o, tuple) and list(o) == list(t) and len(t) > 1 for o in objs[1:] if o is not s)
    twin = object.__new__(K.KentSMoneySession)
    twin.__dict__.update(vars(s))
    with pytest.raises(CapabilityBoundaryError):
        twin.present(1, (0,) * 8, 1e9)


def _present_both(network=None, enforce=False, t1=0.0):
    s = K.KentSMoneySession(params(K.KentScheme.IQT2, 4), seed=5, network=network, enforce_spacelike=enforce)
    s.bank_send_quantum(-5000.0)
    s.bank_distribute(-4000.0)
    s.alice_send_c(0, -3000.0)
    s.bank_forward_c(-2000.0)
    s.present(0, (0,) * 4, 0.0)
    s.present(1, (0,) * 4, t1)
    return s


def _net(dist_m):
    from qmint.core.contracts import Site, SpacetimeNetwork, TopologySource

    sites = [Site(site_id=q, frame="test", x_m=x, y_m=0.0, trust_domain="bob", clock_error_bound_ns=1.0)
             for q, x in (("P", 0.0), ("Q0", -dist_m / 2), ("Q1", dist_m / 2))]
    return SpacetimeNetwork(network_id="m-b4", topology_source=TopologySource.SYNTHETIC, sites=sites)


def test_s1_status_declares_spacelike_precondition():
    """M-B4: without declared geometry, or with timelike presentations, S1 does not apply."""
    s = K.KentSMoneySession(params(K.KentScheme.IQT2, 4), seed=5)
    assert s.s1_presentation_status() == "INCOMPLETE"
    assert _present_both().s1_presentation_status() == "OUT_OF_MODEL"  # no network declared
    assert _present_both(_net(300.0), t1=10.0).s1_presentation_status() == "IN_MODEL"  # lc ~ 1000.7 ns
    assert _present_both(_net(300.0), t1=5000.0).s1_presentation_status() == "OUT_OF_MODEL"
    assert _present_both(_net(300.0), t1=999.5).s1_presentation_status() == "OUT_OF_MODEL"  # clock error


def test_enforce_spacelike_refuses_second_presentation_before_validation():
    with pytest.raises(K.SpacelikeViolation):
        _present_both(_net(300.0), enforce=True, t1=5000.0)
    s = _present_both(_net(300.0), enforce=True, t1=10.0)
    assert set(s.outcomes) == {0, 1}
    with pytest.raises(ValueError):
        K.KentSMoneySession(params(K.KentScheme.IQT2, 4), seed=5, enforce_spacelike=True)
    with pytest.raises(ValueError):
        K.KentSMoneySession(params(K.KentScheme.IQT2, 4), seed=5, network=_net(1.0), sites={"B1": "Q9"})


# ----------------------------------------------------- realistic acceptance rules
def _exact_qt_honest_acceptance(N, p_det, E, gdet, gerr):
    """Pr[no abort and accept] for the simulated honest channel: n~Bin(N,p_det),
    |Delta_b| ~ Bin(n,1/2), errors ~ Bin(|Delta_b|, E), rule errors <= |Delta_b| gamma_err."""
    total = 0.0
    for n in range(N + 1):
        if n < gdet * N:
            continue
        inner = sum(
            binom.pmf(m, n, 0.5) * binom.cdf(math.floor(m * gerr + 1e-12), m, E) for m in range(n + 1)
        )
        total += binom.pmf(n, N, p_det) * inner
    return total


@pytest.mark.parametrize("scheme", REAL)
def test_realistic_honest_acceptance_matches_exact_mixture(scheme):
    N, p_det, E, gdet, gerr, trials = 40, 0.6, 0.08, 0.5, 0.1, 1500
    acc = 0
    for seed in range(trials):
        _, _, ok = honest(
            scheme,
            N,
            seed % 2,
            20_000 + seed,
            channel=K.HonestChannel(p_det, E),
            p={"gdet": gdet, "gerr": gerr},
        )
        acc += bool(ok)
    exact = _exact_qt_honest_acceptance(N, p_det, E, gdet, gerr)
    ci = binomtest(acc, trials).proportion_ci(confidence_level=0.999, method="exact")
    assert 0.05 < exact < 0.95
    assert ci.low <= exact <= ci.high


def test_realistic_abort_when_too_few_detections():
    s, _, ok = honest(K.KentScheme.QT1, 50, 0, 1, channel=K.HonestChannel(p_det=0.1), p={"gdet": 0.5})
    assert not ok and s.aborted
    assert any(e.kind == "reject" and "abort" in e.detail.get("reason", "") for e in s.events)
    with pytest.raises(K.ProtocolOrderError):
        s.alice_send_c(0, 1e9)


def test_realistic_threshold_boundary_is_inclusive():
    """Table 2 step 12 uses <=: exactly floor(|Delta| gamma_err) errors still accepted."""
    N, gerr = 20, 0.1
    s = K.KentSMoneySession(params(K.KentScheme.QT2, N, gdet=0.5, gerr=gerr), seed=3)
    h = s.bank_send_quantum(0.0)
    z = 0
    x = [h.measure(k, bb84_projector("Z" if z == 0 else "X", 0), np.random.default_rng(k)) for k in range(N)]
    s.alice_report_detections(list(range(N)), 1.0)
    s.bank_distribute(2.0)
    s.alice_send_c(0 ^ z, 3.0)  # b = 0
    s.bank_forward_c(4.0)
    sec = s._bank().secret.reveal_for_testing_only()
    delta = [k for k in range(N) if sec["extra"]["u"][k] == z]
    allowed = math.floor(len(delta) * gerr)
    x_bad = list(x)
    for k in delta[:allowed]:
        x_bad[k] ^= 1
    assert s.present(0, x_bad, 5.0)
    s2 = K.KentSMoneySession(params(K.KentScheme.QT2, N, gdet=0.5, gerr=gerr), seed=3)
    h2 = s2.bank_send_quantum(0.0)
    x2 = [h2.measure(k, bb84_projector("Z", 0), np.random.default_rng(k)) for k in range(N)]
    s2.alice_report_detections(list(range(N)), 1.0)
    s2.bank_distribute(2.0)
    s2.alice_send_c(0, 3.0)
    s2.bank_forward_c(4.0)
    for k in delta[: allowed + 1]:
        x2[k] ^= 1
    assert not s2.present(0, x2, 5.0)


# ------------------------------------- S1 dual presentation (simple strategies only)
def _dual_presentation(scheme, N, seed, strategy):
    """Dishonest Alice (IQT1) tries to be accepted at BOTH Q0 and Q1. Bob is honest."""
    s = K.KentSMoneySession(params(scheme, N), seed=seed)
    rng = np.random.default_rng(seed + 99)
    h = s.bank_send_quantum(0.0)
    if strategy == "random_basis_guess":
        y = rng.integers(0, 2, size=N)
        x = [h.measure(k, bb84_projector("Z" if y[k] == 0 else "X", 0), rng) for k in range(N)]
        d, c = list(y), 0  # d~_0 = y (Q0 checks u=y, correct); d~_1 = ~y (Q1 checks u!=y)
        x0, x1 = x, [int(v) for v in rng.integers(0, 2, size=N)]
    elif strategy == "breidbart":
        x = [h.measure(k, projector_from_angle(math.pi / 8), rng) for k in range(N)]
        d, c = [0] * N, 0
        x0 = x1 = x  # outcome guesses the bit in either basis w.p. cos^2(pi/8)
    s.alice_send_d(d, 1.0)
    s.bank_distribute(2.0)
    s.alice_send_c(c, 3.0)
    s.bank_forward_c(4.0)
    s.present(0, x0, 5.0)
    s.present(1, x1, 5.0)  # same time, spacelike-separated sites: no cross-check
    return s.double_presentation_accepted()


@pytest.mark.parametrize(
    "strategy,per_qubit",
    [("random_basis_guess", 0.75), ("breidbart", 0.5 + 1 / (2 * math.sqrt(2)))],
)
def test_s1_dual_presentation_monte_carlo(strategy, per_qubit):
    """MONTE_CARLO lower-bound evidence for two simple strategies (not a bound; lane D owns S1)."""
    N, trials = 3, 4000
    wins = sum(_dual_presentation("IQT1", N, 50_000 + t, strategy) for t in range(trials))
    ci = binomtest(wins, trials).proportion_ci(confidence_level=0.999, method="exact")
    assert ci.low <= per_qubit**N <= ci.high


def test_honest_presentations_never_double_accept_with_large_n():
    assert not any(_dual_presentation("IQT1", 48, t, "random_basis_guess") for t in range(20))


# ------------------------------------------------------------------- mutation
def test_mutation_wrong_measurement_mapping_caught(monkeypatch):
    assert honest(K.KentScheme.IQT1, 32, 0, 1)[2]

    def swapped(basis, bit):  # mutant: Alice's X measurement uses (X,0)=|->
        return bb84_projector(basis, bit if str(getattr(basis, "value", basis)) == "Z" else 1 - bit)

    monkeypatch.setattr(K, "bb84_projector", swapped)
    assert not any(honest(K.KentScheme.IQT1, 32, 0, s)[2] for s in range(5))
