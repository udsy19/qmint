"""Qollab export: OpenQASM 3 circuit + JSON manifest for a BB84 prepare/verify job.

What Qollab is (verified 2026-10-11, see qollab/evidence/sources.json): a community site
(https://qollab.xyz) where open-source Qiskit projects are listed "with runnable code examples";
it ran an IonQ-credit-funded Creative Challenge (submissions closed 2026-04-07). IonQ's
announcement mentions a browser playground. No public API, SDK, upload format or execution
runtime is documented, so programmatic platform integration is BLOCKED. This module only writes a
portable bundle that a human can attach to a Qollab project (or run anywhere Qiskit runs).
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from qmint.core.contracts import Basis, EvidenceKind, EvidenceManifest, ManifestEntry
from qmint.core.serialization import canonical_json, file_sha256
from qmint.quantum.ionq import build_bb84_prepare_verify, circuit_sha256, gate_counts

QOLLAB_PLATFORM_STATUS: dict[str, Any] = {
    "status": "BLOCKED",
    "reason": "no public Qollab API/SDK/upload format documented; only a web UI (login) and project listings",
    "verified_capabilities": [
        "community project listings with runnable code examples (Qiskit required for Creative Challenge)",
        "IonQ compute credits granted to selected Creative Challenge teams (closed 2026-04-07)",
    ],
    "claimed_not_verified": ["browser playground running 'real quantum code' (IonQ press release)"],
    "sources": [
        "https://qollab.xyz/creativechallenge",
        "https://www.ionq.com/news/ionq-partners-with-qollabs-creative-challenge-advancing-creative-quantum-innovation",
    ],
}

STANDALONE_SCRIPT = Path(__file__).resolve().parents[2] / "qollab" / "bb84_standalone.py"


def _git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=STANDALONE_SCRIPT.parent,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def export_bundle(bits: Sequence[int], bases: Sequence[Basis | str], out_dir: str | Path) -> dict[str, Any]:
    """Write <out>/bb84_prepare_verify.qasm, bb84_standalone.py and manifest.json; return the manifest."""
    from qiskit import qasm3

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    qc = build_bb84_prepare_verify(bits, bases)
    qasm_path = out / "bb84_prepare_verify.qasm"
    qasm_path.write_text(qasm3.dumps(qc) + "\n", encoding="utf-8")
    script_path = out / "bb84_standalone.py"
    shutil.copyfile(STANDALONE_SCRIPT, script_path)
    bit_str = "".join(str(int(b)) for b in bits)
    basis_str = "".join(Basis(b).value for b in bases)
    manifest = EvidenceManifest(
        manifest_id=f"qollab-bundle-bb84-{bit_str}-{basis_str}",
        created_utc=datetime.now(UTC).isoformat(),
        source_urls=QOLLAB_PLATFORM_STATUS["sources"],
        command=f"qmint.quantum.qollab.export_bundle(bits={bit_str!r}, bases={basis_str!r})",
        git_sha=_git_sha(),
        evidence_kind=EvidenceKind.UNCERTIFIED,  # a circuit definition, not a measurement
        entries=[
            ManifestEntry(
                path_or_uri=qasm_path.name,
                sha256=file_sha256(qasm_path),
                role="output",
                original_or_derived="derived",
            ),
            ManifestEntry(
                path_or_uri=script_path.name,
                sha256=file_sha256(script_path),
                role="script",
                original_or_derived="original",
            ),
        ],
    )
    doc = {
        "format": "qmint.qollab_bundle.v1",
        "evidence_manifest": manifest.model_dump(mode="json"),
        "circuit": {
            "openqasm_version": 3,
            "file": qasm_path.name,
            "canonical_sha256": circuit_sha256(qc),
            "n_qubits": qc.num_qubits,
            "prepared_bits_qubit_order": bit_str,
            "bases_qubit_order": basis_str,
            "gate_counts_submitted": gate_counts(qc),
            "ideal_expected_outcome_qubit_order": bit_str,
        },
        "conventions": {
            "bb84_map": "(Z,0)=|0>, (Z,1)=|1>, (X,0)=|+>, (X,1)=|->; X measurement = H then Z",
            "clbit_i_measures_qubit_i": True,
            "qiskit_counts_keys": "clbit 0 rightmost (reverse to get qubit order)",
            "ionq_raw_openqasm3_results": "q[0] leftmost (https://docs.ionq.com/api-reference/v0.4/openqasm3)",
        },
        "run_locally": f"python bb84_standalone.py --bits {bit_str} --bases {basis_str} --shots 1000",
        "platform_integration": QOLLAB_PLATFORM_STATUS,
        "not_a_claim": "A gate-model BB84 prepare/verify circuit; not a photonic banknote, not a security proof.",
    }
    (out / "manifest.json").write_text(canonical_json(doc) + "\n", encoding="utf-8")
    return doc
