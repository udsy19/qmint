"""Make the repository's own `qmint/` importable when a script is run by path.

Scripts must import the checkout they live in (never a stray installed copy), so the
repository root is put first on sys.path.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
