import json
from pathlib import Path

import pytest

from qmint.classical.common import lightcone_network
from qmint.core.contracts import SpacetimeNetwork

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "contracts"


@pytest.fixture
def net2() -> SpacetimeNetwork:
    """Frozen bootstrap fixture: two sites 10 km apart, lightcone links 33356.4 ns."""
    return SpacetimeNetwork.model_validate(json.loads((FIXTURES / "network_two_site.json").read_text()))


@pytest.fixture
def net3() -> SpacetimeNetwork:
    return lightcone_network("net-h-test-3site-100km", {"A": (0.0, 0.0), "B": (100_000.0, 0.0), "H": (50_000.0, 0.0)})
