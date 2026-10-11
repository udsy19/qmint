import pytest

from qmint.classical import scenarios as S
from qmint.classical.h2_quorum import home_shard
from qmint.networks.causality import link_lower_bound_ns


def test_home_shard_deterministic_and_spread():
    shards = {home_shard(f"t{i}", 4) for i in range(100)}
    assert shards == {0, 1, 2, 3}
    assert home_shard("x", 4) == home_shard("x", 4)


def test_routes_to_home_shard_not_global_wait(net3):
    r = S.run_h2(net3, f=1)
    assert r.double_spends_successful == 0
    lat = r.local_accept_ns
    home = lat["A|home_leader@A"]
    remote = lat["B|home_leader@A"]
    # co-located leader: only leader->nearest follower RTT (A<->H), not a wait on every site
    expected_home = 2 * S.SITE_PROC_NS + 3 * S.COORD_PROC_NS + 2 * link_lower_bound_ns(net3, "A", "H")
    assert home == pytest.approx(expected_home)
    assert remote == pytest.approx(home + 2 * link_lower_bound_ns(net3, "B", "A"))
    assert home < 2 * link_lower_bound_ns(net3, "A", "B")  # does not wait for the far site


def test_f_faults_tolerated_f_plus_one_unavailable(net3):
    r = S.run_h2(net3, f=1)
    assert r.extra["fault_tests"] == {"crashed_1": "ACCEPT", "crashed_2": "REJECT_UNAVAILABLE"}
