import csv

import pytest

from qmint.classical import comparability, run_baselines
from qmint.core.contracts import PROTOCOL_GAMES, BenchmarkRecord, EvidenceKind, GameId

PLAN_COLUMNS = ("pair_id, left_protocol, right_protocol, adversary_power, quantum_capability, issuer_trust, "
                "agent_trust, trusted_hardware, pre_shared_key_bits, preassignment_of_site, spender_privacy, "
                "site_count, spacelike_separation, finality_semantics, availability_assumptions, proof_certainty, "
                "security_target, local_verification_metric, issuance_included, comparability_status").split(", ")


def test_all_classical_protocols_registered_for_c1_only():
    for pid in ("classical_h0_bearer", "classical_h1_online_ledger", "classical_h2_quorum",
                "classical_h3_preallocated_escrow", "classical_h4_pqc_signed", "classical_h5_secure_hardware",
                "classical_h6_anonymous_ecash"):
        assert PROTOCOL_GAMES[pid] == frozenset({GameId.C1})


@pytest.fixture(scope="module")
def records():
    nets = {n.network_id: n for n in run_baselines.NETWORKS.values()}
    return [run_baselines.to_record(r, nets[r.network_id], "test-sha", "test-lock")
            for r in run_baselines.scenario_results()]


def test_every_record_valid_modelled_latency_and_classical(records):
    assert len(records) >= 20
    for rec in records:
        BenchmarkRecord.model_validate(rec.model_dump())
        assert rec.evidence_kind == EvidenceKind.MODELLED_LATENCY
        assert rec.classical_or_quantum == "classical"
        assert rec.security_target.epsilon_unf is None  # no epsilon claimed for C1
    assert len({r.record_id for r in records}) == len(records)


def test_double_spend_outcomes_per_protocol(records):
    by = {}
    for r in records:
        by.setdefault((r.protocol_id, r.configuration["variant"]), set()).add(r.double_spends_successful)
    assert by[("classical_h0_bearer", "negative_control")] == {1}
    assert by[("classical_h1_online_ledger", "coordinator")] == {0}
    assert by[("classical_h4_pqc_signed", "mldsa_none")] == {1}
    assert by[("classical_h4_pqc_signed", "mldsa_h1_ledger")] == {0}
    assert by[("classical_h5_secure_hardware", "assumption_violated_clone")] == {1}
    assert by[("classical_h6_anonymous_ecash", "cfn88_sec1_k16")] == {1}


def test_comparability_matrix_columns_and_statuses(tmp_path):
    p = comparability.write_csv(tmp_path / "m.csv")
    with open(p, newline="") as fh:
        rd = csv.DictReader(fh)
        assert rd.fieldnames == PLAN_COLUMNS
        rows = list(rd)
    assert {r["comparability_status"] for r in rows} <= {"QUALIFIED", "INCOMPARABLE"}
    st = {r["pair_id"]: r["comparability_status"] for r in rows}
    # fundamental prerequisite differences must never be plotted as a single "better" number
    for pid in ("X11-H0", "X11-H4", "X11-H5", "X11-H6"):
        assert st[pid] == "INCOMPARABLE"
    assert all(r["right_protocol"] == "s_money_kent_2022_ideal_2site" for r in rows)
    assert all(r["left_protocol"].split("[")[0] in PROTOCOL_GAMES for r in rows)
