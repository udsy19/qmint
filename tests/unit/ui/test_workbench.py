"""Lane K: evidence-first workbench tests (wave 1, synthetic fixtures)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from qmint.core.contracts import CertificateStatus, EvidenceKind, SecurityCertificate
from qmint.ui.app import BANNER, FIXTURE_LABEL, render_site
from qmint.ui.build import build, main, site_hash
from qmint.ui.claims import NO_BOUND, Cited, ClaimPanel, UncitedNumberError, bound, render
from qmint.ui.evidence_badges import all_badges, evidence_badge, status_badge
from qmint.ui.records import LoadedRecord, load_records
from qmint.ui.views import certificates_view

ROOT = Path(__file__).resolve().parents[3]
DIRS = [ROOT / "tests" / "fixtures" / "contracts", ROOT / "tests" / "unit" / "ui" / "fixtures"]
Z64 = "0" * 64

SIMULATED = {EvidenceKind.SYNTHETIC, EvidenceKind.SIMULATOR_IDEAL, EvidenceKind.SIMULATOR_NOISY,
             EvidenceKind.MONTE_CARLO, EvidenceKind.MODELLED_LATENCY}
MEASURED = {EvidenceKind.PHOTON_EXPERIMENT, EvidenceKind.QPU, EvidenceKind.MEASURED_LATENCY}


@pytest.fixture(scope="module")
def loaded():
    return load_records(DIRS)


@pytest.fixture(scope="module")
def site(loaded):
    return render_site(*loaded)


def _cert_record(**kw) -> LoadedRecord:
    base = dict(protocol_id="wiesner_ideal", game_id="W1", security_model_id="m", reason="test")
    m = SecurityCertificate.model_validate({**base, **kw})
    return LoadedRecord("certificate", "certificate:t", m, Z64, "t.json")


# --- loading ----------------------------------------------------------------


def test_all_fixtures_load_and_validate(loaded):
    recs, skipped = loaded
    assert skipped == []
    kinds = {r.kind for r in recs}
    assert {"attack", "trace", "calibration", "benchmark", "manifest", "certificate", "network"} <= kinds


def test_invalid_record_is_rejected_not_coerced(tmp_path):
    bad = json.loads((DIRS[1] / "attack_mc_fixture.json").read_text())
    bad["successes"] = bad["trials"] + 1
    (tmp_path / "bad.json").write_text(json.dumps(bad))
    recs, skipped = load_records([tmp_path])
    assert recs == [] and len(skipped) == 1


# --- missing bound is never zero --------------------------------------------


def test_missing_bound_renders_text_not_zero():
    html = render(bound(None, "rec-x", EvidenceKind.UNCERTIFIED))
    assert NO_BOUND in html
    assert re.search(r">\s*0(\.0*)?\s*<", html) is None
    assert "<data" not in html  # no numeric value element at all


def test_missing_bound_in_certificate_view_not_zero():
    rec = _cert_record(targets={"epsilon_unf": 1e-9})  # UNCERTIFIED, upper bound None
    html, _ = certificates_view([rec], [])
    assert NO_BOUND in html
    assert 'value="0' not in html


def test_tiny_bound_not_rounded_to_zero():
    html = render(bound(1e-30, "r", EvidenceKind.PUBLISHED_THEOREM))
    assert "1.000e-30" in html


def test_site_shows_no_applicable_bound(site):
    assert NO_BOUND in site["index.html"]


# --- citations ---------------------------------------------------------------


def test_cited_requires_source_id():
    with pytest.raises(UncitedNumberError):
        Cited(0.5, "", EvidenceKind.MONTE_CARLO)
    with pytest.raises(UncitedNumberError):
        Cited(0.5, "   ", EvidenceKind.MONTE_CARLO)


def test_uncited_number_rejected_from_claim_panel():
    p = ClaimPanel(frozenset({"r1"}))
    with pytest.raises(UncitedNumberError):
        p.add("success {0}", [0.75])  # raw float
    with pytest.raises(UncitedNumberError):
        p.add("success rate is 0.75")  # numeric literal in text
    with pytest.raises(UncitedNumberError):
        p.add("bound 1e-9 achieved")
    with pytest.raises(UncitedNumberError):
        p.add("success {0}", [Cited(0.75, "not-loaded", EvidenceKind.MONTE_CARLO)])  # dangling citation
    with pytest.raises(UncitedNumberError):
        p.add("success {0} and {1}", [Cited(0.75, "r1", EvidenceKind.MONTE_CARLO)])  # unfilled slot
    p.add("game `W1` record `r1` success {0}", [Cited(0.75, "r1", EvidenceKind.MONTE_CARLO)])
    assert len(p.claims) == 1
    assert "src: r1" in p.render()


def test_every_rendered_number_has_a_source(site):
    html = site["index.html"]
    n_data = html.count("<data ")
    assert n_data > 0
    # Each <data> lives inside a cited span that links to a loaded record anchor.
    cited_spans = re.findall(r'<span class="cited">.*?<a class="src" href="#(rec-[^"]+)">', html)
    assert len(cited_spans) >= n_data
    anchors = set(re.findall(r'id="(rec-[^"]+)"', html))
    assert set(cited_spans) <= anchors


# --- badges -------------------------------------------------------------------


def test_simulated_and_measured_badges_distinct():
    sim = {evidence_badge(k) for k in SIMULATED}
    meas = {evidence_badge(k) for k in MEASURED}
    assert {b.label for b in sim}.isdisjoint({b.label for b in meas})
    assert {b.css for b in sim}.isdisjoint({b.css for b in meas})
    assert all(b.origin == "simulated" for b in sim) and all(b.origin == "measured" for b in meas)
    assert evidence_badge(EvidenceKind.MODELLED_LATENCY).label != evidence_badge(EvidenceKind.MEASURED_LATENCY).label


def test_required_badge_labels_present():
    labels = {b.label for b in all_badges()}
    for want in ["THEOREM", "NUMERICAL", "CERTIFIED-NUMERIC", "MONTE-CARLO (lower bound)", "SYNTHETIC",
                 "PHOTON-EXPERIMENT", "QPU", "MODELLED-LATENCY", "MEASURED-LATENCY", "UNCERTIFIED"]:
        assert want in labels


def test_badge_labels_unique():
    css = [b.css for b in all_badges()]
    assert len(css) == len(set(css))


def test_uncertified_never_green():
    for s in CertificateStatus:
        assert (status_badge(s).tone == "ok") == (s == CertificateStatus.CERTIFIED)
    for k in EvidenceKind:
        assert evidence_badge(k).tone != "ok"


def test_uncertified_certificate_renders_without_green(site):
    html, _ = certificates_view([_cert_record()], [])
    assert "b-status-uncertified" in html and "badge b-status-certified" not in html
    assert "badge b-status-certified" not in site["index.html"]  # no fixture is CERTIFIED


def test_certified_is_green_only_when_contract_allows():
    rec = _cert_record(
        proof_check_status="CERTIFIED", assumptions_met=True, proof_reference="P-W1", checker_id="chk",
        evidence_hashes=[Z64], evidence_kind="PUBLISHED_THEOREM",
        upper_bounds={"epsilon_unf": 1e-10}, targets={"epsilon_unf": 1e-9},
    )
    html, _ = certificates_view([rec], [])
    assert "badge b-status-certified" in html


def test_failed_assumptions_red_warning():
    html, _ = certificates_view([_cert_record(failed_assumptions=["iid"])], [])
    assert 'class="alert danger" role="alert"' in html and "failed assumptions" in html


# --- site-level rules ---------------------------------------------------------


def test_banner_and_fixture_label(site):
    html = site["index.html"]
    assert BANNER in html
    assert FIXTURE_LABEL in html
    assert json.loads(site["site_manifest.json"])["fixture_data"] is True


def test_fixture_label_forced_by_synthetic_even_with_real_data_flag(loaded):
    html = render_site(*loaded, real_data=True)["index.html"]
    assert FIXTURE_LABEL in html


def test_self_contained_no_external_resources(site):
    html = site["index.html"]
    assert re.search(r'(src|href)="(https?:)?//', html) is None
    assert "<link" not in html


def test_qpu_not_run_marked(site):
    assert "QPU jobs: not run" in site["index.html"]


def test_no_wallet_or_trading_vocabulary(site):
    low = site["index.html"].lower()
    for word in ("buy now", "price", "portfolio", "trade", "balance", "usd", "$"):
        assert word not in low


def test_spacetime_svg_present(site):
    svgs = [p for p in site if p.startswith("figures/spacetime-")]
    assert svgs and "<svg" in site[svgs[0]]
    assert 'class="cone"' in site[svgs[0]]  # network loaded -> light cones drawn


def test_deterministic_output_hash(tmp_path):
    f1, _, _ = build(DIRS, tmp_path / "a")
    f2, _, _ = build(DIRS, tmp_path / "b")
    assert site_hash(f1) == site_hash(f2)
    for rel in f1:
        assert (tmp_path / "a" / rel).read_bytes() == (tmp_path / "b" / rel).read_bytes()


def test_cli_entrypoint(tmp_path, capsys):
    args = [x for d in DIRS for x in ("--records", str(d))]
    assert main([*args, "--out", str(tmp_path), "--strict"]) == 0
    assert (tmp_path / "index.html").exists()
    assert "site_sha256=" in capsys.readouterr().out
