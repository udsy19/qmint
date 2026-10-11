"""Write the OpenAPI document and evidence-label table consumed by the web client.

``python -m qmint.api.export [--out web/lib/api]`` -> ``openapi.json`` and ``evidence-labels.json``.
Output is deterministic (sorted keys); ``tests/unit/api`` fails if the committed files drift.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from qmint.core.config import REPO_ROOT

DEFAULT_OUT = REPO_ROOT / "web" / "lib" / "api"


def dumps(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def openapi_doc() -> dict[str, Any]:
    from .app import app

    return app.openapi()


def labels_doc() -> dict[str, Any]:
    from .routes.evidence import evidence_labels

    return {"labels": [lab.model_dump() for lab in evidence_labels()]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "openapi.json").write_text(dumps(openapi_doc()), encoding="utf-8")
    (args.out / "evidence-labels.json").write_text(dumps(labels_doc()), encoding="utf-8")
    print(f"wrote {args.out / 'openapi.json'} and {args.out / 'evidence-labels.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
