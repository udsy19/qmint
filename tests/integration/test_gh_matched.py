"""Matched-topology runs: S-money (G) and H0-H6 (H) on one engine, same network, same choreography."""

from __future__ import annotations

import csv
import json

import pytest

from qmint.classical import matched_topology as M
from qmint.core.contracts import BenchmarkRecord, EvidenceKind
from qmint.core.serialization import canonical_json
from qmint.networks.causality import assert_causal, propagation_violations, retrocausal_violations


@pytest.fixture(scope="module")
def cases():
    return M.matched_cases()


def test_s_money_models_kent_table1_stage_ii_relay(cases):
    """Kent et al. 2022 Table I steps 7-9: A sends c = b XOR z to B, B sends c to every B_i, and B_i uses it
    in the causal past of Q_i. G's scenario must relay c B0 -> B1 and B_b's accept must descend from it."""
    case = cases["paper_jinan_2.766km_fibre"]
    run = M.run_matched(case, M.S1, 1, "jiang_dTproc_1507ns")
    evs = {e.event_id: e for e in run.trace.events}
    relay = [e for e in run.trace.events if e.kind == "message_receive" and e.site_id == "L1"
             and e.detail.get("type") == "commitment"]
    assert len(relay) == 1 and evs[evs[relay[0].causal_parent_ids[0]].event_id].site_id == "L0"
    acc = run.result.first("verification_result_available_local", site_id="L1", accepted=True)
    from qmint.networks.causality import ancestors_of

    assert relay[0].event_id in ancestors_of(acc.event_id, run.trace.events)
    fiber = case.link_runtime[("L0", "L1")].latency.delay_ns
    assert run.metrics["pre_presentation_commit_ns"] == pytest.approx(fiber)  # 13.83 us
    assert run.metrics["choice_to_local_accept_ns"] == pytest.approx(15_337.0)  # Jiang: 15.34 +/- 0.01 us
    assert run.metrics["sync_cross_site_msgs_after_presentation"] == 0


@pytest.mark.parametrize("case_id", ["paper_jinan_2.766km_fibre", "paper_yiyuan_mazhan_60.54km_fibre",
                                     "synthetic_1000km"])
def test_matched_latency_structure(cases, case_id):
    case = cases[case_id]
    one_way = case.link_runtime[("L0", "L1")].latency.delay_ns if case_id.startswith("synthetic") else \
        case.link_runtime[case.site_ids[:2]].latency.delay_ns
    get = {lab: M.run_matched(case, lab, 1, "zero_processing").metrics for lab in M.PROTOCOLS}
    s1 = get[M.S1]["choice_to_local_accept_ns"]
    assert s1 == pytest.approx(one_way)
    # no S-money latency edge over the late-commit classical mirror (same Stage-II relay pattern) ...
    for lab in ("H0", "H3_preassigned", "H3_late_commit_disclosed", "H3_late_commit_ot_private", "H4+H3", "H5",
                "H6"):
        assert get[lab]["choice_to_local_accept_ns"] == pytest.approx(s1), lab
    for lab in ("H3_late_commit_disclosed", "H3_late_commit_ot_private"):
        assert get[lab]["pre_presentation_commit_ns"] == pytest.approx(get[M.S1]["pre_presentation_commit_ns"])
    # ... but a 2L/c_fibre edge over every online-ledger design whose ledger is not at L_b
    for lab in ("H1", "H2", "H4+H1"):
        assert get[lab]["choice_to_local_accept_ns"] == pytest.approx(s1 + 2 * one_way), lab
        assert get[lab]["sync_cross_site_msgs_after_presentation"] == 2
    # issuer awareness / settlement: S-money's B_b must still report to L0, so no edge there
    for lab in M.PROTOCOLS:
        assert get[lab]["settlement_ns"] == pytest.approx(2 * one_way), lab


def test_double_spend_outcomes_on_matched_topology(cases):
    case = cases["synthetic_100km"]
    acc = {lab: M.run_matched(case, lab, 1, "jiang_dTproc_1507ns", adversarial=True).metrics["accepted_sites"]
           for lab in M.PROTOCOLS if lab != M.S1}
    assert acc == {"H0": 2, "H1": 1, "H2": 1, "H3_preassigned": 1, "H3_late_commit_disclosed": 1,
                   "H3_late_commit_ot_private": 1, "H4+H1": 1, "H4+H3": 1, "H5": 1, "H6": 2}
    with pytest.raises(ValueError):
        M.run_matched(case, M.S1, 1, "zero_processing", adversarial=True)


def test_every_trace_is_causal(cases):
    """Causality check (no FTL, no retrocausal edge) over every protocol, case, branch, processing model."""
    n = 0
    for case_id, case in cases.items():
        for lab in M.PROTOCOLS:
            for b in (0, 1):
                for adv in ((False,) if lab == M.S1 else (False, True)):
                    run = M.run_matched(case, lab, b, "jiang_dTproc_1507ns", seed=3, case_id=case_id,
                                        adversarial=adv)
                    assert retrocausal_violations(run.trace) == []
                    assert propagation_violations(run.trace, case.network) == []
                    assert_causal(run.trace, case.network)
                    n += 1
    assert n == 6 * (1 * 2 + 10 * 2 * 2)


def test_seeded_runs_are_deterministic(cases):
    case = cases["ripe_helsinki_tampere"]
    for lab in (M.S1, "H1", "H3_late_commit_ot_private"):
        a = M.run_matched(case, lab, 1, "jiang_dTproc_1507ns", seed=7)
        b = M.run_matched(case, lab, 1, "jiang_dTproc_1507ns", seed=7)
        c = M.run_matched(case, lab, 1, "jiang_dTproc_1507ns", seed=8)
        ev = lambda r: canonical_json([e.model_dump() for e in r.trace.events])  # noqa: E731
        assert ev(a) == ev(b)
        assert ev(a) != ev(c)  # RIPE latency resampled per seed
    assert a.trace.latency_evidence == EvidenceKind.MEASURED_LATENCY  # link input; the run itself is a model


def test_reports_written_and_valid(tmp_path):
    rows, runs = M.sweep(seeds_ripe=2, case_ids=("paper_jinan_2.766km_fibre",))
    p = M.write_csv(rows, tmp_path / "m.csv")
    with open(p, newline="") as fh:
        got = list(csv.DictReader(fh))
    assert len(got) == len(M.PROTOCOLS) * 2 * 2
    assert {r["evidence_kind"] for r in got} == {"MODELLED_LATENCY"}
    zero = {(r["case_id"], r["protocol"]): r for r in rows if r["proc_model"] == "zero_processing" and r["b"] == 1}
    for r in rows:
        if r["b"] == 1:
            rec = M.to_record(r, zero[(r["case_id"], r["protocol"])], "sha", "lock")
            BenchmarkRecord.model_validate(rec.model_dump())
            assert rec.evidence_kind == EvidenceKind.MODELLED_LATENCY
    h1 = next(r for r in rows if r["protocol"] == "H1" and r["b"] == 1 and r["proc_model"] == "zero_processing")
    assert h1["s_money_minus_protocol_choice_to_accept_ns"] == pytest.approx(-27_660.0)


def test_figure6_data_has_three_panels_with_evidence_labels():
    _, runs = M.sweep(seeds_ripe=1)
    fig = M.figure6(runs)
    json.dumps(fig)
    assert fig["evidence_kind"] == "MODELLED_LATENCY"
    for case_id, c in fig["cases"].items():
        assert set(c["panels"]) == {"S1", "H1_race", "H3_late_commit", "H3_late_commit_ot"}
        race = c["panels"]["H1_race"]
        decisions = sorted(e["decision"] for e in race["events"] if e["kind"] == "verification_result_available_local")
        assert decisions == ["ACCEPT", "REJECT_DOUBLE_SPEND"], case_id
        for p in c["panels"].values():
            for e in p["message_edges"]:
                if e["from_site"] != e["to_site"]:
                    assert e["t_recv_ns"] - e["t_send_ns"] >= c["lightcone_ns"] - 1e-6
