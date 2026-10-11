"""scripts/build_static_site.py: key derivation (mirrors web/lib/api/static.test.ts) and the request grid."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from qmint.api.app import app

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("build_static_site", SCRIPTS / "build_static_site.py")
bss = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bss)

BODY = {"z": [1.0, 1e-9, None, True, 'é/"x'], "a": {"lo": 6e-06, "hi": 40000000}, "m": 0.17453292519943295}
CANON = '{"a":{"hi":40000000,"lo":0.000006},"m":0.17453292519943295,"z":[1,1e-9,null,true,"é/\\"x"]}'
KEY = "233cfcf1a7dda50a973938b0551b5bf0c4d89d2a4527dbc0d22400e6139a8014"


@pytest.mark.parametrize(
    ("x", "js"),
    [(0, "0"), (1.0, "1"), (1e-9, "1e-9"), (1e-6, "0.000001"), (1e-7, "1e-7"), (1e21, "1e+21"), (-1.234e-06, "-0.000001234"),
     (123456789012345680000.0, "123456789012345680000"), (0.17453292519943295, "0.17453292519943295"), (12.5e10, "125000000000")],
)
def test_js_number_matches_ecmascript(x, js):
    assert bss.js_number(x) == js


def test_canonical_json_and_key_match_typescript():
    assert bss.canonical_json(BODY) == CANON
    assert bss.snapshot_key(BODY) == KEY
    assert bss.snapshot_relpath("POST", "/api/v1/lab/attack", BODY) == f"post/api/v1/lab/attack/{KEY}.json"


def test_ui_default_requests_are_in_the_grid():
    client = TestClient(app)
    presets = client.get("/api/v1/certificates/catalog").json()["data"]["presets"]
    keys = {(p, bss.snapshot_key(b)) for p, b in bss.post_grid(presets)}
    # DEFAULT_MINT_FORM, DEFAULT_ATTACK_FORM and the landing hero's initial selection (mvw_channel, n = 4).
    assert ("/api/v1/lab/mint", bss.snapshot_key(bss.mint_lab_body("wiesner_ideal", 4, "aer", False))) in keys
    assert ("/api/v1/lab/attack", bss.snapshot_key(bss.attack_lab_body("A04_mvw_optimal_channel", 2, 2000))) in keys
    assert ("/api/v1/lab/attack", bss.snapshot_key(bss.hero_attack_body("A04_mvw_optimal_channel", 4, 0, False))) in keys
    assert len(presets) and all(("/api/v1/certificates", bss.snapshot_key(bss.certificate_body(p["request"]))) in keys for p in presets)


def test_build_writes_real_responses(tmp_path, monkeypatch):
    small = [("/api/v1/lab/mint", bss.mint_lab_body("wiesner_ideal", 1, "exact", False))]
    monkeypatch.setattr(bss, "post_grid", lambda presets: small)
    monkeypatch.setattr(bss, "get_paths", lambda ids: ["/api/v1/meta", f"/api/v1/research/sources/{ids[0]}"])
    meta = bss.build(tmp_path / "snap", jobs=1)
    assert meta["counts"] == {"files": 3, "failed": 0}
    on_disk = json.loads((tmp_path / "snap" / bss.snapshot_relpath("POST", *small[0])).read_text())
    live = TestClient(app).post(small[0][0], json=small[0][1]).json()
    assert on_disk["data"]["protocol"] == live["data"]["protocol"]  # stored verbatim from the API
    index = json.loads((tmp_path / "snap" / "index.json").read_text())
    assert {e["method"] for e in index["entries"]} == {"GET", "POST"}
    assert json.loads((tmp_path / "snap" / "meta.json").read_text())["git_sha"]
