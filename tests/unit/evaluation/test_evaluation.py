"""Lane N: figure/table harness. Captions carry valid manifests, stale inputs are rejected,
evidence styles are distinct, missing results render PENDING (never zero), tables match sources."""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
from pathlib import Path

import matplotlib.pyplot as plt
import pytest
import yaml

from qmint.core.contracts import EvidenceKind, TransactionTrace
from qmint.core.manifest import load_manifest, verify_manifest
from qmint.core.records import Provenance, RecordStore
from qmint.core.serialization import file_sha256
from qmint.evaluation import experiments as ex
from qmint.evaluation import make_figures as mf
from qmint.evaluation import plots, tables
from qmint.evaluation.statistics import binomial, zero_success_upper

ROOT = ex.ROOT
READY = {"fig02", "fig03", "fig04", "fig05", "fig10"}
PENDING = {"fig06", "fig07", "fig08", "fig09"}


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, dict]]:
    out = tmp_path_factory.mktemp("figures")
    caps = {s.fig_id: mf.build_figure(s, ROOT, out, "pytest") for s in ex.FIGURES}
    return out, caps


# --------------------------------------------------------------------------- manifests
def test_every_caption_has_a_valid_manifest(built):
    out, caps = built
    assert set(caps) == READY | PENDING
    for spec in ex.FIGURES:
        cap = caps[spec.fig_id]
        p = mf.paths(out, spec)
        m = load_manifest(p["manifest"])
        assert cap["manifest_id"] == m.manifest_id == f"figure-{spec.stem}"
        assert cap["manifest_sha256"] == file_sha256(p["manifest"])
        assert all(c.status == "OK" for c in verify_manifest(m, ROOT)), spec.fig_id
        pinned = {e.path_or_uri for e in m.entries if e.role in ("input", "script")}
        assert pinned == set(spec.inputs) | set(spec.scripts)
        assert {e.role for e in m.entries} >= {"output", "script", "environment"}
        assert [EvidenceKind(k) for k in cap["evidence_kinds"]]
        assert cap["caption"] and cap["status"] in {"READY", "PENDING", "BLOCKED"}
        assert mf.staleness(spec, ROOT, out) == ([] if spec.fig_id in READY else ["status PENDING: always re-evaluated"])


def test_committed_figures_are_fresh_and_valid():
    """The committed figures/ must match the committed evidence and code (regenerate if this fails)."""
    out = ROOT / "figures"
    for spec in ex.FIGURES:
        if spec.fig_id in READY:
            cap = mf.require_fresh(spec, ROOT, out)
            assert cap["status"] == "READY"
        else:
            cap = json.loads(mf.paths(out, spec)["caption"].read_text())
            assert cap["status"] == "PENDING"


# --------------------------------------------------------------------------- stale-cache rejection
def _mini_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    shutil.copy(ROOT / "requirements.lock", root / "requirements.lock")
    (root / "data.json").write_text(json.dumps({"k": 3, "n": 10}))
    for cmd in (["git", "init", "-q"], ["git", "add", "."],
                ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"]):
        subprocess.run(cmd, cwd=root, check=True, capture_output=True)
    return root


def _mini_spec() -> ex.FigureSpec:
    def build(root: Path) -> ex.FigureResult:
        d = json.loads((root / "data.json").read_text())
        e = binomial(d["k"], d["n"])
        fig, ax = plt.subplots()
        ax.errorbar([1], [e.point], yerr=[[e.yerr[0]], [e.yerr[1]]], label=plots.label("MC", "x"), **plots.kw("MC"))
        ax.legend()
        return ex.FigureResult(ex.FigureStatus.READY, fig, "test", (EvidenceKind.MONTE_CARLO,), [{"p": e.point}])
    return ex.FigureSpec("figT", "test", "test", ("data.json",), (), EvidenceKind.MONTE_CARLO, build)


def test_stale_inputs_are_rejected_and_rebuilt(tmp_path):
    root, spec = _mini_repo(tmp_path), _mini_spec()
    out = root / "figs"
    assert mf.staleness(spec, root, out) == ["no cached caption/manifest"]
    mf.build_figure(spec, root, out, "t")
    assert mf.staleness(spec, root, out) == []
    (root / "data.json").write_text(json.dumps({"k": 4, "n": 10}))
    reasons = mf.staleness(spec, root, out)
    assert any(r.startswith("MISMATCH: data.json") for r in reasons)
    with pytest.raises(mf.StaleFigureError):
        mf.require_fresh(spec, root, out)
    mf.build_figure(spec, root, out, "t")
    assert mf.require_fresh(spec, root, out)["status"] == "READY"
    with open(mf.paths(out, spec)["csv"], "a") as f:  # a hand-edited output is stale too
        f.write("0.9\n")
    assert any("MISMATCH" in r and r.endswith(".csv") for r in mf.staleness(spec, root, out))


def test_changed_spec_or_tampered_caption_is_stale(tmp_path):
    root, spec = _mini_repo(tmp_path), _mini_spec()
    out = root / "figs"
    mf.build_figure(spec, root, out, "t")
    (root / "extra.py").write_text("x = 1\n")
    grown = ex.FigureSpec(spec.fig_id, spec.slug, spec.title, spec.inputs, ("extra.py",), spec.primary_evidence, spec.build)
    assert "figure spec inputs/scripts changed" in mf.staleness(grown, root, out)
    cap = mf.paths(out, spec)["caption"]
    cap.write_text(cap.read_text().replace(json.loads(cap.read_text())["manifest_sha256"], "0" * 64))
    assert "caption does not match manifest" in mf.staleness(spec, root, out)


# --------------------------------------------------------------------------- evidence styles
def test_evidence_styles_are_distinct_without_colour():
    sig = [(s.color, s.linestyle, s.marker, s.filled) for t, s in plots.STYLES.items() if t != "PENDING"]
    assert len(sig) == len(set(sig))
    key = ["THEOREM", "MC", "PHOTON-EXPERIMENT", "SYNTHETIC", "MODELLED", "SDP", "SIM-NOISY", "OUT-OF-MODEL"]
    shape = [(plots.STYLES[t].linestyle, plots.STYLES[t].marker, plots.STYLES[t].filled) for t in key]
    assert len(shape) == len(set(shape)), "evidence classes must differ in line/marker, not colour alone"
    assert len({plots.STYLES[t].color for t in ("THEOREM", "MC", "PHOTON-EXPERIMENT", "SYNTHETIC")}) == 4
    assert plots.STYLES["OUT-OF-MODEL"].color == plots.RED


def test_every_legend_entry_is_evidence_tagged(built):
    _, caps = built
    tags = set(plots.STYLES) | set(plots.TAG_OF_KIND.values())
    for fid in READY:
        cap = caps[fid]
        assert cap["legend"], fid
        for entry in cap["legend"]:
            assert entry.startswith("[") and entry[1:entry.index("]")] in tags, (fid, entry)
        if cap["synthetic_content"]:
            assert any(e.startswith("[SYNTHETIC]") for e in cap["legend"])
    assert any(e.startswith("[OUT-OF-MODEL]") for e in caps["fig03"]["legend"])
    assert any(e.startswith("[PHOTON-EXPERIMENT]") for e in caps["fig04"]["legend"])
    assert any("DIFFERENT GAME" in e for e in caps["fig02"]["legend"])


# --------------------------------------------------------------------------- PENDING, never zero
def test_missing_results_render_pending_not_zero(built):
    out, caps = built
    for spec in ex.FIGURES:
        if spec.fig_id in PENDING:
            cap = caps[spec.fig_id]
            assert cap["status"] == "PENDING" and cap["caption"].startswith("PENDING")
            assert cap["evidence_kinds"] == ["UNCERTIFIED"] and cap["legend"] == []
            assert mf.paths(out, spec)["csv"].read_text() == "status\nPENDING\n"
    with open(mf.paths(out, ex.figure_spec("fig05"))["csv"]) as f:
        rows = list(csv.DictReader(f))
    none = [r for r in rows if r["status"] == "NO_ADMISSIBLE_BETA"]
    assert none and all(r["beta_max"] == "" for r in none)
    assert all(float(r["beta_max"]) > 0 for r in rows if r["beta_max"])
    with open(mf.paths(out, ex.figure_spec("fig10"))["csv"]) as f:
        assert any(r["value"] == "NOT_RUN" and r["evidence_kind"] == "QPU" for r in csv.DictReader(f))


def _trace(evidence: str, trace_id: str = "t1") -> TransactionTrace:
    return TransactionTrace.model_validate({
        "trace_id": trace_id, "token_id": "tok", "protocol_id": "p", "network_id": "net", "irrevocability_rule": "r",
        "double_spend_accepted": False, "latency_evidence": evidence,
        "events": [{"event_id": "e1", "site_id": "A", "kind": "issue", "time_ns": 0.0},
                   {"event_id": "e2", "site_id": "B", "kind": "verification_result_available_local", "time_ns": 5e4,
                    "causal_parent_ids": ["e1"]}]})


def test_fixture_data_cannot_be_rendered_as_real():
    with pytest.raises(plots.FixtureDataError):
        plots.fig6_spacetime([_trace("SYNTHETIC")])
    with pytest.raises(plots.FixtureDataError):
        plots.fig6_spacetime([_trace("MODELLED_LATENCY", trace_id="fixture-h1-race")])
    fig = plots.fig6_spacetime([_trace("SYNTHETIC")], fixture_ok=True)
    assert any(t.get_text() == plots.FIXTURE_WATERMARK for t in fig.texts)
    plt.close(fig)
    fig = plots.fig6_spacetime([_trace("MODELLED_LATENCY")])
    assert not any(t.get_text() == plots.FIXTURE_WATERMARK for t in fig.texts)
    plt.close(fig)
    with pytest.raises(ValueError):
        plots.fig6_spacetime([])
    from qmint.core.contracts import BenchmarkRecord

    line = (ROOT / "reports/classical_baseline_notes/benchmark_records.jsonl").read_text().splitlines()[0]
    rec = BenchmarkRecord.model_validate(json.loads(line) | {"evidence_kind": "SYNTHETIC"})
    with pytest.raises(plots.FixtureDataError):
        plots.fig7_latency([rec], {})


def test_synthetic_store_records_keep_figure_pending(tmp_path):
    store = RecordStore(tmp_path / ex.RECORD_STORE)
    prov = Provenance(git_sha="abcdef1", environment_lock="0" * 64, command="pytest")
    store.append("trace", _trace("SYNTHETIC"), provenance=prov, record_id="fixture-trace")
    assert ex.real_records(tmp_path, "trace") == []
    res = ex.figure_spec("fig06").build(tmp_path)
    assert res.status == ex.FigureStatus.PENDING
    plt.close(res.fig)
    store.append("trace", _trace("MODELLED_LATENCY", "real"), provenance=prov, record_id="real-trace")
    res = ex.figure_spec("fig06").build(tmp_path)
    assert res.status == ex.FigureStatus.READY
    plt.close(res.fig)


# --------------------------------------------------------------------------- numbers come from evidence
def test_fig2_and_fig3_numbers_match_lane_c_evidence(built):
    out, _ = built
    c = json.loads((ROOT / ex.C_EVIDENCE).read_text())
    a04 = {r["record"]["token_n"]: r["record"] for r in c["w1_monte_carlo"]
           if r["record"]["attack_id"] == "A04_mvw_optimal_channel"}
    with open(mf.paths(out, ex.figure_spec("fig02"))["csv"]) as f:
        mc = [r for r in csv.DictReader(f) if r["evidence_kind"] == "MONTE_CARLO"]
    assert {int(r["n"]) for r in mc} == set(a04)
    for r in mc:
        rec = a04[int(r["n"])]
        assert float(r["value"]) == pytest.approx(rec["successes"] / rec["trials"])
        assert float(r["lo"]) == pytest.approx(rec["success_rate_ci"]["lo"])
    with open(mf.paths(out, ex.figure_spec("fig03"))["csv"]) as f:
        forms = {r["attack_id"]: r["closed_form"] for r in csv.DictReader(f)}
    assert forms["A01_basis_guess_resend"] == "5/8" and forms["A04_mvw_optimal_channel"] == "3/4"


def test_fig10_caption_is_verbatim(built):
    _, caps = built
    assert caps["fig10"]["caption"].startswith(ex.FIG10_CAPTION)
    assert "QPU: not run" in caps["fig10"]["caption"]


# --------------------------------------------------------------------------- tables
def test_committed_tables_match_regenerated(tmp_path):
    for p in tables.build_tables(ROOT, tmp_path):
        assert p.read_bytes() == (ROOT / "reports/paper" / p.name).read_bytes(), p.name


def test_table1_matches_theorem_seed_and_registry():
    seed = yaml.safe_load((ROOT / tables.THEOREM_SEED).read_text())
    rows = tables.table1(ROOT)
    from qmint.proofs.registry import load_registry

    reg = load_registry(ROOT / tables.OBLIGATIONS)
    by_id = {r["theorem_id"]: r for r in rows}
    for t in seed["theorems"]:
        r = by_id[t["theorem_id"]]
        assert r["game"] == t["game"] and r["transcription_status"] == t["status"]
        if r["obligation"]:
            assert r["proof_status"] == reg.claim(r["obligation"]).status.value
    assert by_id["T-MVW12-THM2"]["obligation"] == "P-W1CV" and "differs" in by_id["T-MVW12-THM2"]["notes"]
    assert {r["obligation"] for r in rows if r["obligation"]} == {c.claim_id for c in reg.claims}


def test_ledger_rows_are_anchored(tmp_path):
    for r in tables.TABLE4 + tables.TABLE5:
        tables.check_row(ROOT, r)
    ok = tables.TABLE4[0]
    bad_anchor = tables.LedgerRow("X", "c", "f", "MONTE_CARLO", ok.source, ("this sentence is not in the source",))
    with pytest.raises(tables.AnchorError):
        tables.check_row(ROOT, bad_anchor)
    stray = tables.LedgerRow("X", "c", ok.finding + " 0.999", ok.evidence_kind, ok.source, ok.anchors)
    with pytest.raises(tables.AnchorError):
        tables.check_row(ROOT, stray)


# --------------------------------------------------------------------------- statistics
def test_statistics():
    e = binomial(0, 1000)
    assert e.point == 0 and e.lo == 0 and 0 < e.hi < 0.004
    assert zero_success_upper(1000) == pytest.approx(1 - 0.05 ** (1 / 1000))
    assert binomial(5, 10, method="wilson").label().startswith("Wilson 95%")
    with pytest.raises(ValueError):
        binomial(1, 2, method="normal")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        zero_success_upper(0)
