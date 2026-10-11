"""Evidence-label rules (moved with ``evidence_labels`` from the retired qmint.ui workbench)."""

from __future__ import annotations

from qmint.api.evidence_labels import all_badges, evidence_badge, status_badge
from qmint.core.contracts import CertificateStatus, EvidenceKind

SIMULATED = {EvidenceKind.SYNTHETIC, EvidenceKind.SIMULATOR_IDEAL, EvidenceKind.SIMULATOR_NOISY,
             EvidenceKind.MONTE_CARLO, EvidenceKind.MODELLED_LATENCY}
MEASURED = {EvidenceKind.PHOTON_EXPERIMENT, EvidenceKind.QPU, EvidenceKind.MEASURED_LATENCY}


def test_simulated_and_measured_labels_distinct():
    sim = {evidence_badge(k) for k in SIMULATED}
    meas = {evidence_badge(k) for k in MEASURED}
    assert {b.label for b in sim}.isdisjoint({b.label for b in meas})
    assert {b.css for b in sim}.isdisjoint({b.css for b in meas})
    assert all(b.origin == "simulated" for b in sim) and all(b.origin == "measured" for b in meas)


def test_required_labels_present_and_unique():
    labels = {b.label for b in all_badges()}
    for want in ["THEOREM", "NUMERICAL", "CERTIFIED-NUMERIC", "MONTE-CARLO (lower bound)", "SYNTHETIC",
                 "PHOTON-EXPERIMENT", "QPU", "MODELLED-LATENCY", "MEASURED-LATENCY", "UNCERTIFIED"]:
        assert want in labels
    css = [b.css for b in all_badges()]
    assert len(css) == len(set(css))


def test_only_certified_is_green():
    for s in CertificateStatus:
        assert (status_badge(s).tone == "ok") == (s == CertificateStatus.CERTIFIED)
    for k in EvidenceKind:
        assert evidence_badge(k).tone != "ok"
