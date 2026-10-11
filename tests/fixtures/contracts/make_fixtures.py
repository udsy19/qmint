"""Regenerate the representative contract fixtures (SYNTHETIC; lead-owned)."""
import json
from pathlib import Path

OUT = Path(__file__).parent
Z64 = "0" * 64
FIX = {
    "protocol_wiesner": {
        "protocol_id": "wiesner_ideal", "source_paper_id": "P01", "theorem_id": "P-W1",
        "protocol_revision": "mvw2012_simple_counterfeiting", "issuer_trust": "honest_bank",
        "same_party_agent_trust": "not_applicable", "redemption_semantics": "single_verifier_bank",
        "quantum_stage": "note_is_quantum_state", "quantum_memory_required": True,
        "classical_authentication": "not_applicable", "adversary_game_id": "W1",
        "security_model_id": "wiesner_ideal_exact_verifier_v1",
        "proof_assumptions": ["iid_uniform_bb84", "exact_projective_verifier", "no_verification_oracle"],
    },
    "protocol_smoney_ideal": {
        "protocol_id": "s_money_kent_2022_ideal_2site", "source_paper_id": "P03", "theorem_id": "P-S1",
        "protocol_revision": "published_table_1", "issuer_trust": "honest_bank",
        "same_party_agent_trust": "trusted", "redemption_semantics": "one_of_two_spacelike_sites",
        "quantum_stage": "short_range_before_commitment", "quantum_memory_required": False,
        "classical_authentication": "pre_shared_authenticated_channels", "adversary_game_id": "S1",
        "security_model_id": "s_money_ideal_v1",
    },
    "token_wiesner": {
        "token_id": "tok-fixture-0001", "protocol_id": "wiesner_ideal", "n_prepared": 8,
        "source_state_family": "BB84", "public_metadata": {"serial": "SN-0001"},
        "issue_event_id": "ev-issue-0001", "state_kind": "ideal_simulated",
        "ownership_context": "fixture_wallet", "backend_provenance": "SYNTHETIC:fixture",
    },
    "certificate_placeholder": {
        "protocol_id": "s_money_kent_2022_realistic", "game_id": "S2",
        "security_model_id": "specific_published_model",
        "parameters": {"N": 0, "error_threshold": None, "loss_threshold": None},
        "targets": {"epsilon_unf": 1e-9, "epsilon_cor": 1e-6},
        "reason": "example_placeholder_not_a_certificate",
    },
    "calibration_synthetic": {
        "calibration_id": "cal-synthetic-0001", "device_id": "synthetic_source",
        "experiment_family": "synthetic", "data_origin": "SYNTHETIC", "n_events": 1000,
        "qber_interval": {"lo": 0.01, "hi": 0.03, "unit": "fraction", "point": 0.02},
        "confidence_level": 0.95, "interval_method": "clopper_pearson",
        "independence_assumptions": ["iid_events_synthetic"],
    },
    "network_two_site": {
        "network_id": "net-synthetic-2site-10km", "topology_source": "synthetic",
        "sites": [
            {"site_id": "A", "frame": "flat_local_approx", "x_m": 0.0, "y_m": 0.0, "trust_domain": "bank", "clock_error_bound_ns": 1.0},
            {"site_id": "B", "frame": "flat_local_approx", "x_m": 10000.0, "y_m": 0.0, "trust_domain": "bank", "clock_error_bound_ns": 1.0},
        ],
        "links": [
            {"src": "A", "dst": "B", "propagation_lower_bound_ns": 33356.4, "latency_model": "lightcone", "latency_evidence": "MODELLED_LATENCY", "authenticated": True},
            {"src": "B", "dst": "A", "propagation_lower_bound_ns": 33356.4, "latency_model": "lightcone", "latency_evidence": "MODELLED_LATENCY", "authenticated": True},
        ],
    },
    "manifest_fixture": {
        "manifest_id": "man-fixture-0001", "created_utc": "2026-10-11T00:00:00Z",
        "command": "python tests/fixtures/contracts/make_fixtures.py", "git_sha": "bootstrap",
        "evidence_kind": "SYNTHETIC",
        "entries": [{"path_or_uri": "tests/fixtures/contracts/token_wiesner.json", "sha256": Z64, "role": "output", "original_or_derived": "derived"}],
    },
}
if __name__ == "__main__":
    for name, obj in FIX.items():
        (OUT / f"{name}.json").write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
