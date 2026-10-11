import pytest

from qmint.classical.common import lightcone_network
from qmint.core.contracts import SpacetimeNetwork


@pytest.fixture
def net2() -> SpacetimeNetwork:
    """Two sites 10 km apart with exact light-cone links (33356.41 ns).

    Not the frozen tests/fixtures/contracts/network_two_site.json: that fixture declares
    33356.4 ns, 0.0095 ns BELOW the light cone, which lane G's engine rejects as superluminal.
    """
    return lightcone_network("net-h-test-2site-10km", {"A": (0.0, 0.0), "B": (10_000.0, 0.0)})


@pytest.fixture
def net3() -> SpacetimeNetwork:
    return lightcone_network("net-h-test-3site-100km", {"A": (0.0, 0.0), "B": (100_000.0, 0.0), "H": (50_000.0, 0.0)})
