#!/usr/bin/env python
"""Precompute the API responses the QMint website needs, for the static GitHub Pages build.

    python scripts/build_static_site.py [--out web/public/snapshot] [--jobs 4]

Every response comes from the real FastAPI app (``qmint.api.app``) through ``TestClient``; nothing is
edited or synthesised. Each file is ``<out>/<method>/<api path>/<sha256(canonical body)>.json`` where the
body of a GET is its query object (``{}`` when there is none). ``canonical_json`` must stay byte-identical
to ``canonicalJson`` in ``web/lib/api/static.ts`` (sorted keys, no whitespace, ECMAScript number text),
because the browser derives the same key from the request it is about to send.

The POST grid is exactly the bodies the UI issues for its defaults plus a small sweep (see ``post_grid``);
any other configuration is answered in the static site with an explicit "not precomputed" error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import _bootstrap  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "web" / "public" / "snapshot"
API = "/api/v1"

# ---------------------------------------------------------------------------------------------- keys


def js_number(x: int | float) -> str:
    """ECMAScript Number::toString for finite numbers (what JSON.stringify emits)."""
    if isinstance(x, bool):
        raise TypeError("bool is not a number")
    if isinstance(x, int) and abs(x) < 10**21:
        return str(x)
    x = float(x)
    if not math.isfinite(x):
        raise ValueError("non-finite number in request body")
    if x == 0:
        return "0"
    sign = "-" if x < 0 else ""
    r = repr(abs(x))  # shortest round-trip digits, same digit string as ECMAScript
    mant, _, exp = r.partition("e")
    whole, _, frac = mant.partition(".")
    digits = (whole + frac).lstrip("0")
    # value = int(whole+frac) * 10**(exp - len(frac)); normalise to digits without trailing zeros
    e10 = (int(exp) if exp else 0) - len(frac)
    stripped = digits.rstrip("0")
    e10 += len(digits) - len(stripped)
    digits = stripped
    k = len(digits)
    n = e10 + k  # value = 0.digits * 10**n
    if k <= n <= 21:
        out = digits + "0" * (n - k)
    elif 0 < n <= 21:
        out = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        out = "0." + "0" * (-n) + digits
    else:
        e = n - 1
        es = ("+" if e >= 0 else "-") + str(abs(e))
        out = (digits if k == 1 else digits[0] + "." + digits[1:]) + "e" + es
    return sign + out


def canonical_json(value: Any) -> str:
    """Sorted keys, no whitespace, JS number text; mirrors web/lib/api/static.ts::canonicalJson."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return js_number(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list | tuple):
        return "[" + ",".join(canonical_json(v) for v in value) + "]"
    if isinstance(value, dict):
        items = sorted(value.items(), key=lambda kv: kv[0].encode("utf-16-be"))  # JS sorts by UTF-16 code unit
        return "{" + ",".join(f"{json.dumps(k, ensure_ascii=False)}:{canonical_json(v)}" for k, v in items) + "}"
    raise TypeError(f"cannot canonicalise {type(value).__name__}")


def snapshot_key(payload: Any) -> str:
    return hashlib.sha256(canonical_json({} if payload is None else payload).encode("utf-8")).hexdigest()


def snapshot_relpath(method: str, path: str, payload: Any) -> str:
    """Relative file path on disk (segments decoded); the browser requests the URL-encoded form."""
    segments = [unquote(s) for s in path.strip("/").split("/")]
    return "/".join([method.lower(), *segments, f"{snapshot_key(payload)}.json"])


# ----------------------------------------------------------------------------------------- requests

NOISE_NONE = {"channel": "none", "strength": 0}
SEED = 42  # DEFAULT_*_FORM.seedText and the landing DEMO_SEED

ATTACKS = [  # web/components/lab/attack-form.ts ATTACK_GROUPS
    "A01_basis_guess_resend",
    "A01b_basis_guess_bayes_resend",
    "A02_breidbart_resend",
    "A02b_breidbart_bayes_resend",
    "A03_universal_buzek_hillery",
    "A03b_phase_covariant_xz",
    "A04_mvw_optimal_channel",
    "A06_split_and_report_loss",
    "A08_adaptive_oracle_probe",
    "CTRL_secret_leak",
]
N_MAX = 8  # LIMITS.nMax
HERO_N = (1, 2, 4, 8)  # instrument-model.ts N_OPTIONS
HERO_ATTACKS = ("A01_basis_guess_resend", "A03b_phase_covariant_xz", "A04_mvw_optimal_channel", "CTRL_secret_leak")
SDP_MAX_N = 2


def get_paths(source_ids: list[str]) -> list[str]:
    fixed = [
        "/health",
        "/meta",
        "/meta/tracker",
        "/games",
        "/protocols",
        "/evidence",
        "/evidence/labels",
        "/evidence/highlights",
        "/research/sources",
        "/benchmarks",
        "/certificates/catalog",
    ]
    return [API + p for p in fixed] + [f"{API}/research/sources/{i}" for i in source_ids]


def mint_lab_body(protocol: str, n: int, backend: str, teaching: bool) -> dict[str, Any]:
    """mint-form.ts buildMintRequest at DEFAULT_MINT_FORM with protocol/n/backend/teaching changed."""
    noisy = protocol == "wiesner_noisy"
    return {
        "protocol_id": protocol,
        "n_qubits": n,
        "threshold": 1 if noisy else 0,
        "seed": SEED,
        "noise": NOISE_NONE,
        "backend": backend,
        "shots": 2000 if backend == "aer" else 1,
        "trials": 1000,
        "teaching_reveal": teaching,
    }


def attack_lab_body(attack: str, n: int, trials: int) -> dict[str, Any]:
    """attack-form.ts buildAttackRequest at DEFAULT_ATTACK_FORM with attack/n/trials changed."""
    return {
        "attack": attack,
        "n": n,
        "seed": SEED,
        "trials": trials,
        "noise": NOISE_NONE,
        "max_loss_fraction": 0.5,
        "max_error_fraction": 0,
        "probes": 10,
        "include_sdp": True,
    }


def hero_attack_body(attack: str, n: int, trials: int, include_sdp: bool) -> dict[str, Any]:
    """instrument-data.ts attackBody and the landing page probe (no noise key)."""
    return {
        "attack": attack,
        "n": n,
        "seed": SEED,
        "trials": trials,
        "include_sdp": include_sdp,
        "max_loss_fraction": 0.5,
        "max_error_fraction": 0,
        "probes": 10,
    }


def hero_mint_body(n: int, reveal: bool) -> dict[str, Any]:
    """instrument-data.ts mintBody."""
    return {
        "protocol_id": "wiesner_ideal",
        "n_qubits": n,
        "seed": SEED,
        "backend": "exact",
        "shots": 1,
        "threshold": 0,
        "trials": 0,
        "teaching_reveal": reveal,
    }


def certificate_body(preset_request: dict[str, Any]) -> dict[str, Any]:
    """certificates/form-model.ts toRequest(fromRequest(preset.request)): what the studio actually POSTs."""
    targets = {k: v for k, v in (preset_request.get("targets") or {}).items() if v is not None}
    parameters = {}
    for k, v in (preset_request.get("parameters") or {}).items():
        parameters[k] = v if isinstance(v, int | float) else {"lo": v["lo"], "hi": v["hi"]}
    return {
        "game": preset_request["game"],
        "protocol_id": preset_request.get("protocol_id"),
        "targets": targets,
        "parameters": parameters,
        "honest_error_tolerance": preset_request.get("honest_error_tolerance"),
        "declared_assumptions": list(preset_request.get("declared_assumptions") or []),
        "noise_source": preset_request.get("noise_source") or None,
        "calibration": preset_request.get("calibration") or "none",
    }


def post_grid(presets: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    """Every POST body the static site can answer, de-duplicated by key."""
    out: list[tuple[str, dict[str, Any]]] = []
    # Mint lab: both schemes x n 1..8 x backend x teaching, at the form defaults (W2 needs n >= 2).
    for protocol in ("wiesner_ideal", "wiesner_noisy"):
        for n in range(1, N_MAX + 1):
            if protocol == "wiesner_noisy" and n < 2:
                continue
            for backend in ("aer", "exact"):
                for teaching in (False, True):
                    out.append((f"{API}/lab/mint", mint_lab_body(protocol, n, backend, teaching)))
    # Attack lab: every attack x n 1..8 at the default trials (A08 is capped at 400) and at 0 (exact only).
    for attack in ATTACKS:
        default_trials = 400 if attack == "A08_adaptive_oracle_probe" else 2000
        for n in range(1, N_MAX + 1):
            for trials in (default_trials, 0):
                out.append((f"{API}/lab/attack", attack_lab_body(attack, n, trials)))
    # Landing hero instrument: every scenario x N_OPTIONS x sampled; plus the section probes.
    for n in HERO_N:
        out.append((f"{API}/lab/mint", hero_mint_body(n, False)))
        out.append((f"{API}/lab/mint", hero_mint_body(n, True)))
        for attack in HERO_ATTACKS:
            out.append((f"{API}/lab/attack", hero_attack_body(attack, 1, 0, False)))
            for trials in (0, 1000):
                out.append((f"{API}/lab/attack", hero_attack_body(attack, n, trials, n <= SDP_MAX_N)))
    for n in (1, 2):
        out.append((f"{API}/lab/attack", hero_attack_body("A04_mvw_optimal_channel", n, 0, True)))
    out.append((f"{API}/lab/attack", hero_attack_body("CTRL_secret_leak", 1, 0, False)))
    # Certificate studio: every catalog preset, as the studio serialises it.
    for p in presets:
        out.append((f"{API}/certificates", certificate_body(p["request"])))
    seen: set[tuple[str, str]] = set()
    unique = []
    for path, body in out:
        k = (path, snapshot_key(body))
        if k not in seen:
            seen.add(k)
            unique.append((path, body))
    return unique


# ------------------------------------------------------------------------------------------ calling

_client = None


def _call(job: tuple[str, str, Any]) -> tuple[str, str, Any, int, bytes]:
    global _client
    if _client is None:
        from fastapi.testclient import TestClient

        from qmint.api.app import app

        _client = TestClient(app)
    method, path, payload = job
    r = _client.get(path, params=payload or None) if method == "GET" else _client.post(path, json=payload)
    return method, path, payload, r.status_code, r.content


def git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def build(out: Path, jobs: int = 1) -> dict[str, Any]:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    index: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    def record(method: str, path: str, payload: Any, status: int, content: bytes) -> None:
        rel = snapshot_relpath(method, path, payload)
        entry = {"method": method, "path": path, "key": snapshot_key(payload), "file": rel, "status": status}
        if status != 200:
            failures.append(entry)
            return
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(json.loads(content), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        index.append(entry)

    # Discovery calls (research ids, catalog presets) in-process.
    lib = _call(("GET", f"{API}/research/sources", {}))
    cat = _call(("GET", f"{API}/certificates/catalog", {}))
    ids = [s["id"] for s in json.loads(lib[4])["data"]["sources"]]
    presets = json.loads(cat[4])["data"]["presets"]
    work: list[tuple[str, str, Any]] = [("GET", p, {}) for p in get_paths(ids)]
    work += [("POST", path, body) for path, body in post_grid(presets)]

    if jobs > 1:
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            results = list(ex.map(_call, work, chunksize=4))
    else:
        results = [_call(w) for w in work]
    for res in results:
        record(*res)

    index.sort(key=lambda e: (e["method"], e["path"], e["key"]))
    meta = {
        "git_sha": git_sha(),
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "generator": "scripts/build_static_site.py",
        "key": "sha256(canonical JSON of the POST body, or of the GET query object; sorted keys, no whitespace)",
        "counts": {"files": len(index), "failed": len(failures)},
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    (out / "index.json").write_text(json.dumps({"entries": index, "failed": failures}, indent=1) + "\n", encoding="utf-8")
    return meta | {"failed": failures}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--jobs", type=int, default=min(4, os.cpu_count() or 1))
    a = ap.parse_args(argv)
    meta = build(a.out, a.jobs)
    print(f"snapshot: {meta['counts']['files']} files, {meta['counts']['failed']} non-200 -> {a.out} (git {meta['git_sha'][:12]})")
    for f in meta["failed"]:
        print(f"  non-200 {f['status']}: {f['method']} {f['path']} {f['key'][:12]}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
